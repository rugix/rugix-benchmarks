/* Prepare RAUC's documented raw 4 KiB SHA-256 index outside timed installs. */
#include <openssl/sha.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    FILE *src = fopen(argv[1], "rb"), *out = fopen(argv[2], "wb");
    if (!src || !out) { perror("open"); return 1; }
    unsigned char block[4096], hash[SHA256_DIGEST_LENGTH];
    SHA256_CTX ctx;
    SHA256_Init(&ctx);
    size_t total = 0, n;
    while ((n = fread(block, 1, sizeof(block), src)) != 0) {
        if (n != sizeof(block)) return 3;
        SHA256(block, n, hash);
        SHA256_Update(&ctx, block, n);
        if (fwrite(hash, 1, sizeof(hash), out) != sizeof(hash)) return 4;
        total += n;
    }
    if (ferror(src) || fflush(out) || fsync(fileno(out)) || fclose(out)) return 5;
    SHA256_Final(hash, &ctx);
    for (size_t i = 0; i < sizeof(hash); ++i) printf("%02x", hash[i]);
    printf(" %zu\n", total);
    fclose(src);
    return 0;
}
