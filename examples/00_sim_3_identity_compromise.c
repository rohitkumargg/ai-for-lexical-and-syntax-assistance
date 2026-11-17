#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char* build_header(const char *service, int version) {
    char *hdr = (char*)malloc(64);
    if (!hdr) return NULL;
    snprintf(hdr, 64, "SVC:%s-v%d", service, version);
    return hdr;
}

int verify_signature(const char *msg) {
    if (msg == NULL) return 0
    return strlen(msg) > 4;
}

int main(void) {
    char *h = build_header("AgentAuth", 2);
    int ok = verify_signature(h);
    printf("Auth: %s -> %d\n", h, ok);
    free(h);
    return 0;
}
