#include <stdio.h>
#include <stdarg.h>
void log_msg(const char *fmt, ...) {
    char buf[128];
    va_list ap;
    va_start(ap, fmt);
    vsprintf(buf, fmt, ap);
    va_end(ap);
    puts(buf);
}
int main(void) {
    log_msg("Hello %d", 123);
    return 0;
}
