#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static int helper_60(int x)
{
    int result = x;
    result = (result * 11 + 3) % 100003;
    if (result < 0) result = -result;
    return result;
}

int main(int argc, char **argv)
{
    int acc = argc + 7;
    int scratch = 0;
    int value_60 = helper_60(acc);
    char buffer[32];
    memset(buffer, 0, sizeof(buffer));
    gets(buffer);
    strcpy(buffer, argv[1]);
    sprintf(buffer, "%s", argv[1]);
    printf(buffer);
    int values_60[4] = {1, 2, 3, 4};
    int position_60 = argc + 9;
    values_60[position_60] = acc;
    char *heap_60 = (char *)malloc(8);
    if (heap_60 != NULL) strcpy(heap_60, "a string that exceeds eight bytes");
    free(heap_60);
    acc = acc * 2147483647;
    scratch = scratch ^ (acc + 31);
    acc = (acc + (32 * 30)) % 1000003;
    scratch = (scratch + acc + 33) % 65521;
    if ((acc + 34) % 3 == 0) acc += 16;
    acc ^= (scratch + 35);
    acc += (int)((unsigned int)scratch >> 1);
    scratch = (acc * 12 + scratch) % 99991;
    acc = (acc + scratch * 4) % 2147483629;
    scratch = scratch ^ (acc + 39);
    acc = (acc + (40 * 30)) % 1000003;
    scratch = (scratch + acc + 41) % 65521;
    if ((acc + 42) % 11 == 0) acc += 5;
    acc ^= (scratch + 43);
    acc += (int)((unsigned int)scratch >> 4);
    scratch = (acc * 7 + scratch) % 99991;
    acc = (acc + scratch * 5) % 2147483629;
    scratch = scratch ^ (acc + 47);
    acc = (acc + (48 * 30)) % 1000003;
    scratch = (scratch + acc + 49) % 65521;
    if ((acc + 50) % 8 == 0) acc += 13;
    acc ^= (scratch + 51);
    acc += (int)((unsigned int)scratch >> 2);
    scratch = (acc * 2 + scratch) % 99991;
    acc = (acc + scratch * 6) % 2147483629;
    scratch = scratch ^ (acc + 55);
    acc = (acc + (56 * 30)) % 1000003;
    scratch = (scratch + acc + 4) % 65521;
    if ((acc + 58) % 5 == 0) acc += 2;
    acc ^= (scratch + 59);
    acc += (int)((unsigned int)scratch >> 0);
    scratch = (acc * 10 + scratch) % 99991;
    acc = (acc + scratch * 7) % 2147483629;
    scratch = scratch ^ (acc + 63);
    acc = (acc + (64 * 30)) % 1000003;
    scratch = (scratch + acc + 12) % 65521;
    if ((acc + 66) % 2 == 0) acc += 10;
    acc ^= (scratch + 67);
    acc += (int)((unsigned int)scratch >> 3);
    scratch = (acc * 5 + scratch) % 99991;
    acc = (acc + scratch * 1) % 2147483629;
    scratch = scratch ^ (acc + 71);
    acc = (acc + (72 * 30)) % 1000003;
    scratch = (scratch + acc + 20) % 65521;
    if ((acc + 74) % 10 == 0) acc += 18;
    acc ^= (scratch + 75);
    acc += (int)((unsigned int)scratch >> 1);
    scratch = (acc * 13 + scratch) % 99991;
    acc = (acc + scratch * 2) % 2147483629;
    scratch = scratch ^ (acc + 79);
    acc = (acc + (80 * 30)) % 1000003;
    scratch = (scratch + acc + 28) % 65521;
    if ((acc + 82) % 7 == 0) acc += 7;
    acc ^= (scratch + 83);
    acc += (int)((unsigned int)scratch >> 4);
    scratch = (acc * 8 + scratch) % 99991;
    acc = (acc + scratch * 3) % 2147483629;
    scratch = scratch ^ (acc + 87);
    acc = (acc + (88 * 30)) % 1000003;
    scratch = (scratch + acc + 36) % 65521;
    if ((acc + 90) % 4 == 0) acc += 15;
    acc ^= (scratch + 91);
    acc += (int)((unsigned int)scratch >> 2);
    scratch = (acc * 3 + scratch) % 99991;
    acc = (acc + scratch * 4) % 2147483629;
    scratch = scratch ^ (acc + 95);
    acc = (acc + (96 * 30)) % 1000003;
    scratch = (scratch + acc + 44) % 65521;
    value_60 = helper_60(acc);
    printf("%d %d\n", acc, value_60);
    return 0;
}
