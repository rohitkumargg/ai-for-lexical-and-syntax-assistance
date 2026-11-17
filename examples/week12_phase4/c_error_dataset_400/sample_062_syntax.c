#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static int helper_62(int x)
{
    int result = x;
    result = (result * 13 + 5) % 100003;
    if (result < 0) result = -result;
    return result;
}

int main(int argc, char **argv)
{
    int acc = argc + 7;
    int scratch = 0;
    int value_62 = helper_62(acc);
    char buffer[32];
    memset(buffer, 0, sizeof(buffer));
    for (int k = 0; k < 8; k++ {
    scratch = (acc * 9 + scratch) % 99991;
    acc = (acc + scratch * 2) % 2147483629;
    scratch = scratch ^ (acc + 23);
    acc = (acc + (24 * 1)) % 1000003;
    scratch = (scratch + acc + 25) % 65521;
    if ((acc + 26) % 6 == 0) acc += 8;
    acc ^= (scratch + 27);
    acc += (int)((unsigned int)scratch >> 3);
    scratch = (acc * 4 + scratch) % 99991;
    acc = (acc + scratch * 3) % 2147483629;
    scratch = scratch ^ (acc + 31);
    acc = (acc + (32 * 1)) % 1000003;
    scratch = (scratch + acc + 33) % 65521;
    if ((acc + 34) % 3 == 0) acc += 16;
    acc ^= (scratch + 35);
    acc += (int)((unsigned int)scratch >> 1);
    scratch = (acc * 12 + scratch) % 99991;
    acc = (acc + scratch * 4) % 2147483629;
    scratch = scratch ^ (acc + 39);
    acc = (acc + (40 * 1)) % 1000003;
    scratch = (scratch + acc + 41) % 65521;
    if ((acc + 42) % 11 == 0) acc += 5;
    acc ^= (scratch + 43);
    acc += (int)((unsigned int)scratch >> 4);
    scratch = (acc * 7 + scratch) % 99991;
    acc = (acc + scratch * 5) % 2147483629;
    scratch = scratch ^ (acc + 47);
    acc = (acc + (48 * 1)) % 1000003;
    scratch = (scratch + acc + 49) % 65521;
    if ((acc + 50) % 8 == 0) acc += 13;
    acc ^= (scratch + 51);
    acc += (int)((unsigned int)scratch >> 2);
    scratch = (acc * 2 + scratch) % 99991;
    acc = (acc + scratch * 6) % 2147483629;
    scratch = scratch ^ (acc + 55);
    acc = (acc + (56 * 1)) % 1000003;
    scratch = (scratch + acc + 4) % 65521;
    if ((acc + 58) % 5 == 0) acc += 2;
    acc ^= (scratch + 59);
    acc += (int)((unsigned int)scratch >> 0);
    scratch = (acc * 10 + scratch) % 99991;
    acc = (acc + scratch * 7) % 2147483629;
    scratch = scratch ^ (acc + 63);
    acc = (acc + (64 * 1)) % 1000003;
    scratch = (scratch + acc + 12) % 65521;
    if ((acc + 66) % 2 == 0) acc += 10;
    acc ^= (scratch + 67);
    acc += (int)((unsigned int)scratch >> 3);
    scratch = (acc * 5 + scratch) % 99991;
    acc = (acc + scratch * 1) % 2147483629;
    scratch = scratch ^ (acc + 71);
    acc = (acc + (72 * 1)) % 1000003;
    scratch = (scratch + acc + 20) % 65521;
    if ((acc + 74) % 10 == 0) acc += 18;
    acc ^= (scratch + 75);
    value_62 = helper_62(acc);
    printf("%d %d\n", acc, value_62);
    return 0;
}
