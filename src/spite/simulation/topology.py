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
    if not isinstance(data, dict) or set(data) - {'elapsed_periods', 'tasks', 'roles', 'people'}:
        raise ValueError('Topology must contain only elapsed_periods and tasks')
    elapsed = data.get('elapsed_periods', 0)
    if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('elapsed_periods must be a finite non-negative number')
    tasks = data.get('tasks')
    if not isinstance(tasks, list):
        raise ValueError('tasks must be a list')
    by_id = {}
    for task in tasks:
        if not isinstance(task, dict) or not {'id', 'name', 'kind', 'status', 'depends_on'} <= set(task) or set(task) - {'id', 'name', 'kind', 'status', 'depends_on', 'roles', 'rework_target'}:
            raise ValueError('Each task must contain id, name, kind, status and depends_on')
        ident = task['id']
        if not isinstance(ident, str) or not ident.strip() or ident in by_id:
            raise ValueError('Task IDs must be non-empty and unique strings')
        if not isinstance(task['name'], str) or not task['name'].strip():
            raise ValueError(f'{ident}: name must be a non-empty string')
        if task['kind'] not in ('task', 'gate', 'exploratory') or task['status'] not in ('pending', 'completed'):
            raise ValueError(f'{ident}: invalid kind or status')
        roles = task.get('roles')
        if roles is None:
            roles = []
        if not isinstance(roles, list) or any(not isinstance(r, str) or not r.strip() for r in roles) or len(set(roles)) != len(roles):
            raise ValueError(f'{ident}: roles must be a list of distinct non-empty strings')
        if roles and task['kind'] == 'gate':
            raise ValueError(f'{ident}: gates cannot require roles')
        if 'rework_target' in task and (task['kind'] != 'gate' or not isinstance(task['rework_target'], str) or not task['rework_target'].strip()):
            raise ValueError(f'{ident}: rework_target must be a task ID on a gate')
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
    def ancestors(ident):
        found = set()
        for dep in by_id[ident]['depends_on']:
            found.add(dep)
            found.update(ancestors(dep))
        return found
    for ident, task in by_id.items():
        target = task.get('rework_target')
        if target is not None and (target not in by_id or target not in ancestors(ident) or by_id[target]['kind'] == 'gate'):
            raise ValueError(f'{ident}: rework_target must refer to an upstream task or exploratory node')
    indices, nodes = {}, []
    for ident in ordered:
        task = by_id[ident]
        if task['status'] == 'pending':
            indices[ident] = len(nodes)
            target = by_id.get(task.get('rework_target'))
            rework_target = (target['name'], tuple(target.get('roles') or [])) if target else None
            nodes.append(Node(task['name'], task['kind'], tuple(indices[d] for d in task['depends_on'] if d in indices), roles=tuple(task.get('roles') or []), rework_target=rework_target))
    return nodes, elapsed, sum(t['status'] == 'completed' for t in tasks)


def resources(path):
    data = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    roles, people = data.get('roles'), data.get('people')
    if roles is not None and people is not None:
        raise ValueError('Specify either roles or people, not both')
    if roles is not None:
        if not isinstance(roles, dict) or not roles or any(not isinstance(k, str) or not k.strip() or isinstance(v, bool) or not isinstance(v, int) or v < 1 for k, v in roles.items()):
            raise ValueError('roles must map non-empty role names to positive counts')
        return [(f'{role}:{i}', (role,)) for role, count in roles.items() for i in range(count)]
    if people is None:
        return None
    if not isinstance(people, list) or not people:
        raise ValueError('people must be a non-empty list')
    result = []
    for person in people:
        if not isinstance(person, dict) or set(person) != {'id', 'roles'} or not isinstance(person['id'], str) or not person['id'].strip():
            raise ValueError('Each person requires an id and roles')
        rs = person['roles']
        if not isinstance(rs, list) or not rs or any(not isinstance(r, str) or not r.strip() for r in rs) or len(set(rs)) != len(rs):
            raise ValueError('Person roles must be a non-empty list of distinct names')
        result.append((person['id'], tuple(rs)))
    if len({ident for ident, _ in result}) != len(result):
        raise ValueError('Person IDs must be unique')
    return result


def template(resource_mode=None):
    data = {'elapsed_periods': 0, 'tasks': [
        {'id': 'explore', 'name': 'Explore requirements', 'kind': 'exploratory', 'status': 'pending', 'depends_on': []},
        {'id': 'build', 'name': 'Build', 'kind': 'task', 'status': 'pending', 'depends_on': ['explore']},
        {'id': 'review', 'name': 'Review', 'kind': 'gate', 'status': 'pending', 'depends_on': ['build'], 'rework_target': 'build'},
    ]}
    if resource_mode == 'people':
        data['people'] = [{'id': 'person1', 'roles': ['biz-design', 'dev-design']},
                          {'id': 'person2', 'roles': ['dev-design', 'dev-build']}]
    elif resource_mode == 'roles':
        data['roles'] = {'biz-design': 1, 'dev-design': 1, 'dev-build': 1}
    if resource_mode:
        data['tasks'][0]['roles'] = ['biz-design', 'dev-design']
        data['tasks'][1]['roles'] = ['dev-build']
    return data


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
