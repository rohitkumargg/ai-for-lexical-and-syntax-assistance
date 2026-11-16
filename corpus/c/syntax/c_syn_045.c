struct Config {
    int timeout
    int retries;
};
int main(void) {
    struct Config c = {10, 3};
    return c.retries;
}
