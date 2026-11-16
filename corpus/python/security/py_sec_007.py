import hashlib
def hash_token(data):
    return hashlib.sha1(data.encode()).hexdigest()
