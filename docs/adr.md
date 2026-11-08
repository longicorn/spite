# Architecture Decision Record (ADR): Spite

[日本語版 (Japanese)](adr.ja.md)

This document records shared architectural decisions. See the [Predict ADR](predict/adr.md) and [Simulation ADR](simulation/adr.md) for feature-specific decisions.

---

## ADR-0004: Abstract periods and optional day conversion

### Status
Accepted; supersedes ADR-0003.

### Decision
Both features express duration in abstract periods. Users may supply approximate days per period as a simple multiplier. Spite does not calculate calendar dates or holidays. Point-based work and throughput calibration are not yet implemented.

### Consequences
Forecasts can be compared without implying calendar precision. A real completion date requires separate consideration of calendars and team circumstances.

---

## ADR-0003: Business Day Calculation Excluding Weekends Without Holiday Calendars

### Status
Superseded by ADR-0004.

### Context
Project lead times need to be mapped between calendar dates (used by human planning) and continuous or discrete working durations (used in statistical distribution calculations).

Calendar calculations introduce domain complexity due to national holidays, regional variations, team-specific working patterns, and external calendar dependencies. For an experimental prototype, embedding heavy holiday calendar dependencies risks complicating execution without addressing the core hypothesis of probabilistic forecasting.

### Decision
1. **Exclude Weekends Only**:
   - Define business days strictly by excluding Saturdays and Sundays.
   - Monday through Friday are treated as working days with duration weight 1.0.
2. **Deterministic Day-to-Date Conversion**:
   - `business_days_between(start_date, end_date)` calculates working days, setting `start_date` as day 0.
   - If an end date falls on a weekend, the weekend days themselves are not counted toward duration.
   - Each feature rounds fractional durations to whole days before calling `add_business_days`: Predict uses the nearest integer, while Simulation rounds up.
3. **Defer Holiday Calendars**:
   - National holidays and company vacations are explicitly deferred to future calendar plug-in architecture.

### Consequences
- **Positive**: Zero external holiday calendar dependencies; highly predictable, lightweight, and cross-platform calculation. Allows immediate focus on testing the core probabilistic distribution logic.
- **Negative / Trade-offs**: Calculations across periods with heavy national holidays may overestimate available working days and skew calendar milestone dates slightly earlier than reality.
