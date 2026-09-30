# octabam DOOM: doomgeneric (upstream/, GPL-2.0) + the Octatrack platform
# (octa/), compiled for the MCF54455 and partially linked into ONE
# relocatable object, doom.o, that the platform build links with every
# other DRAM unit (tools/remix/platform_build.py: a Linked source ending
# in .o is made here first, then linked as is). No libc is installed for
# m68k-elf here, so octa/libc.c is a small freestanding one.
CC      = m68k-elf-gcc
LD      = m68k-elf-ld
UP      = upstream/doomgeneric
B       = build
CFLAGS  = -mcpu=54455 -O2 -fno-common -ffreestanding -fno-builtin-printf \
          -fomit-frame-pointer -nostdinc -isystem octa/include \
          -isystem $(shell $(CC) -print-file-name=include) \
          -DDOOMGENERIC_RESX=320 -DDOOMGENERIC_RESY=200 \
          -w
DOOM    = dummy am_map doomdef doomstat dstrings d_event d_items d_iwad d_loop \
          d_main d_mode d_net f_finale f_wipe g_game hu_lib hu_stuff info i_cdmus \
          i_endoom i_joystick i_scale i_sound i_system i_timer memio m_argv m_bbox \
          m_cheat m_config m_controls m_fixed m_menu m_misc m_random p_ceilng \
          p_doors p_enemy p_floor p_inter p_lights p_map p_maputl p_mobj p_plats \
          p_pspr p_saveg p_setup p_sight p_spec p_switch p_telept p_tick p_user \
          r_bsp r_data r_draw r_main r_plane r_segs r_sky r_things sha1 sounds \
          statdump st_lib st_stuff s_sound tables v_video wi_stuff w_checksum \
          w_file w_main w_wad z_zone w_file_stdc i_input i_video doomgeneric
OCTA    = doom_octa libc mono
OBJS    = $(addprefix $(B)/,$(addsuffix .o,$(DOOM))) \
          $(addprefix $(B)/octa_,$(addsuffix .o,$(OCTA))) $(B)/octa_entry.o

doom.o: $(OBJS)
	$(LD) -r -o $(B)/doom_r.o $(OBJS) $(shell $(CC) -mcpu=54455 -print-libgcc-file-name)
	@# .bss as zeros IN the image: the platform loader depacks the raw
	@# binary and nothing else zeroes memory past it (and a DRAM unit's
	@# bss would sit on the runtime's own stage)
	m68k-elf-objcopy --strip-debug --rename-section .bss=.data.zero,alloc,load,contents,data $(B)/doom_r.o $@
	@if m68k-elf-nm -u $@ | grep -v -E ' (osw_reset|osw_bootpick|osw_bootfiles)$$'; then \
	  echo "doom.o: undefined symbols above"; rm -f $@; exit 1; fi

$(B)/%.o: $(UP)/%.c | $(B)
	$(CC) $(CFLAGS) -c -o $@ $<
$(B)/octa_%.o: octa/%.c octa/octa.h | $(B)
	$(CC) $(CFLAGS) -I$(UP) -c -o $@ $<
$(B)/octa_entry.o: octa/entry.S | $(B)
	$(CC) -mcpu=54455 -c -o $@ $<
$(B):
	mkdir -p $(B)
clean:
	rm -rf $(B) doom.o
.PHONY: clean
