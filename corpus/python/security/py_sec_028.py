import os
def make_file(p):
    with open(p, 'w') as f: f.write('ok')
    os.chmod(p, 0o777)
