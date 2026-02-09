# Environment setup (macOS/Linux)

This repo uses both **R** (AutoSHUD / rSHUD tooling) and **Python** (repo orchestration via `tools/shudnc.py`).

## System dependencies (GDAL/GEOS/PROJ, udunits, netcdf)

You need GDAL/GEOS/PROJ for `sf`/`terra`, plus udunits/netcdf for common geospatial + NetCDF workflows.

### macOS (Homebrew)

```bash
brew install r pkg-config gdal geos proj udunits netcdf
```

If you don’t have a compiler toolchain yet:

```bash
xcode-select --install
```

### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y \
  r-base r-base-dev build-essential pkg-config \
  gdal-bin libgdal-dev libgeos-dev libproj-dev proj-data proj-bin \
  libudunits2-dev \
  libnetcdf-dev netcdf-bin
```

## R (project-local `.Rlib/`)

We install R packages into a **project-local** library directory: `<repo>/.Rlib/`.

1) Make sure submodules exist (for local `rSHUD/` install):

```bash
git submodule update --init --recursive
```

2) Install dependencies into `.Rlib/`:

```bash
Rscript tools/r/install_deps.R
```

If you haven't migrated `rSHUD` away from legacy dependencies yet (or if `rSHUD` install fails), you can still set up the core stack first:

```bash
Rscript tools/r/install_deps.R --skip-rshud
```

3) Check the environment (fails non-zero if missing):

```bash
Rscript tools/r/check_env.R
```

Core-only check (skip `rSHUD`):

```bash
Rscript tools/r/check_env.R --skip-rshud
```

For reproducible runs, you can force R to use the project library:

```bash
R_LIBS_USER="$PWD/.Rlib" Rscript tools/r/check_env.R
```

## Python (`.venv/`)

`tools/shudnc.py` is the entrypoint for running/validating projects (e.g. `projects/qhh/shud.yaml`).

Create a local venv:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

Install the minimal Python deps:

```bash
python -m pip install pyyaml
```

Optional (used by `tools/compare_forcing.py` / `tools/compare_output.py`):

```bash
python -m pip install netCDF4 numpy
```

## Troubleshooting

### `sf`/`terra` build problems

- **macOS**: make sure Homebrew deps are installed and `pkg-config` is available.
- **Linux**: ensure you installed the `-dev` packages (`libgdal-dev`, `libgeos-dev`, `libproj-dev`, `libudunits2-dev`, `libnetcdf-dev`).

If you see errors about PROJ resources (e.g. `proj.db`), confirm your PROJ installation is complete and on PATH. On Homebrew systems this may require a new shell session after installing `proj`.

### zsh history expansion gotcha (`!`)

In zsh, `!` triggers history expansion. This often breaks commands that contain version constraints like `pkg!=1.2.3`.

- For R one-liners, this can also break expressions like `pkgs[!vapply(...)]`.
- Use single quotes: `python -m pip install 'pkg!=1.2.3'`
- Use single quotes: `Rscript -e 'miss<-pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly=TRUE)]'`
- Or disable history expansion for the session: `set +H`
