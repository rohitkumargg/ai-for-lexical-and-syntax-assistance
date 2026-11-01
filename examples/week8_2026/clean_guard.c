int main() {
    int a[10];
    char buf[100];
    char dst[10];
    int *p = NULL;
    long long big = (long long)2147483647 + 1;
    int n = 0;
    for (int i = 0; i < 10; i++) {
        a[i] = i;
    }
    if (p != NULL) {
        *p = 1;
    }
    scanf("%99s", buf);
    memcpy(dst, buf, sizeof(dst));
    printf("%d %s %lld\n", a[0], buf, big);
    return n;
}
