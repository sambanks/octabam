/* The host build of engine.c driven by ref_wavecf.py's stream.
 * usage: drive cmds.bin table.bin out.i32  (out: big-endian int32, as the ColdFire run writes it) */
#include "../wcf.h"
#include <stdio.h>
#include <stdlib.h>

static uint32_t be(const unsigned char *p) { return (uint32_t)p[0] << 24 | p[1] << 16 | p[2] << 8 | p[3]; }

int main(int argc, char **argv)
{
    static int16_t table[(NFR + 1) * FLEN];
    FILE *ft = fopen(argv[2], "rb");
    unsigned char two[2];
    for (int i = 0; i < (NFR + 1) * FLEN; ++i) { if (fread(two, 1, 2, ft) != 2) return 1; table[i] = (int16_t)(two[0] << 8 | two[1]); }
    fclose(ft);
    FILE *fc = fopen(argv[1], "rb"), *fo = fopen(argv[3], "wb");
    static Engine e;
    wcf_init(&e, table);
    unsigned char hdr[4], rec[16];
    int32_t blk[16];
    while (fread(hdr, 1, 4, fc) == 4) {
        uint32_t n = be(hdr);
        for (uint32_t i = 0; i < n; ++i) {
            if (fread(rec, 1, 16, fc) != 16) return 1;
            uint32_t op = be(rec), a = be(rec + 4), b = be(rec + 8), c = be(rec + 12);
            if (op == 0) eng_pos(&e, (int32_t)a);
            else if (op == 1) eng_on(&e, (int)a, b, (int32_t)c);
            else if (op == 2) eng_off(&e, (int)a);
            else if (op == 3) eng_adsr(&e, (int32_t)a, (int32_t)b);
            else if (op == 6) wcf_setup(&e, a & 0xff, (a >> 8) & 0xff, (a >> 16) & 0xff, (a >> 24) & 0xff, b & 0xff, (b >> 8) & 0xff);
            else if (op == 7) wcf_scale(&e, a);
            else if (op == 8) wcf_amp(&e, a & 0xff, (a >> 8) & 0xff, (a >> 16) & 0xff, (a >> 24) & 0xff);
            else if (op == 9) wcf_clock(&e, (int)a);
            else if (op == 4) wcf_note(&e, (int32_t)a, (int)b, (int)c);
            else if (op == 5) wcf_knobs(&e, (int)a, (int)b, (int)c);
        }
        eng_render(&e, blk, 16);
        for (int i = 0; i < 16; ++i) { unsigned char o[4] = {(uint32_t)blk[i] >> 24, (uint32_t)blk[i] >> 16, (uint32_t)blk[i] >> 8, (uint32_t)blk[i]}; fwrite(o, 1, 4, fo); }
    }
    fclose(fo);
    return 0;
}
