#include <stdlib.h>
int main(void) {
    size_t count = 100;
    if (count > 1000) return 1;
    int *buf = (int *)malloc(count * sizeof(int));
    if (buf) free(buf);
    return 0;
}
