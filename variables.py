"""
variables.py -- problem data, binary variable registry, linear expressions.

Energy is measured in integer "units" (e.g. 1 unit = 10 kWh) so that every
inequality has integer coefficients. That lets us encode slack variables
exactly, which is what makes the QUBO <-> constrained-problem equivalence
provable by brute force.

Decision variables (one pair per EV v and time slot t where the EV is parked):
    c_{v}_{t} = 1  -> EV v charges in slot t   (draws p_charge units from grid)
    d_{v}_{t} = 1  -> EV v discharges (V2G)    (feeds p_discharge units back)
No variable exists while an EV is on a trip (it is fixed to 0 implicitly).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


# --------------------------------------------------------------------------
# Problem data
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class EV:
    id: int
    depot: int
    soc0: int        # initial state of charge (units)
    soc_min: int     # battery lower bound (units)
    soc_max: int     # battery upper bound (units)
    soc_target: int  # required SOC at end of horizon (units)


@dataclass(frozen=True)
class Depot:
    id: int
    n_chargers: int  # max simultaneous charge/discharge sessions per slot


@dataclass(frozen=True)
class Trip:
    ev: int
    start: int       # first slot on the road
    end: int         # first slot back at depot (EV away during [start, end))
    energy: int      # units consumed by the trip (booked in slot `start`)


@dataclass
class Instance:
    T: int
    evs: List[EV]
    depots: List[Depot]
    trips: List[Trip]
    price: List[float]            # grid buy price per unit, per slot
    feedin: List[float]           # V2G sell price per unit, per slot
    base_load: List[int]          # non-EV load on the transformer (units/slot)
    transformer_cap: List[int]    # transformer limit (units/slot)
    p_charge: int = 1             # units per charging slot
    p_discharge: int = 1          # units per discharging slot
    deg_cost: float = 0.0         # battery degradation cost per discharged unit
    w_peak: float = 0.0           # weight of the quadratic peak-shaving term

    def on_trip(self, v: int, t: int) -> bool:
        return any(tr.ev == v and tr.start <= t < tr.end for tr in self.trips)

    def trip_energy(self, v: int, t: int) -> int:
        return sum(tr.energy for tr in self.trips if tr.ev == v and tr.start == t)


# --------------------------------------------------------------------------
# Variable registry
# --------------------------------------------------------------------------
class VarIndex:
    """name <-> integer index. Decision variables first, slacks appended later."""

    def __init__(self) -> None:
        self.names: List[str] = []
        self._idx: Dict[str, int] = {}
        self.n_decision: Optional[int] = None

    def add(self, name: str) -> int:
        if name in self._idx:
            raise ValueError(f"duplicate variable {name}")
        self._idx[name] = len(self.names)
        self.names.append(name)
        return self._idx[name]

    def get(self, name: str) -> Optional[int]:
        return self._idx.get(name)

    def __len__(self) -> int:
        return len(self.names)

    def freeze_decision(self) -> None:
        self.n_decision = len(self.names)


def build_variables(inst: Instance) -> VarIndex:
    vi = VarIndex()
    for ev in inst.evs:
        for t in range(inst.T):
            if not inst.on_trip(ev.id, t):
                vi.add(f"c_{ev.id}_{t}")
                vi.add(f"d_{ev.id}_{t}")
    vi.freeze_decision()
    return vi


# --------------------------------------------------------------------------
# Linear expressions over binary variables:  const + sum_i coeff_i * x_i
# --------------------------------------------------------------------------
class LinExpr:
    def __init__(self, coeffs: Optional[Dict[int, float]] = None, const: float = 0):
        self.coeffs: Dict[int, float] = dict(coeffs or {})
        self.const = const

    def add(self, var: Optional[int], coef: float) -> "LinExpr":
        if var is not None:
            self.coeffs[var] = self.coeffs.get(var, 0) + coef
        return self

    def value(self, x) -> float:
        return self.const + sum(a * x[i] for i, a in self.coeffs.items())

    def bounds(self):
        lo = self.const + sum(min(0, a) for a in self.coeffs.values())
        hi = self.const + sum(max(0, a) for a in self.coeffs.values())
        return lo, hi


def soc_expr(inst: Instance, vi: VarIndex, v: int, t: int) -> LinExpr:
    """SOC of EV v at the END of slot t, as a linear function of the binaries.

    SOC_{v,t} = soc0 + sum_{tau<=t} ( p_c*c_{v,tau} - p_d*d_{v,tau} - trip_energy_{v,tau} )
    """
    ev = inst.evs[v]
    e = LinExpr(const=ev.soc0)
    for tau in range(t + 1):
        e.const -= inst.trip_energy(v, tau)
        e.add(vi.get(f"c_{v}_{tau}"), +inst.p_charge)
        e.add(vi.get(f"d_{v}_{tau}"), -inst.p_discharge)
    return e


def grid_load_expr(inst: Instance, vi: VarIndex, t: int) -> LinExpr:
    """Transformer load in slot t = base_load + EV charging - V2G injection."""
    e = LinExpr(const=inst.base_load[t])
    for ev in inst.evs:
        e.add(vi.get(f"c_{ev.id}_{t}"), +inst.p_charge)
        e.add(vi.get(f"d_{ev.id}_{t}"), -inst.p_discharge)
    return e


# --------------------------------------------------------------------------
# Ready-made instances
# --------------------------------------------------------------------------
def make_tiny4() -> Instance:
    """1 EV, 2 slots -> 4 decision bits (16 assignments). V2G in slot 0, recharge in slot 1."""
    return Instance(
        T=2,
        evs=[EV(0, depot=0, soc0=2, soc_min=1, soc_max=4, soc_target=2)],
        depots=[Depot(0, n_chargers=1)],
        trips=[],
        price=[0.30, 0.05],
        feedin=[0.50, 0.10],
        base_load=[3, 3],
        transformer_cap=[5, 5],
        deg_cost=0.02,
        w_peak=0.01,
    )


def make_small() -> Instance:
    """2 EVs, 3 slots, 1 shared charger, 1 trip -> 10 decision bits."""
    return Instance(
        T=3,
        evs=[
            EV(0, depot=0, soc0=3, soc_min=1, soc_max=5, soc_target=2),
            EV(1, depot=0, soc0=1, soc_min=0, soc_max=3, soc_target=3),
        ],
        depots=[Depot(0, n_chargers=1)],
        trips=[Trip(ev=0, start=2, end=3, energy=1)],
        price=[0.30, 0.10, 0.20],
        feedin=[0.45, 0.15, 0.40],
        base_load=[3, 5, 4],
        transformer_cap=[5, 6, 5],
        deg_cost=0.02,
        w_peak=0.02,
    )


INSTANCES = {"tiny4": make_tiny4, "small": make_small}
