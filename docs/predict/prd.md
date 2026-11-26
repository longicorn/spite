# Product Requirements Document (PRD): Predict

[日本語版 (Japanese)](prd.ja.md)

`spite predict` forecasts completion duration using three lognormal scenarios. See the [product PRD](../prd.md) and [Predict ADR](adr.md).

## Inputs

- `--periods`: positive Nominal scenario mode in abstract periods; it is not the median.
- `--target-periods`: optional positive target duration in abstract periods to evaluate completion probability and delay risk.
- `--target-days`: optional positive target duration in approximate days (converted to periods via `--days-per-period`; requires `--days-per-period`, mutually exclusive with `--target-periods`).
- `--actual-periods`: optional non-negative actual duration for retrospective evaluation.
- `--days-per-period`: optional positive multiplier for approximate day equivalents. No calendar or holiday calculation is performed.
- `--best-factor` and `--worst-factor`: scenario mode multipliers, defaulting to 0.8 and 1.5.
- `--sigma`: positive lognormal shape parameter, default 0.5.
- `--format`: `terminal` (default) or `markdown`. `--output` selects a root directory for a new run containing `report.md`, `snapshot.json`, and, in terminal mode, `chart.png`; `--show` displays the image and cannot be combined with Markdown.
- `--distribution`: currently `lognormal` only.

## Outputs

P50, P80 and P90 are given in periods for each scenario, with optional approximate days. The plot displays lognormal density. When actual duration is provided, the report compares it with the Nominal mode and P90 and reports its Nominal CDF percentile. For outcomes above P99.9, the survival function reports the remaining tail probability.

When a target duration (`--target-periods` or `--target-days`) is specified, the report presents the target evaluation across all three scenarios (Best, Nominal, Worst):
- The on-time completion probability: $P(\text{Duration} \le \text{target}) = F(\text{target})$.
- The delay risk: $P(\text{Duration} > \text{target}) = 1 - F(\text{target})$ (using the survival function).
- Reports show whole percentages in one column, rounding half up and deriving displayed delay risk from the rounded completion percentage. Nonzero probabilities rounded to an endpoint are displayed as `<1%` or `>99%` instead. The snapshot retains the unrounded survival probability, including extreme tail risk.
- In Matplotlib charts (`--show`, `chart.png`) and HTML reports, a distinct vertical reference line indicates the target duration. When both actual duration and target duration are present, they are rendered with distinct line styles and labels to remain readily distinguishable.
- In terminal ASCII distribution rendering, a dedicated indicator identifies the target row.
- In Markdown reports using Mermaid `xychart-beta`, vertical target reference lines are deferred due to syntax constraints, relying on the structured target report section.

The mode and sigma determine the distribution: μ = ln(mode) + σ². Historical calibration and additional distribution families remain future work.

The three scenarios are conditional forecasts with different mode assumptions and the same sigma. Their distributions may overlap; the tool does not combine them into a probability-weighted mixture. The scenarios and sigma are assumptions, not calibrated confidence levels.

For now all scenarios retain the same sigma: there is no calibration evidence for assigning a different width to each. Once sufficient outcomes are available, compare the common-sigma model with scenario-specific widths before changing the defaults.
