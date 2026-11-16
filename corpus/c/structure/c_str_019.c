#include <stdio.h>

int compute_step_0(int x) {
    int temp = x + 0;
    int res = temp * 2;
    return res;
}

int compute_step_1(int x) {
    int temp = x + 1;
    int res = temp * 2;
    return res;
}

int compute_step_2(int x) {
    int temp = x + 2;
    int res = temp * 2
    return res;
}

int compute_step_3(int x) {
    int temp = x + 3;
    int res = temp * 2;
    return res;
}

int main(void) {
    int total = 0;
    total += compute_step_0(0);
    total += compute_step_1(1);
    total += compute_step_2(2);
    total += compute_step_3(3);
    return total;
}
