## ADDED Requirements

### Requirement: Split NetCDF outputs by object type
The system SHALL write NetCDF outputs into three files: element, river, and lake, each with its own object dimension and shared `time` semantics.

#### Scenario: River file exists when rivers are present
- **GIVEN** `NumRiv > 0` and NetCDF output enabled
- **WHEN** SHUD finishes
- **THEN** `<prefix>.riv.nc` exists and contains a `river` dimension and `time` dimension

### Requirement: Variable routing is based on full-dimension size
When writing NetCDF outputs, the system SHALL route each `Print_Ctrl` stream to the correct file (element/river/lake) based on the **full-dimension size** (`n_all == NumEle/NumRiv/NumLake`), and SHALL NOT rely solely on variable name prefixes.

#### Scenario: Element variables without `ele` prefix are routed correctly
- **GIVEN** an element-dimension output stream whose variable name does not start with `ele` (e.g., `rn_h`)
- **WHEN** NetCDF output routing is performed
- **THEN** it is written to the element NetCDF file based on `n_all == NumEle`
