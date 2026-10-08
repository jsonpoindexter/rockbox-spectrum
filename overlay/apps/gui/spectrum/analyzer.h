/* Native spectrum analysis. GPL-2.0-or-later. */
#ifndef SPECTRUM_ANALYZER_H
#define SPECTRUM_ANALYZER_H
#include <stdint.h>
#include <stdbool.h>
#define SPECTRUM_SAMPLES 1024
#define SPECTRUM_BANDS 32
#define SPECTRUM_FLOOR (-72 * 256)
struct spectrum_frame {
    uint32_t generation, sequence, sample_rate, tick, capture_us;
    int16_t wave[128][2]; /* DC-removed, box-filtered stereo waveform. */
    int16_t energy[3], onset; /* Low/mid/high Q8 dBFS; positive spectral flux. */
    int16_t db[SPECTRUM_BANDS]; /* Q8 dBFS, [-72, 0] */
};
struct spectrum_analyzer {
    int32_t real[SPECTRUM_SAMPLES], imag[SPECTRUM_SAMPLES];
    uint64_t power[SPECTRUM_SAMPLES / 2];
    uint32_t cached_rate, generation;
    int16_t previous_energy[3];
    uint16_t lo[SPECTRUM_BANDS], hi[SPECTRUM_BANDS];
};
void spectrum_analyze(struct spectrum_analyzer *a, const int16_t *stereo,
                      uint32_t rate, struct spectrum_frame *out);
#endif
