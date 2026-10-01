int main() {
    int a = 5;
    int b = 3;
    int r1 = a & b;
    int r2 = a | b;
    int r3 = a ^ b;
    int r4 = ~a;
    int r5 = a << 1;
    int r6 = a >> 1;
    return r1 + r2 + r3 + r4 + r5 + r6;
}
