#include <stdio.h>
int main(void) {
    char buf[L_tmpnam];
    tmpnam(buf);
    return 0;
}
