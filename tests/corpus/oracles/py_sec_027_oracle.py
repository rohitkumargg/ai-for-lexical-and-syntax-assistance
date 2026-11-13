import os
def get_priv_key():
    return os.environ.get('RSA_KEY', '')
