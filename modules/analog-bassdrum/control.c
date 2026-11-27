/* Native source renderer + stock-page registration, derived from the measured
 * Machinedrum Part/chooser seams and the stock kind-table renderer ABI.
 * The synthesis is upstream of AMP and both FX slots: 808 and 909 on the DSP via ab_glue.asm.
 */
#include "engine.h"
#define U8(a) (*(volatile uint8_t *)(uintptr_t)(a))
#define U32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define BANK 0x46c82456u
#define PART_IDX 0x100b14cfu
#define PART_OFF 0x8ed80u
#define PART_STRIDE 0x18b2u
#define SIG 60u
#define DESC_SIZE 0x1cau
static uint8_t desc[2][DESC_SIZE] = {{0}};
uint32_t ab_desc_p = 0;
uint32_t ab_render_calls = 0, ab_hits = 0;
static unsigned signed_track(const volatile uint8_t *part, unsigned t) {
    const volatile uint8_t *s=part+SIG+30*t;
    return t<8 && part[0x22+t]==1 && s[0]=='A' && s[1]=='B' && s[2]==1;
}
/* Each core owns four independent voice slots, addressed by track. */
static volatile uint8_t *part_base(void) {
    return (volatile uint8_t *)(uintptr_t)(U32(BANK)+PART_OFF+(U8(PART_IDX)&3)*PART_STRIDE);
}
/* Track double-tap must not open FLEX's sample pool for a synthesized source. */
unsigned ab_selected_source(void) {
    unsigned track=U8(0x100b14ccu);
    return !U8(0x80000015u) && track<8 && signed_track(part_base(),track);
}
static void put32(uint8_t *p,uint32_t v) {
    p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v;
}
static void text(uint8_t *p,const char *s,unsigned n) {
    unsigned i=0; for (;i+1<n && s[i];++i) p[i]=(uint8_t)s[i];
    for (;i<n;++i) p[i]=0;
}
void ab_lpf_fmt(char *out,int value) {
    if(!value) { text((uint8_t*)out,"OFF",4); return; }
    if(value==64) { text((uint8_t*)out,"ORIG",5); return; }
    unsigned hz=ab_lpf_frequency((unsigned)value),n=0;
    char digits[5];
    do { digits[n++]=(char)('0'+hz%10); hz/=10; } while(hz && n<5);
    unsigned i=0; while(n) out[i++]=digits[--n]; out[i]=0;
}
static uint32_t page_for(unsigned model) {
    if (!ab_desc_p) {
        const volatile uint8_t *src=(const volatile uint8_t *)0x400d3176u;
        static const char *const names[2][12]={
            {"PITCH","DECAY","TONE","ATK","SWEEP","SAT","","ACCNT","LPF","LOW","HIGH","---"},
            {"PITCH","DECAY","TUNE","ATK","TDEP","SAT","","ACCNT","LPF","LOW","HIGH","---"}
        };
        for(unsigned m=0;m<2;++m) {
            uint8_t *d=desc[m];
            for(unsigned i=0;i<DESC_SIZE;++i) d[i]=src[i];
            text(d+0x3c,"SYN",5); text(d+0x41,"ANALOG BD",13);
            for(unsigned i=0;i<12;++i) {
                text(d+0x4e + 6*i,names[m][i],6);
                d[0x96+i]=ab_mc_defaults[i];
                put32(d+0xa2+4*i,0);
                put32(d+0xd2+4*i,i==6?0:128);
                put32(d+0x102+4*i,i==8 ? (uint32_t)(uintptr_t)ab_lpf_fmt:0);
                put32(d+0x132+4*i,0);
                put32(d+0x162+4*i,0);
            }
            put32(d+0x1c2,0x111); put32(d+0x1c6,0x10111111u);
        }
        ab_desc_p=(uint32_t)(uintptr_t)(desc[0]+0x38);
    }
    return (uint32_t)(uintptr_t)(desc[model!=0]+0x38);
}
/* MACHINES client (modules/machines): ANALOG BD's PLAYBACK page for a track. */
uint32_t ab_mc_page(const volatile uint8_t *type_ptr) {
    volatile uint8_t *part=part_base();
    uintptr_t track=(uintptr_t)type_ptr-(uintptr_t)(part+0x22);
    return page_for(track<8 ? part[0x1da+6+30*track] : 0);
}
/* ABI measured at 4000d430/4000d518. Every track is rendered twice per
 * frame around its event's sample offset; the second call has end=16.
 * Header: source count, ring start, Q26 source rate, Q26 read position.
 * Stock transport converts the high 24 bits of each L/R long to DSP words.
 */
int ab_render(unsigned track,unsigned ping,unsigned start,unsigned end) {
    if(track>=8 || !signed_track(part_base(),track)) {
        return ((int (*)(unsigned,unsigned,unsigned,unsigned))0x40004008u)(track,ping,start,end);
    }
    ++ab_render_calls;
    volatile uint32_t *cursor=(volatile uint32_t *)(uintptr_t)U32(0x80001c80u);
    volatile uint16_t *fp=(volatile uint16_t *)(uintptr_t)U32(0x800062a8u);
    uint8_t p[12];
    for(unsigned k=0;k<12;++k) {
        p[k]=k<6 ? (uint8_t)(fp[k]>>8)
                 : U8(0x80000810u+72*track+0x20+k-6);
    }
    /* The stock builder calls twice, before and after the event offset.
     * Reserve the same space as FLEX so every later track keeps its record
     * boundary. Once the second segment exists, replace the start with a
     * control record: two signature halves, trig flag, then twelve knobs.
     * The transport sends each long as high/low 16-bit DSP words. */
    {
        unsigned n=end>start && end<=16 ? end-start:0;
        for(unsigned i=0;i<4+2*n;++i) cursor[i]=0;
        if(end==16) {
            /* On the first hit the first renderer can still be stock FLEX.
             * Use the packer's fixed slot, not that second call's cursor. */
            volatile uint32_t *record=(volatile uint32_t *)(uintptr_t)
                (0x80001c90u+(ping&1)*0xa80u+336u*track);
            unsigned trig=(U8(0x46104d0cu+track)&16)!=0;
            record[0]=0xab090000u; record[1]=0x09090000u|trig;
            record[2]=record[3]=0;
            for(unsigned k=0;k<6;++k) record[4+k]=((uint32_t)p[2*k]<<16)|p[2*k+1];
            if(trig) ++ab_hits;
        }
        U32(0x80001c80u)=(uint32_t)(uintptr_t)(cursor+4+2*n);
        return 0;
    }
}

/* Sample-pool sized engine browser: stock list navigation and window chrome.
 * Pin the destination at open, so a track/Part change cannot edit another voice.
 * Entries retain the stored MODEL ids; adding a label alone never adds DSP code.
 */
static uint32_t engine_bank = 0;
static unsigned engine_part = 0, engine_track = 0;
void ab_engine_select(unsigned model) {
    unsigned track=engine_track, part=engine_part;
    if(model>1 || U32(BANK)!=engine_bank || (U8(PART_IDX)&3)!=part ||
       U8(0x100b14ccu)!=track || !ab_selected_source()) return;
    unsigned offset=0x1da+6+30*track;
    part_base()[offset]=(uint8_t)model;
    U8(0x100a4eceu+PART_STRIDE*part+offset)=(uint8_t)model;
    U8(0x80000830u+72*track)=(uint8_t)model;
    /* Same dirty flags and bank notification as the stock SRC SETUP editor. */
    U8(engine_bank+0x95048u)|=(uint8_t)(1u<<part);
    U8(0x100b145eu)|=(uint8_t)(1u<<part);
    U32(engine_bank+0x9b332u)=1;
    U32(0x100f8598u)=1;
    ((void (*)(void))0x40027e00u)();
    mc_publish();
    ((void (*)(int))0x4004d948u)(-1);   /* -1 = the current track, as stock calls it */
}
static void engine_808(void) { ab_engine_select(0); }
static void engine_909(void) { ab_engine_select(1); }
static const char *const engine_labels[]={"001 808", "002 909"};
unsigned ab_engine_draw(void) {
    uint32_t window=U32(0x460e5e30u);
    if(!window || U32(0x460e5e2cu)!=(uint32_t)(uintptr_t)engine_labels) return 0;
    void *surface=(void *)(uintptr_t)(window+0x24);
    ((void (*)(void *))0x4003567cu)(surface);
    int height=(int)U32(window+0x28);
    for(unsigned row=0;row<sizeof(engine_labels)/sizeof(engine_labels[0]);++row) {
        int y=height-23-7*(int)row;
        ((void (*)(uint32_t,void *,int,int,int,const char *))0x40012bd8u)
            (0x400ba876u,surface,5,y,-1,engine_labels[row]);
        if(row==U32(0x460e5e40u))
            ((void (*)(void *,int,int,int,int,int))0x40012254u)
                (surface,3,y-1,(int)U32(window+0x24)-5,y+5,-1);
    }
    U32(0x46c7c72cu)=1;
    return 1;
}
void ab_engine_open(void) {
    static void (*const handlers[])(void)={engine_808, engine_909};
    if(!ab_selected_source() || U32(0x460e5e30u)) return;
    engine_bank=U32(BANK);
    engine_part=U8(PART_IDX)&3;
    engine_track=U8(0x100b14ccu);
    unsigned model=part_base()[0x1da+6+30*engine_track]!=0;
    /* Use the stock sample pool's 110 x 64 window at x=-1, y=0.
     * The stock list controller supplies arrows, LEVEL, YES and NO; only
     * its row content and drawing differ from the ordinary sample browser.
     */
    ((void (*)(uint32_t,unsigned,unsigned))0x4007ec60u)
        (0x460e5e38u,6,sizeof(engine_labels)/sizeof(engine_labels[0]));
    ((void (*)(uint32_t,unsigned))0x4007edb0u)(0x460e5e38u,model);
    U32(0x460e5e28u)=(uint32_t)(uintptr_t)handlers;
    U32(0x460e5e2cu)=(uint32_t)(uintptr_t)engine_labels;
    U32(0x460e5e34u)=0;
    uint32_t window=((uint32_t (*)(int,int,int,int,int,uint32_t))0x4005829cu)
        (110,64,-1,0,1,0x4006d754u);
    U32(0x460e5e30u)=window;
    if(!window) return;
    ((void (*)(uint32_t,const char *,unsigned))0x400570b8u)(window,"\xab MACHINE:ANALOG BD",0);
    ((void (*)(uint32_t))0x40031494u)(0x400ce0c4u);
    ab_engine_draw();
}

/* Horizontal navigation mirrors STATIC/FLEX: LEFT returns to the machine
 * column, RIGHT on the signed Analog BD row returns to its engine pool.
 * Other generic lists keep their original no-op LEFT binding. */
extern void ab_stock_pool_open(void);
void ab_engine_left(void) {
    if(!U32(0x460e5e30u) ||
       U32(0x460e5e2cu)!=(uint32_t)(uintptr_t)engine_labels) return;
    ((void (*)(void))0x4006d754u)();
    ab_stock_pool_open();
    ((void (*)(void))0x4007893cu)();
}
extern const uint32_t ab_mc_row;           /* our row on the machine list (MACHINES) */
void ab_engine_right(unsigned key,unsigned value) {
    if(U32(0x460e70e0u) && !U32(0x460e739au) &&
       U32(0x460e738eu)==ab_mc_row && ab_selected_source()) {
        ((void (*)(void))0x400789e4u)();
        ab_engine_open();
        return;
    }
    ((void (*)(unsigned,unsigned))0x4007909cu)(key,value);
}
