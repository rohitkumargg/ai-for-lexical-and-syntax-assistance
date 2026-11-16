#include <stdio.h>
int main(void) {
    const char *key = "-----BEGIN PRIVATE KEY-----\nEXAMPLE_NOT_A_REAL_KEY_0004\n-----END PRIVATE KEY-----";
    if (key) puts("Key present");
    return 0;
}
