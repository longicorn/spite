"""YAML topology validation and starting drafts."""
import math
import subprocess
from pathlib import Path

import yaml

from .engine import Node


def load(path):
    try:
        data = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f'Cannot read topology: {exc}') from exc
    if not isinstance(data, dict) or set(data) - {'elapsed_periods', 'tasks'}:
        raise ValueError('Topology must contain only elapsed_periods and tasks')
    elapsed = data.get('elapsed_periods', 0)
    if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('elapsed_periods must be a finite non-negative number')
    tasks = data.get('tasks')
    if not isinstance(tasks, list):
        raise ValueError('tasks must be a list')
    by_id = {}
    for task in tasks:
        if not isinstance(task, dict) or set(task) != {'id', 'name', 'kind', 'status', 'depends_on'}:
            raise ValueError('Each task must contain id, name, kind, status and depends_on')
        ident = task['id']
        if not isinstance(ident, str) or not ident.strip() or ident in by_id:
            raise ValueError('Task IDs must be non-empty and unique strings')
        if not isinstance(task['name'], str) or not task['name'].strip():
            raise ValueError(f'{ident}: name must be a non-empty string')
        if task['kind'] not in ('task', 'gate', 'exploratory') or task['status'] not in ('pending', 'completed'):
            raise ValueError(f'{ident}: invalid kind or status')
        deps = task['depends_on']
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps) or len(set(deps)) != len(deps):
            raise ValueError(f'{ident}: depends_on must be a list of distinct IDs')
        by_id[ident] = task
    for ident, task in by_id.items():
        for dep in task['depends_on']:
            if dep not in by_id:
                raise ValueError(f'{ident}: unknown dependency {dep}')
            if task['status'] == 'completed' and by_id[dep]['status'] != 'completed':
                raise ValueError(f'{ident}: completed task depends on pending task {dep}')
    ordered, visiting, visited = [], set(), set()
    def visit(ident):
        if ident in visiting:
            raise ValueError('Task dependencies contain a cycle')
        if ident in visited:
            return
        visiting.add(ident)
        for dep in by_id[ident]['depends_on']:
            visit(dep)
        visiting.remove(ident)
        visited.add(ident)
        ordered.append(ident)
    for ident in by_id:
        visit(ident)
    indices, nodes = {}, []
    for ident in ordered:
        task = by_id[ident]
        if task['status'] == 'pending':
            indices[ident] = len(nodes)
            nodes.append(Node(task['name'], task['kind'], tuple(indices[d] for d in task['depends_on'] if d in indices)))
    return nodes, elapsed, sum(t['status'] == 'completed' for t in tasks)


def template():
    return {'elapsed_periods': 0, 'tasks': [
        {'id': 'explore', 'name': 'Explore requirements', 'kind': 'exploratory', 'status': 'pending', 'depends_on': []},
        {'id': 'build', 'name': 'Build', 'kind': 'task', 'status': 'pending', 'depends_on': ['explore']},
        {'id': 'review', 'name': 'Review', 'kind': 'gate', 'status': 'pending', 'depends_on': ['build']},
    ]}


def git_draft(base):
    try:
        subprocess.run(['git', 'rev-parse', '--verify', '--end-of-options', base + '^{commit}'], check=True, capture_output=True, text=True)
        result = subprocess.run(['git', 'log', '--reverse', '--no-merges', '--format=%H%x00%s', base + '..HEAD', '--'], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f'Cannot read Git history: {exc}') from exc
    tasks = []
    for line in result.stdout.splitlines():
        commit, subject = line.split('\0', 1)
        tasks.append({'id': commit, 'name': subject or commit, 'kind': 'task', 'status': 'completed', 'depends_on': []})
    return {'tasks': tasks}


def dump(data):
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
