import tempfile
def create_temp():
    return tempfile.NamedTemporaryFile(delete=False)
