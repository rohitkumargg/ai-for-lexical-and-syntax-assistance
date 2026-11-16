import logging
def authenticate(user, password):
    logging.info('User: %s Password: %s', user, password)
    return True
