## ADDED Requirements

### Requirement: Element NetCDF includes UGRID mesh topology
The element NetCDF file SHALL include UGRID mesh topology and connectivity variables so that element variables can be associated with the mesh.

#### Scenario: Mesh topology variable exists
- **GIVEN** NetCDF output enabled
- **WHEN** `<prefix>.ele.nc` is produced
- **THEN** it contains a mesh topology variable with `cf_role="mesh_topology"` and face connectivity with `start_index=1`

