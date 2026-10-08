# Rockbox Spectrum

[![CI](https://github.com/jsonpoindexter/rockbox-spectrum/actions/workflows/ci.yml/badge.svg)](https://github.com/jsonpoindexter/rockbox-spectrum/actions/workflows/ci.yml)

Experimental native Now Playing spectrum for **Rockbox 4.0 on `ipod6g`**, developed for the iPod Classic 120GB commonly called the 6.5 generation. This is a patch/build project, not a full upstream fork.

Current source: **1.1.0 local preview candidate**, built as **`4.0-spectrum-1.1.0-e094c599fa`**. Published firmware remains **1.0.0**. See [animated visualizers](docs/animated-visualizers.md) for the preview review gate. The version in [`VERSION`](VERSION) identifies our firmware separately from Rockbox 4.0 and the pinned upstream revision. It includes native spectrum analysis, motion/visual gain, theme-owned styling and independently packaged themes. Host validation does not establish hardware acceptance; a built package is not proof of device installation.

## Features

- Native feedback tunnels, phosphor orbits and flowing ribbons via `%pV`; manual/theme effect selection and optional auto cycling. Animation targets 25 fps; physical performance remains unverified.

- True stereo-power FFT spectrum inside Now Playing using `%pF(x,y,width,height,bands,mode,palette)`.
- 8/16/32 displayed bands, bars/lines, mono/classic palettes, theme-configurable guides and colors.
- Fast3/Smooth/Punchy/Classic motion presets; optional display-only automatic gain. Visual gain does not change audio or EQ.
- Owned playback PCM snapshots and a background analysis worker; animation targets at most 50 Hz, with unchanged-frame suppression and batched LCD updates.
- Pause/stop disable capture and animate the existing display down; stop exits after a bounded tail. Hidden WPS/backlight-off cancel animation.
- Existing playback controls and bootloader retained. No bootloader or partition installation is included.

Download [firmware and independent packs](docs/releases.md). See [architecture and controls](docs/architecture.md), [build and test](docs/build.md), [themes](docs/themes.md), and [file-only trial/recovery](docs/device-trial.md).

## Quick start

Portable checks require Python 3.8+, a C compiler and ImageMagick (`convert`):

```sh
python3 tools/test.py --output reports/portable
```

Build in the pinned ARM64 Linux container; Apple Silicon runs it natively. Intel hosts require Docker ARM64 emulation and will be slower:

```sh
docker build --platform linux/arm64 -t rockbox-spectrum-builder .
docker volume create rockbox-spectrum-work
docker volume create rockbox-spectrum-toolchain
docker run --rm --platform linux/arm64 \
  --mount "type=bind,src=$PWD,dst=/project,readonly" \
  --mount type=volume,src=rockbox-spectrum-work,dst=/work \
  --mount type=volume,src=rockbox-spectrum-toolchain,dst=/opt/toolchain \
  rockbox-spectrum-builder \
  python3 /project/tools/ci-build.py --work /work/run-1 --reports /work/reports/run-1 --jobs 4
```

Use a new work/report name for each run. Build outputs remain in the work volume. Never mount an iPod volume into the build container. The [build guide](docs/build.md) explains individual targets and copying local reports/packages out.

## Compatibility

The patch is pinned to [Rockbox v4.0-final](https://github.com/Rockbox/rockbox/tree/e094c599fa60236527f9e272e0b8309d7696e399). Changed upstream files and source archives are fingerprinted before patching.

Custom plugin API **276** (1.0.0 uses 275) and codec API **50** require matching firmware, plugins and codecs as one package. Stock Rockbox 4.0 cannot parse `%pF`; do not mix its executable plugins with this firmware. The original Classic/CrazyBit packs depend on separately installed CrazyBitMono assets/fonts. The new [Winamp, Studio and Adwaita collection](docs/theme-collection.md) supplies complete packs with two layouts each; firmware itself has no theme dependency. Custom themes and presets are never appended to the firmware ZIP. Build them independently with `tools/theme-pack.py`; see [theme packaging and styling](docs/themes.md).

GitHub CI runs portable checks and native ARM64 firmware/simulator/checkwps builds, preserving reports only. Verified packages are published separately as [GitHub Releases](docs/releases.md). Firmware and theme/preset packs use independent tags; experimental builds are marked pre-release.

## Maintenance and provenance

This repository is authoritative for future spectrum firmware development. Device-specific records, settings, backups and installation evidence remain in the separate [iPod project](https://github.com/jsonpoindexter/ipod-classic-6.5). Original local source snapshots remain historical recovery references.

The [migration provenance](docs/provenance.md) identifies the imported fast5 source and file hashes. Existing code and support tools are AI-assisted; upstream acceptance and independent human review are not claimed. [NOTICES](NOTICES.md) describes attribution and component licenses; [COPYING](COPYING) contains GPL v2 terms. Theme text retains its own CC-BY-SA attribution. Complete theme releases include the required licensed fonts/artwork; source Git retains pinned asset locks and attribution.
