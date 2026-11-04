#include <stdio.h>
#include <sqlite3.h>

int main(void) {
    sqlite3 *db;
    char name[64];
    char query[256];

    sqlite3_open("users.db", &db);
    scanf("%63s", name);

    /* user text is pasted straight into the SQL command */
    sprintf(query, "SELECT * FROM users WHERE name = '%s';", name);
    sqlite3_exec(db, query, 0, 0, 0);

    sqlite3_close(db);
    return 0;
}

