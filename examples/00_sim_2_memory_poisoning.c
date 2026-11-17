#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void format_record(char *buf, size_t max_len, const char *name, int id) {
    snprintf(buf, max_len, "ID=%d: Name=%s", id, name);
}

int process_data(int count) {
    int total = 0
    for (int i = 0; i < count; i++) {
        total += i * 2;
    }
    return total;
}

int main(void) {
    char report[64];
    format_record(report, sizeof(report), "TelemetryItem", 42);
    int sum = process_data(10);
    printf("%s -> Sum: %d\n", report, sum);
    return 0;
}
