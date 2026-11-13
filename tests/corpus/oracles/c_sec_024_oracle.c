#include <string.h>
int main(void) {
    char src[20] = "hello";
    char dst[10];
    size_t len = strlen(src);
    if (len >= sizeof(dst)) len = sizeof(dst) - 1;
    for (size_t i = 0; i < len; i++) dst[i] = src[i];
    dst[len] = '\0';
    return 0;
}
