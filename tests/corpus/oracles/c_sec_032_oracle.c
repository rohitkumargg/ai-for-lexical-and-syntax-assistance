#include <stdlib.h>
int main(void) {
    int *p = (int *)malloc(sizeof(int));
    if (p) free(p);
    return 0;
}
