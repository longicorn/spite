# Architecture Decision Record (ADR): Spite

[日本語版 (Japanese)](adr.ja.md)

This document records shared architectural decisions. See the [Predict ADR](predict/adr.md) and [Simulation ADR](simulation/adr.md) for feature-specific decisions.

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
