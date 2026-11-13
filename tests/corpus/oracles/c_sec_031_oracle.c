#include <stdio.h>
int main(void) {
    FILE *f = fopen("secure.dat", "w");
    if (f) { fputs("data", f); fclose(f); }
    return 0;
}
