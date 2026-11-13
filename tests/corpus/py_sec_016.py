import subprocess
def run_cmd(arg):
    return subprocess.Popen(f'ls {arg}', shell=True, stdout=subprocess.PIPE)
