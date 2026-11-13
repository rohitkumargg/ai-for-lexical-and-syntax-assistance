#include <stdio.h>
int main(void) {
    const char *in = "alice 100";
    char name[32];
    int val = 0;
    sscanf(in, "%s %d", name, &val);
    return 0;
}
