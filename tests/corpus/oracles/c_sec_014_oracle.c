#include <stdio.h>
int main(void) {
    char query[128] = "SELECT * FROM users WHERE id = ?";
    puts(query);
    return 0;
}
