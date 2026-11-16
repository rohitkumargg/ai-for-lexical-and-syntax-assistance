#include <stdlib.h>
#include <stdio.h>
int main(void) {
    char templ[] = "/tmp/testXXXXXX";
    mktemp(templ);
    return 0;
}
