struct Point { int x; };
int main(void) {
    struct Point pt = {1};
    int *p = 0;
    return (p == pt);
}
