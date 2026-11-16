#include <stdio.h>
int main(void) {
    FILE *f = fopen("log.txt", "r");
    fclose(f);
    return 0;
}
