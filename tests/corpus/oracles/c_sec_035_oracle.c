#include <string.h>
int main(void) {
    char src[20] = "1234567890123456789";
    char dst[10];
    memcpy(dst, src, sizeof(dst));
    return 0;
}
