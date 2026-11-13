from cryptography.hazmat.primitives.ciphers import algorithms
def get_algo():
    return algorithms.TripleDES(b'0' * 24)
