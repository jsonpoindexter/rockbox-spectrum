/* GPL-2.0-or-later. Theme parameters and per-widget presentation state. */
#ifndef REFERENCE_WIDGET_H
#define REFERENCE_WIDGET_H
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
struct reference_widget {
    int x, y, width, height, bands;
    bool lines, classic, visible;
#ifdef __PCTOOL__
    struct reference_widget *next;
    struct skin_viewport *viewport;
#else
    int next, viewport;
#endif
    uint32_t last_tick, generation;
    int32_t level[32], peak[32];
    uint32_t peak_tick[32], fall_fraction[32], peak_fraction[32];
    int drawn_height[32], drawn_peak[32];
    unsigned drawn_color;
    int dirty_x, dirty_y, dirty_width, dirty_height;
    int cache_x, cache_y, cache_width, cache_height, cache_bands;
    bool cache_classic, cache_lines;
    bool cache_valid;
};
/* Display-only ballistics. Fast2 capture/analysis remains unchanged.
 * At HZ=100 the rise coefficient is 0.4/tick (~20ms time constant).
 * Fractional release/peak accumulation avoids cadence-dependent rounding. */
#define SPECTRUM_ATTACK_MS 15
#define SPECTRUM_RELEASE_DB_PER_SECOND 60
#define SPECTRUM_PEAK_HOLD_MS 140
static inline void reference_widget_step(struct reference_widget *w, int bar,
        int target, uint32_t dt, uint32_t now, uint32_t ticks_per_second)
{
    if (target < -72 * 256) target = -72 * 256;
    if (target > 0) target = 0;
    uint32_t numerator = dt * SPECTRUM_RELEASE_DB_PER_SECOND * 256 +
                         w->fall_fraction[bar];
    int fall = numerator / ticks_per_second;
    w->fall_fraction[bar] = numerator % ticks_per_second;
    int value = w->level[bar];
    if (target > value) {
        int alpha = 65536000 / (1000 + SPECTRUM_ATTACK_MS * ticks_per_second);
        for (uint32_t tick = 0; tick < dt; tick++) {
            int rise = (target - value) * alpha / 65536;
            if (!rise && value < target) rise = 1;
            value += rise;
        }
    } else {
        value -= fall;
        if (value < target) value = target;
    }
    w->level[bar] = value;
    if (value >= w->peak[bar]) {
        w->peak[bar] = value;
        w->peak_tick[bar] = now;
        w->peak_fraction[bar] = 0;
    } else {
        uint32_t hold = (ticks_per_second * SPECTRUM_PEAK_HOLD_MS + 999) / 1000;
        uint32_t age = now - w->peak_tick[bar];
        uint32_t decay = age > hold ? age - hold : 0;
        if (decay > dt) decay = dt;
        numerator = decay * SPECTRUM_RELEASE_DB_PER_SECOND * 256 + w->peak_fraction[bar];
        w->peak[bar] -= (int)(numerator / ticks_per_second);
        w->peak_fraction[bar] = numerator % ticks_per_second;
        if (w->peak[bar] < value) w->peak[bar] = value;
    }
}
static inline bool reference_widget_configure(struct reference_widget *w,
        int x, int y, int width, int height, int bands,
        const char *mode, const char *palette, int vp_width, int vp_height)
{
    if (!mode || !palette || x < 0 || y < 0 || width < 1 || height < 2 ||
        x > vp_width || y > vp_height || width > vp_width - x ||
        height > vp_height - y || (bands != 8 && bands != 16 && bands != 32) ||
        width < 2 * bands || (strcmp(mode, "bars") && strcmp(mode, "lines")) ||
        (strcmp(palette, "mono") && strcmp(palette, "classic"))) return false;
    memset(w, 0, sizeof(*w));
    w->x = x; w->y = y; w->width = width; w->height = height; w->bands = bands;
    w->lines = !strcmp(mode, "lines"); w->classic = !strcmp(palette, "classic");
    w->generation = UINT32_MAX;
    for (int i = 0; i < 32; i++) w->level[i] = w->peak[i] = -72 * 256;
    return true;
}
#endif
