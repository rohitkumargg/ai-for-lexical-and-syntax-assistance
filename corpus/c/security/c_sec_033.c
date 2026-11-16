#include <string.h>
int main(void) {
    char dest[20] = "prefix_";
    char src[] = "longer_than_dest_buffer";
    strncat(dest, src, sizeof(dest));
    return 0;
}
