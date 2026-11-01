#include <stdio.h>
#include <string.h>
int main() {
  char dst[10];
  char src[20];
  scanf("%19s", src);
  strcpy(dst, src);
  return 0;
}
