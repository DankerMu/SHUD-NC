## Implementation
- [x] Add UGRID mesh dimensions (`mesh_node`, `mesh_face`, `max_face_nodes=3`)
- [x] Write node coordinate variables from SHUD mesh
- [x] Write face-node connectivity with `start_index=1`
- [x] Write topology variable and required attributes
- [x] Optionally write face center coords

## Validation
- [x] Generate `<prefix>.ele.nc` and inspect header (`ncdump -h`)
- [x] Open with xarray and ensure dimensions/variables present

