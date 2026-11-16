def query_by_id(cursor, user_id):
    cursor.execute('SELECT * FROM accounts WHERE id = ' + str(user_id))
