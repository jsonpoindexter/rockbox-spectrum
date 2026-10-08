/* A bounded PCM observer feeding a sleeping background worker.
 * GPL-2.0-or-later. Audio callback only copies a mixer chunk and signals.
 * All capture metadata changes outside the callback hold the PCM lock. */
#include "config.h"
#include "service.h"
#include "capture.h"
#include "visualizer.h"
#include "kernel.h"
#include "thread.h"
#include "pcm.h"
#include "pcm_mixer.h"
#include "audio.h"
#include "settings.h"
#include "backlight.h"
#include "lcd.h"
#include "pcmbuf.h"
#include "system.h"
#include <string.h>
#if defined(SIMULATOR) || defined(SPECTRUM_DIAGNOSTICS)
#include "debug.h"
#define SPEC_DEBUG(...) DEBUGF(__VA_ARGS__)
#else
#define SPEC_DEBUG(...) do {} while (0)
#endif

static struct spectrum_capture capture;
static struct spectrum_analyzer analyzer;
static struct spectrum_frame latest;
static struct visualization visual;
static fb_data visual_rows[320*2];
static uint32_t visual_draw_us;
static bool visual_submission;
typedef char visual_pool_budget[(sizeof(visual)+sizeof(visual_rows)<=256*1024)?1:-1];
static struct semaphore available;
static long worker_stack[DEFAULT_STACK_SIZE * 4 / sizeof(long)];
static unsigned long worker_id;
static bool initialized, subscribed, latest_valid;
static bool pressure_suspended, recovering;
static uint32_t healthy_tick, pending_capture_us, pending_sequence, submitted_sequence;
static struct spectrum_timing timing;
static uint32_t previous_submit_us;
static bool cadence_started;
/* Capture lifetime and UI tail lifetime are separate. UI owns tail state;
 * reset_pending is exchanged under the PCM lock with the playback thread. */
static bool fading, reset_pending;
static uint32_t fade_tick, display_generation;
static bool display_allowed;
uint32_t spectrum_clock_us(void)
{
#ifdef USEC_TIMER
    return USEC_TIMER;
#else
    return (uint32_t)current_tick * (1000000 / HZ);
#endif
}
/* Fixed 1ms histogram bins; the last bucket contains >=127ms. */
static void measure(int metric, uint32_t us)
{
    struct spectrum_metric *m = &timing.metric[metric];
    unsigned bucket = us / 1000;
    if (bucket >= SPECTRUM_BUCKETS) bucket = SPECTRUM_BUCKETS - 1;
    m->count++;
    if (us > m->maximum) m->maximum = us;
    m->buckets[bucket]++;
}
void spectrum_timing_snapshot(struct spectrum_timing *out)
{
    pcm_play_lock();
    *out = timing;
    out->windows = capture.windows; out->drops = capture.drops;
    pcm_play_unlock();
}
void spectrum_record_submission(uint32_t us)
{
    pcm_play_lock();
    uint32_t now = spectrum_clock_us();
    measure(3, us);
    if (visual_submission) {
        visualization_cost(&visual,visual_draw_us+us); visual_submission=false;
    }
    if (cadence_started) measure(5, now - previous_submit_us);
    previous_submit_us = now; cadence_started = true;
    if (pending_sequence != submitted_sequence) {
        measure(4, spectrum_clock_us() - pending_capture_us);
        submitted_sequence = pending_sequence;
    }
    pcm_play_unlock();
}

static void observe(const int16_t *pcm, unsigned count, unsigned rate)
{
    uint32_t start = spectrum_clock_us();
    if (spectrum_capture_submit(&capture, pcm, count, rate, current_tick)) {
        capture.slots[capture.published].capture_us = start;
        semaphore_release(&available);
    }
    measure(0, spectrum_clock_us() - start);
}

static void worker(void)
{
    for (;;) {
        semaphore_wait(&available, TIMEOUT_BLOCK);
        pcm_play_lock();
        int slot = spectrum_capture_acquire(&capture);
        pcm_play_unlock();
        if (slot < 0) continue;
        struct spectrum_slot *s = &capture.slots[slot];
        struct spectrum_frame frame;
        memset(&frame, 0, sizeof(frame));
        frame.generation = s->generation;
        frame.sequence = s->sequence;
        frame.tick = s->tick;
        frame.capture_us = s->capture_us;
        uint32_t start = spectrum_clock_us();
        spectrum_analyze(&analyzer, s->pcm, s->rate, &frame);
        pcm_play_lock();
        measure(1, spectrum_clock_us() - start);
        if (capture.enabled && frame.generation == capture.generation) {
            latest = frame;
            latest_valid = true;
        }
        spectrum_capture_release(&capture, slot);
        pcm_play_unlock();
        if (frame.sequence % 20 == 1)
            SPEC_DEBUG("spectrum frame seq=%lu generation=%lu tick=%lu rate=%lu\n",
                   (unsigned long)frame.sequence, (unsigned long)frame.generation,
                   (unsigned long)frame.tick, (unsigned long)frame.sample_rate);
        yield();
    }
}

bool spectrum_set_visible(bool visible)
{
    int status = audio_status();
    bool allowed = visible && global_settings.spectrum_enabled &&
                   lcd_active() && is_backlight_on(false);
    bool playing = (status & AUDIO_STATUS_PLAY) && !(status & AUDIO_STATUS_PAUSE);
    bool eligible = allowed && playing;
    /* Existing audio-buffer pressure always takes precedence over animation.
     * Poll from UI context, never inspect the buffer or wait in the callback. */
    uint32_t now = current_tick;
    if (eligible && pcmbuf_is_lowdata()) {
        if (!pressure_suspended) timing.pressure++;
        pressure_suspended = true; recovering = false;
    } else if (eligible && pressure_suspended) {
        if (!recovering) { healthy_tick = now; recovering = true; }
        if ((uint32_t)(now - healthy_tick) >= 2 * HZ) {
            pressure_suspended = false; recovering = false;
        }
    } else if (!eligible) recovering = false;
    eligible = eligible && !pressure_suspended;
    if (eligible && !initialized) {
        spectrum_capture_init(&capture, SPECTRUM_REFRESH_TICKS);
        semaphore_init(&available, 1, 0);
        initialized = true;
        worker_id = create_thread(worker, worker_stack, sizeof(worker_stack),
                                  0, "spectrum"
                                  IF_PRIO(, PRIORITY_BACKGROUND)
                                  IF_COP(, CPU));
    }
    if (!initialized || !worker_id) return false;
    pcm_play_lock();
    if (reset_pending) {
        /* Seek resets the display; a stop reset must retain its falling tail. */
        if (playing) display_generation++;
        reset_pending = false;
    }
    if (allowed && !playing && subscribed && !pressure_suspended) {
        fading = true; fade_tick = now;
    }
    if (!allowed || pressure_suspended) {
        fading = false;
        if (display_allowed) display_generation++;
    } else if (eligible) fading = false;
    display_allowed = allowed && !pressure_suspended;
    if (fading && (uint32_t)(now - fade_tick) >= SPECTRUM_FADE_TICKS) {
        fading = false;
        display_generation++; /* Final ordinary repaint leaves only guides. */
    }
    if (subscribed != eligible) cadence_started = false;
    spectrum_capture_enable(&capture, eligible);
    pcm_play_unlock();
    if (subscribed != eligible) {
        mixer_set_playback_observer(eligible ? observe : NULL);
        subscribed = eligible;
        SPEC_DEBUG("spectrum active=%d generation=%lu windows=%lu drops=%lu\n",
                   eligible, (unsigned long)capture.generation,
                   (unsigned long)capture.windows, (unsigned long)capture.drops);
    }
    return eligible || fading;
}

void spectrum_reset(void)
{
    if (!initialized) return;
    pcm_play_lock();
    spectrum_capture_reset(&capture);
    reset_pending = true;
    cadence_started = false;
    pcm_play_unlock();
}

static bool get_frame(struct spectrum_frame *out)
{
    bool valid;
    pcm_play_lock();
    valid = initialized && capture.enabled && latest_valid &&
            latest.generation == capture.generation;
    if (valid) *out = latest;
    pcm_play_unlock();
    return valid;
}

void spectrum_get_dirty(struct spectrum_widget *w, struct spectrum_rect *out)
{
    out->x = w->dirty_x; out->y = w->dirty_y;
    out->width = w->dirty_width; out->height = w->dirty_height;
}

/* Guides use theme-configured, precomputed mono strips. Their phase is lane
 * relative, including dirty clears; changing style invalidates the cache. */
static unsigned theme_rgb(uint32_t rgb)
{
    return LCD_RGBPACK((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255);
}
static void guide_horizontal(struct screen *screen, struct spectrum_widget *w,
        int x, int y, int width)
{
    if (w->guide_style == SPECTRUM_GUIDE_SOLID) screen->hline(x, x + width - 1, y);
    else screen->mono_bitmap_part(w->guide_horizontal,0,0,64,x,y,width,1);
}
static void guide_vertical(struct screen *screen, struct spectrum_widget *w,
        int x, int y, int height)
{
    if (w->guide_style == SPECTRUM_GUIDE_SOLID) screen->fillrect(x,y,1,height);
    else screen->mono_bitmap_part(w->guide_vertical,0,y-w->y,8,x,y,1,height);
}
bool spectrum_draw(struct screen *screen, struct spectrum_widget *w, struct viewport *viewport)
{
    uint32_t start = spectrum_clock_us();
    struct spectrum_frame frame = {0};
    bool valid = get_frame(&frame);
    /* Locks can yield; restore the caller's viewport after taking the snapshot. */
    screen->set_viewport_ex(viewport, VP_FLAG_VP_SET_CLEAN);
    uint32_t now = current_tick;
    uint32_t dt = w->last_tick ? now - w->last_tick : 1;
    if (dt > HZ) dt = HZ;
    w->last_tick = now;
    uint32_t generation = display_generation;
    if (w->generation != generation) {
        for (int i = 0; i < 32; i++) {
            w->level[i] = w->peak[i] = SPECTRUM_FLOOR;
            w->peak_tick[i] = now;
            w->fall_fraction[i] = w->peak_fraction[i] = w->peak_accel_fraction[i] = 0;
            w->peak_speed[i] = spectrum_motion_policy(w->motion)->peak_start_db * 256;
        }
        w->visual_gain = 0; w->gain_fraction = 0; w->gain_direction = 0;
        w->generation = generation;
        w->cache_valid = false;
    }
    bool fresh = valid && (uint32_t)(now - frame.tick) <= (HZ / 10);
    if (valid && !fresh) timing.stale++;
    spectrum_widget_motion(w, global_settings.spectrum_motion, now);
    int raw_peak = SPECTRUM_FLOOR;
    if (fresh) for (int i = 0; i < 32; i++)
        if (frame.db[i] > raw_peak) raw_peak = frame.db[i];
    spectrum_widget_gain(w, global_settings.spectrum_auto_gain, fresh, raw_peak, dt, HZ);
    if (w->animated) {
        if (!visualization_render(&visual,w,&frame,fresh,fading,w->visual_gain,
            global_settings.visualization_effect,generation,now,HZ,!w->cache_valid)) return false;
        for (int y=0;y<w->height;y+=2) {
            for (int x=0;x<w->width;x++) {
                uint32_t rgb=visualization_pixel(&visual,x/2,y/2);
                visual_rows[x]=visual_rows[w->width+x]=theme_rgb(rgb);
            }
            screen->bitmap_part(visual_rows,0,0,w->width,w->x,w->y+y,
                                w->width,y+1<w->height?2:1);
        }
        w->dirty_x=w->x; w->dirty_y=w->y;
        w->dirty_width=w->width; w->dirty_height=w->height; w->cache_valid=true;
        if (fresh) { pending_sequence=visual.frame_sequence; pending_capture_us=visual.capture_us; }
        uint32_t elapsed=spectrum_clock_us()-start;
        measure(2,elapsed); visual_draw_us=elapsed; visual_submission=true;
        return true;
    }
    bool guides = global_settings.spectrum_guides && !w->lines &&
        w->guide_style != SPECTRUM_GUIDE_OFF && w->height >= 8 &&
        w->width >= (2 * w->bar_inset + 6) * w->bands;
    if (guides != w->guides) { w->guides = guides; w->cache_valid = false; }
    int plot_height = w->height - (guides ? 6 : 0);
    int base_y = w->y + w->height - 1 - (guides ? 3 : 0);
    unsigned old_color = screen->get_foreground();
    /* Dim only the guides; keep the theme hue and normal bars/peaks. */
    unsigned guide_color = LCD_RGBPACK(RGB_UNPACK_RED(old_color) * 3 / 4,
        RGB_UNPACK_GREEN(old_color) * 3 / 4, RGB_UNPACK_BLUE(old_color) * 3 / 4);
    if (w->guide_rgb != SPECTRUM_COLOR_AUTO) guide_color = theme_rgb(w->guide_rgb);
    unsigned bar_color = w->bar_rgb == SPECTRUM_COLOR_AUTO ? old_color : theme_rgb(w->bar_rgb);
    unsigned peak_color = w->peak_rgb == SPECTRUM_COLOR_AUTO ? old_color : theme_rgb(w->peak_rgb);
    bool full = !w->cache_valid || w->lines || w->drawn_color != old_color ||
        w->cache_x != w->x || w->cache_y != w->y ||
        w->cache_width != w->width || w->cache_height != w->height ||
        w->cache_bands != w->bands || w->cache_classic != w->classic ||
        w->cache_lines != w->lines;
    int left = w->x + w->width, top = w->y + w->height, right = w->x, bottom = w->y;
    if (full) {
        screen->set_drawmode(DRMODE_SOLID | DRMODE_INVERSEVID);
        screen->fillrect(w->x, w->y, w->width, w->height);
        left = w->x; top = w->y; right = left + w->width; bottom = top + w->height;
    }
    screen->set_drawmode(DRMODE_SOLID);
    int previous_x = 0, previous_y = 0;
    for (int bar = 0; bar < w->bands; bar++) {
        int target = SPECTRUM_FLOOR;
        int group = 32 / w->bands;
        if (fresh) for (int i = bar * group; i < (bar + 1) * group; i++)
            if (frame.db[i] > target) target = frame.db[i];
        if (fresh && target > SPECTRUM_FLOOR) target += w->visual_gain;
        if (fading) spectrum_widget_fade(w, bar, dt, HZ);
        else spectrum_widget_step(w, bar, target, dt, now, HZ);
        int h = (w->level[bar] - SPECTRUM_FLOOR) * (plot_height - 1) / -SPECTRUM_FLOOR;
        int peak = (w->peak[bar] - SPECTRUM_FLOOR) * (plot_height - 1) / -SPECTRUM_FLOOR;
        int x = w->x + bar * w->width / w->bands;
        int width = (bar + 1) * w->width / w->bands - bar * w->width / w->bands - 1;
        int y = base_y - h;
        if (w->lines) {
            int center = x + width / 2;
            screen->set_foreground(w->bar_rgb != SPECTRUM_COLOR_AUTO ? bar_color :
                w->classic ? LCD_RGBPACK(0,255,64) : old_color);
            if (bar && (valid || fading)) screen->drawline(previous_x, previous_y, center, y);
            previous_x = center; previous_y = y;
        } else if (full || h != w->drawn_height[bar] || peak != w->drawn_peak[bar]) {
            int clear_y = w->y;
            if (!full) {
                int extent = h;
                if (peak > extent) extent = peak;
                if (w->drawn_height[bar] > extent) extent = w->drawn_height[bar];
                if (w->drawn_peak[bar] > extent) extent = w->drawn_peak[bar];
                clear_y = base_y - extent;
                screen->set_drawmode(DRMODE_SOLID | DRMODE_INVERSEVID);
                screen->fillrect(x, clear_y, width, w->y + w->height - clear_y);
                screen->set_drawmode(DRMODE_SOLID);
                if (x < left) left = x;
                if (clear_y < top) top = clear_y;
                if (x + width > right) right = x + width;
                bottom = w->y + w->height;
            }
            int draw_x = x, draw_width = width;
            if (guides) {
                /* Match all guides; the bottom row is the idle marker. */
                screen->set_foreground(guide_color);
                int guide_y = clear_y > w->y + 3 ? clear_y : w->y + 3;
                int guide_end = w->y + w->height - 3;
                if (w->guide_border != SPECTRUM_BORDER_BASELINE) {
                    if ((bar || w->guide_border == SPECTRUM_BORDER_FRAME) && guide_y < guide_end)
                        guide_vertical(screen,w,x,guide_y,guide_end-guide_y);
                    if (w->guide_border == SPECTRUM_BORDER_FRAME && bar == w->bands - 1 && guide_y < guide_end)
                        guide_vertical(screen,w,x+width-1,guide_y,guide_end-guide_y);
                    if (full) guide_horizontal(screen,w,x,w->y,width);
                }
                guide_horizontal(screen,w,x,w->y+w->height-2,width);
                draw_x += w->bar_inset; draw_width -= 2 * w->bar_inset;
            }
            /* Paint at most three color segments instead of one call per row. */
            int offset = 0;
            bool classic = w->classic && w->bar_rgb == SPECTRUM_COLOR_AUTO;
            for (int segment = 0; segment < (classic ? 3 : 1); segment++) {
                int end = !classic || segment == 2 ? h :
                    (plot_height * (segment == 0 ? 65 : 85) + 99) / 100;
                if (end > h) end = h;
                if (end > offset) {
                    unsigned color = !classic ? bar_color : segment == 0 ?
                        LCD_RGBPACK(0,255,64) : segment == 1 ?
                        LCD_RGBPACK(255,220,32) : LCD_RGBPACK(255,48,32);
                    screen->set_foreground(color);
                    screen->fillrect(draw_x, base_y + 1 - end, draw_width, end - offset);
                }
                offset = end;
            }
            screen->set_foreground(peak_color);
            if (peak) screen->hline(draw_x, draw_x + draw_width - 1, base_y - peak);
        }
        w->drawn_height[bar] = h; w->drawn_peak[bar] = peak;
    }
    screen->set_foreground(old_color);
    screen->set_drawmode(DRMODE_SOLID);
    w->drawn_color = old_color; w->cache_valid = true;
    w->cache_x = w->x; w->cache_y = w->y; w->cache_width = w->width;
    w->cache_height = w->height; w->cache_bands = w->bands;
    w->cache_classic = w->classic; w->cache_lines = w->lines;
    w->dirty_x = left; w->dirty_y = top;
    w->dirty_width = right > left ? right - left : 0;
    w->dirty_height = bottom > top ? bottom - top : 0;
    bool changed = w->dirty_width && w->dirty_height;
    pcm_play_lock();
    measure(2, spectrum_clock_us() - start);
    if (!changed) timing.skipped++;
    if (fresh) { pending_capture_us = frame.capture_us; pending_sequence = frame.sequence; }
    pcm_play_unlock();
    return changed;
}
