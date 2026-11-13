#include <stdlib.h>
int main(void) {
    int a = 10;
    int *p = &a;
    free(p);
    return 0;
}
