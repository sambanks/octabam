| LAZY CHOP TEMPO -- one DRAM unit. GNU as, ColdFire (m68k-elf-as -mcpu=54455). (8thmyth, Nov 2026)
|
| After YES in LAZY CHOP: the slice-count popup as before, then the tempo the
| chops point to, displayed until the next key. Nothing is written to the sample.
|
| Entry points:
|  ct_after_yes  a0 = the chopped slot's record; called by LAZY CHOP at YES
