#include <stdio.h>
int main(void) {
    char query[128];
    sprintf(query, "SELECT * FROM users WHERE name = '%s'", "admin");
    puts(query);
    return 0;
}
