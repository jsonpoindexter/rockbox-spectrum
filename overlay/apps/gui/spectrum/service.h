/* Native Now Playing spectrum service. GPL-2.0-or-later. */
#ifndef SPECTRUM_SERVICE_H
#define SPECTRUM_SERVICE_H
#include "analyzer.h"
#include "screen_access.h"
#include "widget.h"
/* Two ticks at the ipod6g 100 Hz scheduler: at most 50 updates/s. */
#define SPECTRUM_REFRESH_TICKS ((HZ / 50) > 0 ? (HZ / 50) : 1)
/* A full-scale 72dB tail falls at96dB/s;80 ticks allow a final settled draw. */
#define SPECTRUM_FADE_TICKS ((HZ * 4 + 4) / 5)
/* True means the UI should animate, including capture-free pause/stop tails. */
bool spectrum_set_visible(bool visible);
void spectrum_reset(void);
bool spectrum_draw(struct screen *screen, struct spectrum_widget *widget, struct viewport *viewport);
struct spectrum_rect { int x, y, width, height; };
void spectrum_get_dirty(struct spectrum_widget *widget, struct spectrum_rect *out);
uint32_t spectrum_clock_us(void);
void spectrum_record_submission(uint32_t usecs);
#define SPECTRUM_METRICS 6
#define SPECTRUM_BUCKETS 128
struct spectrum_metric { uint32_t count, maximum, buckets[SPECTRUM_BUCKETS]; };
struct spectrum_timing {
    struct spectrum_metric metric[SPECTRUM_METRICS];
    uint32_t windows, drops, stale, pressure, skipped;
};
void spectrum_timing_snapshot(struct spectrum_timing *out);
bool spectrum_debug_menu(void);
#endif
