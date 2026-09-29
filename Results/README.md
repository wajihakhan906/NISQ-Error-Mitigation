# Results

## Published study
The paper evaluates Dynamical Decoupling, T-REx and Zero-Noise Extrapolation on Trotterized circuits
on **IBM Kyoto** and **IBM Osaka** (127 qubits) and the QASM simulator. See the paper for the hardware results:
*Error Mitigation in the NISQ Era*, Mathematics 12(14), 2235, 2024. DOI: [10.3390/math12142235](https://doi.org/10.3390/math12142235)

## Simulated run in this repository (`fake_osaka_n4.json`)
Produced by `python run_experiments.py` using the **FakeOsaka** calibration snapshot as an Aer noise model:
4 qubits on physical chain [24, 25, 26, 27], 8000 shots, 4-qubit Trotterized transverse-field Ising chain.
Mean magnetization ⟨M<sub>z</sub>⟩ (closer to *Ideal* is better):

| Trotter steps | Depth | Ideal | Raw | DD | Readout mit. | ZNE + readout | Hellinger fidelity raw → mitigated |
|---|---|---|---|---|---|---|---|
| 1 | 26 | 0.921 | 0.861 | 0.861 | 0.875 | **0.918** | 0.977 → 0.982 |
| 2 | 42 | 0.724 | 0.656 | 0.642 | 0.666 | **0.726** | 0.988 → 0.990 |
| 3 | 58 | 0.491 | 0.430 | 0.417 | 0.436 | **0.469** | 0.993 → 0.994 |
| 4 | 74 | 0.284 | 0.240 | 0.230 | 0.243 | **0.275** | 0.985 → 0.987 |
| 5 | 90 | 0.126 | 0.086 | 0.099 | 0.086 | **0.096** | 0.955 → 0.959 |
| 6 | 106 | 0.022 | 0.006 | 0.007 | 0.006 | **0.006** | 0.955 → 0.960 |

GHZ-4 state fidelity: raw **0.935** → readout-mitigated **0.964**.

![Mitigation results](../Figures/mitigation_fake_osaka_n4.png)

Simulated numbers vary slightly between runs (shot noise), and differ from real-hardware numbers in the paper.

> Note: the `FakeKyoto` snapshot bundled with `qiskit-ibm-runtime` reports an error of 1.0 for every ECR gate,
> which makes local Kyoto simulation meaningless; use `fake_osaka` locally, or `--backend ibm_kyoto` on real hardware.
