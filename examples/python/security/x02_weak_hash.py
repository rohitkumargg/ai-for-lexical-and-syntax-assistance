import hashlib
digest = hashlib.md5(b"secret").hexdigest()
print(digest)
