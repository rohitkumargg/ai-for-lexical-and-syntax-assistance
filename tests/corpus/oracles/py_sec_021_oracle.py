import os
def get_aws_keys():
    return os.environ.get('AWS_SECRET_ACCESS_KEY', '')
