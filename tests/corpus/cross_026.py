def get_db_url():
    db_uri = "postgres://admin:pass123456@127.0.0.1:5432/app"
    return db_uri

if __name__ == "__main__":
    print(get_db_url())

