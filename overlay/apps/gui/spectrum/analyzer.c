/* Native fixed-point radix-2 FFT. GPL-2.0-or-later.
 * Stereo channels are packed into one complex FFT; power is recovered
 * from conjugate bin pairs, avoiding antiphase cancellation.
 * Each butterfly scales by two; forward transform is normalized by N.
 * No allocation, floating point, or platform dependencies at runtime. */
#include "analyzer.h"
#include "tables.h"
#include <string.h>
#include <limits.h>

static int32_t limit32(int64_t value)
{
    if (value > INT32_MAX) return INT32_MAX;
    if (value < INT32_MIN) return INT32_MIN;
    return (int32_t)value;
}

/* log2 in Q8. Normalize to [1,2) Q31, then eight binary-log steps. */
static int32_t log2_q8(uint64_t value)
{
    if (!value) return -32768;
    unsigned bit = 0;
    uint64_t scan = value;
    while (scan >>= 1) bit++;
    uint64_t x = bit > 31 ? value >> (bit - 31) : value << (31 - bit);
    unsigned fraction = 0;
    for (int i = 0; i < 8; i++) {
        x = (x * x) >> 31;
        fraction <<= 1;
        if (x >= (1ULL << 32)) {
            x >>= 1;
            fraction |= 1;
        }
    }
    return (int32_t)(bit * 256 + fraction);
}

static void transform(struct spectrum_analyzer *a)
{
    for (unsigned i = 1, j = 0; i < SPECTRUM_SAMPLES; i++) {
        unsigned bit = SPECTRUM_SAMPLES >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) {
            int32_t r = a->real[i], im = a->imag[i];
            a->real[i] = a->real[j]; a->imag[i] = a->imag[j];
            a->real[j] = r; a->imag[j] = im;
        }
    }
    for (unsigned len = 2; len <= SPECTRUM_SAMPLES; len <<= 1) {
        unsigned half = len >> 1, stride = SPECTRUM_SAMPLES / len;
        for (unsigned start = 0; start < SPECTRUM_SAMPLES; start += len) {
            for (unsigned j = 0; j < half; j++) {
                unsigned p = start + j, q = p + half, t = j * stride;
                int32_t wr = spectrum_cos[t], wi = spectrum_sin[t];
                int64_t vr = ((int64_t)a->real[q] * wr -
                              (int64_t)a->imag[q] * wi) / 32768;
                int64_t vi = ((int64_t)a->real[q] * wi +
                              (int64_t)a->imag[q] * wr) / 32768;
                int32_t ur = a->real[p], ui = a->imag[p];
                a->real[p] = limit32(((int64_t)ur + vr) / 2);
                a->imag[p] = limit32(((int64_t)ui + vi) / 2);
                a->real[q] = limit32(((int64_t)ur - vr) / 2);
                a->imag[q] = limit32(((int64_t)ui - vi) / 2);
            }
        }
    }
}

void spectrum_analyze(struct spectrum_analyzer *a, const int16_t *stereo,
                      uint32_t rate, struct spectrum_frame *out)
{
    out->sample_rate = rate;
    int64_t sums[2] = {0, 0};
    for (unsigned i = 0; i < SPECTRUM_SAMPLES; i++) {
        sums[0] += stereo[2 * i];
        sums[1] += stereo[2 * i + 1];
    }
    int32_t means[2] = {sums[0] / SPECTRUM_SAMPLES,
                        sums[1] / SPECTRUM_SAMPLES};
    for (unsigned i = 0; i < SPECTRUM_SAMPLES; i++) {
        /* Two real inputs share one complex FFT: Z = FFT(L + iR).
         * Same DC removal, window and normalization as the two-FFT path. */
        a->real[i] = (stereo[2 * i] - means[0]) * (int32_t)spectrum_hann[i];
        a->imag[i] = (stereo[2 * i + 1] - means[1]) * (int32_t)spectrum_hann[i];
    }
    for (unsigned i=0;i<128;i++) for (unsigned channel=0;channel<2;channel++) {
        int sum=0;
        for (unsigned j=0;j<8;j++) sum+=stereo[(i*8+j)*2+channel]-means[channel];
        int value=sum/8;
        out->wave[i][channel]=value<-32768?-32768:value>32767?32767:value;
    }
    transform(a);
    a->power[0] = 0;
    for (unsigned i = 1; i < SPECTRUM_SAMPLES / 2; i++) {
        unsigned mirror = SPECTRUM_SAMPLES - i;
        int64_t r = a->real[i], im = a->imag[i];
        int64_t mr = a->real[mirror], mi = a->imag[mirror];
        /* (|L[k]|^2 + |R[k]|^2)/2 = (|Z[k]|^2 + |Z[N-k]|^2)/4.
         * Divide each nonnegative square first to avoid uint64 sum overflow. */
        a->power[i] = (uint64_t)(r * r) / 4 + (uint64_t)(im * im) / 4 +
                      (uint64_t)(mr * mr) / 4 + (uint64_t)(mi * mi) / 4;
    }
    if (a->cached_rate != rate || !rate) {
        unsigned upper = rate / 2 < 20000 ? rate / 2 : 20000;
        unsigned delta = upper > 60 ? (log2_q8(upper) - log2_q8(60)) / 32 : 0;
        if (delta > 255) delta = 255;
        uint64_t edge = 60ULL << 16;
        for (unsigned band = 0; band < SPECTRUM_BANDS; band++) {
            uint64_t next = band == 31 ? (uint64_t)upper << 16 :
                            (edge * spectrum_exp2[delta]) >> 16;
            unsigned lo = rate ? (edge * SPECTRUM_SAMPLES / rate + 65535) >> 16 : 1;
            unsigned hi = rate ? (next * SPECTRUM_SAMPLES / rate + 65535) >> 16 : 1;
            if (lo < 1) lo = 1;
            if (lo > 511) lo = 511;
            if (hi <= lo) hi = lo + 1;
            if (hi > 512) hi = 512;
            a->lo[band] = lo; a->hi[band] = hi;
            edge = next;
        }
        a->cached_rate = rate;
    }
    /* log2_q8(268419072ULL * 268419072) = 14335. */
    const int32_t ref_log = 14335;
    for (unsigned band = 0; band < SPECTRUM_BANDS; band++) {
        unsigned lo = a->lo[band], hi = a->hi[band];
        uint64_t peak = 0;
        for (unsigned bin = lo; bin < hi; bin++)
            if (a->power[bin] > peak) peak = a->power[bin];
        int32_t db = peak ? (log2_q8(peak) - ref_log) * 771 / 256 : SPECTRUM_FLOOR;
        if (db < SPECTRUM_FLOOR) db = SPECTRUM_FLOOR;
        if (db > 0) db = 0;
        out->db[band] = db;
    }
    out->onset=0;
    for (int region=0;region<3;region++) {
        int peak=SPECTRUM_FLOOR;
        int lo=region==0?0:region==1?9:22;
        int hi=region==0?9:region==1?22:32;
        for (int i=lo;i<hi;i++) if (out->db[i]>peak) peak=out->db[i];
        out->energy[region]=peak;
        int flux=peak-a->previous_energy[region];
        if (a->generation==out->generation && flux>out->onset) out->onset=flux;
        a->previous_energy[region]=peak;
    }
    a->generation=out->generation;

}
