#include <stdint.h>

typedef struct {
    uint32_t position;
    uint32_t step;
    uint32_t phase;
    uint32_t phase_step;
    uint32_t remaining;
    uint32_t cache_start;
    uint32_t cache_frames;
    uint32_t cache_data;
    uint32_t subposition;
} GrGrain;

typedef struct {
    uint32_t active;
    uint32_t slot;
    uint32_t sample_frames;
    uint32_t bytes_per_frame;
    uint32_t scan_position;
    uint32_t scan_step;
    uint32_t grain_frames;
    uint32_t hop_frames;
    uint32_t density;
    uint32_t scatter_frames;
    uint32_t until_spawn;
    uint32_t next_grain;
    uint32_t random;
    GrGrain grains[4];
} GrTrack;

#define TRACKS 8
#define GRAIN_COUNT 4
#define VOICE_BASE 0x800049d8u
#define VOICE_STRIDE 0xa8u
#define FP_POINTER 0x800062a8u
#define CURSOR_POINTER 0x80001c80u
#define NIBBLE_BASE 0x46104d0cu
#define BANK_POINTER 0x46c82456u
#define PART_INDEX 0x100b14cfu
#define PART_SIZE 6322u
#define SLOT_OFFSET 0x8f04bu
#define SETTINGS_BASE 0x100b14f0u
#define SETTINGS_STRIDE 0x448u
#define POOL_STATE 0x46c922c4u
#define POOL_STATE_STRIDE 44u
#define RENDER_STATE_POINTER 0x800062a4u
#define POSITION_SHIFT 8u
#define POSITION_ONE (1u << POSITION_SHIFT)
#define FLEX_PLAYBACK 0x400d31aeu
#define FLEX_PLAYBACK_SIZE 0x192u
#define PAGE_TITLE_OFFSET 0x009u
#define PAGE_NAMES_OFFSET 0x016u
#define PAGE_DEFAULTS_OFFSET 0x05eu
#define PAGE_MIN_OFFSET 0x06au
#define PAGE_COUNT_OFFSET 0x09au
#define PAGE_FORMATTERS_OFFSET 0x0cau
#define PAGE_WIDGETS_OFFSET 0x0fau
#define PAGE_HANDLERS_OFFSET 0x12au
#define STOCK_RENDERER 0x40004008u
#define POOL_READ_DIRECTION 1u
#define PITCH_MIN 4u
#define PITCH_MAX 124u

/* Q16 rates: stock FLEX uses five raw units per semitone, centred on 64. */
static const uint32_t gr_pitch_steps[PITCH_MAX - PITCH_MIN + 1u] = {
    32768u, 33149u, 33534u, 33924u, 34318u, 34716u, 35120u, 35528u,
    35941u, 36358u, 36781u, 37208u, 37641u, 38078u, 38520u, 38968u,
    39421u, 39879u, 40342u, 40811u, 41285u, 41765u, 42250u, 42741u,
    43238u, 43740u, 44248u, 44762u, 45283u, 45809u, 46341u, 46879u,
    47424u, 47975u, 48533u, 49097u, 49667u, 50244u, 50828u, 51419u,
    52016u, 52620u, 53232u, 53850u, 54476u, 55109u, 55749u, 56397u,
    57052u, 57715u, 58386u, 59064u, 59751u, 60445u, 61147u, 61858u,
    62576u, 63304u, 64039u, 64783u, 65536u, 66297u, 67068u, 67847u,
    68635u, 69433u, 70240u, 71056u, 71882u, 72717u, 73562u, 74416u,
    75281u, 76156u, 77041u, 77936u, 78841u, 79758u, 80684u, 81622u,
    82570u, 83530u, 84500u, 85482u, 86475u, 87480u, 88497u, 89525u,
    90565u, 91617u, 92682u, 93759u, 94848u, 95950u, 97065u, 98193u,
    99334u, 100488u, 101656u, 102837u, 104032u, 105241u, 106464u, 107701u,
    108952u, 110218u, 111499u, 112794u, 114105u, 115431u, 116772u, 118129u,
    119501u, 120890u, 122295u, 123715u, 125153u, 126607u, 128078u, 129567u,
    131072u,
};

GrTrack gr_state[TRACKS] = {0};
uint8_t gr_page_descriptor[FLEX_PLAYBACK_SIZE] = {0};
uint32_t gr_page_ready = 0;

void gr_pool_read(uint32_t slot, uint32_t frame, uint32_t *data, uint32_t *frames);

static uint32_t gr_slot_for(uint32_t bank, uint32_t part, uint32_t track)
{
    uint32_t offset = part * PART_SIZE + SLOT_OFFSET + track * 5u;
    if (bank == 0u || part >= 16u || track >= TRACKS)
        return 0xffu;
    return *(volatile uint8_t *)(bank + offset);
}

static int gr_name_matches(uint32_t slot)
{
    volatile uint8_t *name;
    volatile uint8_t *base;
    uint32_t i;
    uint32_t c;

    if (slot >= 128u)
        return 0;
    name = (volatile uint8_t *)(SETTINGS_BASE + slot * SETTINGS_STRIDE);
    base = name;
    for (i = 0; i < 255u && name[i] != 0; ++i)
        if (name[i] == '/')
            base = name + i + 1u;
    for (i = 0; i < 4u; ++i) {
        c = base[i];
        if (c == 0u)
            return 0;
        if (c >= 'a' && c <= 'z')
            c -= 'a' - 'A';
        if (c != (uint32_t)"GRAN"[i])
            return 0;
    }
    return 1;
}

uint32_t gr_resolve_page(uint32_t stock, uint32_t bank, uint32_t part,
                         uint32_t track)
{
    static const uint8_t names[36] = {
        'P','T','C','H',0,0, 'S','C','A','N',0,0,
        'S','I','Z','E',0,0, 'S','P','E','E','D',0,
        'D','E','N','S',0,0, 'S','C','A','T',0,0
    };
    static const uint8_t defaults[6] = {64, 0, 48, 64, 80, 0};
    volatile uint8_t *descriptor;
    volatile uint8_t copied_byte;
    volatile uint32_t *words;
    uint32_t slot;
    uint32_t i;

    if (stock != FLEX_PLAYBACK || track >= TRACKS)
        return stock;
    slot = gr_slot_for(bank, part, track);
    if (!gr_name_matches(slot))
        return stock;

    if (!gr_page_ready) {
        descriptor = (volatile uint8_t *)gr_page_descriptor;
        for (i = 0; i < FLEX_PLAYBACK_SIZE; ++i) {
            copied_byte = ((volatile uint8_t *)FLEX_PLAYBACK)[i];
            descriptor[i] = copied_byte;
        }

        descriptor = (volatile uint8_t *)gr_page_descriptor;
        descriptor[PAGE_TITLE_OFFSET + 0] = 'G';
        descriptor[PAGE_TITLE_OFFSET + 1] = 'R';
        descriptor[PAGE_TITLE_OFFSET + 2] = 'A';
        descriptor[PAGE_TITLE_OFFSET + 3] = 'N';
        descriptor[PAGE_TITLE_OFFSET + 4] = 'U';
        descriptor[PAGE_TITLE_OFFSET + 5] = 'L';
        descriptor[PAGE_TITLE_OFFSET + 6] = 'A';
        descriptor[PAGE_TITLE_OFFSET + 7] = 'R';
        descriptor[PAGE_TITLE_OFFSET + 8] = 0;
        for (i = 0; i < sizeof(names); ++i)
            descriptor[PAGE_NAMES_OFFSET + i] = names[i];
        for (i = 0; i < 6u; ++i)
            descriptor[PAGE_DEFAULTS_OFFSET + i] = defaults[i];
        for (i = 0; i < 6u; ++i) {
            words = (volatile uint32_t *)(descriptor + PAGE_MIN_OFFSET + i * 4u);
            *words = i == 0u ? PITCH_MIN : 0u;
            words = (volatile uint32_t *)(descriptor + PAGE_COUNT_OFFSET + i * 4u);
            *words = i == 0u ? PITCH_MAX - PITCH_MIN + 1u : 128u;
            words = (volatile uint32_t *)(descriptor + PAGE_FORMATTERS_OFFSET + i * 4u);
            if (i != 0u)
                *words = 0;
            words = (volatile uint32_t *)(descriptor + PAGE_WIDGETS_OFFSET + i * 4u);
            *words = 0;
            words = (volatile uint32_t *)(descriptor + PAGE_HANDLERS_OFFSET + i * 4u);
            if (i != 0u)
                *words = 0;
        }
        gr_page_ready = 1u;
    }
    return (uint32_t)gr_page_descriptor;
}

static uint32_t gr_param(uint32_t parameters, uint32_t index)
{
    return (*(volatile uint16_t *)(parameters + index * 2u) >> 8) & 127u;
}

static uint32_t gr_pitch_step(uint32_t pitch)
{
    if (pitch < PITCH_MIN)
        pitch = PITCH_MIN;
    if (pitch > PITCH_MAX)
        pitch = PITCH_MAX;
    return gr_pitch_steps[pitch - PITCH_MIN];
}

static uint32_t gr_sample_meta(GrTrack *state, uint32_t slot)
{
    volatile uint32_t *record;
    uint32_t flags;

    record = (volatile uint32_t *)(POOL_STATE + slot * POOL_STATE_STRIDE);
    flags = record[0];
    state->sample_frames = record[4];
    if (state->sample_frames > 0x00ffffffu)
        state->sample_frames = 0x00ffffffu;
    state->bytes_per_frame = ((flags & 2u) ? 2u : 3u) * ((flags & 1u) ? 2u : 1u);
    return state->sample_frames != 0u;
}

static uint32_t gr_read_sample(GrTrack *state, GrGrain *grain, uint32_t frame)
{
    uint32_t data;
    uint32_t frames;
    uint32_t bytes_per_sample;
    uint32_t byte_offset;
    volatile uint8_t *sample;
    uint32_t left;
    uint32_t right;

    if (frame >= state->sample_frames)
        return 0;
    if (frame < grain->cache_start ||
        frame - grain->cache_start >= grain->cache_frames) {
        gr_pool_read(state->slot, frame, &data, &frames);
        if (data == 0u || frames == 0u)
            return 0;
        grain->cache_start = frame;
        grain->cache_frames = frames;
        grain->cache_data = data;
    }

    byte_offset = (frame - grain->cache_start) * state->bytes_per_frame;
    sample = (volatile uint8_t *)(grain->cache_data + byte_offset);
    /* Both pool formats are big-endian; interpolation uses their top 16 bits. */
    left = ((uint32_t)sample[0] << 8) | sample[1];
    if (state->bytes_per_frame < 4u)
        return (left << 16) | left;
    bytes_per_sample = state->bytes_per_frame / 2u;
    right = ((uint32_t)sample[bytes_per_sample] << 8) |
            sample[bytes_per_sample + 1u];
    return (left << 16) | right;
}

static void gr_spawn(GrTrack *state, GrGrain *grain,
                    uint32_t grain_frames, uint32_t pitch,
                    uint32_t scatter)
{
    uint32_t span;
    int32_t random_offset;
    int32_t start;
    uint32_t max_start;

    state->random = state->random * 1664525u + 1013904223u;
    span = state->sample_frames / 1016u * scatter;
    span += state->sample_frames % 1016u * scatter / 1016u;
    random_offset = span ? (int32_t)(state->random % (span * 2u + 1u)) -
                           (int32_t)span : 0;
    start = (int32_t)(state->scan_position >> POSITION_SHIFT) + random_offset;
    if (start < 0)
        start = 0;
    max_start = state->sample_frames > grain_frames ?
                state->sample_frames - grain_frames : 0u;
    if ((uint32_t)start > max_start)
        start = (int32_t)max_start;

    grain->position = (uint32_t)start << POSITION_SHIFT;
    grain->step = pitch;
    grain->subposition = 0u;
    grain->phase = 0u;
    grain->phase_step = 65536u / grain_frames;
    grain->remaining = grain_frames;
    grain->cache_frames = 0u;
}

static void gr_configure(GrTrack *state, uint32_t parameters)
{
    uint32_t size = gr_param(parameters, 2u);
    uint32_t speed = gr_param(parameters, 3u);
    uint32_t density = gr_param(parameters, 4u);
    uint32_t scatter = gr_param(parameters, 5u);

    state->grain_frames = 64u + size * 8128u / 127u;
    state->density = 1u + density * 4u / 128u;
    state->hop_frames = state->grain_frames / state->density;
    if (state->hop_frames == 0u)
        state->hop_frames = 1u;
    state->scan_step = speed * 4u;
    state->scatter_frames = scatter;
}

static void gr_begin(GrTrack *state, uint32_t slot, uint32_t parameters,
                     uint32_t track)
{
    uint32_t start;
    uint32_t scan_limit;
    uint32_t i;

    state->active = 0u;
    state->slot = slot;
    if (!gr_sample_meta(state, slot))
        return;

    gr_configure(state, parameters);
    start = gr_param(parameters, 1u);
    scan_limit = state->sample_frames > state->grain_frames ?
                 state->sample_frames - state->grain_frames : 0u;
    state->scan_position =
        (scan_limit / 127u * start + scan_limit % 127u * start / 127u) <<
        POSITION_SHIFT;
    state->random = 0x9e3779b9u ^ slot ^ (track * 0x45d9f3bu);
    state->until_spawn = 0u;
    state->next_grain = 0u;
    for (i = 0; i < GRAIN_COUNT; ++i)
        state->grains[i].remaining = 0u;
    state->active = 1u;
}

static int32_t gr_interpolate(int16_t first, int16_t second, uint32_t fraction)
{
    int32_t difference = (int32_t)second - first;
    return (int32_t)first + ((difference * (int32_t)fraction) >> 8);
}

static void gr_mix(GrTrack *state, uint32_t parameters,
                   uint32_t track, uint32_t cursor)
{
    uint32_t count;
    uint32_t voice;
    uint32_t pitch = gr_pitch_step(gr_param(parameters, 0u));
    uint32_t i;

    gr_configure(state, parameters);
    if (cursor == 0u)
        return;
    count = *(volatile uint8_t *)(cursor + 3u);
    voice = VOICE_BASE + track * VOICE_STRIDE;
    for (i = 0; i < count; ++i) {
        uint32_t total_weight = 0u;
        int32_t left_sum = 0;
        int32_t right_sum = 0;
        uint32_t g;
        int32_t left;
        int32_t right;

        if (*(volatile uint8_t *)voice != 0u) {
            if (state->until_spawn == 0u &&
                state->scan_position < (state->sample_frames << POSITION_SHIFT)) {
                gr_spawn(state, &state->grains[state->next_grain],
                         state->grain_frames, pitch, state->scatter_frames);
                state->next_grain = (state->next_grain + 1u) & 3u;
                state->until_spawn = state->hop_frames;
            }
            if (state->until_spawn != 0u)
                --state->until_spawn;
            if (state->scan_position < (state->sample_frames << POSITION_SHIFT)) {
                uint32_t remaining =
                    (state->sample_frames << POSITION_SHIFT) - state->scan_position;
                state->scan_position += state->scan_step < remaining ?
                                       state->scan_step : remaining;
            }
        }

        for (g = 0; g < GRAIN_COUNT; ++g) {
            GrGrain *grain = &state->grains[g];
            uint32_t frame;
            uint32_t fraction;
            uint32_t weight;
            uint32_t advance;
            uint32_t first;
            uint32_t second;
            int16_t l0;
            int16_t l1;
            int16_t r0;
            int16_t r1;

            if (grain->remaining == 0u)
                continue;
            frame = grain->position >> POSITION_SHIFT;
            fraction = grain->position & (POSITION_ONE - 1u);
            first = gr_read_sample(state, grain, frame);
            second = fraction != 0u ?
                     gr_read_sample(state, grain, frame + 1u) : first;
            l0 = (int16_t)(first >> 16);
            r0 = (int16_t)first;
            l1 = (int16_t)(second >> 16);
            r1 = (int16_t)second;
            left = gr_interpolate(l0, l1, fraction);
            right = gr_interpolate(r0, r1, fraction);
            weight = grain->phase < 32768u ?
                     grain->phase >> 8 : (65536u - grain->phase) >> 8;
            left_sum += left * (int32_t)weight;
            right_sum += right * (int32_t)weight;
            total_weight += weight;
            advance = grain->subposition + grain->step;
            grain->subposition = advance & 255u;
            advance >>= 8;
            grain->phase += grain->phase_step;
            --grain->remaining;
            if (advance >= (state->sample_frames << POSITION_SHIFT) - grain->position)
                grain->remaining = 0u;
            else
                grain->position += advance;
        }

        left = total_weight ? left_sum / (int32_t)total_weight : 0;
        right = total_weight ? right_sum / (int32_t)total_weight : 0;
        {
            volatile uint32_t *out =
                (volatile uint32_t *)(cursor + 16u + i * 8u);
            out[0] = (uint32_t)(int32_t)(left * 65536);
            out[1] = (uint32_t)(int32_t)(right * 65536);
        }
    }
}

int32_t gr_render(uint32_t track, uint32_t ping, uint32_t start, uint32_t end)
{
    typedef int32_t (*Renderer)(uint32_t, uint32_t, uint32_t, uint32_t);
    Renderer stock = (Renderer)STOCK_RENDERER;
    uint32_t bank;
    uint32_t part;
    uint32_t slot;
    uint32_t parameters;
    uint32_t is_granular;
    uint32_t event;
    uint16_t saved[6];
    uint16_t *parameter_words = (uint16_t *)0;
    uint32_t i;
    uint32_t result;
    uint32_t render_state;
    uint32_t cursor;
    GrTrack *state;

    if (track >= TRACKS)
        return stock(track, ping, start, end);

    state = &gr_state[track];
    bank = *(volatile uint32_t *)BANK_POINTER;
    part = *(volatile uint8_t *)PART_INDEX;
    slot = gr_slot_for(bank, part, track);
    is_granular = gr_name_matches(slot);
    event = *(volatile uint8_t *)(NIBBLE_BASE + track);
    parameters = *(volatile uint32_t *)FP_POINTER;
    cursor = *(volatile uint32_t *)CURSOR_POINTER;

    if (end == 16u && (event & 0x10u)) {
        if (is_granular && parameters != 0u) {
            gr_begin(state, slot, parameters, track);
            render_state = *(volatile uint32_t *)RENDER_STATE_POINTER;
            if (render_state != 0u)
                *(volatile uint32_t *)(render_state + 4u) = 0u;
        } else {
            state->active = 0u;
        }
    }

    if (state->active && parameters != 0u) {
        parameter_words = (uint16_t *)parameters;
        for (i = 0; i < 6u; ++i)
            saved[i] = parameter_words[i];
        parameter_words[0] = 0x4000u;
        parameter_words[1] = 0u;
        parameter_words[2] = 0x7f00u;
        parameter_words[3] = 0x7f00u;
        parameter_words[4] = 0u;
        parameter_words[5] = 0u;
    }

    result = stock(track, ping, start, end);

    if (state->active && parameters != 0u) {
        render_state = *(volatile uint32_t *)RENDER_STATE_POINTER;
        if (render_state != 0u)
            *(volatile uint32_t *)(render_state + 4u) = 0u;
        for (i = 0; i < 6u; ++i)
            parameter_words[i] = saved[i];
        gr_mix(state, parameters, track, cursor);
    }
    return (int32_t)result;
}
