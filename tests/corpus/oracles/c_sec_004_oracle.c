#include <stdio.h>
int main(void) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%s", "safe");
    return 0;
}
