import os
def get_key():
    return os.environ.get('API_KEY', '')
