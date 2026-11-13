#include <string.h>
int main(void) {
    char dst[32] = "hello";
    strncat(dst, " world", sizeof(dst) - strlen(dst) - 1);
    return 0;
}
