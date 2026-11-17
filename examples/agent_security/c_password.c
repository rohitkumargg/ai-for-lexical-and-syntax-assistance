/* TEST FIXTURE: hardcoded password (fake value) */
#include <stdio.h>
#include <string.h>

#define ADMIN_PASSWORD "admin123!"

int check_login(const char *user, const char *pass) {
  return strcmp(user, "admin") == 0 && strcmp(pass, ADMIN_PASSWORD) == 0;
}

int main(void) {
  printf("login ok: %d\n", check_login("admin", "guess"));
  return 0;
}
