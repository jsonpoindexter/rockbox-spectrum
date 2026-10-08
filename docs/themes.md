# Independent themes and presets

Firmware and themes share this repository but have separate inputs, versions, ZIPs and installation commands. `build.py` packages firmware and matching executables with upstream default themes; it never appends our text themes or presets. Firmware installation has no CrazyBitMono requirement and preserves already installed themes. Theme-only updates need no compiler, firmware rebuild or firmware replacement once firmware 1.0.0 is installed.

| Pack source | Version | Minimum custom firmware | Runtime files |
| --- | --- | --- | --- |
| `theme-packs/ClassicSpectrum` | 1.3 | 1.0.0 | Theme cfg and WPS |
| `theme-packs/CrazyBitSpectrum` | 2.0 | 1.0.0 | Theme cfg and WPS |
| `theme-packs/CrazyBitSpectrumColor` | 2.0 | 1.0.0 | Theme cfg and WPS |
| `theme-packs/SpectrumPresets` | 1.0 | 1.0.0 | Motion, visual-gain and guide toggle cfg files |

[ClassicSpectrum](../theme-packs/ClassicSpectrum/README.md) retains metadata, playback/battery indicators, volume, progress and Hold layout while allocating a 280×70 area to 16 bars. Its five approximate labels (100 Hz, 250 Hz, 1 kHz, 4 kHz, 10 kHz) guide the logarithmic scale; they are not exact FFT-bin or pitch readings. Version 1.3 explicitly requests the default dot appearance. Existing seven-argument WPS tags also retain that appearance.

The three original adapted themes require separately installed original [CrazyBit Mono theme, ID 3951](https://themes.rockbox.org/index.php?themeid=3951&target=ipod6g) SBS, icons, bitmaps and fonts, including LanaPixel. This repository redistributes adapted text only; credits remain in each source file and [NOTICES](../NOTICES.md). Preset files have no artwork dependency. Schema2 ZIP manifests record payload hashes, license, minimum firmware version, required spectrum skin API and direct asset references. Existing schema1 development packs remain supported by the installer. Install the complete original asset/font set, including assets used indirectly by its SBS; those legacy packs remain text-only.

Download each pack independently from [its release](releases.md). Verify its `SHA256SUMS`, then use the installation commands below with the downloaded filename. The three original theme packs require the complete original CrazyBitMono asset/font set; SpectrumPresets and the new complete collection do not.

## Complete collection

| Pack | Version | Layouts / style |
| --- | --- | --- |
| [WinampSpectrum](../theme-packs/WinampSpectrum/README.md) | 1.0 | Detail / Visualizer; charcoal, pixel type, classic 32 bars |
| [StudioSpectrum](../theme-packs/StudioSpectrum/README.md) | 1.0 | Detail 16 bars / Visualizer 32-band line; amber |
| [AdwaitaSpectrum](../theme-packs/AdwaitaSpectrum/README.md) | 1.0 | Detail thumbnail + 16 bars / Visualizer 32 bars; light/blue |

Each schema3 ZIP includes both layouts, menu skin, required fonts/images and component licenses. It needs custom firmware 1.0.0 / skin API2, with no original theme installation. Build/install commands below apply with the desired pack and ZIP names. Select `<Pack>-Detail` or `<Pack>-Visualizer` after installation. These cfg files load appearance and enable the spectrum; they preserve audio/EQ, navigation, motion/gain and backlight preferences. [Design, asset locks and simulator procedure](theme-collection.md).

## Build, verify and install one pack

These commands run on the host without an ARM toolchain. Use a fresh output filename:

```sh
python3 tools/theme-pack.py build theme-packs/ClassicSpectrum --output build/themes/ClassicSpectrum-1.3.zip
python3 tools/theme-pack.py verify build/themes/ClassicSpectrum-1.3.zip
```

The build prints the ZIP SHA-256. Fixed ZIP metadata makes identical inputs reproducible in the same Python/zlib environment. Review the dependency list; use the printed checksum and your actual mounted path for a dry run:

```sh
python3 tools/theme-pack.py install build/themes/ClassicSpectrum-1.3.zip \
  --sha256 PACKAGE_SHA256 --volume /path/to/ipod --session /path/to/fresh-theme-session
```

Repeat with `--apply` to copy only the pack payload files. The host session retains only overwritten theme files plus before/after hashes; it is not a new full device backup. Firmware, plugins/codecs, music and saved settings are excluded by the payload whitelist. The installer never selects the theme or loads a cfg. Safely eject, then select **Settings → Theme Settings → Browse Theme Files → ClassicSpectrum**. Ensure **Spectrum Visualizer** is On. For SpectrumPresets, load a single cfg via **Manage Settings → Browse .cfg Files**.

To undo a theme file update, use the recorded session (dry-run by default):

```sh
python3 tools/theme-pack.py rollback --volume /path/to/ipod --session /path/to/recorded-theme-session
```

Repeat with `--apply`. Later edits to installed theme files block rollback rather than being overwritten. Select the previous theme/settings manually if you changed them on the device. Selecting a theme can load its cfg sound settings; copying or rolling back its files does not restore saved settings.

## Theme-owned spectrum presentation

Firmware 1.0.0 accepts either the original seven fields, or fourteen fields including the complete presentation block:

```text
%pF(x,y,width,height,bands,mode,palette)
%pF(x,y,width,height,bands,mode,palette,guides,guidecolor,pitch,border,barcolor,peakcolor,inset)
%pF(0,0,280,70,16,bars,mono,dots,auto,4,lanes,auto,auto,1)
```

Partial optional blocks and unknown values are rejected at parse time. Coordinates must fit the viewport and the 320×240 target. Bands are 8/16/32, mode is `bars`/`lines`, palette is `mono`/`classic`.

| Presentation field | Values / meaning | Compatibility default |
| --- | --- | --- |
| `guides` | `dots`, `solid`, `off` | `dots` |
| `guidecolor` | Six hexadecimal RGB digits or `auto`; auto uses 75% of foreground channels | `auto` |
| `pitch` | Dot interval, integer 2–16 pixels; phase starts at each lane | `4` |
| `border` | `lanes` = top/bottom markers plus interior separators; `frame` additionally draws left/right edges; `baseline` = bottom markers only | `lanes` |
| `barcolor` | Six RGB digits or `auto`; explicit color overrides mono/classic bar palette and line color | `auto` |
| `peakcolor` | Six RGB digits or `auto`; auto retains foreground peak caps | `auto` |
| `inset` | Horizontal inset per side of each bar when guides are drawn, integer 1–3 pixels | `1` |

Guides retain the three-pixel vertical reservation per end; the top marker is at y=0 and bottom at height−2. Horizontal rows are lane-relative and exclude the one-pixel inter-lane gap; frame adds outer vertical columns without changing that phase or marker geometry. Global **Spectrum Lane Guides → Off** overrides theme guides. Guides are not drawn in line mode, below eight pixels height or below `(2×inset+6)` pixels lane pitch; those cases retain plain-bar geometry. RGB colors are quantized to the display format. The default is the existing single-dot style, with no outer vertical frame. Bar colors, peak colors and guide colors are independent.

Theme parameters control presentation only. FFT mapping, capture cadence, responsiveness, motion presets, auto gain and pause/stop descent remain firmware behavior. Modify text and bump that pack's `pack.json` version for a theme update; native changes use the firmware version in `VERSION`. Theme manifests and ZIPs stay outside the firmware manifest.

CI builds/verifies all seven packs independently and verifies that firmware contains none of their runtime files. Complete-pack WPS/SBS checks load real packaged bitmaps; legacy WPS checks use synthetic bitmaps with preserved sprite frame counts. Font metrics and complete appearance require separate simulator inspection. CI does not claim physical-device validation.
