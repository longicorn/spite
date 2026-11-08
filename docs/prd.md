# Product Requirements Document (PRD): Spite

[日本語版 (Japanese)](prd.ja.md)

Spite is an experimental tool for forecasting software delivery as a probability distribution. It helps teams compare assumptions and explain uncertainty.

[Predict](predict/prd.md) uses an expected duration as the mode of a lognormal distribution and supports retrospective evaluation. [Simulation](simulation/prd.md) models dependencies, resource constraints, discovery and rework.

Both use abstract periods. The user defines what a period means, such as a sprint. An optional days-per-period multiplier displays an approximate duration; Spite does not calculate calendar dates or holidays. See the [shared ADR](adr.md). Point-based work and calibration from project data are future work, not current simulation inputs.

[History](history/prd.md) reports observed Git history on the current branch and can compare its timestamp span with a saved forecast.
