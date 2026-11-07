# Product Requirements Document (PRD): Spite

[日本語版 (Japanese)](prd.ja.md)

## 1. Vision & Background

In software development, delivery deadlines are frequently demanded as a single deterministic date. However, software engineering inherently carries high uncertainty, complexity, and variability. Treating deadlines as a single point in time often leads to inaccurate planning and hidden project risks.

**Spite** is an experimental tool designed to model software delivery deadlines as a **probability distribution** rather than a single fixed date. Inspired by the perspective that "a system's deadline is a probability distribution" (Walker Royce, Bent Flyvbjerg's empirical project studies), Spite enables teams to:
- Establish an initial hypothetical probability distribution from project inception.
- Adjust assumptions (scenarios, parameters, variance) dynamically.
- Evaluate completed project results against past assumptions to iteratively improve estimation accuracy.

Spite focuses on completion lead times rather than subjective estimation units such as story points or velocity sizing.

---

## 2. Target Users & Use Cases

### Target Users
- Engineering Managers, Technical Leaders, and Project Managers looking for empirical and probabilistic project forecasting.
- Agile / Scrum teams seeking to communicate delivery likelihoods and confidence intervals to stakeholders without relying on arbitrary single-date commitments.

### Key Use Cases
1. **Forward-looking Forecasting (Prediction Mode)**
   - Before or during development, predict the completion probability distribution and milestone dates (P50, P80, P90) based on start date and target delivery deadline.
2. **Post-delivery Retrospective (Retrospective Mode)**
   - When a project or milestone completes, evaluate how the actual delivery date compared against initial probabilistic expectations (percentile ranking, delay/advance margins, extreme tail occurrence).

---

## 3. Product Scope & Functional Requirements

### 3.1. CLI Command: `spite predict`

The tool provides a unified command line interface via `spite predict`.

#### Inputs & Parameters
- `--start-date` (YYYY-MM-DD, Required): Project start date.
- `--deadline` (YYYY-MM-DD, Required): Initial target deadline. Must be a business day strictly following the start date.
- `--actual-end-date` (YYYY-MM-DD, Optional): Actual completion date. Must be equal to or greater than the start date.
- `--best-factor` (Float, Default: `0.8`): Factor applied to nominal business duration to determine the peak of the optimistic scenario ($0 < \text{best-factor} < 1$).
- `--worst-factor` (Float, Default: `1.5`): Factor applied to nominal business duration to determine the peak of the pessimistic scenario ($\text{worst-factor} > 1$).
- `--sigma` (Float, Default: `0.5`): Log-scale shape parameter ($\sigma$) shared across all three scenarios ($\sigma > 0$).
- `--output` (Path, Optional): File path to save generated chart images (PNG, etc.).
- `--show` (Flag, Optional): Display the generated chart window using GUI backend.
- `--distribution` / `-d` (String, Default: `lognormal`): Distribution family (currently supports `lognormal`).

### 3.2. Forecast Mode (`--actual-end-date` omitted)
- Calculates duration in working business days from `--start-date` to `--deadline`.
- Generates 3 scenarios:
  - **Best scenario**: Peak lead time = $\text{Nominal} \times \text{best-factor}$
  - **Nominal scenario**: Peak lead time = $\text{Nominal}$
  - **Worst scenario**: Peak lead time = $\text{Nominal} \times \text{worst-factor}$
- For each scenario, calculates percentiles:
  - **P50** (Median): 50% likelihood of completion on or before this date.
  - **P80**: 80% confidence completion date.
  - **P90**: 90% confidence completion date.
- Outputs an ASCII distribution representation in terminal by default, or generates matplotlib charts when `--output` or `--show` is provided.

### 3.3. Retrospective Mode (`--actual-end-date` provided)
- Renders the 3 scenarios as in forecast mode, extended along the x-axis to cover the actual lead time if needed.
- Evaluates the actual duration against the **Nominal scenario**:
  - Difference in working days and percentage relative to the nominal duration (e.g., "Actual completed N business days (X.X%) delayed/early").
  - Percentile ranking of the actual completion using Cumulative Distribution Function (CDF).
  - Variance against the Nominal P90 milestone.
  - Survival Function (SF) probability if the actual outcome exceeds P99.9 (indicating severe tail risk).
- Displays an actual marker and narrative summary on the chart and terminal.

---

## 4. Technical & Mathematical Architecture

### 4.1. Business Day Calculation
- Non-working days are defined as Saturdays and Sundays.
- National holidays are currently not excluded and deferred to future calendar extensions.
- Conversion between calendar dates and working days is strictly monotonically computed.

### 4.2. Probability Distribution Model
- **Lognormal Distribution**:
  $$\text{mode} = \exp(\mu - \sigma^2) \implies \mu = \ln(\text{mode}) + \sigma^2$$
  where mode is set to the peak working days of each scenario.
- Percentiles and probabilities are computed via `scipy.stats.lognorm`.

---

## 5. Non-Goals & Future Milestones

The following capabilities are excluded from the current baseline and planned for future iterations:
- **Historical Data Calibration**: Automatic estimation of $\sigma$ or factors from historical issue/PR datasets (GitHub, GitLab, Jira).
- **Advanced Distribution Families**: Spliced distributions (Lognormal + Generalized Pareto Distribution / Pareto) for heavy tails, and Weibull distributions for testing/defect convergence.
- **Holiday & Calendar Support**: Regional public holidays and flexible team non-working calendars.
- **Persistent Storage**: Database or file-based history storage for recurring sprint tracking.
