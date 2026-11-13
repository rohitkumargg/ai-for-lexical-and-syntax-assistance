import ssl
def get_context():
    return ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
