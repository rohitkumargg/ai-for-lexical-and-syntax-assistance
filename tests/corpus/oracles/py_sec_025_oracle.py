import re
def check_pattern(s):
    # Safe bounded regex
    return re.match(r'^[a-z]{1,20}$', s)
