"""Compare raw vs. mitigated results on a noisy IBM backend model or real hardware.

Examples:
    python run_experiments.py                       # FakeOsaka noise model (local)
    python run_experiments.py --backend ibm_kyoto   # real device (needs IBM Quantum account)
"""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from qiskit import transpile
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator

from circuits import ghz, trotter_ising
from layout import best_chain
from mitigation import (add_dynamical_decoupling, assignment_matrix, calibration_circuits, fold_global,
                        hellinger_fidelity_dict, mean_magnetization, mitigate_counts, richardson_extrapolate)


def get_backend(name):
    if name.startswith("fake_"):
        from qiskit_ibm_runtime import fake_provider

        cls = getattr(fake_provider, "Fake" + name[5:].capitalize())
        device = cls()
        return AerSimulator.from_backend(device), device
    from qiskit_ibm_runtime import QiskitRuntimeService

    device = QiskitRuntimeService().backend(name)
    return device, device


def run(backend, circuits, shots):
    if hasattr(backend, "options") and isinstance(backend, AerSimulator):
        job = backend.run(circuits, shots=shots)
        return [job.result().get_counts(i) for i in range(len(circuits))]
    from qiskit_ibm_runtime import SamplerV2

    result = SamplerV2(mode=backend).run(circuits, shots=shots).result()
    return [r.data.meas.get_counts() for r in result]


def ideal_probs(circuit):
    return Statevector(circuit.remove_final_measurements(inplace=False)).probabilities_dict()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="fake_osaka")
    ap.add_argument("--qubits", type=int, default=4)
    ap.add_argument("--max-steps", type=int, default=6)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--layout", type=int, nargs="*", default=None, help="physical qubits, e.g. 0 1 2 3 (default: best-calibrated chain)")
    ap.add_argument("--out", default="../Results")
    args = ap.parse_args()

    backend, device = get_backend(args.backend)
    n = args.qubits
    layout = args.layout or best_chain(device, n)
    print("physical qubits:", layout)
    tp = lambda c: transpile(c, device, initial_layout=layout, optimization_level=1, seed_transpiler=7)

    # 1. readout calibration
    cal = calibration_circuits(n)
    cal_counts = dict(zip([l for l, _ in cal], run(backend, [tp(c) for _, c in cal], args.shots)))
    A = assignment_matrix(cal_counts, n)

    rows = []
    for steps in range(1, args.max_steps + 1):
        qc = trotter_ising(n, steps)
        ideal = ideal_probs(qc)
        base = tp(qc)
        folded = [tp(fold_global(qc, s)) for s in (1, 3, 5)]
        circuits = [base, add_dynamical_decoupling(base, device)] + folded
        raw, dd, *zne_counts = run(backend, circuits, args.shots)

        mem = mitigate_counts(raw, A)
        zne_mem = [mean_magnetization(mitigate_counts(c, A)) for c in zne_counts]
        rows.append({
            "steps": steps,
            "depth": base.depth(),
            "ideal_mz": mean_magnetization(ideal),
            "raw_mz": mean_magnetization(raw),
            "dd_mz": mean_magnetization(dd),
            "mem_mz": mean_magnetization(mem),
            "zne_mem_mz": richardson_extrapolate([1, 3, 5], zne_mem),
            "raw_fidelity": hellinger_fidelity_dict(ideal, raw),
            "mem_fidelity": hellinger_fidelity_dict(ideal, mem),
        })
        print({k: round(v, 4) if isinstance(v, float) else v for k, v in rows[-1].items()})

    # GHZ: readout mitigation on a state with a known answer
    g = ghz(n)
    g_raw = run(backend, [tp(g)], args.shots)[0]
    g_mem = mitigate_counts(g_raw, A)
    ghz_summary = {"raw_fidelity": hellinger_fidelity_dict(ideal_probs(g), g_raw),
                   "mem_fidelity": hellinger_fidelity_dict(ideal_probs(g), g_mem)}
    print("GHZ:", ghz_summary)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{args.backend}_n{n}"
    (out / f"{tag}.json").write_text(json.dumps({"backend": args.backend, "qubits": n, "layout": layout,
                                                  "shots": args.shots, "trotter": rows, "ghz": ghz_summary}, indent=2))

    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4))
    s = [r["steps"] for r in rows]
    for key, lbl, st in [("ideal_mz", "Ideal", "k-"), ("raw_mz", "Raw", "o--"), ("dd_mz", "DD", "^--"),
                         ("mem_mz", "Readout mitigation", "s-"), ("zne_mem_mz", "ZNE + readout", "d-")]:
        a.plot(s, [r[key] for r in rows], st, label=lbl)
    a.set_xlabel("Trotter steps"); a.set_ylabel(r"$\langle M_z \rangle$"); a.set_title("Magnetization"); a.legend(fontsize=8)
    b.plot(s, [r["raw_fidelity"] for r in rows], "o--", label="Raw")
    b.plot(s, [r["mem_fidelity"] for r in rows], "s-", label="Readout mitigation")
    b.set_xlabel("Trotter steps"); b.set_ylabel("Hellinger fidelity"); b.set_title("Distribution fidelity"); b.legend(fontsize=8)
    fig.suptitle(f"{n}-qubit Trotterized Ising chain on {args.backend}")
    fig.tight_layout()
    fig.savefig(Path("../Figures") / f"mitigation_{tag}.png", dpi=200)

    fig, ax = plt.subplots(figsize=(5, 4.5))
    im = ax.imshow(A, cmap="viridis", vmin=0, vmax=1)
    ax.set_title(f"Readout assignment matrix ({args.backend})"); ax.set_xlabel("prepared state"); ax.set_ylabel("measured state")
    fig.colorbar(im); fig.tight_layout()
    fig.savefig(Path("../Figures") / f"assignment_matrix_{tag}.png", dpi=200)


if __name__ == "__main__":
    main()
