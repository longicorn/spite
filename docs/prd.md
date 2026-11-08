# Product Requirements Document (PRD): Spite

[日本語版 (Japanese)](prd.ja.md)

## Vision

Spite is an experimental tool for forecasting software delivery as a probability distribution. It helps teams communicate uncertainty, compare assumptions, and evaluate outcomes against forecasts. It focuses on elapsed business days rather than subjective estimation units.

## Users and use cases

Engineering managers, technical leads, and teams use Spite to forecast delivery and explain uncertainty to stakeholders. They can compare scenarios, identify possible delays, and review a completed project's actual delivery against an earlier prediction.

## Capabilities

- [Predict](predict/prd.md) builds a lognormal forecast from a target deadline and supports retrospective evaluation against actual completion.
- [Simulation](simulation/prd.md) models project structure, resource constraints, discovery, and rework to produce empirical completion distributions.

Both capabilities report lead times in business days. The [shared ADR](adr.md) describes the current calendar convention. Feature-specific documents define their inputs, outputs, limitations, and planned work.

## Shared scope

Weekends are excluded from business days; holidays and configurable team calendars are not currently supported. Automatic calibration from historical project data and persistent project history remain future work.
