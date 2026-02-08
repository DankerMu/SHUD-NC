## Implementation
- [ ] Define `IPrintSink` interface
- [ ] Store `n_all` (original full dimension) and `icol[]` in `Print_Ctrl` for sink usage
- [ ] Call sink hooks at:
  - [ ] after `Init` (metadata ready)
  - [ ] on each interval boundary (t_quantized + selected buffer)
  - [ ] on close/destruct
- [ ] Ensure legacy ASCII/BINARY output remains unchanged

## Validation
- [ ] Build: `make shud`
- [ ] Run baseline short simulation and compare legacy outputs vs pre-change

