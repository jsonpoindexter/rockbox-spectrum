# Complete animated theme collection — 2.0 preview

The three packs now use distinct compositions and native animations. This is a
local preview requiring firmware 1.1.0 / skin API 3, not a published release.

| Pack | Detail | Immersive (`Visualizer`) |
| --- | --- | --- |
| WinampSpectrum | Inset feedback window beside LED time; title ticker and compact deck | Large feedback canvas above a narrow transport strip |
| StudioSpectrum | Left data rail beside a tall amber phosphor instrument | Large track heading above a broad orbit; one transport row below |
| AdwaitaSpectrum | Centered album sleeve, headline title/artist and quiet ribbon band | Wide flowing canvas above airy centered captions |

Detail retains metadata, codec/bitrate, queue/modes, volume, battery/charging,
state and time/progress. Immersive emphasizes movement and essential track/time
information. Hold and menus follow each pack's typography and spatial identity.
See [design rules](../.interface-design/system.md) and [native animation API](animated-visualizers.md).

Font viewports use actual RB12 heights: Lana07 17px, Lana14 28px, Cantarell18 23px,
Cantarell20Bold 21px and Cantarell24 28px. Menus and the global UI font use
28px-high fonts in all three packs, including settings/submenus: Lana14 for
Winamp/Studio, and the pinned upstream accessibility Cantarell24 for Adwaita.
Studio Immersive replaces the narrow side rail with a full-width title, artist,
296×144 phosphor stage and a single time/state/volume row; battery and progress
remain visible. Detail and Hold retain their existing compositions.
Animation cannot paint over text or artwork. Missing album
art uses an original geometric fallback; missing metadata falls back to filename
and unknown artist/album. Existing font/art licenses and locked sources remain.

## Packaging contract

Schema 3 scopes every runtime path to the pack ID: two cfg/WPS layouts, one SBS, namespaced fonts, a namespaced bitmap directory and component-license directory. Complete packs have no external theme dependency. The cfg allowlist accepts appearance and `spectrum enabled: on`; it refuses sound, EQ, motion/gain, navigation/language and backlight changes. Firmware, codecs/plugins, music and saved `config.cfg` are never payloads. Schema 1/2 installations and their recovery sessions remain supported.

Archive limits are 32 MiB compressed, 64 MiB expanded and 256 files. The original smaller limits remain for legacy packs. Paths, symlinks, duplicate/case-colliding names, hashes, dependencies and signatures are checked before installation. Each pack has isolated filenames so it can be installed/rolled back independently; fonts from another pack are never overwritten. Dry runs do not create a session or change the mounted tree. Apply retains only overwritten files, verifies copies and restores prior bytes on a write failure. Later edits block rollback.

Downloaded assets stay in an ignored content-addressed cache. Both the download and selected members are SHA-256 checked; downloads are HTTPS-only and bounded. Release ZIPs redistribute the required licensed assets; source Git stores their locks and licenses, not binary copies. Each component retains its license and source credit. The original font bytes are unmodified and only filesystem names change for isolation.

## Real simulator previews

Build the 1.1.0 candidate simulator using `tools/build.py --kind simulator`. Inside a Linux environment with SDL2, Xvfb, xdotool and ImageMagick:

```sh
xvfb-run -a python3 tools/theme-preview.py \
  --simulator /work/spectrum-simulator/rockboxui \
  --base /work/spectrum-simulator/simdisk \
  --packages /work/theme-packs --output /reports/previews
```

Use `docker run --init` when wrapping this command in Docker, so Xvfb's readiness signal is handled correctly. The output must be fresh. The harness creates disposable player trees, deterministic synthetic PCM and fictional metadata/cover art. It loads the actual complete theme ZIP, runs real playback and captures 320×240 PNGs plus a looping GIF. With optional FFmpeg installed in the preview container, it records six seconds at 25 fps into lossless video, MP4 and GIF; sampled lossless frames feed the appearance checks. Installing this preview dependency does not change the pinned compiler inputs. It does not access an iPod or personal music. The simulator temporarily forces the backlight on (including Hold), enables display-only gain and uses Smooth motion; none of those fixture settings enter a theme ZIP.

`--scenario long-metadata`, `missing-metadata` or `spectrum-off` makes separate edge-case captures; `--theme` restricts the pack. Normal captures include browser, playback, pause tail, paused state, Hold, main menu and resumed playback. Captures are evidence to inspect, not an automatic claim of visual acceptance. GIF timing is illustrative screen capture timing, not a device frame-rate measurement. Native portable animation tests remain the numeric correctness checks.

`tools/parse-theme.py --asset-root /path/to/extracted-pack` checks each new WPS and SBS using real packaged bitmaps. Legacy parser checks retain synthetic bitmap dependencies and make no artwork claim. CI builds all seven independent packs, parses their skins and verifies the firmware ZIP excludes custom themes.

## Validation boundary

Native code and tools require portable checks plus complete firmware, simulator,
parser and package validation. Inspect actual six-layout simulator captures and
edge cases before presenting previews. Animated captures illustrate appearance,
not physical frame rate. Publication and device installation follow user visual
review and a short device trial. Device records, settings and recovery stay in
the separate iPod project.

## Review gallery

With FFmpeg available, the captures include self-contained MP4 clips as well as
GIFs. `tools/verify-animation-previews.py` checks moving animation regions,
stable normal metadata and settled pause/off screens. Use the four capture
folders `preview-final-normal`, `preview-final-long-metadata`,
`preview-final-missing-metadata`, `preview-final-spectrum-off` beneath a report
root, then generate the portable HTML review artifact:

```sh
python3 tools/theme-gallery.py reports --output reports/preview-gallery.html
```

The gallery embeds its videos/images and needs no server or external assets.
Its stock simulator menu labels do not replace personal Music/Extras settings.
