<# 
start_native.ps1
FixundFertig Native Mode (Windows, ohne Docker)

Start:
  powershell -ExecutionPolicy Bypass -File .\start_native.ps1
#>

$ErrorActionPreference = "Stop"

# Farben
function Write-Blue($msg)  { Write-Host $msg -ForegroundColor Cyan }
function Write-Green($msg) { Write-Host $msg -ForegroundColor Green }
function Write-Red($msg)   { Write-Host $msg -ForegroundColor Red }
function Write-Yellow($msg){ Write-Host $msg -ForegroundColor Yellow }

Write-Blue "🚀 Starte FixundFertig (Native Mode, Windows, ohne Docker)"

# Repo Root
$RepoRoot = Get-Location

# -----------------------------------------------
# 1) Checks
# -----------------------------------------------
# Python check
$pythonCmd = $null
foreach ($cmd in @("python", "py")) {
  if (Get-Command $cmd -ErrorAction SilentlyContinue) { $pythonCmd = $cmd; break }
}
if (-not $pythonCmd) {
  Write-Red "❌ Python nicht gefunden. Installiere Python 3 und starte neu."
  Write-Red "Tipp: https://www.python.org/downloads/windows/"
  exit 1
}

# Ensure Python3
try {
  $pyVersion = & $pythonCmd --version 2>&1
  Write-Green "✅ Gefunden: $pyVersion"
} catch {
  Write-Red "❌ Konnte Python nicht ausführen."
  exit 1
}

# Node / npm check (für n8n)
$HasNode = $true
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  $HasNode = $false
  Write-Yellow "⚠️  Node.js / npm nicht gefunden. n8n wird übersprungen."
  Write-Yellow "Install: https://nodejs.org/"
} else {
  $npmVersion = (npm -v 2>$null)
  Write-Green "✅ npm gefunden: $npmVersion"
}

# -----------------------------------------------
# 2) Python App Setup
# -----------------------------------------------
Write-Blue "🐍 Richte Python Umgebung ein..."

$appDir = Join-Path $RepoRoot "app"
if (-not (Test-Path $appDir)) {
  Write-Red "❌ Ordner 'app' nicht gefunden. Starte das Script im Repo Root."
  exit 1
}
Set-Location $appDir

$venvDir = Join-Path $appDir "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
  Write-Blue "Erstelle virtuelle Umgebung..."
  if ($pythonCmd -eq "py") {
    & py -3 -m venv $venvDir
  } else {
    & python -m venv $venvDir
  }
}

Write-Blue "Installiere/Update Abhängigkeiten..."
# Requirements leise installieren, Fehler trotzdem sichtbar
& $venvPip install -r "requirements.txt" | Out-Null

Write-Green "✅ Setup fertig."

# -----------------------------------------------
# 3) Prozesse starten + Cleanup
# -----------------------------------------------
$n8nProc = $null

# Cleanup Handler (Ctrl+C / Script Ende)
$cleanup = {
  Write-Yellow "`n🧹 Beende Prozesse..."
  if ($script:n8nProc -and -not $script:n8nProc.HasExited) {
    try { $script:n8nProc.Kill($true) } catch {}
    Write-Yellow "n8n gestoppt."
  }
}

# Ctrl+C abfangen
$null = Register-EngineEvent PowerShell.Exiting -Action $cleanup

# Start n8n
if ($HasNode) {
  Write-Blue "🤖 Starte n8n Automatisierung..."
  $n8nLog = Join-Path $RepoRoot "n8n_log.txt"

  # npx n8n start, output in Logfile
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = "cmd.exe"
  $psi.Arguments = "/c npx n8n start"
  $psi.WorkingDirectory = $RepoRoot.Path
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true

  $script:n8nProc = New-Object System.Diagnostics.Process
  $script:n8nProc.StartInfo = $psi
  $script:n8nProc.Start() | Out-Null

  # Async log writer
  Start-Job -ScriptBlock {
    param($p, $logPath)
    try {
      $sw = New-Object System.IO.StreamWriter($logPath, $false, [System.Text.Encoding]::UTF8)
      while (-not $p.HasExited) {
        while (-not $p.StandardOutput.EndOfStream) { $sw.WriteLine($p.StandardOutput.ReadLine()) }
        while (-not $p.StandardError.EndOfStream)  { $sw.WriteLine($p.StandardError.ReadLine()) }
        Start-Sleep -Milliseconds 200
      }
      while (-not $p.StandardOutput.EndOfStream) { $sw.WriteLine($p.StandardOutput.ReadLine()) }
      while (-not $p.StandardError.EndOfStream)  { $sw.WriteLine($p.StandardError.ReadLine()) }
      $sw.Close()
    } catch {}
  } -ArgumentList $script:n8nProc, $n8nLog | Out-Null

  Write-Green "✅ n8n läuft. Logs: $n8nLog"
} else {
  Write-Yellow "⚠️  Überspringe n8n Start (Node.js fehlt)"
}

# Info
Write-Blue "💻 Starte NiceGUI App..."
Write-Host "---------------------------------------------------"
Write-Green "👉 App URL: http://localhost:8080"
if ($HasNode) { Write-Green "👉 n8n URL: http://localhost:5678" }
Write-Host "---------------------------------------------------"
Write-Host "Drücke Ctrl+C um alles zu beenden."
Write-Host ""

# Start Python App (foreground)
$mainPy = Join-Path $appDir "main.py"
if (-not (Test-Path $mainPy)) {
  Write-Red "❌ main.py nicht gefunden unter: $mainPy"
  & $cleanup
  exit 1
}

try {
  & $venvPython $mainPy
} finally {
  & $cleanup
  Set-Location $RepoRoot
}
