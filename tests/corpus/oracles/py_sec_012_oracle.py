import os
def get_db_pwd():
    return os.environ.get('DB_PASS', '')
