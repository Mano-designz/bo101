"""
objective.py -- Fleet cost + V2G cost/revenue + grid peak penalty.

    f(x) =  sum_{v,t} price_t * p_c * c_{v,t}                    (fleet charging cost)
          - sum_{v,t} feedin_t * p_d * d_{v,t}                   (V2G revenue)
          + sum_{v,t} deg * p_d * d_{v,t}                        (battery degradation)
          + w_peak * sum_t ( base_t + p_c*sum_v c - p_d*sum_v d )^2   (peak shaving)

The last term is a quadratic in the binaries, so it goes straight into Q.
"""
from __future__ import annotations

from variables import Instance, VarIndex, grid_load_expr


def add_objective(qubo, inst: Instance, vi: VarIndex) -> None:
    for ev in inst.evs:
        for t in range(inst.T):
            ic, idd = vi.get(f"c_{ev.id}_{t}"), vi.get(f"d_{ev.id}_{t}")
            if ic is None:
                continue
            qubo.add_linear(ic, inst.price[t] * inst.p_charge)
            qubo.add_linear(idd, (-inst.feedin[t] + inst.deg_cost) * inst.p_discharge)

    if inst.w_peak:
        for t in range(inst.T):
            qubo.add_square(grid_load_expr(inst, vi, t), inst.w_peak)


def evaluate_objective(inst: Instance, vi: VarIndex, x) -> float:
    """Direct (loop-based) evaluation of f(x), independent of the QUBO matrix."""
    def val(name):
        i = vi.get(name)
        return 0 if i is None else x[i]

    total = 0.0
    for t in range(inst.T):
        load = inst.base_load[t]
        for ev in inst.evs:
            c, d = val(f"c_{ev.id}_{t}"), val(f"d_{ev.id}_{t}")
            total += inst.price[t] * inst.p_charge * c
            total += (-inst.feedin[t] + inst.deg_cost) * inst.p_discharge * d
            load += inst.p_charge * c - inst.p_discharge * d
        total += inst.w_peak * load ** 2
    return total
