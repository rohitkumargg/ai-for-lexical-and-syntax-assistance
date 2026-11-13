#include <stdlib.h>
int main(void) {
    void *p = malloc(16);
    if (!p) return 1;
    free(p);
    p = NULL;
    return 0;
}
