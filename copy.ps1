# copy.ps1
# Multi part export (tree + full file contents streamed across parts) to clipboard.
# No head tail truncation. Uses a state file to continue where the last part ended.
# ASCII only in this script itself, no emojis, no backticks.

param(
  [int]$MaxTotalChars = 120000,
  [int]$TreeMaxLines  = 800,
  [bool]$SortSmallFirst = $true,
  [switch]$WriteOutfile,

  [int]$Part = 1,
  [switch]$Resume,
  [switch]$ResetState,
  [string]$StatePath = ".\temp_code_export_state.json",

  [string]$OnlyFile = "",
  [string]$OnlyFileRegex = "",

  [int]$ReserveTailChars = 2200
)

$ErrorActionPreference = 'Stop'
$NL = [Environment]::NewLine

$OutfileBase = 'temp_code_export_part'
$Root = (Get-Location).Path

$IgnoreDirs = @(
  'venv', '.git', '__pycache__', 'n8n_data', 'storage', '.vscode', '.idea',
  'node_modules', '.next', 'dist', 'build', '.ruff_cache', '.pytest_cache', '.mypy_cache'
)

$AllowedExtensions = @('.py', '.yml', '.yaml', '.txt', '.sh', '.md', '.toml', '.ini', '.cfg', '.json')
$AllowedExactNames = @('Dockerfile', 'Makefile', 'pyproject.toml', 'requirements.txt')

$ExcludeNames = @('.env', '.env.local', '.DS_Store', 'copy_project.sh', 'copy_project.ps1')

function Is-InIgnoredDir([string]$fullPath) {
  foreach ($d in $IgnoreDirs) {
    if ($fullPath -match "([\\/])$([Regex]::Escape($d))([\\/]|$)") { return $true }
  }
  return $false
}

function Should-IncludeFile([System.IO.FileInfo]$f) {
  if ($ExcludeNames -contains $f.Name) { return $false }
  if (Is-InIgnoredDir $f.FullName) { return $false }

  if ($AllowedExactNames -contains $f.Name) { return $true }
  if ($AllowedExtensions -contains $f.Extension.ToLowerInvariant()) { return $true }

  return $false
}

function RelPath([string]$fullPath) {
  return $fullPath.Replace($Root, '.')
}

function Read-FileSafe([string]$path) {
  try {
    return Get-Content -Path $path -Raw -Encoding UTF8
  } catch {
    try {
      return Get-Content -Path $path -Raw
    } catch {
      return '[WARN] Could not read file: ' + $path
    }
  }
}

function Load-State([string]$path) {
  if (-not (Test-Path $path)) { return $null }
  try {
    $raw = Get-Content -Path $path -Raw -Encoding UTF8
    if (-not $raw) { return $null }
    return ($raw | ConvertFrom-Json)
  } catch {
    return $null
  }
}

function Save-State([string]$path, $stateObj) {
  $json = $stateObj | ConvertTo-Json -Depth 6
  $json | Set-Content -Path $path -Encoding UTF8
}

if ($ResetState) {
  if (Test-Path $StatePath) { Remove-Item $StatePath -Force -ErrorAction SilentlyContinue }
}

$state = $null
if ($Resume) {
  $state = Load-State $StatePath
}

if ($null -eq $state) {
  $state = [pscustomobject]@{
    version = 1
    root = $Root
    cursor = [pscustomobject]@{
      file_index = 0
      file_offset = 0
      wrote_tree = $false
    }
    completed = $false
    last_part = 0
    filters = [pscustomobject]@{
      only_file = $OnlyFile
      only_file_regex = $OnlyFileRegex
      sort_small_first = $SortSmallFirst
    }
  }
} else {
  # Basic sanity if user moved folders
  if ($state.root -ne $Root) {
    # Root changed, safest is reset cursor
    $state.root = $Root
    $state.cursor.file_index = 0
    $state.cursor.file_offset = 0
    $state.cursor.wrote_tree = $false
    $state.completed = $false
  }
}

# Build file list
$files = Get-ChildItem -Path '.' -Recurse -Force -File | Where-Object { Should-IncludeFile $_ }

if ($OnlyFile -and $OnlyFile.Trim()) {
  $needle = $OnlyFile.Trim()
  $files = $files | Where-Object { (RelPath $_.FullName) -eq $needle }
}

if ($OnlyFileRegex -and $OnlyFileRegex.Trim()) {
  $rx = $OnlyFileRegex.Trim()
  $files = $files | Where-Object { (RelPath $_.FullName) -match $rx }
}

if ($SortSmallFirst) {
  $files = $files | Sort-Object Length, FullName
} else {
  $files = $files | Sort-Object FullName
}

# Output builder with budget
$sb = New-Object System.Text.StringBuilder
$script:used = 0

function AppendText([string]$text) {
  $len = $text.Length
  $null = $sb.Append($text)
  $script:used += $len
}

function AppendTextClamped([string]$text, [int]$maxAllowedChars) {
  if ($maxAllowedChars -le 0) { return 0 }
  if ($text.Length -le $maxAllowedChars) {
    AppendText $text
    return $text.Length
  }
  AppendText ($text.Substring(0, $maxAllowedChars))
  return $maxAllowedChars
}

function AppendLine([string]$line) {
  AppendText ($line + $NL)
}

# Decide start cursor
$startFileIndex = 0
$startFileOffset = 0
$wroteTree = $false

if ($Resume -and -not $ResetState) {
  $startFileIndex = [int]($state.cursor.file_index)
  $startFileOffset = [int]($state.cursor.file_offset)
  $wroteTree = [bool]($state.cursor.wrote_tree)
} else {
  $startFileIndex = 0
  $startFileOffset = 0
  $wroteTree = $false
}

# Header
AppendLine ('=== EXPORT PART ' + $Part + ' ===')
AppendLine ('Root: ' + $Root)
AppendLine ('MaxTotalChars: ' + $MaxTotalChars + ', ReserveTailChars: ' + $ReserveTailChars)
if ($OnlyFile) { AppendLine ('OnlyFile: ' + $OnlyFile) }
if ($OnlyFileRegex) { AppendLine ('OnlyFileRegex: ' + $OnlyFileRegex) }
AppendLine ''

# Tree only once by default
if (-not $wroteTree) {
  AppendLine '=== PROJECT STRUCTURE (limited) ==='
  $treeLines = 0

  Get-ChildItem -Path '.' -Recurse -Force |
    Where-Object { -not (Is-InIgnoredDir $_.FullName) } |
    ForEach-Object { RelPath $_.FullName } |
    Sort-Object |
    ForEach-Object {
      if ($treeLines -ge $TreeMaxLines) { return }
      $treeLines++
      AppendLine $_
    }

  if ($treeLines -ge $TreeMaxLines) {
    AppendLine ('[INFO] Tree output limited to ' + $TreeMaxLines + ' lines.')
  }

  AppendLine ''
  AppendLine '=== FILE CONTENTS (streamed) ==='
  AppendLine ''

  $wroteTree = $true
}

# Stream files with resume cursor
$nextFileIndex = $startFileIndex
$nextFileOffset = $startFileOffset
$completed = $true

# Content budget leaves room for footer instructions
$contentBudget = $MaxTotalChars - $ReserveTailChars
if ($contentBudget -lt 1000) { $contentBudget = [Math]::Max(1000, $MaxTotalChars - 400) }

for ($i = $startFileIndex; $i -lt $files.Count; $i++) {

  if ($script:used -ge $contentBudget) {
    $completed = $false
    $nextFileIndex = $i
    $nextFileOffset = $nextFileOffset
    break
  }

  $f = $files[$i]
  $rel = RelPath $f.FullName

  $header = '--- FILE: {0} (size: {1} bytes) ---' -f $rel, $f.Length
  AppendLine $header

  $raw = Read-FileSafe $f.FullName
  if ($null -eq $raw) { $raw = '' }

  $offset = 0
  if ($i -eq $startFileIndex) { $offset = $startFileOffset }

  if ($offset -gt 0) {
    AppendLine ('[INFO] Continuing at offset ' + $offset)
  }

  if ($offset -ge $raw.Length) {
    # File changed or offset too large, restart at 0
    $offset = 0
    if ($i -eq $startFileIndex -and $startFileOffset -gt 0) {
      AppendLine '[INFO] Offset beyond file length, restarting this file at 0'
    }
  }

  $remainingForContent = $contentBudget - $script:used
  if ($remainingForContent -le 0) {
    $completed = $false
    $nextFileIndex = $i
    $nextFileOffset = $offset
    break
  }

  $slice = $raw.Substring($offset)
  $written = AppendTextClamped ($slice + $NL) $remainingForContent

  if ($written -lt (($slice + $NL).Length)) {
    # We cut in the middle of this file
    $completed = $false
    $nextFileIndex = $i

    # How many chars from slice were actually written (exclude the NL if it got cut)
    $sliceWritten = $written
    if ($sliceWritten -gt $slice.Length) { $sliceWritten = $slice.Length }

    $nextFileOffset = $offset + $sliceWritten
    AppendLine ''  # best effort, might not fit but ok if it fits
    break
  } else {
    # Finished this file
    $nextFileOffset = 0
    $nextFileIndex = $i + 1
    AppendLine ''
  }
}

# Footer and next step
AppendLine '=== SUMMARY ==='
AppendLine ('Used chars: ' + $script:used + ' / ' + $MaxTotalChars)
AppendLine ('Files total: ' + $files.Count)
AppendLine ('Completed: ' + ($completed -as [string]))
AppendLine ('Next cursor: file_index=' + $nextFileIndex + ', file_offset=' + $nextFileOffset)

if (-not $completed) {
  AppendLine ''
  AppendLine 'Next command'
  AppendLine ('.\copy.ps1 -Resume -Part ' + ($Part + 1))
} else {
  AppendLine ''
  AppendLine 'All files exported.'
}

# Update state
$state.cursor.file_index = $nextFileIndex
$state.cursor.file_offset = $nextFileOffset
$state.cursor.wrote_tree = $wroteTree
$state.completed = $completed
$state.last_part = $Part
$state.filters.only_file = $OnlyFile
$state.filters.only_file_regex = $OnlyFileRegex
$state.filters.sort_small_first = $SortSmallFirst

Save-State $StatePath $state

# Clipboard and optional outfile
$text = $sb.ToString()

if ($WriteOutfile) {
  $out = ($OutfileBase + $Part + '.txt')
  $text | Set-Content -Encoding UTF8 $out
  Write-Host ('Wrote export to ' + $out)
}

$text | Set-Clipboard
Write-Host ('Copied export part ' + $Part + ' to clipboard. Used ' + $script:used + ' chars (cap: ' + $MaxTotalChars + ').')
Write-Host ('State saved to ' + $StatePath)
