#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: bash scripts/check-deployment.sh SSH_TARGET https://app.example.com [EXPECTED_COMMIT]" >&2
  exit 2
fi

target=$1
base_url=${2%/}
expected_commit=${3:-}
ssh_command=(ssh -o BatchMode=yes -o ConnectTimeout=10 "$target")

source_revision=$("${ssh_command[@]}" 'git -C "$HOME/fixundfertig" rev-parse HEAD')
container_revision=$("${ssh_command[@]}" 'docker exec fixundfertig_app printenv APP_REVISION')
image_revision=$("${ssh_command[@]}" 'docker inspect --format "{{index .Config.Labels \"org.opencontainers.image.revision\"}}" fixundfertig_app')
container_health=$("${ssh_command[@]}" 'docker inspect --format "{{.State.Health.Status}}" fixundfertig_app')
health_json=$(curl --connect-timeout 10 --max-time 20 --fail --silent --show-error "$base_url/healthz")
health_revision=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("revision", ""))' "$health_json")
health_status=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("status", ""))' "$health_json")
frontend_revision=$(curl --connect-timeout 10 --max-time 20 --fail --silent --show-error "$base_url/" | python3 -c 'import re,sys; match=re.search(r"app-revision\" content=\"([^\"]+)", sys.stdin.read()); print(match.group(1) if match else "")')

printf 'source=%s\nimage=%s\ncontainer=%s\ncontainer_health=%s\nhealth=%s (%s)\nfrontend=%s\n' \
  "$source_revision" "$image_revision" "$container_revision" "$container_health" "$health_status" "$health_revision" "$frontend_revision"

test -n "$expected_commit" || expected_commit=$source_revision
if [[ "$source_revision" == "$expected_commit" &&
      "$image_revision" == "$expected_commit" &&
      "$container_revision" == "$expected_commit" &&
      "$health_revision" == "$expected_commit" &&
      "$frontend_revision" == "$expected_commit" &&
      "$container_health" == "healthy" && "$health_status" == "ok" ]]; then
  echo "Deployment verified."
else
  echo "Deployment mismatch or unhealthy application." >&2
  exit 1
fi
