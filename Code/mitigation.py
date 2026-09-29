"""Error-mitigation techniques for NISQ hardware.

* Measurement (readout) error mitigation: build the assignment matrix A from
  calibration circuits, then recover the ideal distribution by constrained
  least squares (A p = p_noisy, p >= 0, sum p = 1).
* Zero-noise extrapolation (ZNE): amplify noise by global unitary folding
  U -> U (U^dag U)^k and extrapolate an observable back to zero noise.
* Dynamical decoupling (DD): insert X-X sequences into idle windows.
"""
from itertools import product

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import XGate
from qiskit.transpiler import PassManager
from scipy.optimize import minimize


# --------------------------------------------------------------------------- #
# Measurement error mitigation
# --------------------------------------------------------------------------- #
def calibration_circuits(n_qubits):
    """One circuit per computational basis state |b>, measured immediately."""
    circuits = []
    for bits in product("01", repeat=n_qubits):
        label = "".join(bits)
        qc = QuantumCircuit(n_qubits, name=f"cal_{label}")
        for q, b in enumerate(reversed(label)):  # Qiskit is little-endian
            if b == "1":
                qc.x(q)
        qc.measure_all()
        circuits.append((label, qc))
    return circuits


def assignment_matrix(cal_counts, n_qubits):
    """A[i, j] = P(measure i | prepared j) from {prepared_label: counts}."""
    dim = 2**n_qubits
    A = np.zeros((dim, dim))
    for prepared, counts in cal_counts.items():
        j = int(prepared, 2)
        shots = sum(counts.values())
        for measured, c in counts.items():
            A[int(measured, 2), j] = c / shots
    return A


def counts_to_vector(counts, n_qubits):
    v = np.zeros(2**n_qubits)
    for k, c in counts.items():
        v[int(k, 2)] = c
    return v / v.sum()


def vector_to_probs(v, n_qubits):
    return {format(i, f"0{n_qubits}b"): float(p) for i, p in enumerate(v) if p > 1e-12}


def mitigate_counts(counts, A, method="least_squares"):
    """Apply readout mitigation. `method`: 'inverse' or 'least_squares'."""
    n = int(np.log2(A.shape[0]))
    p_noisy = counts_to_vector(counts, n)
    if method == "inverse":
        p = np.linalg.pinv(A) @ p_noisy
        p = np.clip(p, 0, None)
        return vector_to_probs(p / p.sum(), n)

    def cost(x):
        return np.sum((p_noisy - A @ x) ** 2)

    x0 = np.clip(np.linalg.pinv(A) @ p_noisy, 0, None)
    x0 = x0 / x0.sum() if x0.sum() > 0 else np.full_like(p_noisy, 1 / len(p_noisy))
    res = minimize(cost, x0, method="SLSQP", bounds=[(0, 1)] * len(x0),
                   constraints={"type": "eq", "fun": lambda x: np.sum(x) - 1}, options={"maxiter": 1000})
    return vector_to_probs(res.x, n)


# --------------------------------------------------------------------------- #
# Zero-noise extrapolation
# --------------------------------------------------------------------------- #
def fold_global(circuit, scale):
    """Unitary folding U (U^dag U)^k; `scale` must be an odd integer (1, 3, 5, ...)."""
    if scale < 1 or scale % 2 == 0:
        raise ValueError("scale must be an odd positive integer")
    body = circuit.remove_final_measurements(inplace=False)
    folded = body.copy()
    for _ in range((scale - 1) // 2):
        folded.compose(body.inverse(), inplace=True)
        folded.compose(body, inplace=True)
    folded.measure_all()
    return folded


def richardson_extrapolate(scales, values):
    """Polynomial fit of degree len(scales)-1 evaluated at zero noise."""
    coeffs = np.polyfit(scales, values, deg=len(scales) - 1)
    return float(np.polyval(coeffs, 0.0))


def linear_extrapolate(scales, values):
    coeffs = np.polyfit(scales, values, deg=1)
    return float(np.polyval(coeffs, 0.0))


# --------------------------------------------------------------------------- #
# Dynamical decoupling
# --------------------------------------------------------------------------- #
def add_dynamical_decoupling(circuit, backend):
    """Schedule the transpiled circuit and pad idle windows with X-X pulses."""
    from qiskit.transpiler.passes import ALAPScheduleAnalysis, PadDynamicalDecoupling

    durations = backend.target.durations()
    pm = PassManager([ALAPScheduleAnalysis(durations), PadDynamicalDecoupling(durations, [XGate(), XGate()])])
    return pm.run(circuit)


# --------------------------------------------------------------------------- #
# Observables
# --------------------------------------------------------------------------- #
def expectation_z_parity(probs):
    """<Z...Z> from a probability (or counts) dictionary."""
    total = sum(probs.values())
    return sum((-1) ** k.count("1") * v for k, v in probs.items()) / total


def mean_magnetization(probs):
    """(1/n) sum_i <Z_i>."""
    total = sum(probs.values())
    n = len(next(iter(probs)))
    return sum(v * sum(1 - 2 * int(b) for b in k) / n for k, v in probs.items()) / total


def hellinger_fidelity_dict(p, q):
    keys = set(p) | set(q)
    sp, sq = sum(p.values()), sum(q.values())
    return float(sum(np.sqrt(p.get(k, 0) / sp * q.get(k, 0) / sq) for k in keys) ** 2)
