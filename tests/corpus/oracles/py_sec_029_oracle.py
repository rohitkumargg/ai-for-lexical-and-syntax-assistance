import logging
def authenticate(user, password):
    logging.info('Login attempt for user: %s', user)
    return True
