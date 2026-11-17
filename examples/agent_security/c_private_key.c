/* TEST FIXTURE: embedded private key (fake, non-functional body) */
#include <stdio.h>

static const char *private_key =
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIEowIBAAKCAQEAFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE\n"
    "THISISNOTAREALKEYTHISISNOTAREALKEYTHISISNOTAREALKEYTHISISNOTAREAL\n"
    "FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE\n"
    "-----END RSA PRIVATE KEY-----\n";

int main(void) {
  printf("loaded key (%zu bytes)\n", sizeof(private_key));
  return 0;
}
