# Spite

[日本語版 (Japanese)](README.ja.md)

Spite is an experimental tool for forecasting software development deadlines based on probability distributions.

Conventional deadline forecasting and effort management typically rely on engineer intuition, business-driven targets, or extrapolations from past throughput and cycle time. While the concept that "a software deadline is a probability distribution" is well known, practical methods for applying and updating distributions throughout a complex development lifecycle remain underexplored.

Spite explores this problem by letting teams set an initial probability distribution from project start, compare Best / Nominal / Worst scenarios, and evaluate actual completion results against initial assumptions.

## Usage

Spite currently models delivery lead time using the lognormal distribution across three scenarios (Best, Nominal, and Worst), supporting both forward-looking prediction and post-completion retrospective evaluation.

Run `--help` to check all available options:

```bash
$ uv run spite predict --help
```

### Forecast Mode (In-progress or upcoming project)

Outputs P50, P80, and P90 completion dates (in working business days) for Best, Nominal, and Worst scenarios. By default, an ASCII chart is rendered in the terminal; pass `--output` or `--show` to render with matplotlib.

```bash
$ uv run spite predict --distribution lognormal --start-date 2024-09-10 --deadline 2024-09-30 --output output.png
```

### Retrospective Mode (Completed project)

Pass `--actual-end-date` to evaluate actual completion duration against the initial Nominal scenario (deviation in business days and percentage, CDF percentile, P90 delta, and tail probability).

```bash
$ uv run spite predict --distribution lognormal --start-date 2024-09-10 --deadline 2024-09-30 --actual-end-date 2024-12-10 --output output.png
```

## Documentation

- [Product Requirements Document (PRD)](docs/prd.md) ([日本語](docs/prd.ja.md))
- [Architecture Decision Record (ADR)](docs/adr.md) ([日本語](docs/adr.ja.md))
