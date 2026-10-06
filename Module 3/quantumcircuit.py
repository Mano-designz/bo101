"""
quantum/circuit.py -- Build parameterized QAOA ansatz circuits (p-layers).
"""
from __future__ import annotations
from qiskit.circuit import QuantumCircuit, ParameterVector


def build_qaoa_circuit(operator, p: int = 1) -> tuple[QuantumCircuit, ParameterVector, ParameterVector]:
    """
    Constructs the QAOA circuit ansatz for a given Ising operator and depth p.
    Returns: (circuit, gamma_parameters, beta_parameters)
    """
    num_qubits = operator.num_qubits
    qc = QuantumCircuit(num_qubits)
    
    gamma = ParameterVector('γ', p)
    beta = ParameterVector('β', p)
    
    # Initial superposition state
    qc.h(range(num_qubits))
    
    # Apply p layers of QAOA
    for layer in range(p):
        # Cost Hamiltonian evolution (exp(-i * gamma * H_C))
        for pauli, coeff in operator.to_list():
            active_qubits = [i for i, char in enumerate(reversed(pauli)) if char != 'I']
            if len(active_qubits) == 1:
                qc.p(2.0 * coeff * gamma[layer], active_qubits[0])
            elif len(active_qubits) == 2:
                q0, q1 = active_qubits
                qc.cx(q0, q1)
                qc.p(2.0 * coeff * gamma[layer], q1)
                qc.cx(q0, q1)
                
        # Mixer Hamiltonian evolution (exp(-i * beta * H_M))
        for i in range(num_qubits):
            qc.rx(2.0 * beta[layer], i)
            
    qc.measure_all()
    return qc, gamma, beta