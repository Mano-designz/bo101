"""
qubo.py -- assemble  E(x) = x^T Q x + offset  from objective + constraint penalties.

Since x_i^2 = x_i for binaries, linear terms live on the diagonal of Q.
Q is returned upper-triangular (Q[i,j], i<j holds the full pair coefficient).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from variables import Instance, VarIndex, LinExpr, build_variables
from objective import add_objective
from constraints import add_constraint_penalties


class QUBO:
    def __init__(self) -> None:
        self.lin: Dict[int, float] = {}
        self.quad: Dict[Tuple[int, int], float] = {}
        self.offset: float = 0.0

    def add_linear(self, i: int, w: float) -> None:
        self.lin[i] = self.lin.get(i, 0.0) + w

    def add_quadratic(self, i: int, j: int, w: float) -> None:
        if i == j:
            self.add_linear(i, w)
            return
        key = (min(i, j), max(i, j))
        self.quad[key] = self.quad.get(key, 0.0) + w

    def add_square(self, expr: LinExpr, weight: float) -> None:
        """Add weight * (const + sum a_i x_i)^2 using x_i^2 = x_i."""
        items = list(expr.coeffs.items())
        c0 = expr.const
        for i, a in items:
            self.add_linear(i, weight * (a * a + 2 * c0 * a))
        for p in range(len(items)):
            for q in range(p + 1, len(items)):
                (i, a), (j, b) = items[p], items[q]
                self.add_quadratic(i, j, weight * 2 * a * b)
        self.offset += weight * c0 * c0

    def abs_sum(self) -> float:
        return sum(abs(v) for v in self.lin.values()) + sum(abs(v) for v in self.quad.values())

    def to_matrix(self, n: int) -> np.ndarray:
        Q = np.zeros((n, n))
        for i, w in self.lin.items():
            Q[i, i] += w
        for (i, j), w in self.quad.items():
            Q[i, j] += w
        return Q


@dataclass
class QUBOModel:
    inst: Instance
    vi: VarIndex
    qubo: QUBO
    Q: np.ndarray
    offset: float
    penalty: float
    constraints: list

    @property
    def n(self) -> int:
        return len(self.vi)

    @property
    def n_decision(self) -> int:
        return self.vi.n_decision

    def energy(self, x) -> float:
        x = np.asarray(x, dtype=float)
        return float(x @ self.Q @ x + self.offset)


def build_qubo(inst: Instance, penalty: Optional[float] = None) -> QUBOModel:
    """
    penalty=None -> automatic lambda = 1 + sum|objective coefficients|.
    All residuals are integers, so any violation costs >= lambda, which exceeds
    the whole objective range: constrained optimum == QUBO optimum.
    (For QAOA you may later try smaller lambda; re-run validate_qubo.py after.)
    """
    vi = build_variables(inst)
    q = QUBO()
    add_objective(q, inst, vi)
    lam = penalty if penalty is not None else 1.0 + q.abs_sum()
    cons = add_constraint_penalties(q, inst, vi, lam)
    return QUBOModel(inst, vi, q, q.to_matrix(len(vi)), q.offset, lam, cons)


# --------------------------------------------------------------------------
# Qiskit hand-off (requires: pip install qiskit qiskit-optimization)
# --------------------------------------------------------------------------
def to_qiskit(model: QUBOModel):
    """Return a qiskit_optimization.QuadraticProgram (all-binary, minimize)."""
    from qiskit_optimization import QuadraticProgram

    qp = QuadraticProgram("ev_grid_qubo")
    for name in model.vi.names:
        qp.binary_var(name)
    names = model.vi.names
    linear = {names[i]: w for i, w in model.qubo.lin.items()}
    quadratic = {(names[i], names[j]): w for (i, j), w in model.qubo.quad.items()}
    qp.minimize(constant=model.offset, linear=linear, quadratic=quadratic)
    return qp


def to_ising(model: QUBOModel):
    """(SparsePauliOp, offset) ready for QAOA / sampling."""
    return to_qiskit(model).to_ising()
