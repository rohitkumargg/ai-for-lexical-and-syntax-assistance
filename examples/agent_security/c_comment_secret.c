/* TEST FIXTURE: secret leaked inside a comment (fake value) */
#include <stdio.h>

// TODO: remove before commit -- prod DB password is "Pr0d!Passw0rd#2024"
/* github token for CI: ghp_FAKE1234567890abcdefghijklmnopqrstuv */

int main(void) {
  puts("nothing suspicious in the code itself");
  return 0;
}