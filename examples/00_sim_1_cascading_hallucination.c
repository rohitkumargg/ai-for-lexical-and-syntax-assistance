#include <stdio.h>
#include <string.h>

int compute_factorial(int n) {
    if (n <= 1) return 1;
    return n * compute_factorial(n - 1);
}

int calculate_discount(int price, int percent) {
    int discount = (price * percent) / 100
    return price - discount;
}

int main(void) {
    int p = 250;
    int f = compute_factorial(5);
    int final_price = calculate_discount(p, 10);
    printf("Factorial: %d, Final: %d\n", f, final_price);
    return 0;
}
