int test_depth(int a, int b, int c, int d, int e) {
    if (a) if (b) if (c) if (d) if (e) return 1;
    return 0;
}
int main(void) { return test_depth(1,1,1,1,1); }
