## ADDED Requirements

### Requirement: Full-dimension NetCDF variables with fill values
NetCDF output variables SHALL use full object dimensions (NumEle/NumRiv/NumLake). When a column is disabled in legacy selection, the NetCDF variable SHALL contain `_FillValue` at that index.

#### Scenario: Disabled element column is filled
- **GIVEN** an element is disabled in `cfg.output`
- **WHEN** NetCDF output is written
- **THEN** the corresponding element index contains `_FillValue` and the mask is 0

