char *strcpy(char *dest, char *src);
int main() {
    char dst[20];
    char src[20];
    snprintf(dst, sizeof(dst), "%s", src);
    return 0;
}