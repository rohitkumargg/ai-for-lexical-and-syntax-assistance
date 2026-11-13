#include <stdlib.h>
int main(void) {
    int count = 100;
    int *buf = (int *)malloc(count * sizeof(int));
    if (buf) free(buf);
    return 0;
}
