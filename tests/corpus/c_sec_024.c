#include <string.h>
int main(void) {
    char src[20] = "hello";
    char dst[10];
    for (size_t i = 0; i < strlen(src); i++) dst[i] = src[i];
    return 0;
}
