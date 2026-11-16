struct Point { int x; };
int main(void) {
    struct Point pt = {1};
    int *p = pt;
    return (p != 0);
}
