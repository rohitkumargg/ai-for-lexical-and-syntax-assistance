#include <stdlib.h>
int main(void) {
    int secret_token = rand() % 10000;
    return secret_token;
}
