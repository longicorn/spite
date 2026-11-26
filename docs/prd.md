# Product Requirements Document (PRD): Spite

[日本語版 (Japanese)](prd.ja.md)

Spite is an experimental tool for forecasting software delivery as a probability distribution. It helps teams compare assumptions and explain uncertainty.

[Predict](predict/prd.md) uses an expected duration as the mode of a lognormal distribution and supports retrospective evaluation. [Simulation](simulation/prd.md) models dependencies, resource constraints, discovery and rework.

Both use abstract periods. The user defines what a period means, such as a sprint. An optional days-per-period multiplier displays an approximate duration; Spite does not calculate calendar dates or holidays. See the [shared ADR](adr.md). Point-based work and calibration from project data are future work, not current simulation inputs.

Both `predict` and `simulate` can evaluate completion probability against a user-defined target duration (`--target-periods` or `--target-days`), reporting on-time completion chances and delay risks across scenarios. When target evaluation is active, distribution charts in Matplotlib (PNG/GUI) and HTML reports display a distinct vertical reference line for the target (distinguishable from any retrospective actual duration line), and terminal ASCII displays indicate the target position. Markdown reports retain Mermaid syntax without target vertical lines due to syntax limitations, relying instead on structured summary sections and deferring Mermaid reference line support to future enhancements.

[History](history/prd.md) reports observed Git history on the current branch and can compare its timestamp span with a saved forecast.

## Reporting and Output Formats

Spite supports multiple report formats to serve both developer workflows and stakeholder communication:

- **Markdown (`--format markdown`)**: The default human-readable text format, optimized for version control, code review, and repository browsing.
- **Terminal (`--format terminal`)**: Formatted console output for interactive CLI usage.
- **HTML (`--format html`)**: Self-contained, portable HTML reports designed for sharing with non-engineering stakeholders, presentations, or printing to PDF. When saved or rendered, styles and forecast chart images (base64 data URI) are embedded into a single standalone file without external network dependencies.
- **Machine-readable snapshots (`snapshot.json`)**: Persistent JSON representations of model runs for programmatic inspection and downstream tooling.
