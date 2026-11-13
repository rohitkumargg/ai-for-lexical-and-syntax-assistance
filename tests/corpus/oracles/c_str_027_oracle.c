typedef int (*OpFunc)(int, int);
int do_op(int a, int b, OpFunc f) { return f(a, b); }
int sub(int a, int b) { return a - b; }
int main(void) { return do_op(10, 4, sub); }
