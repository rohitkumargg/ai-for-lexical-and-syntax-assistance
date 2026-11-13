#define SWAP(a, b) do { \
    int _tmp = (a); \
    (a) = (b); \
    (b) = _tmp; \
} while(0)
int main(void) {
    int x = 1, y = 2;
    SWAP(x, y);
    return x;
}
