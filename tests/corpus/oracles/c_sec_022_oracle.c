#include <stdio.h>
int main(void) {
    FILE *f = fopen("out.txt", "w");
    if (!f) return 1;
    if (fputs("hello\n", f) == EOF) { fclose(f); return 1; }
    fclose(f);
    return 0;
}
