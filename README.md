# 
  Readme file for The repo and https://sgiev.lovable.app/


⚡ Quantum Optimization for Electric Vehicle Grid Integration

### A QUBO-Based Optimization Framework for EV Charging, Fleet Scheduling, Transformer Load Balancing & Vehicle-to-Grid

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Qiskit](https://img.shields.io/badge/Qiskit-Quantum%20Computing-purple.svg)](https://www.ibm.com/quantum/qiskit)
[![QUBO](https://img.shields.io/badge/Optimization-QUBO-orange.svg)](https://en.wikipedia.org/wiki/Quadratic_unconstrained_binary_optimization)
[![OR--Tools](https://img.shields.io/badge/Classical-OR--Tools-green.svg)](https://developers.google.com/optimization)
[![D-Wave Dimod](https://img.shields.io/badge/Solver-Dimod%20%2F%20Simulated%20Annealing-red.svg)](https://docs.ocean.dwavesys.com/en/stable/docs_dimod/)
[![License](https://img.shields.io/badge/License-Research-lightgrey.svg)]()

---

## 🌍 Overview

The rapid adoption of electric vehicles is creating a new infrastructure challenge for modern power grids.

Large EV fleets do not simply increase electricity consumption. Their charging schedules interact with:

* ⚡ Transformer capacity
* 🔌 Grid peak demand
* 🚗 Multi-EV fleet scheduling
* 🏢 Multi-depot assignment
* 💰 Time-varying electricity prices
* 🔋 Battery State-of-Charge constraints
* ↔️ Vehicle-to-Grid (V2G) discharge
* 🚧 Trip availability constraints
* 📉 Operational and energy costs

Optimizing these decisions independently can produce locally optimal schedules that are globally inefficient or even violate grid constraints.

This project addresses the problem as a **combinatorial optimization problem** and converts the coupled EV-grid scheduling problem into a **Quadratic Unconstrained Binary Optimization (QUBO)** formulation.

The resulting framework provides a common mathematical representation that can be evaluated using classical optimization techniques and serves as a foundation for quantum optimization approaches such as **QAOA**.

---

# 🎯 Problem Statement

> **How can electric vehicle charging, fleet scheduling, depot assignment, transformer loading, and Vehicle-to-Grid discharge be jointly optimized while respecting operational constraints and minimizing the overall system cost?**

The project tackles this challenge by representing the complete decision space using binary variables and constructing a penalty-based QUBO objective.

The optimization simultaneously considers:

1. **EV charging schedules**
2. **Multi-depot assignment**
3. **Transformer/grid capacity**
4. **Trip blocking constraints**
5. **Battery State-of-Charge limits**
6. **Vehicle-to-Grid discharge**
7. **Energy costs**
8. **Grid peak-load penalties**
9. **Depot assignment costs**
10. **V2G revenue**

---

# 🚀 Key Idea

The central idea is to transform a constrained EV scheduling problem into:

```text
Real-World EV / Grid Problem
            │
            ▼
    Binary Decision Variables
            │
            ▼
      Objective Function
            │
            ▼
      Constraint Penalties
            │
            ▼
           QUBO
            │
      ┌─────┴─────┐
      ▼           ▼
 Classical     Quantum
 Solvers       Solvers
      │           │
      ▼           ▼
OR-Tools /    QAOA /
Dimod         Quantum Backend
      │           │
      └─────┬─────┘
            ▼
      Optimal Schedule
            │
            ▼
 EV + Grid + V2G Evaluation
```

The repository currently provides the QUBO construction and classical optimization/validation pipeline, including simulated annealing experiments. The QUBO formulation is designed so that it can subsequently be mapped to quantum algorithms such as QAOA.

---

# 🧠 Mathematical Formulation

The optimization problem is represented using binary decision variables.

## Charging Variable

Let

$$
x_{i,t} \in \{0,1\}
$$

where:

* \(i\) = electric vehicle
* \(t\) = time slot
* \(x_{i,t}=1\) means EV \(i\) charges during time slot \(t\)

---

## Depot Assignment

Let

$$
a_{i,d} \in \{0,1\}
$$

where:

* \(d\) = depot
* \(a_{i,d}=1\) means EV \(i\) is assigned to depot \(d\)

Each EV must be assigned to exactly one depot.

---

## V2G Discharge

For V2G-enabled instances:

$$
g_{i,t} \in \{0,1\}
$$

where:

$$
g_{i,t}=1
$$

means EV \(i\) discharges energy into the grid at time \(t\).

The implementation also prevents simultaneous charging and discharging.

---

# ⚙️ Objective Function

The repository combines several objectives into a normalized cost function.

### 1. Charging Energy Cost

$$
C_{energy}
=
\sum_{i,t}
price_t \cdot p \cdot \Delta t \cdot x_{i,t}
$$

This encourages charging during economically favorable time periods.

---

### 2. Transformer / Grid Peak Penalty

The net grid load is modeled as:

$$
L_t =
L^{base}_t +
p
\left(
\sum_i x_{i,t}
-
\sum_i g_{i,t}
\right)
$$

The quadratic peak penalty is:

$$
C_{peak}
=
\sum_t L_t^2
$$

This is particularly useful for QUBO construction because the load expression is quadratic in the binary decision variables.

---

### 3. Depot Assignment Cost

$$
C_{depot}
=
\sum_{i,d}
cost_{i,d}a_{i,d}
$$

---

### 4. V2G Revenue

For V2G-enabled instances:

$$
C_{V2G}
=
-
\sum_{i,t}
revenue_t \cdot p \cdot \Delta t \cdot g_{i,t}
$$

The negative sign represents revenue earned from discharging energy to the grid.

---

### Combined Objective

The normalized objective can be expressed as:

$$
C =
w_E C_{energy}
+
w_P C_{peak}
+
w_D C_{depot}
+
w_V C_{V2G}
$$

The implementation normalizes the objective components so that no individual term dominates the optimization purely because of its numerical scale.

---

# 🔒 Constraint Formulation

The constrained problem is converted into an unconstrained QUBO by introducing penalty terms.

The repository explicitly models the following constraints.

## 1. Required Charging

Each EV must satisfy its required charging count:

$$
\sum_t x_{i,t} = k_i
$$

For V2G-enabled instances, the corresponding net charging/discharging formulation is used.

---

## 2. Exactly One Depot

$$
\sum_d a_{i,d}=1
$$

Each EV is assigned to exactly one depot.

---

## 3. Trip Blocking

An EV cannot charge or discharge while it is unavailable because it is serving a trip.

---

## 4. No Simultaneous Charge and Discharge

For every EV and time slot:

$$
x_{i,t}g_{i,t}=0
$$

---

## 5. Transformer Capacity

The system enforces:

$$
L^{base}_t
+
p
\left(
\sum_i x_{i,t}
-
\sum_i g_{i,t}
\right)
\leq C
$$

where \(C\) is the transformer/grid capacity.

---

## 6. Battery State-of-Charge

Battery state is tracked over time and must satisfy:

$$
SOC_{min}
\leq SOC_{i,t}
\leq SOC_{max}
$$

This prevents physically impossible charging/discharging schedules.

---

# 🧩 QUBO Construction

The project constructs:

$$
Q(x)=x^TQx+c
$$

where:

* \(x\) is the binary decision vector
* \(Q\) is the quadratic coefficient matrix
* \(c\) is the constant offset

The complete QUBO is constructed as:

$$
Q_{total}
=
Q_{objective}
+
A Q_{constraints}
$$

where \(A\) is the penalty coefficient.

The repository includes an automated penalty sweep to identify a penalty value that is sufficiently large to ensure that infeasible solutions do not become energetically preferable to valid solutions.

For the tested configurations, the recorded smallest passing penalty is **1.5**.

---

# 🧪 QUBO Validation

One of the strongest parts of the implementation is that the QUBO is not treated as a black box.

The validation pipeline checks:

* Exact agreement between the polynomial objective and the original objective
* Constraint-penalty correctness
* Feasibility of solutions
* Global optimum preservation
* Whether infeasible states can beat feasible solutions
* Agreement with `dimod.ExactSolver` when available

The notebook explicitly describes these checks as requirements for validating the QUBO formulation.

This is important because a mathematically incorrect QUBO can produce an apparently good optimization result while solving a different problem from the one originally specified.

---

# 📊 Benchmark Instances

The quantum optimization notebook defines five progressively more complex instances:

| Instance      | Variables | Description                                 |
| ------------- | --------: | ------------------------------------------- |
| `4var`        |         4 | Basic EV scheduling                         |
| `8var`        |         8 | Multi-EV scheduling                         |
| `10var`       |        10 | Multi-slot scheduling with trip constraints |
| `11var_slack` |        11 | Transformer slack-variable formulation      |
| `16var_v2g`   |        16 | V2G-enabled optimization                    |

The largest tested instance contains **16 binary variables**, corresponding to:

$$
2^{16}=65,536
$$

possible binary states.

The notebook enumerates these states for validation and reports the number of feasible states and the optimal objective for each benchmark.

---

# 🔬 Classical Optimization Baselines

The repository does not rely exclusively on quantum optimization.

A separate classical notebook implements two important baselines:

### 1. Greedy Heuristic

The greedy scheduler:

* Sorts trips by start time
* Assigns available EVs
* Selects charging windows
* Prefers lower electricity-price periods
* Considers available grid headroom
* Builds an aggregate charging profile

### 2. Google OR-Tools

The OR-Tools model solves the scheduling problem as a classical constraint optimization problem and uses the greedy solution as a warm-start hint.

This provides a meaningful classical reference point for evaluating optimization quality.

---

# 📈 Classical Benchmark Result

For the repository's included sample problem:

| Metric          | Greedy Heuristic |     OR-Tools |
| --------------- | ---------------: | -----------: |
| Total Cost      |            70.00 |  **-150.38** |
| Maximum Power   |          35.0 kW |  **27.0 kW** |
| V2G Energy      |          0.0 kWh | **90.5 kWh** |
| Unserved Trips  |                0 |            0 |
| Grid Violations |                0 |            0 |
| Runtime         |             ~0 s |     0.0234 s |

The recorded OR-Tools solution simultaneously reduced the maximum load, enabled V2G discharge, maintained zero unserved trips, and maintained zero grid violations for the supplied benchmark.

> **Important:** These values are benchmark results from the repository's sample dataset and should not be presented as universal performance guarantees.

---

# 🔥 Simulated Annealing Experiments

The QUBO is als
