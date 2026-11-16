#include <stdio.h>
int main(void) {
    FILE *f = fopen("out.txt", "w");
    if (!f) return 1;
    fputs("hello\n", f);
    fclose(f);
    return 0;
}
