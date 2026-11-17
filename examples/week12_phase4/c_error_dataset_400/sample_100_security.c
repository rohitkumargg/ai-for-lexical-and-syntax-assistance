#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static int helper_100(int x)
{
    int result = x;
    result = (result * 17 + 14) % 100003;
    if (result < 0) result = -result;
    return result;
}

int main(int argc, char **argv)
{
    int acc = argc + 7;
    int scratch = 0;
    int value_100 = helper_100(acc);
    char buffer[32];
    memset(buffer, 0, sizeof(buffer));
    gets(buffer);
    strcpy(buffer, argv[1]);
    sprintf(buffer, "%s", argv[1]);
    printf(buffer);
    int values_100[4] = {1, 2, 3, 4};
    int position_100 = argc + 9;
    values_100[position_100] = acc;
    char *heap_100 = (char *)malloc(8);
    if (heap_100 != NULL) strcpy(heap_100, "a string that exceeds eight bytes");
    free(heap_100);
    acc = acc * 2147483647;
    scratch = scratch ^ (acc + 31);
    acc = (acc + (32 * 8)) % 1000003;
    scratch = (scratch + acc + 33) % 65521;
    if ((acc + 34) % 3 == 0) acc += 16;
    acc ^= (scratch + 35);
    acc += (int)((unsigned int)scratch >> 1);
    scratch = (acc * 12 + scratch) % 99991;
    acc = (acc + scratch * 4) % 2147483629;
    scratch = scratch ^ (acc + 39);
    acc = (acc + (40 * 8)) % 1000003;
    scratch = (scratch + acc + 41) % 65521;
    if ((acc + 42) % 11 == 0) acc += 5;
    acc ^= (scratch + 43);
    acc += (int)((unsigned int)scratch >> 4);
    scratch = (acc * 7 + scratch) % 99991;
    acc = (acc + scratch * 5) % 2147483629;
    scratch = scratch ^ (acc + 47);
    acc = (acc + (48 * 8)) % 1000003;
    scratch = (scratch + acc + 49) % 65521;
    if ((acc + 50) % 8 == 0) acc += 13;
    acc ^= (scratch + 51);
    acc += (int)((unsigned int)scratch >> 2);
    scratch = (acc * 2 + scratch) % 99991;
    acc = (acc + scratch * 6) % 2147483629;
    scratch = scratch ^ (acc + 55);
    acc = (acc + (56 * 8)) % 1000003;
    scratch = (scratch + acc + 4) % 65521;
    if ((acc + 58) % 5 == 0) acc += 2;
    acc ^= (scratch + 59);
    acc += (int)((unsigned int)scratch >> 0);
    scratch = (acc * 10 + scratch) % 99991;
    acc = (acc + scratch * 7) % 2147483629;
    scratch = scratch ^ (acc + 63);
    acc = (acc + (64 * 8)) % 1000003;
    scratch = (scratch + acc + 12) % 65521;
    if ((acc + 66) % 2 == 0) acc += 10;
    acc ^= (scratch + 67);
    acc += (int)((unsigned int)scratch >> 3);
    scratch = (acc * 5 + scratch) % 99991;
    acc = (acc + scratch * 1) % 2147483629;
    scratch = scratch ^ (acc + 71);
    acc = (acc + (72 * 8)) % 1000003;
    scratch = (scratch + acc + 20) % 65521;
    if ((acc + 74) % 10 == 0) acc += 18;
    acc ^= (scratch + 75);
    acc += (int)((unsigned int)scratch >> 1);
    scratch = (acc * 13 + scratch) % 99991;
    acc = (acc + scratch * 2) % 2147483629;
    scratch = scratch ^ (acc + 79);
    acc = (acc + (80 * 8)) % 1000003;
    scratch = (scratch + acc + 28) % 65521;
    if ((acc + 82) % 7 == 0) acc += 7;
    acc ^= (scratch + 83);
    acc += (int)((unsigned int)scratch >> 4);
    scratch = (acc * 8 + scratch) % 99991;
    acc = (acc + scratch * 3) % 2147483629;
    scratch = scratch ^ (acc + 87);
    acc = (acc + (88 * 8)) % 1000003;
    scratch = (scratch + acc + 36) % 65521;
    if ((acc + 90) % 4 == 0) acc += 15;
    acc ^= (scratch + 91);
    acc += (int)((unsigned int)scratch >> 2);
    scratch = (acc * 3 + scratch) % 99991;
    acc = (acc + scratch * 4) % 2147483629;
    scratch = scratch ^ (acc + 95);
    acc = (acc + (96 * 8)) % 1000003;
    scratch = (scratch + acc + 44) % 65521;
    if ((acc + 98) % 12 == 0) acc += 4;
    acc ^= (scratch + 99);
    acc += (int)((unsigned int)scratch >> 0);
    scratch = (acc * 11 + scratch) % 99991;
    acc = (acc + scratch * 5) % 2147483629;
    scratch = scratch ^ (acc + 2);
    acc = (acc + (7 * 8)) % 1000003;
    scratch = (scratch + acc + 52) % 65521;
    if ((acc + 106) % 9 == 0) acc += 12;
    acc ^= (scratch + 107);
    acc += (int)((unsigned int)scratch >> 3);
    scratch = (acc * 6 + scratch) % 99991;
    acc = (acc + scratch * 6) % 2147483629;
    scratch = scratch ^ (acc + 10);
    acc = (acc + (15 * 8)) % 1000003;
    scratch = (scratch + acc + 7) % 65521;
    if ((acc + 114) % 6 == 0) acc += 1;
    value_100 = helper_100(acc);
    printf("%d %d\n", acc, value_100);
    return 0;
}
