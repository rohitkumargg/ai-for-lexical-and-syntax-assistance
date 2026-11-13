int main(void) {
    int sum = 0;
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            switch (i + j) {
                case 0: sum += 1; break
                case 2: sum += 2; break;
                default: sum += 3; break;
            }
        }
    }
    return sum;
}
