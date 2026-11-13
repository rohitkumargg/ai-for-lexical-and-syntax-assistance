#include <stdio.h>
int main(void) {
    char buf[10] = "abcdef";
    for (int i = 0; i < 6; i++) {
        putchar(buf[i]);
    }
    return 0;
}
