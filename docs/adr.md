# Architecture Decision Record (ADR): Spite

[日本語版 (Japanese)](adr.ja.md)

This document records shared architectural decisions. See the [Predict ADR](predict/adr.md) and [Simulation ADR](simulation/adr.md) for feature-specific decisions.

---

## ADR-0006: Target Completion Probability Evaluation for Forecasts

### Status
Accepted.

### Context
While percentile forecasts (such as P50, P80, P90) describe the shape of uncertainty, project managers and stakeholders frequently ask a specific forward-looking question: "What is the probability of delivering on or before date/milestone X?" or "What is our risk of delay past X?"

Without explicit target evaluation, users must manually interpolate between percentiles or guess where their deadline falls on the distribution curve. Furthermore, to adhere to ADR-0004, target evaluations must avoid false calendar precision and maintain consistency between abstract periods and optional day multipliers.

### Decision
1. **Unified Target CLI Options**:
   - Provide `--target-periods <float>` across both `predict` and `simulate` to accept a target duration in abstract periods.
   - Provide `--target-days <float>` as a convenience option when `--days-per-period` is specified (converting days to periods via `target_periods = target_days / days_per_period`). `--target-days` requires `--days-per-period` and cannot be combined with `--target-periods`.
   - Adhere strictly to ADR-0004: do not attempt calendar dates or holiday calculations.
2. **Dual Metric Reporting (Completion Probability & Delay Risk)**:
   - For each scenario (Best, Nominal, Worst), calculate and report both:
     - **Completion Probability**: $P(\text{Duration} \le \text{target})$ as a percentage.
     - **Delay Risk (Tail Probability)**: $P(\text{Duration} > \text{target}) = 1 - P(\text{Duration} \le \text{target})$ as a percentage.
3. **Engine-Specific Computation**:
   - In `predict`: Compute analytically using the cumulative distribution function (CDF) and survival function (SF) of the fitted lognormal distribution.
   - In `simulate`: Compute empirically from the completed Monte Carlo trial durations ($\text{count}(\text{duration} \le \text{target}) / N$).
4. **Consistent Multi-format Output**:
   - In terminal, Markdown, and HTML reports, show whole percentages in one column, for example `73% (delay 27%)`. Round completion probability to the nearest integer with half rounded up and derive the displayed delay percentage as its complement. For nonzero probabilities below 0.5%, show `<1% (delay >99%)`; when completion is at least 99.5% and delay is nonzero, show `>99% (delay <1%)`. Exact zero or one is displayed as `0%` or `100%`. Simulation results are empirical estimates.
   - Preserve unrounded completion and delay probabilities in structured `snapshot.json`.
5. **Distribution Target Visualization**:
   - In Matplotlib-based visualizations (HTML report embedded images, `--format png`, and interactive `--show`), render a dedicated vertical reference line for the target duration across scenarios, styled distinctly from retrospective actual duration lines.
   - In terminal ASCII distribution plots, mark the target duration with a dedicated row indicator.
   - In Markdown reports, defer vertical lines inside Mermaid `xychart-beta` blocks due to syntax limitations, relying on the executive summary table while keeping Mermaid vertical line support as a future enhancement.

### Consequences
- **Positive**:
  - Directly answers deadline-feasibility questions for stakeholders with concrete probability metrics.
  - Aligns cleanly with ADR-0004 without adding calendar logic complexity.
  - Shared semantics across both parametric (`predict`) and structural simulation (`simulate`) commands.
- **Negative / Trade-offs**:
  - Probabilities remain conditional on model assumptions (e.g., team size, uncertainty level, mode); documentation must emphasize that high probability does not eliminate Black Swan events.

---

## ADR-0005: Self-contained HTML report format for sharing forecasts

### Status
Accepted.

### Context
Spite's primary deliverables are probabilistic forecasts and retrospective evaluations. While Markdown is well suited for developers inspecting reports inside a repository or editor, sharing results with business stakeholders, product managers, and external partners often requires a richer, visually clear presentation without requiring specialized Markdown viewers.

Exporting to separate formats such as PDF often introduces heavy system or headless browser dependencies (e.g., WeasyPrint, Chromium), complicating installation and cross-platform compatibility. Furthermore, sharing multi-file bundles (HTML referencing local images) often leads to broken image links when files are distributed via chat tools or email.

### Decision
1. **Support `--format html` across reporting commands**:
   - Provide `--format html` for commands generating reports (`predict`, `simulate`, and `history`).
   - Markdown remains the default document format.
2. **Self-contained, standalone single-file output**:
   - All styles (CSS) must be embedded in `<style>` blocks within the HTML document.
   - Any generated charts (e.g., probability distribution curves, DAG diagrams) must be inlined directly as base64-encoded data URIs (`data:image/png;base64,...`) when written to HTML.
   - The document must render cleanly offline and when opened directly from a local filesystem (`file://`) without external network requests or CDN dependencies.
3. **Print-to-PDF synergy**:
   - Include print-friendly CSS media queries (`@media print`) so users can export high-quality PDFs directly via standard browser print functionality, eliminating native PDF rendering dependencies.
4. **Lightweight rendering architecture**:
   - Keep rendering logic lightweight and avoid heavy external dependencies.

### Consequences
- **Positive**:
  - Teams can effortlessly distribute forecast reports as a single attachment that renders identically on any browser.
  - Zero heavy external PDF dependencies required; high-quality PDF generation is offloaded to the user's browser print engine.
  - No broken image links during file transfers.
- **Negative / Trade-offs**:
  - Inlining base64 images increases the raw HTML file size slightly compared to separate text files.

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
