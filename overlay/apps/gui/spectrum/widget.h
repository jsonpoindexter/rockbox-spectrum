/* GPL-2.0-or-later. Theme parameters and per-widget presentation state. */
#ifndef SPECTRUM_WIDGET_H
#define SPECTRUM_WIDGET_H
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
struct spectrum_widget {
    int x, y, width, height, bands;
    bool animated;
    int effect;
    uint32_t visual_colors[3];
    bool lines, classic, visible;
#ifdef __PCTOOL__
    struct spectrum_widget *next;
    struct skin_viewport *viewport;
#else
    int next, viewport;
#endif
    uint32_t last_tick, generation;
    int32_t level[32], peak[32];
    uint32_t peak_tick[32], fall_fraction[32], peak_fraction[32];
    uint32_t peak_speed[32], peak_accel_fraction[32];
    int motion, visual_gain, gain_direction;
    uint32_t gain_fraction;
    bool auto_gain, guides;
    int drawn_height[32], drawn_peak[32];
    unsigned drawn_color;
    int dirty_x, dirty_y, dirty_width, dirty_height;
    int cache_x, cache_y, cache_width, cache_height, cache_bands;
    bool cache_classic, cache_lines;
    bool cache_valid;
    /* Theme-owned presentation, fixed when the skin is parsed. RGB is stored
     * unquantized; the renderer packs it for the actual display format. */
    int guide_style, guide_border, dot_pitch, bar_inset;
    uint32_t guide_rgb, bar_rgb, peak_rgb;
    unsigned char guide_vertical[256], guide_horizontal[64];
};
/* Display-only policies; profile0 reproduces the accepted fast3 curve. */
enum spectrum_motion { SPECTRUM_MOTION_FAST3, SPECTRUM_MOTION_SMOOTH,
    SPECTRUM_MOTION_PUNCHY, SPECTRUM_MOTION_CLASSIC, SPECTRUM_MOTION_COUNT };
struct spectrum_motion_policy {
    unsigned attack_ms, release_db, hold_ms, peak_start_db, peak_accel_db, peak_max_db;
};
static inline const struct spectrum_motion_policy *spectrum_motion_policy(int profile)
{
    static const struct spectrum_motion_policy policies[] = {
        {15, 60, 140, 60, 0, 60}, /* Accepted fast3: linear peaks. */
        {20, 45, 160, 15, 120, 120},
        {5, 90, 80, 30, 240, 180},
        {0, 60, 0, 6, 120, 150},
    };
    if (profile < 0 || profile >= SPECTRUM_MOTION_COUNT) profile = 0;
    return &policies[profile];
}
static inline void spectrum_widget_motion(struct spectrum_widget *w, int profile, uint32_t now)
{
    if (profile < 0 || profile >= SPECTRUM_MOTION_COUNT) profile = 0;
    if (w->motion == profile) return;
    w->motion = profile;
    for (int i = 0; i < 32; i++) {
        w->peak[i] = w->level[i]; w->peak_tick[i] = now;
        w->fall_fraction[i] = w->peak_fraction[i] = w->peak_accel_fraction[i] = 0;
        w->peak_speed[i] = spectrum_motion_policy(profile)->peak_start_db * 256;
    }
    w->cache_valid = false;
}
static inline void spectrum_widget_gain(struct spectrum_widget *w, bool enabled,
        bool fresh, int raw_peak, uint32_t dt, uint32_t ticks_per_second)
{
    if (w->auto_gain != enabled) {
        w->auto_gain = enabled; w->visual_gain = 0;
        w->gain_direction = 0; w->gain_fraction = 0;
    }
    /* Silence/stale frames must never cause gain to climb. */
    if (!enabled || !fresh || raw_peak <= -66 * 256) return;
    int desired = -6 * 256 - raw_peak;
    if (desired > 18 * 256) desired = 18 * 256;
    if (desired < -12 * 256) desired = -12 * 256;
    int direction = desired > w->visual_gain ? 1 : desired < w->visual_gain ? -1 : 0;
    if (direction != w->gain_direction) w->gain_fraction = 0;
    w->gain_direction = direction;
    unsigned rate = direction > 0 ? 384 : 24 * 256; /* +1.5 / -24 dB per second. */
    uint32_t numerator = dt * rate + w->gain_fraction;
    int change = numerator / ticks_per_second;
    w->gain_fraction = numerator % ticks_per_second;
    int value = w->visual_gain + direction * change;
    if ((direction > 0 && value > desired) || (direction < 0 && value < desired)) value = desired;
    w->visual_gain = value;
}
static inline void spectrum_widget_step(struct spectrum_widget *w, int bar,
        int target, uint32_t dt, uint32_t now, uint32_t ticks_per_second)
{
    const struct spectrum_motion_policy *p = spectrum_motion_policy(w->motion);
    if (target < -72 * 256) target = -72 * 256;
    if (target > 0) target = 0;
    uint32_t numerator = dt * p->release_db * 256 + w->fall_fraction[bar];
    int fall = numerator / ticks_per_second;
    w->fall_fraction[bar] = numerator % ticks_per_second;
    int value = w->level[bar];
    if (target > value) {
        if (!p->attack_ms && dt) value = target;
        else {
            int alpha = 65536000 / (1000 + p->attack_ms * ticks_per_second);
            for (uint32_t tick = 0; tick < dt; tick++) {
                int rise = (target - value) * alpha / 65536;
                if (!rise && value < target) rise = 1;
                value += rise;
            }
        }
    } else {
        value -= fall;
        if (value < target) value = target;
    }
    w->level[bar] = value;
    if (value >= w->peak[bar]) {
        w->peak[bar] = value; w->peak_tick[bar] = now;
        w->peak_fraction[bar] = w->peak_accel_fraction[bar] = 0;
        w->peak_speed[bar] = p->peak_start_db * 256;
    } else {
        uint32_t hold = (ticks_per_second * p->hold_ms + 999) / 1000;
        uint32_t age = now - w->peak_tick[bar];
        uint32_t decay = age > hold ? age - hold : 0;
        if (decay > dt) decay = dt;
        /* Integrate one scheduler tick at a time, independent of draw cadence. */
        for (uint32_t tick = 0; tick < decay; tick++) {
            numerator = w->peak_speed[bar] + w->peak_fraction[bar];
            w->peak[bar] -= (int)(numerator / ticks_per_second);
            w->peak_fraction[bar] = numerator % ticks_per_second;
            numerator = p->peak_accel_db * 256 + w->peak_accel_fraction[bar];
            w->peak_speed[bar] += numerator / ticks_per_second;
            w->peak_accel_fraction[bar] = numerator % ticks_per_second;
            if (w->peak_speed[bar] > p->peak_max_db * 256)
                w->peak_speed[bar] = p->peak_max_db * 256;
        }
        if (w->peak[bar] < value) w->peak[bar] = value;
    }
}
/* Pause/stop releases bypass peak hold and profile gravity. Keep fractional
 * elapsed-time decay and independent peak height; never jump at transition. */
static inline void spectrum_widget_fade(struct spectrum_widget *w, int bar,
        uint32_t dt, uint32_t ticks_per_second)
{
    uint32_t numerator = dt * 96 * 256 + w->fall_fraction[bar];
    int fall = numerator / ticks_per_second;
    w->fall_fraction[bar] = numerator % ticks_per_second;
    w->level[bar] -= fall;
    w->peak[bar] -= fall;
    if (w->level[bar] < -72 * 256) w->level[bar] = -72 * 256;
    if (w->peak[bar] < w->level[bar]) w->peak[bar] = w->level[bar];
}
enum spectrum_guide_style { SPECTRUM_GUIDE_OFF, SPECTRUM_GUIDE_DOTS, SPECTRUM_GUIDE_SOLID };
enum spectrum_guide_border { SPECTRUM_BORDER_LANES, SPECTRUM_BORDER_FRAME, SPECTRUM_BORDER_BASELINE };
#define SPECTRUM_COLOR_AUTO UINT32_MAX
static inline bool spectrum_theme_color(const char *text, uint32_t *out)
{
    if (!text) return false;
    if (!strcmp(text, "auto")) { *out = SPECTRUM_COLOR_AUTO; return true; }
    if (strlen(text) != 6) return false;
    uint32_t value = 0;
    for (int i = 0; i < 6; i++) {
        char c = text[i];
        int digit = c >= '0' && c <= '9' ? c - '0' :
            c >= 'a' && c <= 'f' ? c - 'a' + 10 :
            c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
        if (digit < 0) return false;
        value = (value << 4) | digit;
    }
    *out = value; return true;
}
/* Optional presentation block. Existing seven-argument tags use these same
 * defaults. No analyzer, audio setting or global motion policy is changed. */
static inline bool spectrum_widget_style(struct spectrum_widget *w,
        const char *guides, const char *guide_color, int pitch,
        const char *border, const char *bar_color, const char *peak_color, int inset)
{
    if (!guides || !border || pitch < 2 || pitch > 16 || inset < 1 || inset > 3)
        return false;
    int style = !strcmp(guides, "dots") ? SPECTRUM_GUIDE_DOTS :
        !strcmp(guides, "solid") ? SPECTRUM_GUIDE_SOLID :
        !strcmp(guides, "off") ? SPECTRUM_GUIDE_OFF : -1;
    int edge = !strcmp(border, "lanes") ? SPECTRUM_BORDER_LANES :
        !strcmp(border, "frame") ? SPECTRUM_BORDER_FRAME :
        !strcmp(border, "baseline") ? SPECTRUM_BORDER_BASELINE : -1;
    uint32_t guide_rgb, bar_rgb, peak_rgb;
    if (style < 0 || edge < 0 ||
        !spectrum_theme_color(guide_color, &guide_rgb) ||
        !spectrum_theme_color(bar_color, &bar_rgb) ||
        !spectrum_theme_color(peak_color, &peak_rgb)) return false;
    w->guide_style = style; w->guide_border = edge;
    w->dot_pitch = pitch; w->bar_inset = inset;
    w->guide_rgb = guide_rgb; w->bar_rgb = bar_rgb; w->peak_rgb = peak_rgb;
    /* Rockbox vertical-packed mono strips: one column / one row. Bounded for
     * the 320x240 target and its widest lane (40px at eight bands). */
    memset(w->guide_vertical, 0, sizeof(w->guide_vertical));
    memset(w->guide_horizontal, 0, sizeof(w->guide_horizontal));
    for (int y = 0; y < 256; y += pitch)
        w->guide_vertical[(y / 8) * 8] |= 1u << (y % 8);
    for (int x = 0; x < 64; x += pitch) w->guide_horizontal[x] = 1;
    w->cache_valid = false;
    return true;
}
static inline bool spectrum_widget_configure(struct spectrum_widget *w,
        int x, int y, int width, int height, int bands,
        const char *mode, const char *palette, int vp_width, int vp_height)
{
    if (!mode || !palette || x < 0 || y < 0 || width < 1 || width > 320 || height < 2 || height > 240 ||
        x > vp_width || y > vp_height || width > vp_width - x ||
        height > vp_height - y || (bands != 8 && bands != 16 && bands != 32) ||
        width < 2 * bands || (strcmp(mode, "bars") && strcmp(mode, "lines")) ||
        (strcmp(palette, "mono") && strcmp(palette, "classic"))) return false;
    memset(w, 0, sizeof(*w));
    w->x = x; w->y = y; w->width = width; w->height = height; w->bands = bands;
    w->lines = !strcmp(mode, "lines"); w->classic = !strcmp(palette, "classic");
    spectrum_widget_style(w, "dots", "auto", 4, "lanes", "auto", "auto", 1);
    w->generation = UINT32_MAX;
    for (int i = 0; i < 32; i++) {
        w->level[i] = w->peak[i] = -72 * 256;
        w->peak_speed[i] = spectrum_motion_policy(0)->peak_start_db * 256;
    }
    return true;
}

static inline bool visualization_widget_configure(struct spectrum_widget *w,
    int x, int y, int width, int height, const char *effect,
    const char *background, const char *primary, const char *accent,
    int vp_width, int vp_height)
{
    if (!effect || x<0 || y<0 || width<16 || height<16 || width>320 || height>240 ||
        x>vp_width || y>vp_height || width>vp_width-x || height>vp_height-y) return false;
    int mode=!strcmp(effect,"feedback")?0:!strcmp(effect,"phosphor")?1:
        !strcmp(effect,"ribbons")?2:-1;
    uint32_t colors[3];
    if (mode<0 || !spectrum_theme_color(background,&colors[0]) ||
        !spectrum_theme_color(primary,&colors[1]) || !spectrum_theme_color(accent,&colors[2]) ||
        colors[0]==SPECTRUM_COLOR_AUTO || colors[1]==SPECTRUM_COLOR_AUTO || colors[2]==SPECTRUM_COLOR_AUTO)
        return false;
    memset(w,0,sizeof(*w)); w->animated=true; w->effect=mode;
    w->x=x; w->y=y; w->width=width; w->height=height;
    memcpy(w->visual_colors,colors,sizeof(colors)); w->generation=UINT32_MAX;
    return true;
}
#endif
