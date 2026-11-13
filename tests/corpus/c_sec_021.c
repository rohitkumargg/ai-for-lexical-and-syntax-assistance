#include <stdio.h>
int main(void) {
    const char *cs = "Server=sql.internal;User Id=dbuser;Password=EXAMPLE_NOT_A_REAL_KEY_0003;";
    if (cs) puts("Connected");
    return 0;
}
