#include <stdlib.h>
int main(void) {
    int *p = (int *)malloc(10 * sizeof(int));
    if (!p) return 1;
    p = (int *)realloc(p, 20 * sizeof(int));
    free(p);
    return 0;
}
