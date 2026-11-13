#include <stdlib.h>
#include <stdio.h>
int main(void) {
    const char *pwd = getenv("APP_PASS");
    if (pwd) puts("Logged in");
    return 0;
}
