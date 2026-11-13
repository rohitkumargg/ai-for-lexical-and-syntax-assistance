#include <stdlib.h>
int main(void) {
    int *ptr = (int *)malloc(sizeof(int));
    if (ptr == NULL) return 1;
    *ptr = 10;
    free(ptr);
    return 0;
}
