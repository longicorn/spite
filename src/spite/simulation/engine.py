"""Resource-constrained discrete-event project simulation."""
from dataclasses import dataclass
import heapq
import hashlib
import random


@dataclass(frozen=True)
class Node:
    name: str
    kind: str
    deps: tuple[int, ...]
    effort: float = 1.0
    roles: tuple[str, ...] = ()
    rework_target: tuple[str, tuple[str, ...]] | None = None
    rework_target_effort: float = 1.0
    rework_probability: float | None = None
    rework_fraction: float = 1.0
    discovery_effort: float = 1.0


@dataclass
class Result:
    duration: float
    nodes: list[Node]
    critical_path: list[int]
    gate_time: float
    resource_edges: list[tuple[int, int]]


def generate(pattern, scale, task_count=None, topology_rng=None, design_effort=1.0, dev_effort=1.0, effort_trend="flat", completed_tasks=0):
    n = {'small': 8, 'medium': 20, 'large': 40}[scale]
    if task_count is not None:
        n = task_count
    if n == 0:
        return []
    offset = completed_tasks / (completed_tasks + n) if completed_tasks else 0
    trend = {'flat': 0, 'fatigue': .5, 'accelerating': -.3}[effort_trend]
    nodes = [Node('Start', 'task', (), dev_effort * (1 + trend * offset) if completed_tasks else design_effort)]
    development_indices = [i for i in range(1, n) if i % 7 != 0]
    for i in range(1, n):
        if pattern == 'linear':
            deps = (i - 1,)
        elif pattern == 'parallel':
            deps = (0,)
        elif topology_rng is not None:
            candidates = list(range(max(0, i - 3), i))
            deps = tuple(sorted(topology_rng.sample(candidates, topology_rng.randint(1, len(candidates)))))
        else:
            deps = (max(0, i - 3),) if i % 4 else tuple(range(max(0, i - 3), i))
        kind = 'gate' if i % 7 == 0 else 'exploratory' if pattern == 'exploratory' or i % 5 == 0 else 'task'
        label = 'Review' if kind == 'gate' else kind.title()
        progress = development_indices.index(i) / (len(development_indices) - 1) if kind != 'gate' and len(development_indices) > 1 else 0
        multiplier = 1 + trend * (offset + (1 - offset) * progress)
        nodes.append(Node(f'{label} {i}', kind, deps, dev_effort * multiplier if kind != 'gate' else 1.0))
    if topology_rng is not None and pattern in ('complex', 'exploratory'):
        used = {dep for node in nodes for dep in node.deps}
        final_deps = tuple(i for i in range(n) if i not in used)
    else:
        final_deps = tuple(range(max(0, n - 3), n)) if pattern != 'parallel' else tuple(range(1, n))
    nodes.append(Node('Integration review', 'gate', final_deps))
    return nodes


class PairedRandom:
    """Reproducible draws addressed by logical event, independent of scheduling order."""
    def __init__(self, seed):
        self.seed = seed

    def source(self, key):
        digest = hashlib.blake2b(repr((self.seed, key)).encode(), digest_size=16).digest()
        return random.Random(int.from_bytes(digest, 'big'))


def simulate(nodes, team_size, discovery, rework, gate_factor, rng, task_periods=1.0, complexity_risk="off", people=None, switching_cost=0):
    """Simulate a DAG and retain an execution graph including resource contention."""
    nodes = list(nodes)
    if not nodes:
        return Result(0.0, [], [], 0.0, [])
    original = list(nodes)
    keys = [("node", i) for i in range(len(nodes))]
    def random_source(key):
        return rng.source(key) if isinstance(rng, PairedRandom) else rng
    if complexity_risk != "off":
        upper = {"low": 1.25, "medium": 1.5, "high": 2.0}[complexity_risk]
        factor = random_source(("complexity",)).triangular(1, upper, 1)
        task_periods *= factor
        discovery = min(1.0, discovery * factor)
    children = [[] for _ in nodes]
    remaining = [len(n.deps) for n in nodes]
    for i, node in enumerate(nodes):
        for d in node.deps:
            children[d].append(i)
    ranks = [0.0] * len(nodes)
    for i in reversed(range(len(nodes))):
        ranks[i] = (nodes[i].effort * task_periods if nodes[i].kind != 'gate' else 1.0) + max((ranks[c] for c in children[i]), default=0)
    ready = [(-ranks[i], i) for i, count in enumerate(remaining) if not count]
    heapq.heapify(ready)
    events = []
    slots = [(0.0, slot, None) for slot in range(team_size)]
    heapq.heapify(slots)
    # Each entry tracks the last assigned role and the most recent execution.
    members = [[ident, set(roles), 0.0, None, None] for ident, roles in (people or [])]
    def assignment(required, available):
        if not required:
            return [(available[0], None)] if available else None
        def match(index, chosen):
            if index == len(required):
                return chosen
            for member in available:
                if member not in [m for m, _ in chosen] and required[index] in members[member][1]:
                    found = match(index + 1, chosen + [(member, required[index])])
                    if found is not None:
                        return found
            return None
        return match(0, [])
    if people is not None:
        for node in nodes:
            if node.kind != 'gate' and assignment(node.roles, list(range(len(members)))) is None:
                raise ValueError(f'No feasible assignment for task {node.name!r}')
            if node.rework_target and assignment(node.rework_target[1], list(range(len(members)))) is None:
                raise ValueError(f'No feasible assignment for rework target {node.rework_target[0]!r}')
    now = 0.0
    attempts = [0] * len(nodes)
    prerequisites = [[] for _ in nodes]
    execution = []
    ends = []
    starts = []
    resource_edges = []

    def insert(node, successors, rank, deps, key):
        i = len(nodes)
        nodes.append(node)
        keys.append(key)
        children.append(successors)
        remaining.append(0)
        ranks.append(rank)
        attempts.append(0)
        prerequisites.append(list(deps))
        for child in successors:
            remaining[child] += 1
        heapq.heappush(ready, (-rank, i))

    while ready or events:
        deferred = []
        while ready:
            priority, i = heapq.heappop(ready)
            node = nodes[i]
            selected = assignment(node.roles, [j for j, m in enumerate(members) if m[2] <= now]) if people is not None and node.kind != 'gate' else None
            if node.kind != 'gate' and ((people is not None and selected is None) or (people is None and (not slots or slots[0][0] > now))):
                deferred.append((priority, i))
                continue
            deps = list(prerequisites[i])
            slot = None
            if node.kind == 'gate':
                duration = random_source((keys[i], "duration", attempts[i])).triangular(.25, 2, .7) * gate_factor
            else:
                if people is None:
                    available_at, slot, previous = heapq.heappop(slots)
                    allocated = [(available_at, previous)]
                    penalty = 0
                else:
                    slot = selected
                    allocated = [(members[j][2], members[j][3]) for j, role in selected]
                    penalty = max((switching_cost if role is not None and members[j][4] is not None and role != members[j][4] else 0 for j, role in selected), default=0)
                duration = random_source((keys[i], "duration", attempts[i])).triangular(.5, 2, 1) * node.effort * task_periods
                duration += penalty
                dependency_ready = max((ends[d] for d in deps), default=0)
                for available_at, previous in allocated:
                    if previous is not None and available_at > dependency_ready:
                        deps.append(previous)
                        resource_edges.append((previous, len(execution)))
            execution_id = len(execution)
            execution.append(Node(node.name, node.kind, tuple(dict.fromkeys(deps)), node.effort))
            starts.append(now)
            ends.append(now + duration)
            if people is not None and slot is not None:
                for j, role in slot:
                    members[j][2] = float("inf")
                    if role is not None:
                        members[j][4] = role
            heapq.heappush(events, (now + duration, execution_id, i, slot))
        for item in deferred:
            heapq.heappush(ready, item)
        if not events:
            raise ValueError('Graph cannot make progress')
        now, execution_id, i, slot = heapq.heappop(events)
        if slot is not None:
            if people is None:
                heapq.heappush(slots, (now, slot, execution_id))
            else:
                for j, role in slot:
                    members[j][2] = now
                    members[j][3] = execution_id
        if nodes[i].kind == 'gate' and attempts[i] < 10 and random_source((keys[i], "rework", attempts[i])).random() < (nodes[i].rework_probability if nodes[i].rework_probability is not None else rework):
            attempts[i] += 1
            # Re-execute the latest engineering prerequisite, preserving its effort.
            candidates = [d for d in original[i].deps if original[d].kind != 'gate'] if i < len(original) else []
            if not candidates:
                candidates = [j for j in range(min(i, len(original))) if original[j].kind != 'gate']
            target = max(candidates, key=lambda d: ranks[d]) if candidates else None
            explicit = original[i].rework_target if i < len(original) else None
            source = Node(explicit[0], 'task', (), effort=original[i].rework_target_effort, roles=explicit[1]) if explicit else original[target] if target is not None else Node('Work', 'task', ())
            insert(Node(f'{source.name} (rework {attempts[i]})', 'task', (), source.effort * nodes[i].rework_fraction, source.roles), [i], ranks[i] + 1, [execution_id], (keys[i], "rework", attempts[i]))
            prerequisites[i] = []
            continue
        if nodes[i].kind == 'exploratory' and random_source((keys[i], "discovery")).random() < discovery:
            insert(Node(f'Discovery {i}', 'task', (), effort=nodes[i].discovery_effort, roles=nodes[i].roles), list(children[i]), ranks[i], [execution_id], (keys[i], "discovery"))
        for child in children[i]:
            prerequisites[child].append(execution_id)
            remaining[child] -= 1
            if remaining[child] == 0:
                heapq.heappush(ready, (-ranks[child], child))
    current = max(range(len(execution)), key=ends.__getitem__)
    path = []
    while True:
        path.append(current)
        deps = execution[current].deps
        if not deps:
            break
        current = max(deps, key=ends.__getitem__)
    path.reverse()
    return Result(now, execution, path, sum(ends[i] - starts[i] for i in path if execution[i].kind == 'gate'), resource_edges)
