/* Single producer (PCM callback), single consumer. GPL-2.0-or-later.
 * Consumer metadata operations must hold the platform PCM lock. */
#ifndef SPECTRUM_CAPTURE_H
#define SPECTRUM_CAPTURE_H
#include "analyzer.h"
enum spectrum_slot_state { SPEC_FREE, SPEC_READY, SPEC_READING };
struct spectrum_slot {
    int16_t pcm[2 * SPECTRUM_SAMPLES];
    enum spectrum_slot_state state;
    uint32_t generation, sequence, rate, tick, capture_us;
};
struct spectrum_capture {
    struct spectrum_slot slots[2];
    int16_t history[2 * SPECTRUM_SAMPLES];
    unsigned write_pos, history_count;
    bool enabled, scheduled;
    int published;
    uint32_t generation, sequence, next_tick, period, rate;
    uint32_t drops, windows;
};
void spectrum_capture_init(struct spectrum_capture *c, uint32_t period);
void spectrum_capture_enable(struct spectrum_capture *c, bool enabled);
void spectrum_capture_reset(struct spectrum_capture *c);
bool spectrum_capture_submit(struct spectrum_capture *c, const int16_t *pcm,
                              unsigned frames, uint32_t rate, uint32_t tick);
int spectrum_capture_acquire(struct spectrum_capture *c);
void spectrum_capture_release(struct spectrum_capture *c, int slot);
#endif
