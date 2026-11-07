# Architecture Decision Record (ADR): Spite

[日本語版 (Japanese)](adr.ja.md)

This document consolidates the architectural and design decisions established for Spite.

---

## Table of Decisions

- [ADR-0001: Lognormal Distribution and Three-Scenario Forecasting](#adr-0001-lognormal-distribution-and-three-scenario-forecasting)
- [ADR-0002: Retrospective Evaluation Benchmarked Against Nominal Scenario](#adr-0002-retrospective-evaluation-benchmarked-against-nominal-scenario)
- [ADR-0003: Business Day Calculation Excluding Weekends Without Holiday Calendars](#adr-0003-business-day-calculation-excluding-weekends-without-holiday-calendars)

---

## ADR-0001: Lognormal Distribution and Three-Scenario Forecasting

### Status
Accepted

### Context
Traditional software delivery estimation often assumes symmetric uncertainty (e.g., standard normal distribution) or relies on subjective single-point guesses. However, software development exhibits strong right-skewness: tasks can rarely finish significantly earlier than an optimal threshold, while delays can extend significantly due to unforeseen technical complexity, coordination friction, and dependencies.

Furthermore, communicating a single distribution can fail to reflect external scenario dependencies (optimistic vs. nominal vs. pessimistic conditions).

### Decision
1. **Adopt the Lognormal Distribution** as the primary baseline distribution family for lead time modeling.
2. **Derive Parameters from Mode and Sigma**:
   - The user inputs the expected completion duration in working business days, which is set as the distribution's mode (peak probability density).
   - A default shape parameter $\sigma = 0.5$ is adopted across all scenarios.
   - The log-scale mean is calculated as:
     $$\mu = \ln(\text{mode}) + \sigma^2$$
3. **Generate Three Scenarios Using Multipliers**:
   - **Best scenario**: $\text{mode}_{\text{best}} = \text{mode}_{\text{nominal}} \times 0.8$
   - **Nominal scenario**: $\text{mode}_{\text{nominal}} = \text{mode}$
   - **Worst scenario**: $\text{mode}_{\text{worst}} = \text{mode}_{\text{nominal}} \times 1.5$
4. Compute P50 (median), P80, and P90 percentiles using `scipy.stats.lognorm`.

### Consequences
- **Positive**: Captures asymmetric lead time behavior (hard lower bound near start, long right tail). Provides intuitive scenario-based planning (Best, Nominal, Worst) without requiring deep statistical expertise from the user.
- **Negative / Trade-offs**: The default multipliers (0.8, 1.5) and $\sigma = 0.5$ are working heuristics and have not yet been calibrated against empirical multi-project datasets. Severe fat-tailed phenomena (e.g., power-law extremes) may be underestimated compared to spliced Pareto / GPD models.

---

## ADR-0002: Retrospective Evaluation Benchmarked Against Nominal Scenario

### Status
Accepted

### Context
When completing a development project, teams need to evaluate how their actual execution compared against their original probabilistic plans. In Spite's three-scenario forecast (Best, Nominal, Worst), evaluating the outcome against all three distributions simultaneously could create conflicting or confusing signals.

Additionally, completed projects with severe delays may fall far into the tail of the distribution, where conventional percentile representations fail to convey the rarity of the event.

### Decision
1. **Benchmark Against the Nominal Scenario**:
   - In retrospective mode (`--actual-end-date`), numerical evaluations (deviations, percentiles, milestones) are evaluated strictly against the **Nominal scenario** distribution.
   - Best and Worst scenarios remain visible on charts for visual comparison of spread, but do not generate secondary evaluation metrics.
2. **Cumulative Distribution Function (CDF) for Percentile**:
   - The actual lead time is mapped to its percentile on the Nominal CDF:
     $$\text{Percentile} = F_{\text{nominal}}(\text{actual\_days})$$
3. **P90 and P99.9 Tail Evaluations**:
   - Calculate the delta between the actual working days and the Nominal P90 milestone.
   - If the actual outcome exceeds the 99.9th percentile ($F_{\text{nominal}} > 0.999$), display it as "exceeding P99.9" and calculate the residual tail probability using the Survival Function (SF, $1 - \text{CDF}$) to indicate extreme outliers.
4. **Single-Project Scope**:
   - Retrospective evaluation is currently designed for single-project reflection, not for automatic Bayesian updating of hyperparameters ($\sigma$, factors).

### Consequences
- **Positive**: Provides a clear, unambiguous benchmark baseline for project review without confusing multi-distribution evaluations. Explicitly flags extreme tail events using SF rather than misleading 100% rounding.
- **Negative / Trade-offs**: A single historical result is not yet fed back into the system to automatically recalibrate prior distributions for future projects.

---

## ADR-0003: Business Day Calculation Excluding Weekends Without Holiday Calendars

### Status
Accepted

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
   - `add_business_days(start_date, round(days))` restores calculated fractional percentile durations back into calendar dates.
3. **Defer Holiday Calendars**:
   - National holidays and company vacations are explicitly deferred to future calendar plug-in architecture.

### Consequences
- **Positive**: Zero external holiday calendar dependencies; highly predictable, lightweight, and cross-platform calculation. Allows immediate focus on testing the core probabilistic distribution logic.
- **Negative / Trade-offs**: Calculations across periods with heavy national holidays may overestimate available working days and skew calendar milestone dates slightly earlier than reality.
