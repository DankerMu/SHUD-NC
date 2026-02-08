## Implementation
- [ ] Add UGRID mesh dimensions (`mesh_node`, `mesh_face`, `max_face_nodes=3`)
- [ ] Write node coordinate variables from SHUD mesh
- [ ] Write face-node connectivity with `start_index=1`
- [ ] Write topology variable and required attributes
- [ ] Optionally write face center coords

## Validation
- [ ] Generate `<prefix>.ele.nc` and inspect header (`ncdump -h`)
- [ ] Open with xarray and ensure dimensions/variables present

