/* NEGATIVE CONTROL: suspicious-looking names, but NO secrets. Should NOT be
 * flagged. */
#include <stdio.h>
#include <stdlib.h>

int main(void) {
  const char *api_key = getenv("API_KEY");      /* read from environment */
  const char *password = getenv("DB_PASSWORD"); /* read from environment */
  const char *token = NULL;                     /* unset */
  char private_key_path[] =
      "/etc/app/keys/id_rsa"; /* path only, not key material */

  if (!api_key || !password) {
    fprintf(stderr, "missing configuration\n");
    return 1;
  }
  printf("key path: %s, token set: %d\n", private_key_path, token != NULL);
  return 0;
}
