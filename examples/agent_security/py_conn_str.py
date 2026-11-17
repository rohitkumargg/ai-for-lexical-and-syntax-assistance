"""TEST FIXTURE: connection strings with embedded credentials (fake)"""
import psycopg2

PG_URL    = "postgresql://admin:SuperSecret123@db.internal.example.com:5432/prod"
MONGO_URL = "mongodb://root:hunter2@mongo.example.com:27017/app?authSource=admin"
REDIS_URL = "redis://:r3d1sP@ss@cache.example.com:6379/0"

def connect():
    return psycopg2.connect(PG_URL)

if __name__ == "__main__":
    connect()