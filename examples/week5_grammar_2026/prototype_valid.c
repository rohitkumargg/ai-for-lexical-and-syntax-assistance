int add(int a, int b);
void display(void);
short compute(long x, unsigned int y);

int add(int a, int b) {
    return a + b;
}

void display(void) {
    int s = add(2, 3);
}

int main() {
    display();
    return 0;
}
