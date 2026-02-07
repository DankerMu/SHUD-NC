#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "${repo_root}/tools/shudnc.py" "${repo_root}/projects/qhh/shud.yaml" run --profile baseline
