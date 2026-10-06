/* On-demand timing report: no observer/worker filesystem operations.
 * GPL-2.0-or-later. */
#include "config.h"
#include "service.h"
#include "list.h"
#include "action.h"
#include "file.h"
#include "splash.h"
#include "kernel.h"
#include <stdio.h>
static struct spectrum_timing snapshot;
static const char *names[] = {"Observer", "Analysis", "Draw", "LCD submit", "Frame age", "Submit interval"};
static unsigned percentile(const struct spectrum_metric *m)
{
    uint32_t need = m->count - m->count / 20, total = 0;
    if (!need) return 0;
    for (unsigned i = 0; i < SPECTRUM_BUCKETS; i++) {
        total += m->buckets[i];
        if (total >= need) return i + 1;
    }
    return SPECTRUM_BUCKETS;
}
static const char *p95(const struct spectrum_metric *m, char *text)
{
    unsigned value = percentile(m);
    if (!m->count) snprintf(text, 24, "no samples");
    else if (value == SPECTRUM_BUCKETS) snprintf(text, 24, ">=127ms");
    else snprintf(text, 24, "<%ums", value);
    return text;
}
static int timing_action(int action, struct gui_synclist *lists)
{
    (void)lists;
    if (action == ACTION_STD_OK) {
        int fd = open("/.rockbox/spectrum-timing.txt", O_WRONLY | O_CREAT | O_TRUNC, 0666);
        if (fd >= 0) {
            fdprintf(fd, "fast5 timing since boot; p95 rounded to 1ms, >=127ms overflow\n"
                "Capture to LCD submission age; not audible/display latency.\n");
            for (int i = 0; i < SPECTRUM_METRICS; i++) {
                char text[24];
                fdprintf(fd, "%s: n=%lu p95=%s max=%luus\n", names[i],
                    (unsigned long)snapshot.metric[i].count, p95(&snapshot.metric[i], text),
                    (unsigned long)snapshot.metric[i].maximum);
            }
            fdprintf(fd, "windows=%lu drops=%lu stale draws=%lu pressure events=%lu skipped draws=%lu\n",
                (unsigned long)snapshot.windows, (unsigned long)snapshot.drops,
                (unsigned long)snapshot.stale, (unsigned long)snapshot.pressure,
                (unsigned long)snapshot.skipped);
            close(fd);
            splash(HZ, "Saved spectrum-timing.txt");
        } else splash(HZ, "Timing export failed");
        return ACTION_REDRAW;
    }
    return action;
}
bool spectrum_debug_menu(void)
{
    struct simplelist_info info;
    spectrum_timing_snapshot(&snapshot);
    simplelist_info_init(&info, "Spectrum timing", 0, NULL);
    info.action_callback = timing_action;
    simplelist_reset_lines();
    simplelist_addline("Since boot; Center exports report");
    for (int i = 0; i < SPECTRUM_METRICS; i++) {
        char text[24];
        simplelist_addline("%s p95 %s max %luus", names[i], p95(&snapshot.metric[i], text),
            (unsigned long)snapshot.metric[i].maximum);
    }
    simplelist_addline("Windows %lu; drops %lu", (unsigned long)snapshot.windows, (unsigned long)snapshot.drops);
    simplelist_addline("Pressure %lu; stale %lu", (unsigned long)snapshot.pressure, (unsigned long)snapshot.stale);
    simplelist_addline("Skipped %lu", (unsigned long)snapshot.skipped);
    simplelist_addline("Age is to LCD submission only");
    return simplelist_show_list(&info);
}
