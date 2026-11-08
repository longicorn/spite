# Spite

[日本語版 (Japanese)](README.ja.md)

Spite is an experimental tool for forecasting software development deadlines based on probability distributions.

Conventional deadline forecasting and effort management typically rely on engineer intuition, business-driven targets, or extrapolations from past throughput and cycle time. While the concept that "a software deadline is a probability distribution" is well known, practical methods for applying and updating distributions throughout a complex development lifecycle remain underexplored.

Spite explores this problem by letting teams set an initial probability distribution from project start, compare Best / Nominal / Worst scenarios, and evaluate actual completion results against initial assumptions.

## Usage

Spite has three commands:

- `predict` forecasts completion duration from a user-supplied nominal period.
- `simulate` forecasts from synthetic task dependencies, resource limits, discovery and rework.
- `history` reports the Git history of the current branch and can compare it with a saved forecast.

A period is an abstract duration chosen by the user, such as one sprint. `--days-per-period` optionally adds approximate days using a simple multiplier. Spite does not calculate forecast completion dates or holidays.

### Predict

`--periods` sets the most likely duration (the mode) of the Nominal scenario, not its median. Use `--actual-periods` for a retrospective.

```bash
uv run spite predict --periods 6 --format markdown --output tmp/spite/
uv run spite predict --periods 6 --actual-periods 8 --days-per-period 5
```

### Simulate

`--tasks-per-period` is a reference rate per team member; its reciprocal is the most likely duration of one task. Actual simulated durations vary, so the rate is not guaranteed throughput. Reviews have separate waiting times.

```bash
uv run spite simulate --tasks-per-period 5 --days-per-period 5 --output tmp/spite/
uv run spite simulate --output tmp/spite/ --continue-from YOUR_RUN_ID --elapsed-periods 2 --completed-tasks 5 --remaining-tasks 8
```

An update generates a new synthetic graph for the known remaining tasks; it does not reconstruct the actual completed dependencies or work in progress.

### History after merging

Run `history` in the repository with the **release destination branch** checked out. The current branch's HEAD is the end of the analysis. `--base` selects the starting commit, which must be an ancestor of HEAD; it does not select a merged feature branch.

For example, after merging several feature branches into `main`, use a tag on `main` from before those merges as the base:

```bash
git switch main
uv run spite history --base v1.0 --days-per-period 5 --output tmp/spite/
```

The range is `base..HEAD`: commits reachable from HEAD but not from the base, including commits from merged branches. The base and its history are excluded. A branch name, tag, or commit ID can be used as the base. If `--base main` points to the current HEAD, the range is empty. If a merged feature branch tip is used as the base, that commit and its ancestors are excluded, so it does not mean “analyze only this merged branch.” Use a previous release tag or a commit ID to keep the starting point stable.

Each non-merge commit is an observed work unit; merges are counted separately. Git ancestry describes visible history, not actual task dependencies or simultaneous work. Squash merges can hide the original branches. The first-to-last committer timestamp span includes inactivity and is not measured development time. Add `--forecast-id YOUR_RUN_ID` with the same output root and `--days-per-period` to compare this span as a proxy with a saved simulation forecast; use `--forecast-kind predict` for a Predict forecast.

### Saved runs

`--output` is a root directory. Each command saves `report.md` and `snapshot.json` under `<root>/<command>/<run-id>/`; some formats also save `chart.png`. Without `--output`, reports are printed in the terminal. Run `uv run spite --help` or a subcommand with `--help` for all options.

## Documentation

- [Product PRD](docs/prd.md) ([日本語](docs/prd.ja.md)) and [ADR](docs/adr.md) ([日本語](docs/adr.ja.md))
- [Predict PRD](docs/predict/prd.md) ([日本語](docs/predict/prd.ja.md)) and [ADR](docs/predict/adr.md) ([日本語](docs/predict/adr.ja.md))
- [Simulation PRD](docs/simulation/prd.md) ([日本語](docs/simulation/prd.ja.md)) and [ADR](docs/simulation/adr.md) ([日本語](docs/simulation/adr.ja.md))
- [History PRD](docs/history/prd.md) ([日本語](docs/history/prd.ja.md))
