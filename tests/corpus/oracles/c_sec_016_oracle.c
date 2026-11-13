#include <stdio.h>
int main(void) {
    FILE *f = fopen("safe_temp.txt", "w");
    if (f) { fputs("data", f); fclose(f); }
    return 0;
}
