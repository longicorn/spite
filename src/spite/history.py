"""Report observable local Git history without inferring task timing."""
import subprocess
from datetime import datetime, timezone
from .storage import load_run, save_run
from .units import positive_float


def configure(subparsers):
    p = subparsers.add_parser('history', help='Report the current branch history since an ancestor')
    p.add_argument('--base', required=True, help='Ancestor commit or tag (excluded from the work-unit count)')
    p.add_argument('--development-start', help='Development start in ISO 8601 with timezone offset')
    p.add_argument('--days-per-period', type=positive_float, help='Optional calendar-day conversion for the observed timestamp span')
    p.add_argument('--forecast-id', help='Saved forecast run ID under --output')
    p.add_argument('--forecast-kind', choices=['simulate', 'predict'], default='simulate')
    p.add_argument('--output', help='Root directory for the report and snapshot')
    return p


def git(*args):
    try:
        result = subprocess.run(['git', *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=False)
    except OSError as exc:
        raise ValueError(f'Could not execute git: {exc}') from exc
    if result.returncode:
        raise ValueError(result.stderr.strip() or f'git {args[0]} failed (exit {result.returncode})')
    return result.stdout.strip()


def run(args, parser):
    if args.forecast_id and (not args.output or args.days_per_period is None):
        parser.error('--forecast-id requires --output and --days-per-period')
    try:
        branch = git('symbolic-ref', '--quiet', '--short', 'HEAD')
        head = git('rev-parse', '--verify', 'HEAD^{commit}')
        base = git('rev-parse', '--verify', '--end-of-options', f'{args.base}^{{commit}}')
        git('merge-base', '--is-ancestor', base, head)
        shallow = git('rev-parse', '--is-shallow-repository') == 'true'
        raw = git('log', '--topo-order', '--reverse', '--format=%H%x00%P%x00%cI', f'{base}..{head}', '--')
        commits = []
        for line in raw.splitlines():
            commit_id, parents, timestamp = line.split('\x00')
            commits.append({'id': commit_id, 'parents': parents.split(), 'committed_at': timestamp})
        forecast = load_run(args.output, args.forecast_id, args.forecast_kind) if args.forecast_id else None
    except (ValueError, OSError) as exc:
        parser.error(f'Cannot read Git history or forecast: {exc}')
    start = None
    if args.development_start:
        try:
            start = datetime.fromisoformat(args.development_start)
            if start.utcoffset() is None:
                raise ValueError('timezone offset required')
            start = start.astimezone(timezone.utc)
        except ValueError as exc:
            parser.error(f'Invalid --development-start: {exc}')
    nodes = {item['id'] for item in commits}
    # Preserve boundary parents: multiple parents outside the selected range are distinct.
    boundary = {parent for item in commits for parent in item['parents'] if parent not in nodes}
    children = {node: 0 for node in nodes | boundary}
    for item in commits:
        for parent in item['parents']:
            children[parent] += 1
    forks = sum(count > 1 for count in children.values())
    merges = sum(len(item['parents']) > 1 for item in commits)
    branched = forks > 0
    shape = 'Parallel paths present' if branched else 'Linear within the observed range'
    if not commits:
        shape = 'No commits in the selected range'
    times = [datetime.fromisoformat(item['committed_at']).astimezone(timezone.utc) for item in commits]
    first, last = (min(times), max(times)) if times else (None, None)
    span = (last - first).total_seconds() / 86400 if times else None
    if start and first and start > first:
        parser.error('--development-start must not be later than the earliest commit timestamp')
    pre_git = (first - start).total_seconds() / 86400 if start and first else None
    work_times = [datetime.fromisoformat(c['committed_at']).astimezone(timezone.utc) for c in commits if len(c['parents']) <= 1]
    merge_times = [datetime.fromisoformat(c['committed_at']).astimezone(timezone.utc) for c in commits if len(c['parents']) > 1]
    last_work = max(work_times) if work_times else None
    later_merges = [t for t in merge_times if last_work and t > last_work]
    last_merge = max(later_merges) if later_merges else None
    release_wait = (last_merge - last_work).total_seconds() / 86400 if last_merge else None
    def display_time(value):
        local = value.astimezone()
        clock = local.strftime('%Y-%m-%d %H:%M:%S')
        if local.microsecond:
            clock += f'.{local.microsecond:06d}'.rstrip('0')
        zone = local.strftime('%Z') or local.strftime('%z')
        return f'{clock}({zone})'

    def duration(days):
        result = f'{days:.2f} calendar days'
        if args.days_per_period is not None:
            result += f' (approximately {days / args.days_per_period:.2f} periods)'
        return result
    observed_periods = span / args.days_per_period if span is not None and args.days_per_period is not None else None
    lines = ['# Local release history', '', f'Branch: `{branch}`; base: `{base}`; HEAD: `{head}`', '',
             f'Observed work units (non-merge commits): {len(commits) - merges}; merge commits: {merges}; history forks: {forks}.',
             f'History structure: **{shape}**.', '',
             'Each non-merge commit is counted as one observed work unit. Merge commits describe history joins and are counted separately. Git ancestry does not establish actual task dependencies or simultaneous work. Squash merges and missing history can hide branches and work units.']
    if shallow:
        lines += ['', '**The repository is shallow; earlier history may be unavailable.**']
    if times:
        lines += ['', '## Observed commit timestamp span', '',
                  f'- Earliest committer timestamp: {display_time(first)}',
                  f'- Latest committer timestamp: {display_time(last)}',
                  f'- Span: {span:.2f} calendar days' + (f' (approximately {observed_periods:.2f} periods at {args.days_per_period:g} days per period)' if observed_periods is not None else ''), '',
                  'This is the elapsed span between commit timestamps, not measured development duration. The first commit may follow the start of work; timestamps can be edited, and inactivity and holidays are included.']
    else:
        lines += ['', 'There are no commit timestamps to compare in the selected range.']
    if pre_git is not None:
        lines += ['', '## Pre-Git period', '', f'- Development start: {display_time(start)}', f'- Earliest commit: {display_time(first)}', f'- Elapsed: {duration(pre_git)}', '', 'This may include planning and development before the first commit.']
    if release_wait is not None:
        lines += ['', '## Release-wait period', '', f'- Last non-merge commit: {display_time(last_work)}', f'- Last subsequent merge: {display_time(last_merge)}', f'- Elapsed: {duration(release_wait)}', '', 'This proxy may include approval, release scheduling, further work, and inactivity; Git does not establish the reason. Timestamps can be altered.']
    if forecast:
        if observed_periods is None:
            parser.error('Cannot compare a forecast: the selected range contains no commits')
        try:
            stats = forecast['summary']['Nominal']['total'] if args.forecast_kind == 'simulate' else forecast['scenarios']['Nominal']['percentiles']
            metrics = {label: float(stats[label]) for label in ('p50', 'p80', 'p90')}
        except (KeyError, TypeError, ValueError) as exc:
            parser.error(f'Forecast snapshot is missing Nominal percentiles: {exc}')
        lines += ['', '## Comparison with saved forecast', '',
                  f'Forecast: `{args.forecast_id}` ({args.forecast_kind}). The observed timestamp span is only a proxy and should not be treated as actual task duration.', '',
                  '| Measure | Periods |', '| --- | ---: |', f'| Observed commit timestamp span | {observed_periods:.2f} |']
        for label, value in metrics.items():
            lines.append(f'| Forecast {label.upper()} | {value:.2f} |')
    if commits:
        lines += ['', '## Observed Git history', '', 'Boundary nodes are parents outside the selected range. Dashed borders identify period nodes; commit borders and arrows are solid. Period nodes group display paths and are not Git commits or evidence of ancestry or actual work order; grouping may obscure individual parent relationships.', '', '```mermaid', 'flowchart LR']
        if pre_git is not None:
            lines.append(f'    PreGit["Pre-Git: {duration(pre_git)}"]')
        if release_wait is not None:
            lines.append(f'    ReleaseWait["Release wait: {duration(release_wait)}"]')
        for node in sorted(boundary):
            label = f'Base {node[:10]}' if node == base else f'Earlier {node[:10]}'
            lines.append(f'    N{node}["{label}"]')
        if pre_git is not None or release_wait is not None:
            lines.append('    classDef period stroke-dasharray: 5 5')
            if pre_git is not None:
                lines.append('    class PreGit period')
            if release_wait is not None:
                lines.append('    class ReleaseWait period')
        edges = set()
        for item, timestamp in zip(commits, times):
            label = ('Merge ' if len(item['parents']) > 1 else 'Commit ') + item['id'][:10]
            lines.append(f'    N{item["id"]}["{label}"]')
            for parent in item['parents']:
                path = [f'N{parent}']
                if pre_git is not None and parent in boundary:
                    path.append('PreGit')
                if release_wait is not None and len(item['parents']) > 1 and timestamp == last_merge:
                    path.append('ReleaseWait')
                path.append(f'N{item["id"]}')
                edges.update(zip(path, path[1:]))
        for source, target in sorted(edges):
            lines.append(f'    {source} --> {target}')
        lines.append('```')
    report = '\n'.join(lines) + '\n'
    if args.output:
        snapshot = {'branch': branch, 'base': base, 'head': head, 'shallow': shallow,
                    'commits': commits, 'work_units': len(commits) - merges, 'merge_commits': merges,
                    'forks': forks, 'classification': shape, 'observed_calendar_days': span,
                    'days_per_period': args.days_per_period, 'observed_periods': observed_periods,
                    'development_start': start.isoformat() if start else None, 'pre_git_calendar_days': pre_git,
                    'release_wait_start': last_work.isoformat() if last_merge else None,
                    'release_wait_end': last_merge.isoformat() if last_merge else None, 'release_wait_calendar_days': release_wait,
                    'forecast_id': args.forecast_id, 'forecast_kind': args.forecast_kind if forecast else None}
        try:
            path, run_id = save_run(args.output, 'history', snapshot, report)
        except (OSError, ValueError) as exc:
            parser.error(f'Cannot save run: {exc}')
        print(f'Run ID: {run_id}\nReport: {path / "report.md"}\nSnapshot: {path / "snapshot.json"}')
    else:
        print(report, end='')
    return 0
