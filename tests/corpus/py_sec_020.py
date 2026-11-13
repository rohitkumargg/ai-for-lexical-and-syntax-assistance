import shelve
def load_records(filename):
    return shelve.open(filename)
