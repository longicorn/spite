"""Resource-constrained discrete-event project simulation."""
from dataclasses import dataclass
import heapq


@dataclass(frozen=True)
class Node:
    name: str
    kind: str
    deps: tuple[int, ...]
    effort: float = 1.0


@dataclass
class Result:
    duration: float
    nodes: list[Node]
    critical_path: list[int]
    gate_time: float
    resource_edges: list[tuple[int, int]]


def generate(pattern, scale):
    n = {'small': 8, 'medium': 20, 'large': 40}[scale]
    nodes = [Node('Start', 'task', ())]
    for i in range(1, n):
        if pattern == 'linear':
            deps = (i - 1,)
        elif pattern == 'parallel':
            deps = (0,)
        else:
            deps = (max(0, i - 3),) if i % 4 else tuple(range(max(0, i - 3), i))
        kind = 'gate' if i % 7 == 0 else 'exploratory' if pattern == 'exploratory' or i % 5 == 0 else 'task'
        label = 'Review' if kind == 'gate' else kind.title()
        nodes.append(Node(f'{label} {i}', kind, deps))
    nodes.append(Node('Integration review', 'gate', tuple(range(max(0, n - 3), n)) if pattern != 'parallel' else tuple(range(1, n))))
    return nodes


def simulate(nodes, team_size, discovery, rework, gate_factor, rng, task_periods=1.0):
    """Simulate a DAG and retain an execution graph including resource contention."""
    nodes = list(nodes)
    original = list(nodes)
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
    now = 0.0
    attempts = [0] * len(nodes)
    prerequisites = [[] for _ in nodes]
    execution = []
    ends = []
    starts = []
    resource_edges = []

    def insert(node, successors, rank, deps):
        i = len(nodes)
        nodes.append(node)
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
            if node.kind != 'gate' and (not slots or slots[0][0] > now):
                deferred.append((priority, i))
                continue
            deps = list(prerequisites[i])
            slot = None
            if node.kind == 'gate':
                duration = rng.triangular(.25, 2, .7) * gate_factor
            else:
                available_at, slot, previous = heapq.heappop(slots)
                duration = rng.triangular(.5, 2, 1) * node.effort * task_periods
                dependency_ready = max((ends[d] for d in deps), default=0)
                if previous is not None and available_at > dependency_ready:
                    deps.append(previous)
                    resource_edges.append((previous, len(execution)))
            execution_id = len(execution)
            execution.append(Node(node.name, node.kind, tuple(dict.fromkeys(deps)), node.effort))
            starts.append(now)
            ends.append(now + duration)
            heapq.heappush(events, (now + duration, execution_id, i, slot))
        for item in deferred:
            heapq.heappush(ready, item)
        if not events:
            raise ValueError('Graph cannot make progress')
        now, execution_id, i, slot = heapq.heappop(events)
        if slot is not None:
            heapq.heappush(slots, (now, slot, execution_id))
        if nodes[i].kind == 'gate' and attempts[i] < 10 and rng.random() < rework:
            attempts[i] += 1
            # Re-execute the latest engineering prerequisite, preserving its effort.
            candidates = [d for d in original[i].deps if original[d].kind != 'gate'] if i < len(original) else []
            if not candidates:
                candidates = [j for j in range(min(i, len(original))) if original[j].kind != 'gate']
            target = max(candidates, key=lambda d: ranks[d]) if candidates else None
            source = original[target] if target is not None else Node('Work', 'task', ())
            insert(Node(f'{source.name} (rework {attempts[i]})', 'task', (), source.effort), [i], ranks[i] + 1, [execution_id])
            prerequisites[i] = []
            continue
        if nodes[i].kind == 'exploratory' and rng.random() < discovery:
            insert(Node(f'Discovery {i}', 'task', ()), list(children[i]), ranks[i], [execution_id])
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
