int eval(int x) {
    if (x > 0) {
        if (x > 10) {
            return 100;
        }
    }
    return 0;
}
int main(void) {
    return eval(15);
}
