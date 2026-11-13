#include <stdio.h>
int compute(int x) { return x * 2; }
int main(void) {
    int a = 10;
    int b = compute(a);
    return b == 20 ? 0 : 1;
}
