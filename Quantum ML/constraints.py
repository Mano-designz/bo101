"""
constraints.py -- hard constraints and their conversion into QUBO penalties.

Constraint list
  1. No simultaneous charge + discharge:  c*d = 0            (native quadratic penalty)
  2. SOC bounds every slot:               soc_min <= SOC_{v,t} <= soc_max
  3. Required SOC at end of horizon:      SOC_{v,T-1} >= soc_target
  4. Depot charger capacity:              sum_{v in depot}(c+d) <= n_chargers
  5. Transformer limit:                   base + p_c*sum(c) - p_d*sum(d) <= cap_t

Inequalities become equalities with binary-encoded slack bits, then squared:
    a.x <= b   ->   lambda * (a.x - b + s)^2 ,  s in [0, smax]
    a.x >= b   ->   lambda * (a.x - b - s)^2
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from variables import Instance, LinExpr, VarIndex, soc_expr, grid_load_expr


class InfeasibleInstance(Exception):
    pass


@dataclass
class LinearConstraint:
    name: str
    expr: LinExpr
    sense: str   # "<=" or ">="
    rhs: float


# --------------------------------------------------------------------------
# Build the constraint list
# --------------------------------------------------------------------------
def _keep(name: str, expr: LinExpr, sense: str, rhs: float):
    """Drop constraints that can never be violated; reject ones that can never hold."""
    lo, hi = expr.bounds()
    if sense == "<=":
        if hi <= rhs:
            return None
        if lo > rhs:
            raise InfeasibleInstance(name)
    else:
        if lo >= rhs:
            return None
        if hi < rhs:
            raise InfeasibleInstance(name)
    return LinearConstraint(name, expr, sense, rhs)


def exclusivity_pairs(inst: Instance, vi: VarIndex) -> List[Tuple[int, int]]:
    pairs = []
    for ev in inst.evs:
        for t in range(inst.T):
            ic, idd = vi.get(f"c_{ev.id}_{t}"), vi.get(f"d_{ev.id}_{t}")
            if ic is not None:
                pairs.append((ic, idd))
    return pairs


def build_constraints(inst: Instance, vi: VarIndex) -> List[LinearConstraint]:
    cons: List[LinearConstraint] = []
    cand = []

    for ev in inst.evs:
        for t in range(inst.T):
            e = soc_expr(inst, vi, ev.id, t)
            cand.append((f"soc_min[{ev.id},{t}]", e, ">=", ev.soc_min))
            cand.append((f"soc_max[{ev.id},{t}]", e, "<=", ev.soc_max))
        cand.append((f"soc_target[{ev.id}]", soc_expr(inst, vi, ev.id, inst.T - 1),
                     ">=", ev.soc_target))

    for dep in inst.depots:
        for t in range(inst.T):
            e = LinExpr()
            for ev in inst.evs:
                if ev.depot == dep.id:
                    e.add(vi.get(f"c_{ev.id}_{t}"), 1)
                    e.add(vi.get(f"d_{ev.id}_{t}"), 1)
            cand.append((f"depot[{dep.id},{t}]", e, "<=", dep.n_chargers))

    for t in range(inst.T):
        cand.append((f"transformer[{t}]", grid_load_expr(inst, vi, t),
                     "<=", inst.transformer_cap[t]))

    for name, e, sense, rhs in cand:
        c = _keep(name, e, sense, rhs)
        if c is not None:
            cons.append(c)
    return cons


# --------------------------------------------------------------------------
# Penalty construction
# --------------------------------------------------------------------------
def slack_weights(smax: int) -> List[int]:
    """Bounded binary encoding: subset sums cover exactly 0..smax."""
    weights, rem, w = [], smax, 1
    while rem > 0:
        take = min(w, rem)
        weights.append(take)
        rem -= take
        w *= 2
    return weights


def add_constraint_penalties(qubo, inst: Instance, vi: VarIndex, lam: float):
    """Add all penalty terms to `qubo`. Appends slack variables to `vi`."""
    # 1. c*d = 0  (exact for binaries)
    for ic, idd in exclusivity_pairs(inst, vi):
        qubo.add_quadratic(ic, idd, lam)

    # 2-5. slack-encoded inequalities
    cons = build_constraints(inst, vi)
    for k, con in enumerate(cons):
        lo, hi = con.expr.bounds()
        smax = (con.rhs - lo) if con.sense == "<=" else (hi - con.rhs)
        if abs(smax - round(smax)) > 1e-9:
            raise ValueError(f"{con.name}: non-integer slack range {smax}; use integer units")
        sign = +1 if con.sense == "<=" else -1
        residual = LinExpr(con.expr.coeffs, con.expr.const - con.rhs)
        for j, w in enumerate(slack_weights(int(round(smax)))):
            s = vi.add(f"s{k}_{j}")
            residual.add(s, sign * w)
        qubo.add_square(residual, lam)
    return cons


# --------------------------------------------------------------------------
# Independent feasibility check (does NOT use the penalty machinery)
# --------------------------------------------------------------------------
def is_feasible_direct(inst: Instance, vi: VarIndex, x) -> bool:
    """Simulate the physical system step by step; x indexed by variable index."""
    def val(name):
        i = vi.get(name)
        return 0 if i is None else x[i]

    soc = {ev.id: ev.soc0 for ev in inst.evs}
    for t in range(inst.T):
        load = inst.base_load[t]
        used = {dep.id: 0 for dep in inst.depots}
        for ev in inst.evs:
            c, d = val(f"c_{ev.id}_{t}"), val(f"d_{ev.id}_{t}")
            if c and d:
                return False
            soc[ev.id] += inst.p_charge * c - inst.p_discharge * d - inst.trip_energy(ev.id, t)
            if not (ev.soc_min <= soc[ev.id] <= ev.soc_max):
                return False
            used[ev.depot] += c + d
            load += inst.p_charge * c - inst.p_discharge * d
        if any(used[dep.id] > dep.n_chargers for dep in inst.depots):
            return False
        if load > inst.transformer_cap[t]:
            return False
    return all(soc[ev.id] >= ev.soc_target for ev in inst.evs)
