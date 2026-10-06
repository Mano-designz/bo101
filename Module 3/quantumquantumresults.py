"""
quantum/quantum_results.py -- Execute QAOA across depths (p=1, 2, 3) and output metrics.
"""
from __future__ import annotations
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from quantum.qubo_to_ising import get_ising_representation
from quantum.circuit import build_qaoa_circuit
from qiskit_aer import AerSimulator
from qiskit import transpile


def run_experiment(instance_name: str = "tiny4"):
    print(f"=== Starting Quantum Execution for Instance: {instance_name} ===")
    model, operator, offset = get_ising_representation(instance_name)
    
    simulator = AerSimulator()
    
    for p in [1, 2, 3]:
        print(f"\n--- Testing QAOA Depth p = {p} ---")
        qc, gamma, beta = build_qaoa_circuit(operator, p=p)
        
        bound_qc = qc.bind_parameters({**{g: 0.1 for g in gamma}, **{b: 0.2 for b in beta}})
        transpiled_qc = transpile(bound_qc, simulator)
        
        job = simulator.run(transpiled_qc, shots=1024)
        result = job.result()
        counts = result.get_counts(transpiled_qc)
        
        top_bitstring = max(counts, key=counts.get)
        print(f"Circuit Depth: {transpiled_qc.depth()} | Top Bitstring: {top_bitstring} (Count: {counts[top_bitstring]})")


if __name__ == "__main__":
    run_experiment("tiny4")