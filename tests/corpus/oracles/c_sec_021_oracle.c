#include <stdlib.h>
#include <stdio.h>
int main(void) {
    const char *cs = getenv("DB_URI");
    if (cs) puts("Connected");
    return 0;
}
