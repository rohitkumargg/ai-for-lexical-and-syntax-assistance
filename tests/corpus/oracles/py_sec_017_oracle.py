import os
def get_jwt_secret():
    return os.environ.get('JWT_SECRET', '')
