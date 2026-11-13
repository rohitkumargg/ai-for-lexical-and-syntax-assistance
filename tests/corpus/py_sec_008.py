def fetch_user(cursor, username):
    cursor.execute(f'SELECT * FROM users WHERE name = "{username}"')
