/* Owned rolling sample history and replaceable snapshots. GPL-2.0-or-later. */
#include "capture.h"
#include <string.h>
void spectrum_capture_init(struct spectrum_capture *c, uint32_t period)
{
    memset(c, 0, sizeof(*c));
    c->published = -1;
    c->period = period ? period : 1;
}
void spectrum_capture_reset(struct spectrum_capture *c)
{
    c->generation++;
    c->write_pos = c->history_count = 0;
    c->published = -1;
    c->scheduled = false;
    for (unsigned i = 0; i < 2; i++)
        if (c->slots[i].state != SPEC_READING) c->slots[i].state = SPEC_FREE;
}
void spectrum_capture_enable(struct spectrum_capture *c, bool enabled)
{
    if (c->enabled != enabled) {
        c->enabled = enabled;
        spectrum_capture_reset(c);
    }
}
bool spectrum_capture_submit(struct spectrum_capture *c, const int16_t *pcm,
                              unsigned frames, uint32_t rate, uint32_t tick)
{
    if (!c->enabled || !pcm || !frames || !rate) return false;
    if (c->rate != rate) {
        spectrum_capture_reset(c);
        c->rate = rate;
    }
    /* Even unusually large callbacks require at most one history window copy. */
    if (frames > SPECTRUM_SAMPLES) {
        pcm += (size_t)(frames - SPECTRUM_SAMPLES) * 2;
        frames = SPECTRUM_SAMPLES;
    }
    unsigned first = SPECTRUM_SAMPLES - c->write_pos;
    if (first > frames) first = frames;
    memcpy(c->history + 2*c->write_pos, pcm, first*2*sizeof(*pcm));
    memcpy(c->history, pcm + 2*first, (frames-first)*2*sizeof(*pcm));
    c->write_pos = (c->write_pos + frames) % SPECTRUM_SAMPLES;
    c->history_count += frames;
    if (c->history_count > SPECTRUM_SAMPLES) c->history_count = SPECTRUM_SAMPLES;
    if (c->history_count < SPECTRUM_SAMPLES ||
        (c->scheduled && (int32_t)(tick-c->next_tick) < 0)) return false;
    c->next_tick = tick + c->period;
    c->scheduled = true;
    int selected = -1;
    for (int i = 0; i < 2; i++)
        if (c->slots[i].state == SPEC_FREE) { selected = i; break; }
    if (selected < 0) {
        for (int i = 0; i < 2; i++)
            if (c->slots[i].state == SPEC_READY &&
                (selected < 0 || (int32_t)(c->slots[i].sequence-
                                          c->slots[selected].sequence) < 0)) selected = i;
        if (selected < 0) { c->drops++; return false; }
        c->drops++; /* Replace unread work; never overwrite READING. */
    }
    struct spectrum_slot *s = &c->slots[selected];
    unsigned tail = SPECTRUM_SAMPLES - c->write_pos;
    memcpy(s->pcm, c->history + 2*c->write_pos, tail*2*sizeof(*pcm));
    memcpy(s->pcm + 2*tail, c->history, c->write_pos*2*sizeof(*pcm));
    s->rate = rate; s->generation = c->generation; s->tick = tick;
    s->sequence = ++c->sequence;
    s->state = SPEC_READY; c->published = selected; c->windows++;
    return true;
}
int spectrum_capture_acquire(struct spectrum_capture *c)
{
    int selected = -1;
    for (int i = 0; i < 2; i++)
        if (c->slots[i].state == SPEC_READY &&
            (selected < 0 || (int32_t)(c->slots[i].sequence-
                                      c->slots[selected].sequence) > 0)) selected = i;
    if (selected >= 0) {
        for (int i = 0; i < 2; i++)
            if (i != selected && c->slots[i].state == SPEC_READY) {
                c->slots[i].state = SPEC_FREE; c->drops++;
            }
        c->slots[selected].state = SPEC_READING;
    }
    return selected;
}
void spectrum_capture_release(struct spectrum_capture *c, int slot)
{
    if (slot >= 0 && slot < 2 && c->slots[slot].state == SPEC_READING)
        c->slots[slot].state = SPEC_FREE;
}
