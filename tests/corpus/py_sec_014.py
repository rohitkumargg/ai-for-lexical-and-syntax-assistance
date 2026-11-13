import ssl
def get_ssl_ctx():
    return ssl._create_unverified_context()
