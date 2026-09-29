"""Benchmark circuits: Trotterized transverse-field Ising evolution and GHZ states."""
from qiskit import QuantumCircuit


def trotter_ising(n_qubits=4, steps=3, dt=0.2, J=1.0, h=1.0, measure=True):
    """First-order Trotterization of H = -J sum Z_i Z_{i+1} - h sum X_i on an open chain.

    The ideal evolution is computed exactly by the statevector simulator, so the
    circuit is a controlled test of how noise and mitigation affect depth-growing
    Trotter circuits.
    """
    qc = QuantumCircuit(n_qubits, name=f"ising_n{n_qubits}_s{steps}")
    for _ in range(steps):
        for i in range(n_qubits - 1):
            qc.rzz(-2 * J * dt, i, i + 1)
        for i in range(n_qubits):
            qc.rx(-2 * h * dt, i)
    if measure:
        qc.measure_all()
    return qc


def ghz(n_qubits=4, measure=True):
    qc = QuantumCircuit(n_qubits, name=f"ghz_{n_qubits}")
    qc.h(0)
    for i in range(n_qubits - 1):
        qc.cx(i, i + 1)
    if measure:
        qc.measure_all()
    return qc
