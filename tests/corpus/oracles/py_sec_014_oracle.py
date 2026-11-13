import ssl
def get_ssl_ctx():
    return ssl.create_default_context()
