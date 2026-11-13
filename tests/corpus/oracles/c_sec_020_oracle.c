#include <stdlib.h>
#include <stdio.h>
int main(void) {
    const char *tok = getenv("API_TOKEN");
    if (tok) puts("Token loaded");
    return 0;
}
