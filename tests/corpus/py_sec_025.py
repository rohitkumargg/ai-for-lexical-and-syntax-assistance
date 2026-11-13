import re
def check_pattern(s):
    # Catastrophic backtracking regex
    return re.match(r'^(a+)+$', s)
