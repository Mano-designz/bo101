"""
quantum/qubo_to_ising.py -- Convert validated QUBO into an Ising Hamiltonian for QAOA.
"""
from __future__ import annotations

import sys
import os

# Add parent directory to path to import model files if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qubo import build_qubo, INSTANCES


def get_ising_representation(instance_name: str = "tiny4"):
    """Builds instance, generates QUBO, and converts to Qiskit Ising operator."""
    inst = INSTANCES[instance_name]()
    model = build_qubo(inst)
    
    # Converts QuadraticProgram to Ising Pauli operators
    operator, offset = model.qubo_to_ising_operator() if hasattr(model, 'qubo_to_ising_operator') else _convert(model)
    print(f"[{instance_name.upper()}] Converted QUBO to Ising: {len(operator)} terms, offset = {offset:.4f}")
    return model, operator, offset


def _convert(model):
    from qubo import to_ising
    return to_ising(model)


if __name__ == "__main__":
    get_ising_representation("tiny4")