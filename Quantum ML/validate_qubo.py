"""
validate_qubo.py -- brute-force proof that the QUBO has the same optimum as the
original constrained problem.

Usage:  python validate_qubo.py [tiny4|small] [--qiskit]

Checks
  A. True optimum: enumerate all 2^n_decision assignments, keep those that pass the
     independent physical feasibility check, evaluate f(x) directly.
  B. QUBO optimum: enumerate all 2^(n_decision + n_slack) assignments of E(x)=x^T Q x + offset.
  C. For every decision assignment, min over slack bits of E must equal f(x) if feasible,
     and be strictly greater than the true optimum if infeasible.
  D. Global QUBO argmin (projected to decision bits) must be a true optimum.
"""
from __future__ import annotations

import sys

import numpy as np

from variables import INSTANCES
from constraints import is_feasible_direct
from objective import evaluate_objective
from qubo import build_qubo, to_qiskit

TOL = 1e-9


def bits(k: int, n: int):
    return [(k >> i) & 1 for i in range(n)]


def all_energies(Q: np.ndarray, offset: float, chunk: int = 1 << 16) -> np.ndarray:
    n = Q.shape[0]
    total = 1 << n
    out = np.empty(total)
    shifts = np.arange(n)
    for start in range(0, total, chunk):
        idx = np.arange(start, min(start + chunk, total))
        X = ((idx[:, None] >> shifts) & 1).astype(float)
        out[start:start + len(idx)] = ((X @ Q) * X).sum(axis=1) + offset
    return out


def main() -> int:
    name = next((a for a in sys.argv[1:] if not a.startswith("--")), "tiny4")
    inst = INSTANCES[name]()
    m = build_qubo(inst)
    nd, n = m.n_decision, m.n
    print(f"instance={name}  decision bits={nd}  slack bits={n - nd}  total={n}  "
          f"penalty lambda={m.penalty:.4f}")
    print(f"constraints kept: {len(m.constraints)}  -> {[c.name for c in m.constraints]}")
    print(f"brute force: 2^{nd} = {1 << nd} decision assignments, 2^{n} = {1 << n} QUBO states\n")

    # ---- A. true constrained optimum --------------------------------------
    true_val = {}
    for k in range(1 << nd):
        x = bits(k, nd)
        if is_feasible_direct(inst, m.vi, x):
            true_val[k] = evaluate_objective(inst, m.vi, x)
    if not true_val:
        print("No feasible assignment exists for this instance.")
        return 1
    opt = min(true_val.values())
    opt_set = {k for k, v in true_val.items() if abs(v - opt) < TOL}
    print(f"[A] feasible assignments: {len(true_val)} / {1 << nd}")
    print(f"    true optimum f* = {opt:.6f} at decision bits "
          f"{[m.vi.names[i] for i in range(nd) if bits(next(iter(opt_set)), nd)[i]]}")

    # ---- B. QUBO brute force ----------------------------------------------
    E = all_energies(m.Q, m.offset)
    best = int(np.argmin(E))
    best_dec = best & ((1 << nd) - 1)
    print(f"[B] QUBO minimum E* = {E[best]:.6f} at decision bits "
          f"{[m.vi.names[i] for i in range(nd) if bits(best_dec, nd)[i]]}")

    # sanity: matrix energy equals dictionary-form energy on random states
    rng = np.random.default_rng(0)
    for k in rng.integers(0, 1 << n, size=min(50, 1 << n)):
        x = bits(int(k), n)
        assert abs(m.energy(x) - E[int(k)]) < 1e-7

    # ---- C. per-decision check --------------------------------------------
    per_dec = E.reshape(1 << (n - nd), 1 << nd).min(axis=0)   # slack bits are the high bits
    bad = 0
    for k in range(1 << nd):
        if k in true_val:
            if abs(per_dec[k] - true_val[k]) > 1e-7:
                bad += 1
        else:
            if per_dec[k] <= opt + 1e-7:
                bad += 1
    print(f"[C] decision assignments whose QUBO value is wrong: {bad}")

    # ---- D. verdict ---------------------------------------------------------
    ok = (abs(E[best] - opt) < 1e-7) and (best_dec in opt_set) and bad == 0
    print(f"[D] QUBO argmin is a true optimum: {best_dec in opt_set};  "
          f"|E* - f*| = {abs(E[best] - opt):.2e}")
    print("\nRESULT:", "PASS - QUBO is equivalent to the constrained problem" if ok else "FAIL")

    if nd <= 4:
        print("\nAll assignments (decision bits -> true f / feasible / min QUBO energy):")
        print("  " + " ".join(m.vi.names[:nd]))
        for k in range(1 << nd):
            f = f"{true_val[k]: .4f}" if k in true_val else "   -   "
            print(f"  {bits(k, nd)}  f={f}  feasible={k in true_val!s:5}  E_min={per_dec[k]: .4f}")

    if "--qiskit" in sys.argv:
        qp = to_qiskit(m)
        print("\nQiskit QuadraticProgram:", qp.get_num_binary_vars(), "binary vars")
        op, off = qp.to_ising()
        print("Ising operator terms:", len(op), " offset:", round(off, 6))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
