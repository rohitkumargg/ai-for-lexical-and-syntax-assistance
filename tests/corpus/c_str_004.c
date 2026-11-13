int add(int a, int b) { return a + b; }
int main(void) {
    int (*fn)(int, int) = add
    return fn(2, 3);
}
