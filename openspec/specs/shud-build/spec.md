# Spec: SHUD Build (Makefile)

## Purpose
定义 SHUD 的构建约定与依赖（baseline），并为后续阶段 A/B 的可选 NetCDF 功能预留扩展点与回归基线。
## Requirements
### Requirement: Baseline build produces `shud`
The SHUD Makefile SHALL build an executable `shud` (serial) under the `SHUD/` directory when SUNDIALS is available.

#### Scenario: Build with default settings
- **GIVEN** `SUNDIALS_DIR` is correctly configured
- **WHEN** user runs `make shud` in `SHUD/`
- **THEN** an executable `SHUD/shud` is produced

### Requirement: OpenMP build is optional
The SHUD Makefile SHALL provide an optional OpenMP build target (`shud_omp`) that can be built when OpenMP is available and enabled.

#### Scenario: OpenMP build target exists
- **GIVEN** OpenMP toolchain is installed
- **WHEN** user runs `make shud_omp`
- **THEN** an executable `SHUD/shud_omp` is produced

### Requirement: Optional NetCDF support build flag
The SHUD build system SHALL support enabling NetCDF support behind an explicit build flag (e.g., `NETCDF=1`) and keep it disabled by default.

#### Scenario: Default build does not require NetCDF
- **GIVEN** NetCDF is not installed
- **WHEN** user runs `make shud`
- **THEN** the build succeeds and NetCDF support remains disabled

#### Scenario: NetCDF-enabled build links NetCDF
- **GIVEN** NetCDF is installed and discoverable via `nc-config` or `pkg-config`
- **WHEN** user runs `make shud NETCDF=1`
- **THEN** the build links against `libnetcdf` and enables NetCDF support

