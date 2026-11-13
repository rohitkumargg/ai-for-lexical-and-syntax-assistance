import subprocess
def run_cmd(arg):
    return subprocess.Popen(['ls', arg], stdout=subprocess.PIPE)
