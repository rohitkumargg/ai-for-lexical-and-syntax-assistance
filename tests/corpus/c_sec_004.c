#include <stdio.h>
int main(void) {
    char buf[32];
    sprintf(buf, "%s", "vulnerable");
    return 0;
}
