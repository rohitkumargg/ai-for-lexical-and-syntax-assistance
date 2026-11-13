#include <stdio.h>

const char *cert_key = "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7dummykey1234567\n-----END PRIVATE KEY-----\n";

int main(void) {
    printf("Certificate loaded.\n");
    return 0;
}
