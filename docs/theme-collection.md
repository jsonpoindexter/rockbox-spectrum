# Complete spectrum theme collection

Three independently versioned 1.0 packs, six layouts, one existing firmware API. WinampSpectrum uses charcoal panels, LanaPixel and classic 32-bar color; StudioSpectrum uses amber and a 32-band frequency line in its Visualizer layout; AdwaitaSpectrum adapts Adwaitapod's light surfaces, Cantarell typography and GNOME status artwork. Its Detail view adds album art. Each pack supplies its own WPS, menu/SBS, fonts, assets and licenses.

## Layout contract

The canvas is 320×240. Header occupies the first 23 pixels. Detail reserves y=26–110 for metadata, y=114–191 for a 296×78 spectrum. Visualizer uses compact metadata through y=60 and a 296×130 spectrum at y=62–191. Approximate log-frequency labels share y=195; playback state/volume/battery use y=208, volume y=219 and times/progress y=227–233. Labels describe approximate frequencies, not exact bin centers or pitch detection.

Detail keeps title, artist, album/year, codec/bitrate, queue, shuffle/repeat, battery/charging, volume, state, elapsed/total time and seek progress. Visualizer intentionally removes album/codec/queue detail. Hold uses time, title, artist, battery, state and elapsed/total time, with no spectrum. The inherited backlight-on-Hold preference can turn the screen off; a theme does not override it.

Font metrics are read from the actual RB12 header: LanaPixel 07 is **17 pixels tall**, 14 is **28**; Cantarell Regular 18 is **23**, Bold 20 is **21**. The filename number is not the viewport height. Small labels use Rockbox's built-in 6×8 font. Text viewports allow a complete line; long metadata scrolls without overlapping the analyzer. The menu reserves its own list viewport so the header/footer cannot be overwritten by menu entries.

## Packaging contract

Schema 3 scopes every runtime path to the pack ID: two cfg/WPS layouts, one SBS, namespaced fonts, a namespaced bitmap directory and component-license directory. Complete packs have no external theme dependency. The cfg allowlist accepts appearance and `spectrum enabled: on`; it refuses sound, EQ, motion/gain, navigation/language and backlight changes. Firmware, codecs/plugins, music and saved `config.cfg` are never payloads. Schema 1/2 installations and their recovery sessions remain supported.

Archive limits are 32 MiB compressed, 64 MiB expanded and 256 files. The original smaller limits remain for legacy packs. Paths, symlinks, duplicate/case-colliding names, hashes, dependencies and signatures are checked before installation. Each pack has isolated filenames so it can be installed/rolled back independently; fonts from another pack are never overwritten. Dry runs do not create a session or change the mounted tree. Apply retains only overwritten files, verifies copies and restores prior bytes on a write failure. Later edits block rollback.

Downloaded assets stay in an ignored content-addressed cache. Both the download and selected members are SHA-256 checked; downloads are HTTPS-only and bounded. Release ZIPs redistribute the required licensed assets; source Git stores their locks and licenses, not binary copies. Each component retains its license and source credit. The original font bytes are unmodified and only filesystem names change for isolation.

## Real simulator previews

Build the unchanged 1.0.0 simulator using `tools/build.py --kind simulator`. Inside a Linux environment with SDL2, Xvfb, xdotool and ImageMagick:

```sh
xvfb-run -a python3 tools/theme-preview.py \
  --simulator /work/spectrum-simulator/rockboxui \
  --base /work/spectrum-simulator/simdisk \
  --packages /work/theme-packs --output /reports/previews
```

Use `docker run --init` when wrapping this command in Docker, so Xvfb's readiness signal is handled correctly. The output must be fresh. The harness creates disposable player trees, deterministic synthetic PCM and fictional metadata/cover art. It loads the actual complete theme ZIP, runs real playback and captures 320×240 PNGs plus a looping GIF. It does not access an iPod or personal music. The simulator temporarily forces the backlight on (including Hold), enables display-only gain and uses Smooth motion; none of those fixture settings enter a theme ZIP.

`--scenario long-metadata`, `missing-metadata` or `spectrum-off` makes separate edge-case captures; `--theme` restricts the pack. Normal captures include browser, playback, pause tail, paused state, Hold, main menu and resumed playback. Captures are evidence to inspect, not an automatic claim of visual acceptance. GIF timing is illustrative screen capture timing, not a device frame-rate measurement. Native portable animation tests remain the numeric correctness checks.

`tools/parse-theme.py --asset-root /path/to/extracted-pack` checks each new WPS and SBS using real packaged bitmaps. Legacy parser checks retain synthetic bitmap dependencies and make no artwork claim. CI builds all seven independent packs, parses their skins and verifies the firmware ZIP excludes custom themes.

## Validation boundary

The collection changes theme source and host packaging/preview tooling only. Firmware VERSION remains 1.0.0 and the native patch/overlay fingerprints are unchanged. Simulator appearance and portable transaction tests do not establish physical iPod boot, audio, performance, battery life or installation. Release notes identify the exact source and evidence. Device-specific installation/recovery and Music/Extras navigation stay in the separate iPod record project.
