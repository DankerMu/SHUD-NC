#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 1) AutoSHUD (Step1-3): generate static inputs + forcing CSV
bash "${repo_root}/tools/run_qhh_baseline_autoshud.sh"

# 2) SHUD baseline run (reads forcing CSV)
shud_bin="${repo_root}/SHUD/shud"
run_root="${repo_root}/runs/qhh/baseline"

if [[ ! -x "${shud_bin}" ]]; then
  echo "SHUD binary not found/executable: ${shud_bin}" >&2
  echo "Build it in ${repo_root}/SHUD (e.g. ./configure && make shud) then re-run." >&2
  exit 1
fi

mkdir -p "${run_root}/logs"

(
  cd "${run_root}"
  "${shud_bin}" qhh 2>&1 | tee "${run_root}/logs/shud_qhh.log"
)

echo "Done."
echo "- Inputs:  ${run_root}/input/qhh"
echo "- Outputs: ${run_root}/output/qhh.out"
echo "- Log:     ${run_root}/logs/shud_qhh.log"

