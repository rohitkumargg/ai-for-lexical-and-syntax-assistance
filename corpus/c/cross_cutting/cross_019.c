#include <stdio.h>
#include <string.h>

int check_pass(const char *buf) {
    int password_len = (int)strlen(buf);
    int password_buffer_size = 64;
    if (password_len > password_buffer_size) {
        return 0;
    }
    return 1;
}

int main(void) {
    printf("Result: %d\n", check_pass("test"));
    return 0;
}

