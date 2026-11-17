/* TEST FIXTURE: connection strings with embedded credentials (fake) */
#include <stdio.h>

static const char *pg_url =
    "postgresql://admin:SuperSecret123@db.internal.example.com:5432/prod";
static const char *mongo_url =
    "mongodb://root:hunter2@mongo.example.com:27017/app?authSource=admin";
static const char *redis_url = "redis://:r3d1sP@ss@cache.example.com:6379/0";

int main(void) {
  printf("Connecting to %s\n", pg_url);
  return 0;
}
