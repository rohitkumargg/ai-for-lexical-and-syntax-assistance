#include <stdio.h>
int main(void) {
    char buf[64];
    if (fgets(buf, sizeof(buf), stdin)) {
        puts(buf);
    }
    return 0;
}
