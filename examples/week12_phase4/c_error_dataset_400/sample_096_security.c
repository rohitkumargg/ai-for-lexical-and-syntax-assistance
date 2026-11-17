#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static int helper_96(int x)
{
    int result = x;
    result = (result * 13 + 10) % 100003;
    if (result < 0) result = -result;
    return result;
}

int main(int argc, char **argv)
{
    int acc = argc + 7;
    int scratch = 0;
    int value_96 = helper_96(acc);
    char buffer[32];
    memset(buffer, 0, sizeof(buffer));
    gets(buffer);
    strcpy(buffer, argv[1]);
    sprintf(buffer, "%s", argv[1]);
    printf(buffer);
    int values_96[4] = {1, 2, 3, 4};
    int position_96 = argc + 9;
    values_96[position_96] = acc;
    char *heap_96 = (char *)malloc(8);
    if (heap_96 != NULL) strcpy(heap_96, "a string that exceeds eight bytes");
    free(heap_96);
    acc = acc * 2147483647;
    scratch = scratch ^ (acc + 31);
    acc = (acc + (32 * 4)) % 1000003;
    scratch = (scratch + acc + 33) % 65521;
    if ((acc + 34) % 3 == 0) acc += 16;
    acc ^= (scratch + 35);
    acc += (int)((unsigned int)scratch >> 1);
    scratch = (acc * 12 + scratch) % 99991;
    acc = (acc + scratch * 4) % 2147483629;
    scratch = scratch ^ (acc + 39);
    acc = (acc + (40 * 4)) % 1000003;
    scratch = (scratch + acc + 41) % 65521;
    if ((acc + 42) % 11 == 0) acc += 5;
    acc ^= (scratch + 43);
    acc += (int)((unsigned int)scratch >> 4);
    scratch = (acc * 7 + scratch) % 99991;
    acc = (acc + scratch * 5) % 2147483629;
    scratch = scratch ^ (acc + 47);
    acc = (acc + (48 * 4)) % 1000003;
    scratch = (scratch + acc + 49) % 65521;
    if ((acc + 50) % 8 == 0) acc += 13;
    acc ^= (scratch + 51);
    acc += (int)((unsigned int)scratch >> 2);
    scratch = (acc * 2 + scratch) % 99991;
    acc = (acc + scratch * 6) % 2147483629;
    scratch = scratch ^ (acc + 55);
    acc = (acc + (56 * 4)) % 1000003;
    scratch = (scratch + acc + 4) % 65521;
    value_96 = helper_96(acc);
    printf("%d %d\n", acc, value_96);
    return 0;
}
