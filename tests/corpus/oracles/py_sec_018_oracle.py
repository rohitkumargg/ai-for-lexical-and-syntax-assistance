import tarfile
def extract_safe(tf, path):
    # Extract with member filter
    tf.extractall(path=path, filter='data')
