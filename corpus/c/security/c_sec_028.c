#include <stdlib.h>
int main(void) {
    int arr[10];
    int *p = arr + 500;
    return (p != NULL);
}
