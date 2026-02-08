## ADDED Requirements

### Requirement: Provide regression compare tooling
The project SHALL provide tooling to compare baseline vs NetCDF forcing/output runs for regression verification.

#### Scenario: Sampled comparison produces a diff summary
- **GIVEN** two run directories (baseline and nc)
- **WHEN** user runs the compare tool
- **THEN** it prints a summary including max/mean diffs and sample points

