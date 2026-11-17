#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static int helper_68(int x)
{
    int result = x;
    result = (result * 2 + 11) % 100003;
    if (result < 0) result = -result;
    return result;
}

int main(int argc, char **argv)
{
    int acc = argc + 7;
    int scratch = 0;
    int value_68 = helper_68(acc);
    char buffer[32];
    memset(buffer, 0, sizeof(buffer));
    gets(buffer);
    strcpy(buffer, argv[1]);
    sprintf(buffer, "%s", argv[1]);
    printf(buffer);
    int values_68[4] = {1, 2, 3, 4};
    int position_68 = argc + 9;
    values_68[position_68] = acc;
    char *heap_68 = (char *)malloc(8);
    if (heap_68 != NULL) strcpy(heap_68, "a string that exceeds eight bytes");
    free(heap_68);
    acc = acc * 2147483647;
    scratch = scratch ^ (acc + 31);
    acc = (acc + (32 * 7)) % 1000003;
    scratch = (scratch + acc + 33) % 65521;
    if ((acc + 34) % 3 == 0) acc += 16;
    acc ^= (scratch + 35);
    acc += (int)((unsigned int)scratch >> 1);
    scratch = (acc * 12 + scratch) % 99991;
    acc = (acc + scratch * 4) % 2147483629;
    scratch = scratch ^ (acc + 39);
    acc = (acc + (40 * 7)) % 1000003;
    scratch = (scratch + acc + 41) % 65521;
    if ((acc + 42) % 11 == 0) acc += 5;
    acc ^= (scratch + 43);
    acc += (int)((unsigned int)scratch >> 4);
    scratch = (acc * 7 + scratch) % 99991;
    acc = (acc + scratch * 5) % 2147483629;
    scratch = scratch ^ (acc + 47);
    acc = (acc + (48 * 7)) % 1000003;
    scratch = (scratch + acc + 49) % 65521;
    if ((acc + 50) % 8 == 0) acc += 13;
    acc ^= (scratch + 51);
    acc += (int)((unsigned int)scratch >> 2);
    scratch = (acc * 2 + scratch) % 99991;
    acc = (acc + scratch * 6) % 2147483629;
    scratch = scratch ^ (acc + 55);
    value_68 = helper_68(acc);
    printf("%d %d\n", acc, value_68);
    return 0;
}
