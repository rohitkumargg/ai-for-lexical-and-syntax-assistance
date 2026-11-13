import hashlib
def hash_token(data):
    return hashlib.sha256(data.encode()).hexdigest()
