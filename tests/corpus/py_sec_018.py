import tarfile
def extract_archive(tf, path):
    tf.extractall(path=path)
