#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
config="${repo_root}/qhh/config/qhh_cmfd_2017_2018.baseline.autoshud.txt"

cd "${repo_root}/AutoSHUD"
Rscript Step1_RawDataProcessng.R "${config}"
Rscript Step2_DataSubset.R "${config}"
Rscript Step3_BuidModel.R "${config}"

echo "Done. Outputs under: ${repo_root}/runs/qhh/baseline"

