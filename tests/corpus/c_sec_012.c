#include <stdlib.h>
#include <stdio.h>
int main(void) {
    char cmd[128];
    sprintf(cmd, "echo %s", "input");
    system(cmd);
    return 0;
}
