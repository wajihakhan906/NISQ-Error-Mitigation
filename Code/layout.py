"""Pick the best-calibrated linear chain of physical qubits on a device.

Calibration snapshots of large devices usually contain a few broken couplers
(two-qubit error = 1) and qubits with very high readout error; running on them
hides every mitigation effect. We search all simple paths of length n and score
them by summed two-qubit and readout error.
"""
import math


def _two_qubit_errors(target):
    errors = {}
    for name in target.operation_names:
        props = target[name]
        for qargs, p in props.items():
            if qargs is None or len(qargs) != 2 or p is None or p.error is None:
                continue
            key = tuple(sorted(qargs))
            errors[key] = min(errors.get(key, 1.0), p.error)
    return errors


def _readout_errors(target, n_qubits):
    ro = {}
    if "measure" in target.operation_names:
        for qargs, p in target["measure"].items():
            if qargs and p is not None and p.error is not None:
                ro[qargs[0]] = p.error
    return {q: ro.get(q, 0.05) for q in range(n_qubits)}


def best_chain(backend, n):
    target = backend.target
    cx = _two_qubit_errors(target)
    ro = _readout_errors(target, target.num_qubits)
    neighbours = {}
    for a, b in cx:
        if cx[(a, b)] < 0.5:  # skip broken couplers
            neighbours.setdefault(a, []).append(b)
            neighbours.setdefault(b, []).append(a)

    best, best_cost = None, math.inf

    def dfs(path, cost):
        nonlocal best, best_cost
        if cost >= best_cost:
            return
        if len(path) == n:
            best, best_cost = list(path), cost
            return
        for nb in neighbours.get(path[-1], []):
            if nb not in path:
                edge = cx[tuple(sorted((path[-1], nb)))]
                path.append(nb)
                dfs(path, cost + edge + ro[nb])
                path.pop()

    for q in neighbours:
        dfs([q], ro[q])
    if best is None:
        raise RuntimeError(f"no connected chain of {n} usable qubits found")
    return best
