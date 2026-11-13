#include <stdlib.h>
int main(void) {
    int *ptr = (int *)malloc(sizeof(int));
    *ptr = 10;
    free(ptr);
    return 0;
}
