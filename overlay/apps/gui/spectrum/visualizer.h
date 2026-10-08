/* Original native music animation engine. GPL-2.0-or-later. */
#ifndef SPECTRUM_VISUALIZER_H
#define SPECTRUM_VISUALIZER_H
#include "analyzer.h"
#include "widget.h"
#define VIS_PIXELS (160 * 120)
/* One UI-owned pool, no allocation/callback work. RGB888 scratch is independent
 * of LCD packing. 3 surfaces support feedback and snapshot crossfades. */
struct visualization {
    uint32_t pixels[2][VIS_PIXELS], transition[VIS_PIXELS];
    uint32_t tick, cycle_ticks, transition_tick, generation;
    uint32_t frame_sequence, capture_us;
    uint32_t colors[3];
    const struct spectrum_widget *owner;
    int width, height, page, effect, selection, signature;
    int envelope[3], pulse;
    unsigned interval, slow_frames, healthy_frames, fade_remaining;
    bool started, crossing;
};
bool visualization_render(struct visualization *v, const struct spectrum_widget *w,
    const struct spectrum_frame *frame, bool fresh, bool fading, int gain,
    int selection, uint32_t generation, uint32_t now, unsigned hz, bool force);
uint32_t visualization_pixel(const struct visualization *v, int x, int y);
void visualization_cost(struct visualization *v, uint32_t usecs);
#endif
