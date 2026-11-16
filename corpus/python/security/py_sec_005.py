import yaml
def load_config(s):
    return yaml.load(s, Loader=yaml.Loader)
