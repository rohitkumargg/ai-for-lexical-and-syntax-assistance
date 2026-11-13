#include <stdio.h>
int main(void) {
    const char *in = "alice 100";
    char name[32];
    int val = 0;
    if (sscanf(in, "%31s %d", name, &val) == 2) puts(name);
    return 0;
}
