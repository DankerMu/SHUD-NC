## MODIFIED Requirements

### Requirement: Time semantics (step function)
Forcing in SHUD SHALL behave as a **step function** over forcing time intervals, independent of forcing source.

#### Scenario: Provider swap does not change behavior
- **GIVEN** the baseline CSV forcing source
- **WHEN** forcing is accessed through a provider abstraction
- **THEN** values and `currentTimeMin/nextTimeMin` semantics remain unchanged

