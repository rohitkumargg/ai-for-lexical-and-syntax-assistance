#include <stdlib.h>
int main(void) {
    int *p = (int *)malloc(sizeof(int));
    if (!p) return 1;
    *p = 42;
    free(p);
    p = NULL;
    return 0;
}
