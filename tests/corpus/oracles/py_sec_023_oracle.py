from cryptography.hazmat.primitives.ciphers import algorithms
def get_algo():
    return algorithms.AES(b'0' * 32)
