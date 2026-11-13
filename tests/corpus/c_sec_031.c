#include <fcntl.h>
#include <unistd.h>
int main(void) {
    int fd = open("secure.dat", O_CREAT | O_WRONLY, 0777);
    if (fd >= 0) close(fd);
    return 0;
}
