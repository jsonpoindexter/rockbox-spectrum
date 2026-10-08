# Native music animations — local preview candidate

Firmware 1.1.0 introduces skin API 3 and custom plugin API 276, with matching
plugins and unchanged codec API 50. These local candidates have not been released
or installed. Existing 1.0.0 releases remain immutable. Theme packs are version 2.0
and require 1.1.0; classic `%pF` themes remain supported.

## Theme API and controls

```
%pV(x,y,width,height,effect,background,primary,accent)
%pV(0,0,312,172,feedback,080d18,42aaff,f75fae)
```

Effects are `feedback`, `phosphor`, `ribbons`. Colors require six hexadecimal RGB
digits; `auto` is not accepted. Geometry must fit the viewport, with width 16–320
and height 16–240. One pV tag per skin is supported, using a shared UI-owned pool.
Legacy pF tags retain their original parser and rendering behavior.

**Display → Visualization Effect:** Theme Default, Feedback Tunnel, Phosphor
Orbit, Flowing Ribbons, Auto Cycle. Theme Default uses the pV signature. Manual
selection persists across theme changes. Auto starts with the theme signature,
cycles every 30 seconds of fresh active playback, and blends over 750 ms. Saved key:
`visualization effect: theme|feedback|phosphor|ribbons|auto`.

The existing Spectrum Visualizer enable switch and optional display-only Auto
Gain also control animations. Spectrum Motion and Lane Guides remain pF-only.
Selecting a theme does not override effect, gain, audio or navigation settings.
`<Pack>-Visualizer` is the immersive layout; filenames remain stable.

## Engine and performance boundary

The existing observer still only copies PCM/signals its worker. The worker adds
128 DC-removed box-filtered stereo waveform samples, three frequency-region
peak levels and positive spectral flux to its published frame. Existing FFT band
outputs remain unchanged. Only UI code uses the animation pool.

All effects use integer lookup tables and a maximum 160×120 internal canvas,
scaled to the requested viewport. Feedback mirrors, rotates, bilinearly samples and fades previous traces;
phosphor uses stereo-modulated rotating loops and afterglow; ribbons layer
frequency-reactive flowing color fields. This is original CPU-rendered animation,
not a MilkDrop preset engine or a plugin launcher.

A fixed shared pool plus LCD row staging is compile-time bounded below 256 KiB.
There are no per-frame allocations. Target cadence is 25 fps; eight render/LCD
submissions above 30 ms reduce it to 12.5 fps. One hundred submissions below 15 ms
restore 25 fps. Time-based phase/envelopes avoid queued catch-up frames. Existing
buffer pressure suspension, hidden/backlight cancellation, capture-free pause
fade and bounded 800 ms stop exit apply. Display-only normalization never changes
PCM/EQ. Simulator timing is not evidence of physical frame rate or battery life.

## Review and rollout

Review all six actual simulator animations, metadata/art/off edge cases, Hold
and menus before publication or installation. Candidate source is committed
locally. After visual approval, use the existing file-only device trial with the
exact current firmware tree retained and existing host backup reused. Measure
available frame/submission/pressure diagnostics and use normal playback for a
brief user check. Only then prepare immutable experimental firmware/theme
releases; record device work separately in the iPod project.

## Local validation — 2026-10-08

- All 11 portable suites passed, including sanitized animation/service tests,
  legacy 17,280-frame pixel comparisons, 32 disposable installation tests and
  eight build-support tests. New coverage checks stale decay, linear pause
  settling, stereo waveform features, viewport isolation, effect selection,
  auto cycling, bounded memory, overload hysteresis and tick rollover.
- Fresh pinned baseline and custom builds passed. Final firmware, simulator and
  checkwps native fingerprints matched current source. The final package contains
  166 API 276 plugins, 43 API 50 codecs and preserves 884 original English strings.
- All 42 parser cases passed (including 12 new-animation cases); all seven theme
  packs built and 12 skins parsed. The three 2.0 ZIPs reproduced byte-for-byte.
- Actual simulator captures covered all six layouts in normal, long-metadata,
  missing-metadata/art and visualization-off states. Each normal animation had
  24 distinct sampled frames, unchanged metadata regions and a settled pause.
  Hold/menu screenshots and representative motion frames were visually inspected.
- Review fixes included signed timer overflow, Adwaita album-art overpainting,
  feedback staircases, stale-frame blanking and pause-tail settling. Final
  manual diff review found no remaining actionable issue. This was a single-agent
  review, not an independent human review or a physical-device acceptance test.

The self-contained HTML gallery includes six video clips and 36 supporting
screenshots. Browser automation was unavailable on the host; native simulator
images were inspected directly and gallery structure/assets were checked.
Local artifacts are retained under `reports/animated-visualizers/` in the main
checkout; compiled candidates are under `build/animated-visualizers/`. They are
ignored by Git. No remote publication or device action occurred during this work.
