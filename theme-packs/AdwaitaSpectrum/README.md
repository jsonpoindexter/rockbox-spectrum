# AdwaitaSpectrum 1.0

Light GNOME-inspired surfaces, blue bars, Cantarell typography and status icons.

Two independently selectable layouts in one complete pack for the 320×240 iPod Classic:

| Layout | Spectrum | Information |
| --- | --- | --- |
| Detail | 296×78, 16 bars | Title, artist, album/year, codec/bitrate, queue, shuffle/repeat, volume, battery/charging, state and times |
| Visualizer | 296×130, 32 blue bars | Title, artist, volume, battery/charging, state and times |

Both include approximate frequency labels, progress/volume bars, a coordinated menu skin and a Hold composition without a spectrum. Adwaita Detail includes a 58×58 album thumbnail with a drawn fallback. Winamp and Studio dedicate that space to metadata. Long metadata scrolls within its viewport. Hold/backlight power behavior remains the user's firmware setting.

Requires **custom firmware 1.0.0 / spectrum skin API 2**. Stock Rockbox and the older fast9 build cannot use the complete fourteen-field styling tag. No firmware rebuild is needed once compatible firmware is installed. Both layouts share their pack's isolated fonts/assets; another theme pack is not required.

## Download and select

[Download the experimental 1.0 release](https://github.com/jsonpoindexter/rockbox-spectrum/releases/tag/theme-adwaitaspectrum-v1.0). It includes real SDL simulator previews; these are not photographs or physical-device acceptance tests.

Follow the [pack installation and rollback guide](../../docs/themes.md). After copying and safely ejecting, select `AdwaitaSpectrum-Detail` or `AdwaitaSpectrum-Visualizer` in **Settings → Theme Settings → Browse Theme Files**. Selection enables the spectrum and loads appearance settings. Audio/EQ, motion/automatic gain, navigation and backlight settings remain user-controlled. The menu still uses your current language/menu configuration, including any separately configured Music/Extras labels.

## Build from source

```sh
python3 tools/theme-pack.py build theme-packs/AdwaitaSpectrum --output build/themes/AdwaitaSpectrum-1.0.zip
python3 tools/theme-pack.py verify build/themes/AdwaitaSpectrum-1.0.zip
```

`assets.json` pins HTTPS source URLs, full download hashes and individual member hashes. The builder downloads into ignored `build/theme-assets`, verifies every byte and includes only selected assets. Pass `--asset-cache /path/to/cache` for a read-only source checkout. Source Git contains text/locks/licenses; the release ZIP contains the fonts and images. Identical inputs reproduce the ZIP in the same Python/zlib environment.

## Credits and design

Adwaitapod by Evan Kenny (Dook), pinned in assets.json. Cantarell/Noto Sans fonts (SIL OFL 1.1); GNOME status sprites (CC-BY-SA 3.0). Layout and menu/Hold composition adapted; font and sprite bytes unchanged. See the included [attribution](.rockbox/themes/AdwaitaSpectrum/licenses/ATTRIBUTION.txt) and adjacent full license texts. New/adapted skin text is CC-BY-SA 3.0; AI-assisted with OpenAI Codex, 2026-10-08. See the [collection design and simulator procedure](../../docs/theme-collection.md).
