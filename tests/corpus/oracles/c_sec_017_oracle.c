#include <stdio.h>
int main(void) {
    FILE *f = fopen("log.txt", "r");
    if (f == NULL) return 1;
    fclose(f);
    return 0;
}
