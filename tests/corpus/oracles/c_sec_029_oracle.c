#include <stdlib.h>
#include <stdio.h>
int main(void) {
    const char *key = getenv("PRIV_KEY");
    if (key) puts("Key present");
    return 0;
}
