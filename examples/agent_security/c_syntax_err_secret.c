/* TEST FIXTURE: file does NOT compile (intentional syntax errors) but still
 * contains a secret. Scanners must catch secrets even when parsing fails. */
#include <stdio.h>

static const char *api_token = "xoxb-FAKE-1234567890-abcdefghijklmnopqrstuvwx";

int main( {
    printf("token: %s\n", api_token)
    return 0
}
}