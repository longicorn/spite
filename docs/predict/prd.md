# Product Requirements Document (PRD): Predict

[日本語版 (Japanese)](prd.ja.md)

`spite predict` forecasts completion duration using three lognormal scenarios. See the [product PRD](../prd.md) and [Predict ADR](adr.md).

## Inputs

- `--periods`: positive Nominal scenario mode in abstract periods; it is not the median.
- `--actual-periods`: optional non-negative actual duration for retrospective evaluation.
- `--days-per-period`: optional positive multiplier for approximate day equivalents. No calendar or holiday calculation is performed.
- `--best-factor` and `--worst-factor`: scenario mode multipliers, defaulting to 0.8 and 1.5.
- `--sigma`: positive lognormal shape parameter, default 0.5.
- `--format`: `terminal` (default) or `markdown`. `--output` selects a root directory for a new run containing `report.md`, `snapshot.json`, and, in terminal mode, `chart.png`; `--show` displays the image and cannot be combined with Markdown.
- `--distribution`: currently `lognormal` only.

## Outputs

P50, P80 and P90 are given in periods for each scenario, with optional approximate days. The plot displays lognormal density. When actual duration is provided, the report compares it with the Nominal mode and P90 and reports its Nominal CDF percentile. For outcomes above P99.9, the survival function reports the remaining tail probability.

The mode and sigma determine the distribution: μ = ln(mode) + σ². Historical calibration and additional distribution families remain future work.
