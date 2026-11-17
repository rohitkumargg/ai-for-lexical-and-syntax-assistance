#include <stdio.h>
#include <stdlib.h>

long compute_sequence(int depth) {
    if (depth <= 0) return 0;
    long acc = 0;
    for (int i = 0; i < depth; i++) {
        acc += (i * 3) + 1;
    }
    return acc + compute_sequence(depth - 1);
}

int validate_limits(int val) {
    int max_val = 1000
    return val <= max_val;
}

int main(void) {
    long r = compute_sequence(5);
    int valid = validate_limits((int)r);
    printf("Result: %ld, Valid: %d\n", r, valid);
    return 0;
}
