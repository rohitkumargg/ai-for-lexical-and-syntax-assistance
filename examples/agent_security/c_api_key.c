/* TEST FIXTURE: hardcoded API key (fake value) */
#include <stdio.h>

#define API_KEY "sk_live_FAKE0123456789abcdefghijklmnop"
static const char *aws_access_key = "AKIAIOSFODNN7EXAMPLE";
static const char *aws_secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY";

int main(void) {
  printf("Calling API with key %s\n", API_KEY);
  return 0;
}