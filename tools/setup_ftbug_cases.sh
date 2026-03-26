#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_INPUT_DIR="${ROOT_DIR}/runs/ftbug/base/route-only/input/ftbug"
CASES_ROOT="${ROOT_DIR}/runs/ftbug/route-only"
BASE_SHUD="${ROOT_DIR}/runs/ftbug/base/route-only/ftbug.SHUD"

declare -A CASE_RIV=(
  [truth]="${ROOT_DIR}/testdata/ftbug/truth.sp.riv"
  [fixed]="${ROOT_DIR}/runs/ftbug/preprocess/fixed.sp.riv"
  [old]="${ROOT_DIR}/runs/ftbug/preprocess/old.sp.riv"
  [slope-only]="${ROOT_DIR}/runs/ftbug/preprocess/slope-only.sp.riv"
  [point-only]="${ROOT_DIR}/runs/ftbug/preprocess/point-only.sp.riv"
)

required_paths=(
  "${BASE_INPUT_DIR}"
  "${BASE_SHUD}"
)

for case in "${!CASE_RIV[@]}"; do
  required_paths+=("${CASE_RIV[$case]}")
done

for path in "${required_paths[@]}"; do
  if [[ ! -e "${path}" ]]; then
    printf 'Missing required path: %s\n' "${path}" >&2
    exit 1
  fi
done

mkdir -p "${CASES_ROOT}"

inject_diag_interval() {
  local para_path="$1"

  if grep -Eq '^[[:space:]]*DT_DIAG_RIV[[:space:]]+' "${para_path}"; then
    perl -0pi -e 's/^[ \t]*DT_DIAG_RIV[ \t]+.*\n/DT_DIAG_RIV\t60\n/m' "${para_path}"
    return
  fi

  if grep -Eq '^[[:space:]]*DT_QR_UP[[:space:]]+' "${para_path}"; then
    perl -0pi -e 's/^(DT_QR_UP[ \t]+.*\n)/$1DT_DIAG_RIV\t60\n/m' "${para_path}"
  else
    printf 'DT_DIAG_RIV\t60\n' >> "${para_path}"
  fi
}

write_project_file() {
  local shud_path="$1"
  local input_dir="$2"
  local output_dir="$3"

  cat <<EOF > "${shud_path}"
PRJ	ftbug
INPATH	${input_dir}
OUTPATH	${output_dir}
MESH	${input_dir}/ftbug.sp.mesh
ATT	${input_dir}/ftbug.sp.att
RIV	${input_dir}/ftbug.sp.riv
RIVSEG	${input_dir}/ftbug.sp.rivseg
CALIB	${input_dir}/ftbug.cfg.calib
PARA	${input_dir}/ftbug.cfg.para
INIT	${input_dir}/ftbug.cfg.ic
LC	${input_dir}/ftbug.para.lc
SOIL	${input_dir}/ftbug.para.soil
GEOL	${input_dir}/ftbug.para.geol
FORC	${input_dir}/ftbug.tsd.forc
LAI	${input_dir}/ftbug.tsd.lai
MF	${input_dir}/ftbug.tsd.mf
EOF
}

for case in truth fixed old slope-only point-only; do
  case_root="${CASES_ROOT}/${case}"
  input_dir="${case_root}/input/ftbug"
  output_dir="${case_root}/output/ftbug.out"

  rm -rf "${case_root}"
  mkdir -p "${input_dir}" "${output_dir}"

  cp -a "${BASE_INPUT_DIR}/." "${input_dir}/"
  cp "${CASE_RIV[$case]}" "${input_dir}/ftbug.sp.riv"

  inject_diag_interval "${input_dir}/ftbug.cfg.para"
  write_project_file "${case_root}/ftbug.SHUD" "${input_dir}" "${output_dir}"

  printf 'Prepared case %-10s -> %s\n' "${case}" "${case_root}"
done
