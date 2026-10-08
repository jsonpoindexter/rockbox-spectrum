# WinampSpectrum 2.0 — local preview

Complete Detail and immersive Visualizer layouts with **Feedback Tunnel** as the signature.
Requires custom firmware **1.1.0 / skin API 3**. Not yet published or installed.

[Composition, font metrics and preview workflow](../../docs/theme-collection.md).
[Effect selection and native rendering](../../docs/animated-visualizers.md).

The pack includes its menu/Hold design, namespaced fonts/assets and component
licenses. Detail retains full track/status information; Visualizer emphasizes
animation. Theme selection changes appearance and enables visualization while
preserving effect preference, sound/EQ, motion/gain, navigation and backlight.

```sh
python3 tools/theme-pack.py build theme-packs/WinampSpectrum --output build/themes/WinampSpectrum-2.0.zip
python3 tools/theme-pack.py verify build/themes/WinampSpectrum-2.0.zip
```

After the preview review and device trial, follow the [independent installation
and rollback guide](../../docs/themes.md). Select `WinampSpectrum-Detail` or
`WinampSpectrum-Visualizer` via Browse Theme Files. Prior 1.0 releases remain unchanged.

Original skin text CC-BY-SA 3.0; bundled components retain their licenses and pinned
source attribution. See [.rockbox component notices](.rockbox/themes/WinampSpectrum/licenses/ATTRIBUTION.txt).
AI-assisted with OpenAI Codex, 2026-10-08. No proprietary player artwork or preset
files are included.
