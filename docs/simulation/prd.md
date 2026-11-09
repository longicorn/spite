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

The **Simulation Module** (`/simulation`) introduces a structural simulation engine based on the **Lane-Model** concept. Instead of assuming a fixed graph or an arbitrary parametric distribution, the module generates ensembles of hypothetical project topologies, simulates resource-constrained execution across scenarios, and outputs empirical completion distributions alongside shareable structured Markdown and Mermaid diagrams.

---

## 2. Target Users & Key Use Cases

### Target Users
- **Engineering Managers & Tech Leads**: Who need to explain *why* projects face tail risks, why adding engineers does or does not accelerate delivery, and where critical bottlenecks lie.
- **Agile / Scrum Teams**: Seeking to update forecasts iteratively across sprints by locking in completed actuals and re-simulating remaining uncertainty.
- **Project Stakeholders & Decision Makers**: Who require transparent, verifiable rationale behind Best / Nominal / Worst project timelines.

### Key Use Cases

#### UC-1: Structural Forward Forecasting (Project Inception)
Before project kickoff, users define high-level assumptions (scale, uncertainty, structural pattern, team size). The engine generates thousands of simulated project topologies for Best, Nominal, and Worst scenarios, computing empirical P50, P80, and P90 lead times.

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
- `--pattern` (Enum: `linear`, `parallel`, `complex`, `exploratory`, Default: `complex`): Structural topology template.
- `--scale` (Enum: `small`, `medium`, `large`, Default: `medium`): Base scope indicating approximate expected node volume.
- `--uncertainty` (Enum: `low`, `medium`, `high`, Default: `medium`): Propensity to discover hidden nodes and edges during execution.
- `--rework-rate` (Float: `0.0` to `1.0`, Default: `0.15`): Probability of rework triggered after review decisions.
- `--team-size` (Integer, Default: `2`): Concurrency limit for parallel active tasks.
- `--tasks-per-period` (positive number, default: `1`): Reference task rate per team member. Its reciprocal is the most likely task duration in periods; it does not guarantee completed throughput. Task, discovery, and rework durations use a triangular distribution from 0.5 to 2 times this duration, with its peak at that duration. Review waiting times use a separate distribution.
- `--iterations` (Integer, Default: `2000`): Number of Monte Carlo iterations per scenario.
- `--format` (Enum: `markdown`, `terminal`, `png`, Default: `markdown`): Primary output presentation format.
- `--output` (Path, optional): Root directory for per-run `report.md` and `snapshot.json`; PNG format also saves `chart.png`.
- `--continue-from` (run ID, optional): Load a prior simulation from the output root. Requires cumulative `--elapsed-periods`, `--completed-tasks`, and known `--remaining-tasks`. Remaining tasks form a new synthetic graph; completed dependencies and work in progress are unknown. Settings are inherited unless overridden. Reports compare total P50, P80 and P90 against the prior run and show remaining and total forecasts.

---

### 3.2. Structural Graph Generation Model

Rather than randomizing only duration, the engine generates dynamic project graphs $G \sim P(G \mid X)$ based on structural topology patterns:

| Pattern | Topology Characteristics | Representative Software Scenario |
| :--- | :--- | :--- |
| **Linear (`linear`)** | Strictly sequential chains ($A \to B \to C$) with conditional rework | Deep investigation, sequential refactoring, rigid single-track pipeline |
| **Parallel (`parallel`)** | High branching factor ($A \to \{B, C, D\} \to \text{Merge}$) | Modular multi-component feature additions, independent service development |
| **Complex (`complex`)** | Diamond shapes, staggered dependencies, reviews, and integration merges | Typical multi-tier feature development with frontend/backend/DB dependencies |
| **Exploratory (`exploratory`)** | High Fog of War, dynamic node decomposition, discovery of hidden dependencies | Legacy code overhaul, uncharted architectural research, zero-to-one exploration |

#### Scenario Calibration
- **Best Scenario**: Low uncertainty (few hidden nodes), minimal rework probability ($< 5\%$), fast review turnarounds.
- **Nominal Scenario**: Standard parameters based on user inputs.
- **Worst Scenario**: High uncertainty ($+50\%$ discovered nodes), elevated rework rate ($25-40\%$), prolonged review waiting times.

---

### 3.3. Discrete Event & Resource Simulation Engine

Each simulated iteration executes the generated graph under resource and dependency constraints:
1. **Node Duration Sampling**: Each node's required effort is sampled from an underlying distribution (e.g., lognormal or triangular based on node complexity).
2. **Resource Queuing**: Available team capacity (`--team-size`) is allocated to ready nodes. If ready nodes exceed team size, nodes queue based on critical-path priority.
3. **Review and Approval Waiting**: A review adds waiting time without occupying a development team slot. A stochastic decision determines whether it passes or triggers rework of an upstream task.
4. **Dynamic Discovery**: Completing an exploratory node triggers a probability check to dynamically inject newly discovered child nodes or dependencies into the active execution graph.
5. **Completion Time Metric**: The total elapsed periods when all sink nodes complete represents the sample duration $T_i$.

---

### 3.4. Output & Structured Markdown Reporting

When `--format markdown` is selected, the tool generates a fully self-contained Markdown report designed for Git version control and PR inclusion:

1. **Executive Summary Table**:
   - P50 (Median), P80, and P90 completion durations in periods, with optional approximate days for Best, Nominal, and Worst scenarios.
   - Identified critical path bottleneck summary (e.g., "Review and approval waiting accounted for 32% of critical path").
2. **Mermaid Topology Visualization**:
   - A representative project DAG rendered via Mermaid `flowchart LR` / `flowchart TD`.
   - Node styling highlighting the critical path (`style NodeX stroke:#e74c3c,stroke-width:3px`) and review and approval bottlenecks.
3. **Empirical Distribution Representation**:
   - Percentile tables, a plain-language explanation of the Nominal P50, P80 and P90, and a Mermaid `xychart-beta` chart of the simulated empirical distributions. Explain that results depend on assumptions and do not guarantee actual completion times.
4. **Actionable Recommendations**:
   - Staffing sensitivity assessment (e.g., "Increasing team size from 2 to 4 yields only a 6% P80 reduction due to linear review dependencies").

---

## 4. Technical Architecture

### 4.1. Module Structure
The `/simulation` capability resides in `src/spite/simulation/`:
- `models.py`: Definitions for `Node`, `Edge`, `Gate`, `ProjectGraph`, and `SimulationResult`.
- `generator.py`: Topology generator producing synthetic project graphs according to patterns and scenario configurations.
- `engine.py`: Discrete-event / critical-path simulator handling resource allocation, rework loops, and node discovery.
- `reporters/`:
  - `markdown.py`: Markdown and Mermaid diagram generator.
  - `terminal.py`: Terminal summary and ASCII rendering.
- `cli.py`: Integration with Spite CLI parser.

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

`spite simulate --topology FILE` reads YAML with `elapsed_periods` (non-negative number, default 0) and `tasks` (list). Each task has a unique string `id`, string `name`, `kind` (`task`, `gate`, `exploratory`), `status` (`pending`, `completed`), and `depends_on` (list of IDs). Dependencies must exist and form a DAG. Completed tasks may depend only on completed tasks. Enter in-progress work as pending remaining work. Completed tasks satisfy dependencies without simulation. Reports show remaining and total forecasts, adding elapsed periods to the latter.

Exploratory tasks use existing scenario discovery probabilities; discovered work blocks immediate successors. Duration, review and rework use existing settings. Invalid YAML topology inputs are rejected with a message identifying the file. With `--topology`, `--pattern` and `--scale` are ignored with a warning; `--continue-from` remains incompatible.

`spite simulate --template` prints an editable example. `spite simulate --from-git BASE` prints a draft containing one completed task per non-merge commit in `BASE..HEAD`, without inferred dependencies or elapsed time. Redirect output to a file and edit it, adding remaining and exploratory work. Uncommitted and future work are absent from history.
