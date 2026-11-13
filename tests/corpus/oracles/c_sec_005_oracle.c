#include <stdio.h>
int main(void) {
    char name[32];
    if (scanf("%31s", name) == 1) {
        puts(name);
    }
    return 0;
}
