def admin_action(user):
    if not user.get('is_admin'):
        raise PermissionError('Unauthorized')
    return 'done'
