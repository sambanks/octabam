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
#define STOCK_RENDERER 0x40004008u
#define POOL_READ_DIRECTION 1u

GrTrack gr_state[TRACKS];
uint8_t gr_page_descriptor[FLEX_PLAYBACK_SIZE];
uint32_t gr_page_ready;

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
        for (i = 0; i < FLEX_PLAYBACK_SIZE; ++i)
            descriptor[i] = ((volatile uint8_t *)FLEX_PLAYBACK)[i];

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
            *words = 0;
            words = (volatile uint32_t *)(descriptor + PAGE_COUNT_OFFSET + i * 4u);
            *words = 128u;
            words = (volatile uint32_t *)(descriptor + PAGE_FORMATTERS_OFFSET + i * 4u);
            *words = 0;
            words = (volatile uint32_t *)(descriptor + PAGE_WIDGETS_OFFSET + i * 4u);
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

static int16_t gr_read_channel(GrTrack *state, GrGrain *grain,
                               uint32_t frame, uint32_t channel)
{
    uint32_t data;
    uint32_t frames;
    uint32_t flags;
    uint32_t bytes_per_sample;
    uint32_t channels;
    uint32_t byte_offset;
    volatile uint8_t *sample;
    uint32_t raw;

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

    flags = *(volatile uint32_t *)(POOL_STATE + state->slot * POOL_STATE_STRIDE);
    bytes_per_sample = (flags & 2u) ? 2u : 3u;
    channels = (flags & 1u) ? 2u : 1u;
    if (channel >= channels)
        channel = channels - 1u;
    byte_offset = (frame - grain->cache_start) * state->bytes_per_frame +
                  channel * bytes_per_sample;
    sample = (volatile uint8_t *)(grain->cache_data + byte_offset);
    if (bytes_per_sample == 2u) {
        raw = ((uint32_t)sample[0] << 8) | sample[1];
        return (int16_t)raw;
    }
    raw = ((uint32_t)sample[0] << 16) |
          ((uint32_t)sample[1] << 8) | sample[2];
    raw >>= 8;
    if (raw & 0x8000u)
        raw |= 0xffff0000u;
    return (int16_t)raw;
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
    grain->step = 128u + pitch * 2u;
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
    uint32_t pitch = gr_param(parameters, 0u);
    uint32_t i;

    gr_configure(state, parameters);
    if (cursor == 0u)
        return;
    count = *(volatile uint8_t *)(cursor + 3u);
    voice = VOICE_BASE + track * VOICE_STRIDE;
    for (i = 0; i < count; ++i) {
        uint32_t left_weight = 0u;
        uint32_t right_weight = 0u;
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
            int16_t l0;
            int16_t l1;
            int16_t r0;
            int16_t r1;

            if (grain->remaining == 0u)
                continue;
            frame = grain->position >> POSITION_SHIFT;
            fraction = grain->position & (POSITION_ONE - 1u);
            l0 = gr_read_channel(state, grain, frame, 0u);
            l1 = gr_read_channel(state, grain, frame + 1u, 0u);
            if (state->bytes_per_frame == 2u || state->bytes_per_frame == 3u) {
                r0 = l0;
                r1 = l1;
            } else {
                r0 = gr_read_channel(state, grain, frame, 1u);
                r1 = gr_read_channel(state, grain, frame + 1u, 1u);
            }
            left = gr_interpolate(l0, l1, fraction);
            right = gr_interpolate(r0, r1, fraction);
            weight = grain->phase < 32768u ?
                     grain->phase >> 8 : (65536u - grain->phase) >> 8;
            left_sum += left * (int32_t)weight;
            right_sum += right * (int32_t)weight;
            left_weight += weight;
            right_weight += weight;
            grain->position += grain->step;
            grain->phase += grain->phase_step;
            --grain->remaining;
            if ((grain->position >> POSITION_SHIFT) >= state->sample_frames)
                grain->remaining = 0u;
        }

        left = left_weight ? left_sum / (int32_t)left_weight : 0;
        right = right_weight ? right_sum / (int32_t)right_weight : 0;
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
