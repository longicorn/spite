# Product Requirements Document (PRD): Simulation Module

[日本語版 (Japanese)](prd.ja.md)

## 1. Vision & Background

In software development forecasting, traditional techniques typically follow one of two approaches:
1. **Parametric distribution fitting (current Spite baseline)**: Modeling the entire project duration using an overarching probability distribution (e.g., lognormal), where scenario differences (Best, Nominal, Worst) are adjusted via subjective scalar multipliers.
2. **Deterministic network scheduling (PERT / CPM / Static Monte Carlo)**: Decomposing projects into a fixed Directed Acyclic Graph (DAG) of tasks (WBS) and randomizing only task durations.

However, real-world software engineering suffers from deep structural uncertainty—what can be described as a **Fog of War**:
- **Dynamic Task Discovery**: Many tasks (Unknown Unknowns) and hidden dependencies are only uncovered as design, investigation, or implementation proceeds.
- **Rework & Iteration**: Code review rejections, specification mismatches, and regression defects trigger circular rework loops rather than simple acyclic flows.
- **Review and Approval Waiting**: Review queues, architecture approvals, customer acceptance, and external API releases create non-linear waiting times that cannot be compressed simply by adding developers.
- **Concurrency Bottlenecks**: The relationship between team size and duration is bounded by Amdahl's Law and Brooks's Law, determined by serial bottlenecks and merge/integration complexity.

The **Simulation Module** (`/simulation`) introduces a structural simulation engine based on the **Lane-Model** concept. Instead of assuming a fixed graph or an arbitrary parametric distribution, the module simulates project topologies with stochastic discovery and rework, simulates resource-constrained execution across scenarios, and outputs empirical completion distributions alongside shareable structured Markdown and Mermaid diagrams.

---

## 2. Target Users & Key Use Cases

### Target Users
- **Engineering Managers & Tech Leads**: Who need to explain *why* projects face tail risks, why adding engineers does or does not accelerate delivery, and where critical bottlenecks lie.
- **Agile / Scrum Teams**: Seeking to update forecasts iteratively across sprints by locking in completed actuals and re-simulating remaining uncertainty.
- **Project Stakeholders & Decision Makers**: Who require transparent, verifiable rationale behind Best / Nominal / Worst project timelines.

### Key Use Cases

#### UC-1: Structural Forward Forecasting (Project Inception)
Before project kickoff, users define high-level assumptions (scale, uncertainty, structural pattern, team size). The engine simulates thousands of executions of a deterministic preset skeleton for Best, Nominal, and Worst scenarios, computing empirical P50, P80, and P90 lead times.

#### UC-2: Staffing & Resource Sensitivity Analysis
Teams evaluate the impact of changing team size (e.g., 1 developer vs. 2 vs. 4 developers) on delivery percentiles to identify concurrency saturation points caused by serial chains or review and approval bottlenecks.

#### UC-3: Iterative Sprint Re-forecasting (In-flight Updating)
As development progresses, cumulative elapsed periods and completed task counts are recorded. A new synthetic graph is generated from the known remaining task count; actual completed dependencies and in-progress work are not reconstructed.

#### UC-4: Shareable Markdown & Mermaid Reporting
Teams generate structured Markdown reports with embedded Mermaid flowcharts representing typical project topologies, critical paths, and review and approval bottlenecks, allowing seamless diff-tracking and review directly within Git PRs and team wikis.

---

## 3. Product Scope & Functional Requirements

### 3.1. CLI Interface: `spite simulate`

The simulation engine is accessed through a dedicated CLI sub-command:

```bash
uv run spite simulate [OPTIONS]
```

#### Core Inputs & Parameters
- `--days-per-period` (positive number, optional): Approximate days per period; no calendar or holiday calculation.
- `--target-periods` (positive number, optional): Target completion duration in abstract periods to evaluate probability of on-time delivery and delay risk.
- `--target-days` (positive number, optional): Target completion duration in approximate days (converted to periods via `--days-per-period`; requires `--days-per-period`, mutually exclusive with `--target-periods`).
- `--pattern` (Enum: `linear`, `parallel`, `complex`, `exploratory`, Default: `complex`): Structural topology template.
- `--scale` (Enum: `small`, `medium`, `large`, Default: `medium`): Base scope indicating approximate expected node volume.
- `--uncertainty` (Enum: `low`, `medium`, `high`, Default: `medium`): Propensity to discover hidden nodes and edges during execution.
- `--rework-rate` (Float: `0.0` to `1.0`, Default: `0.15`): Probability of rework triggered after review decisions.
- `--team-size` (Integer, Default: `2`): Concurrency limit for parallel active tasks when `--roles` is omitted.
- `--roles` (String, optional, format: `"<role1>:<count>,<role2>:<count>"`): Role-based resource pool (e.g., `"pm:1,dev:2,qa:1"`). When omitted, `--team-size` acts as a homogeneous resource pool without role constraints or switching costs. Each count creates distinct people dedicated to that role. CLI counts override YAML people or roles.
- `--switching-cost` (Non-negative number, optional, default: `0.0`): Overhead delay in periods added when switching between distinct roles across consecutive tasks on shared/multi-role resources. Defaults to 0 (no switching penalty).
- `--tasks-per-period` (positive number, default: `1`): Reference task rate per team member. Its reciprocal is the most likely task duration in periods; it does not guarantee completed throughput. Task, discovery, and rework durations use a triangular distribution from 0.5 to 2 times this duration, with its peak at that duration. Review waiting times use a separate distribution.
- `--design-effort` (positive number, default: `1.0`): Multiplier for initial design and architecture task effort in preset topologies. Ignored when `--topology` is supplied.
- `--dev-effort` (positive number, default: `1.0`): Multiplier for core development and implementation task effort in preset topologies. Ignored when `--topology` is supplied.
- `--effort-trend` (Enum: `flat`, `fatigue`, `accelerating`, Default: `flat`): Progression dynamic for implementation task effort in preset topologies. `flat` keeps task effort constant. `fatigue` compounds effort toward later tasks to reflect architectural debt and integration friction. `accelerating` tapers effort toward later tasks to reflect team learning effects. These trends are experimental, uncalibrated assumptions and may overlap with `--complexity-risk`. Ignored when `--topology` is supplied.
- `--iterations` (Integer, Default: `2000`): Number of Monte Carlo iterations per scenario.
- `--format` (Enum: `markdown`, `terminal`, `png`, Default: `markdown`): Primary output presentation format.
- `--output` (Path, optional): Root directory for per-run `report.md` and `snapshot.json`; PNG format also saves `chart.png`.
- `--continue-from` (run ID, optional): Load a prior simulation from the output root. Requires cumulative `--elapsed-periods`, `--completed-tasks`, and known `--remaining-tasks`. Remaining tasks form a new synthetic graph; completed dependencies and work in progress are unknown. Settings are inherited unless overridden. Trend progress is estimated from cumulative completed and remaining task counts; task identities and phases are unknown. Reports compare total P50, P80 and P90 against the prior run and show remaining and total forecasts.

---

### 3.2. Structural Graph Generation Model

By default each preset generates a deterministic initial skeleton for a given pattern and scale. Optional topology variation changes the initial skeleton; discovery and rework can also change the execution graph during a trial:

| Pattern | Topology Characteristics | Representative Software Scenario |
| :--- | :--- | :--- |
| **Linear (`linear`)** | Strictly sequential chains ($A \to B \to C$) with conditional rework | Deep investigation, sequential refactoring, rigid single-track pipeline |
| **Parallel (`parallel`)** | High branching factor ($A \to \{B, C, D\} \to \text{Merge}$) | Modular multi-component feature additions, independent service development |
| **Complex (`complex`)** | Diamond shapes, staggered dependencies, reviews, and integration merges | Typical multi-tier feature development with frontend/backend/DB dependencies |
| **Exploratory (`exploratory`)** | High Fog of War, dynamic node decomposition, discovery of hidden dependencies | Legacy code overhaul, uncharted architectural research, zero-to-one exploration |

#### Lifecycle Phases & Dynamic Effort Tuning
Preset topologies structure nodes into standard development lifecycle phases:
- **Design / Architecture**: Upstream foundation nodes whose effort scales with `--design-effort`. High values represent projects burdened by complex architectural investigations or heavy upfront specifications.
- **Development / Implementation**: Midstream execution nodes whose baseline effort scales with `--dev-effort`. When `--effort-trend` is set to `fatigue`, subsequent task efforts increase progressively (up to 1.5x) to model compounding technical debt, codebase sprawl, and integration drag. Under `accelerating`, task efforts taper downward (down to 0.7x) to reflect team learning effects and component reuse.
- **Review / Gate**: Intermediate and final milestone checkpoints where `--rework-rate` governs rejection likelihood, capturing reviewer strictness and gatekeeping barriers.

#### Scenario Settings
- **Best Scenario**: Low uncertainty (few hidden nodes), minimal rework probability ($< 5\%$), fast review turnarounds.
- **Nominal Scenario**: Standard parameters based on user inputs. Task duration distributions are identical across all scenarios; only discovery, rework and review waiting change.
- **Worst Scenario**: Discovery probability multiplied by 1.5 (capped at 1), elevated rework probability (at least 25%, capped at 100%), prolonged review waiting times.

---

### 3.3. Discrete Event & Resource Simulation Engine

Each simulated iteration executes the generated graph under resource and dependency constraints:
1. **Node Duration Sampling**: Each node's required effort is sampled from an underlying distribution (e.g., lognormal or triangular based on node complexity).
2. **Resource Queuing & Role Allocation**:
   - In default mode (unspecified roles), ready nodes acquire available generic team slots up to `--team-size`, prioritized by critical-path depth.
   - When role-based allocation is active (`--roles` or topology-level `roles`), ready nodes acquire people with the required capabilities.
   - **Joint-Role Tasks**: Tasks requiring multiple roles (e.g., co-allocated design or review tasks `roles: [pm, dev]`) must acquire a distinct person for each role concurrently before execution begins.
   - **Context-Switching Cost**: When a person executes tasks in distinct assigned roles consecutively, an overhead delay (`--switching-cost`) is incurred before work on the new role begins. If roles are unspecified, no switching penalty is evaluated.
3. **Review and Approval Waiting**: A review adds waiting time without occupying a development team slot. A stochastic decision determines whether it passes or triggers rework of an upstream task.
4. **Dynamic Discovery**: Completing an exploratory node triggers a probability check to dynamically inject newly discovered child nodes or dependencies into the active execution graph.
5. **Completion Time Metric**: The total elapsed periods when all sink nodes complete represents the sample duration $T_i$.

---

### 3.4. Output & Structured Markdown Reporting

When `--format markdown` is selected, the tool generates a fully self-contained Markdown report designed for Git version control and PR inclusion:

1. **Executive Summary Table**:
   - P50 (Median), P80, and P90 completion durations in periods, with optional approximate days for Best, Nominal, and Worst scenarios.
   - Identified critical path bottleneck summary (e.g., "Review and approval waiting accounted for 32% of critical path").
   - When the target is strictly less than elapsed duration, include a warning in the target evaluation advising users to check target and progress inputs. Equality does not trigger the warning.
   - When `--target-periods` or `--target-days` is specified: empirical on-time completion probability ($P(\text{Duration} \le \text{target})$) and delay risk ($P(\text{Duration} > \text{target})$) across Best, Nominal, and Worst scenarios.
2. **Mermaid Topology Visualization**:
   - A representative project DAG rendered via Mermaid `flowchart LR` / `flowchart TD`.
   - Node styling highlighting the critical path (`style NodeX stroke:#e74c3c,stroke-width:3px`) and review and approval bottlenecks.
3. **Empirical Distribution Representation**:
   - Percentile tables, a plain-language explanation of the Nominal P50, P80 and P90, and a distribution chart of the simulated empirical distributions. Explain that results depend on assumptions and do not guarantee actual completion times.
   - When target evaluation is specified, Matplotlib outputs (HTML reports and `--format png`) display a distinct vertical reference line for the target duration. In Mermaid `xychart-beta` charts, vertical target lines are deferred due to Mermaid syntax limitations, relying on the executive summary table.
4. **Actionable Recommendations**:
   - Staffing sensitivity assessment (e.g., "Increasing team size from 2 to 4 yields only a 6% P80 reduction due to linear review dependencies").

---

## 4. Technical Architecture

### 4.1. Module Structure

The implementation resides in `src/spite/simulation/`: `engine.py` generates preset skeletons and simulates execution, `topology.py` validates YAML and generates drafts, and `cli.py` runs scenarios and renders reports.

### 4.2. Performance Requirements
- Running 2,000 iterations across 3 scenarios (6,000 graph executions of ~20–50 nodes) MUST complete within 5 seconds on standard developer hardware.
- Memory allocation must remain minimal without caching unnecessary intermediate execution states across iterations.

---

## 5. Non-Goals & Phased Roadmap

### Phase 1: MVP (Target of this PRD)
- Core graph generation with 4 preset patterns (`linear`, `parallel`, `complex`, `exploratory`).
- Discrete resource simulation with team size limits and rework loops.
- Structured Markdown reporting with Mermaid diagrams and percentile tables.
- CLI command `spite simulate`.

### Phase 2: In-flight Calibration & History (Future)
- Re-forecasting with actual task identities, dependencies, and work-in-progress state.
- Historical accuracy retrospectives across saved forecasts.

### Phase 3: External Integration (Future)
- Ingesting GitHub / GitLab issue graphs or PR reviews to calibrate initial pattern parameters.

## User-supplied topology

`spite simulate --topology FILE` reads YAML with optional top-level `people` list or `roles` mapping (e.g., `{pm: 1, dev: 2, qa: 1}`), `elapsed_periods` (non-negative number, default 0), and `tasks` (list). Each task has a unique string `id`, string `name`, `kind` (`task`, `gate`, `exploratory`), `status` (`pending`, `completed`), optional `roles` (list of role strings, e.g. `[dev]` or `[pm, dev]`), optional `effort` (finite positive number, default 1.0; forbidden on gates), optional `rework_probability` (finite number in `[0.0, 1.0]`; valid only on gates), optional `rework_target` (upstream non-gate task ID; valid only on gates), and `depends_on` (list of IDs). Each person has a unique `id` and a non-empty `roles` list; role names are user-defined capabilities. If task `roles` are omitted, the task consumes any one available person without changing their last role. Gates accept omitted, null, or empty roles; they cannot require roles or specify `effort`. A joint task requires a distinct person per role; a multi-role person fills only one role per task. The first assigned role has no switching cost; a joint task adds the maximum switching cost of its assigned people. Discovered and rework tasks inherit the originating task roles. Exploratory tasks may specify `discovery_effort` (finite positive number, default 1.0) for discovered work. Gates may specify `rework_fraction` (finite fraction from 0 to 1, default 1.0), multiplying the target effort for each rework attempt. Task durations scale proportionally with `effort`, which widens duration dispersion for larger tasks. When a gate specifies `rework_probability`, that value overrides the scenario-wide rework setting for rejection checks at that gate. An impossible assignment or invalid property is rejected. If top-level `roles` are defined in YAML and `--roles` is also supplied via CLI, CLI arguments take precedence. Dependencies must exist and form a DAG. Completed tasks may depend only on completed tasks. Enter in-progress work as pending remaining work. Completed tasks satisfy dependencies without simulation. Reports show remaining and total forecasts, adding elapsed periods to the latter.

Exploratory tasks use existing scenario discovery probabilities; discovered work blocks immediate successors. Duration, review and rework use existing settings unless overridden by task `effort` or gate `rework_probability`. Invalid YAML topology inputs are rejected with a message identifying the file. With `--topology`, `--pattern` and `--scale` are ignored with a warning; `--continue-from` remains incompatible.

`spite simulate --template` prints an editable example. Add `--template-resources people` for a multi-role people example or `--template-resources roles` for dedicated role counts. `spite simulate --from-git BASE` prints a draft containing one completed task per non-merge commit in `BASE..HEAD`, without inferred dependencies or elapsed time. Redirect output to a file and edit it, adding remaining and exploratory work. Uncommitted and future work are absent from history.

## Model limitations and calibration

By default task durations are independently sampled from a bounded triangular distribution; the optional experimental complexity factor introduces correlated variation. Structural discovery and rework add variability, but the resulting tail is not calibrated against historical outcomes. Different tasks can share real-world risks that this model omits. `predict` and `simulate` use different assumptions, so their percentile ratios are not directly interchangeable.

Investigate project-wide correlated factors using historical projects or documented expert assumptions. Compare observed completion outcomes with forecast percentiles using out-of-sample evaluation; examine sensitivity to the factor distribution, scenario assumptions, discovery and rework before selecting defaults. Avoid counting the same risk twice. No new factor or calibrated accuracy is claimed until supported by evidence.

Staffing sensitivity pairs nominal trials with doubled-team trials using common random values keyed by logical task, discovery and review attempt. Scheduling can still change outcomes; small estimated differences can be sampling noise.

## Experimental project-wide complexity risk

`--complexity-risk` accepts `off` (default), `low`, `medium` or `high`. Each trial draws one factor from a triangular distribution with minimum and mode 1 and maximum 1.25, 1.5 or 2 respectively. Multiply all development task durations, including discovered work and rework, and the scenario discovery probability by this factor; cap the probability at 1. Review waiting and rejection probability are unchanged. Known YAML tasks and preset skeletons are not multiplied. The same factor applies to paired staffing trials.

These ranges are illustrative assumptions, not calibrated probabilities. The factors only increase duration and discovery relative to the base assumptions; they can overlap with other risk settings. Reports disclose the selected level and ranges. The value is saved and inherited on synthetic continuation, and can be overridden with `off`.

## Experimental preset topology variation

`--topology-variation random` varies preset skeletons per trial; `off` is the default. Linear and parallel retain their fixed chain and fan-out structures. Complex and exploratory select one to three distinct predecessors from up to the three immediately preceding nodes; the integration review depends on all terminal nodes. Node counts and kinds remain fixed. The nominal and doubled-staffing trials share the same skeleton. The seed controls reproducibility. This heuristic is experimental and not calibrated to observed projects. YAML input ignores this option with a warning. Saved runs inherit the setting on synthetic continuation and `off` overrides it.

### People example

```yaml
people:
  - id: alice
    roles: [biz-design, dev-design]
  - id: bob
    roles: [dev-design, dev-build]
tasks:
  - id: design
    name: Joint design
    kind: task
    status: pending
    roles: [biz-design, dev-design]
    depends_on: []
```

A `roles: {pm: 1, dev: 1}` mapping instead defines two dedicated people. `people` and `roles` cannot both appear in YAML. Staffing sensitivity duplicates the defined people with their capabilities. Atomic allocation does not guarantee fairness.

### Review work and rework target

Represent review work that occupies a person as a `task` with roles, followed by a resource-free `gate` for waiting and rejection. A gate may specify `rework_target: build`, referencing an upstream `task` or `exploratory` ID, including a completed task. On rejection, the simulator repeats that task's work with its roles and then retries the gate. Intermediate tasks, including review work, are not repeated. Without `rework_target`, the existing automatic selection remains unchanged. Gates reject non-empty roles; omitted, null and empty roles are accepted.
