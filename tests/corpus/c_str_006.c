static int counter(void) {
    static int count = 0
    return ++count;
}
int main(void) {
    return counter();
}
