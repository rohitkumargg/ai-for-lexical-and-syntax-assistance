#include <string.h>
int main(void) {
    char src[] = "test";
    char dst[16];
    strncpy(dst, src, sizeof(dst) - 1);
    dst[sizeof(dst) - 1] = '\0';
    return 0;
}
