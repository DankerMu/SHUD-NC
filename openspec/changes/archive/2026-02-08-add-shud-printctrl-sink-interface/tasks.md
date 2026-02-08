## Implementation
- [x] Define `IPrintSink` interface
- [x] Store `n_all` (original full dimension) and `icol[]` in `Print_Ctrl` for sink usage
- [x] Call sink hooks at:
  - [x] after `Init` (metadata ready)
  - [x] on each interval boundary (t_quantized + selected buffer)
  - [x] on close/destruct
- [x] Ensure legacy ASCII/BINARY output remains unchanged

## Validation
- [x] Build: `make shud`
- [x] Run baseline short simulation and compare legacy outputs vs pre-change

