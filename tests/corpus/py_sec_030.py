import ssl
def get_context():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.options &= ~ssl.OP_NO_SSLv3
    return ctx
