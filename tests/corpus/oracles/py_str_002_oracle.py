def repeat(fn):
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

@repeat
def do_action():
    return 'ok'
