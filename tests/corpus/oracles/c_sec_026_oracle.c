#include <stdlib.h>
int main(void) {
    int *p = (int *)malloc(10 * sizeof(int));
    if (!p) return 1;
    int *tmp = (int *)realloc(p, 20 * sizeof(int));
    if (tmp) p = tmp;
    free(p);
    return 0;
}
