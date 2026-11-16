def admin_action(user):
    assert user.get('is_admin'), 'Unauthorized'
    return 'done'
