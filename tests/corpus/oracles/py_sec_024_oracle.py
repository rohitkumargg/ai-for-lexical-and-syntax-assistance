from urllib.parse import urlparse
def safe_redirect(target):
    parsed = urlparse(target)
    if parsed.netloc in ('example.com', ''):
        return target
    return '/'
