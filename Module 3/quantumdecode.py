"""
quantum/decode.py -- Decode quantum measurement bitstrings and verify feasibility.
"""
from __future__ import annotations
from typing import Dict
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from constraints import is_feasible_direct


def decode_and_filter_counts(counts: Dict[str, int], model) -> list[dict]:
    """
    Takes measurement counts from Qiskit execution, sorts by probability,
    decodes decision bits, and validates constraint feasibility.
    """
    sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    decoded_results = []
    
    for bitstring, count in sorted_counts:
        bits = [int(b) for b in reversed(bitstring[:model.n])]
        feasible = is_feasible_direct(model.inst, model.vi, bits)
        energy = model.energy(bits)
        
        decoded_results.append({
            "bitstring": bitstring,
            "counts": count,
            "feasible": feasible,
            "energy": energy
        })
        
    return decoded_results