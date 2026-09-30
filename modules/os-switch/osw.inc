| OS SWITCH -- the addresses both units share, and the gate reads
| (tools/verify/verify_osswitch.py parses the `.set` lines of this file).
|
| The stage is the top of octabam's platform reserve (tools/remix/arena.py:
| the first 1,707 pages of stock's audio page arena, 0x40a955e0..0x41495de0,
| in every remix that carries a DRAM unit). Stock never touches the reserve
| (docs/contributing/PLACEMENT.md), and nothing between a reset and the OS
| entry's `movea.l #0x48000000,%sp` writes SDRAM above the image the
| bootstrap depacks (read from the bootstrap's copy in the image,
| docs/proposals/FIRMWARE_SWITCHER.md). Every address is the UNCACHED
| alias (+0x08000000): the running OS has the D-cache on, copyback, over
| the cached window, and the stage must be in DRAM, not in a line, when the
| unit resets.

        .set    OSW_MBOX,    0x49200000     | the mailbox, 64 bytes
        .set    OSW_STUB,    0x49200100     | the copy stub runs here, outside the image it overwrites
        .set    OSW_BODY,    0x49200400     | the chainloader's body, placed by the switcher (chain.s is the ROM gate)
        .set    OSW_BODYMAX, 0x00000200     | its length in longs, at most (2 KB, below OSW_IMG)
        .set    OSW_IMG,     0x49201000     | the staged image
        .set    OSW_END,     0x49495de0     | the reserve's end
        .set    OSW_MAXLEN,  0x00294be0     | OSW_END - OSW_IMG - 512: a last partial sector reads whole
        .set    OSW_MAGIC,   0x4f535731     | "OSW1"

| mailbox fields
        .set    MB_MAGIC,    0              | OSW_MAGIC while a switch is pending; cleared before anything runs
        .set    MB_LEN,      4              | the image's length in bytes
        .set    MB_HASH,     8              | rolling x33 over the image (loader.S's hash)
        .set    MB_CHECK,    12             | MAGIC ^ LEN ^ HASH: random DRAM is not a mailbox
        .set    MB_STATUS,   16             | written by the chainloader at every boot (below)
        .set    MB_RESET,    20             | written by the switcher: the last reset path it reached
        .set    MB_NAME,     24             | the file's name, NUL-terminated, 32 bytes
        .set    MB_PARK,     56             | the DSP cores that took the park command: bit 0 core 0, bit 1 core 1
        .set    MB_BODYLEN,  60             | the body's length in longs
        .set    MB_BODYSUM,  64             | the sum of its longs: the gate runs it only whole
        .set    MB_FLASH,    68             | the FLASHED image's name, 16 bytes: written by a switch from it, carried by a switch from a switched image

| status words (MB_STATUS)
        .set    ST_BOOT,     0x424f4f54     | "BOOT" handed over to the staged image
        .set    ST_RUN,      0x52554e20     | "RUN " the boot after a BOOT: this image came from the stage
        .set    ST_NONE,     0x4e4f4e45     | "NONE" no mailbox (a power-on, or the stage did not survive)
        .set    ST_SIZE,     0x53495a45     | "SIZE" length 0 or past OSW_MAXLEN
        .set    ST_BVER,     0x42564552     | "BVER" its bootstrap version is not NOR's: it would reflash the bootstrap
        .set    ST_HASH,     0x48415348     | "HASH" the stage changed between the switch and the boot

| reset paths (MB_RESET): which one the switcher reached before the unit reset
        .set    RS_SPIN,     0x5350494e     | "SPIN" armed: interrupts masked, the panel being reset (build 1: a stock spin)
        .set    RS_RCR,      0x52435220     | "RCR " the reset controller's soft reset requested

| the stock facts (docs/proposals/FIRMWARE_SWITCHER.md, read from the 1.40C image)
        .set    OS_ENTRY,    0x40000400     | where the bootstrap depacks the OS and what it calls
        .set    OS_ARGCELL,  0x400b9650     | the entry parks the bootstrap's argument here first
        .set    OS_RESUME,   0x40000418     | the instruction after the entry's `movea.l #0x48000000,%sp`
        .set    OS_VEROFF,   0x000de648     | 0x400dea48 - OS_ENTRY: the bootstrap version the image carries
        .set    NOR_BOOTVER, 0x00003ffc     | the bootstrap version NOR holds
        .set    CACR_OFF,    0x00040100     | BCINVA | ICINVA, both caches off
        .set    CACR_BOOT,   0x0008c000     | what the bootstrap leaves in CACR when it calls the entry (0x22dc)
