# Architecture and controls

The mixer observer copies playback PCM before voice/beeps and mixer amplitude into owned rolling stereo history. Two replaceable snapshots keep slow analysis from blocking audio; a reader's snapshot is protected. A sleeping worker applies DC removal, a periodic Hann window and a fixed-point 1024-frame FFT. Separate-channel power preserves opposite-phase content.

Analysis uses 32 logarithmic bands between 60 Hz and the lower of 20 kHz and Nyquist. At 44.1 kHz, FFT bin spacing is about 43 Hz; low bands can share bins. This is a visualizer, not a calibrated audio measurement instrument.

The backward-compatible WPS tag is `%pF(x,y,width,height,bands,mode,palette)`. Required integer coordinates and dimensions must fit the viewport. Bands are 8, 16 or 32; modes are `bars` or `lines`; palettes are `mono` or `classic`. Example:

```text
%pF(0,0,280,70,16,bars,classic)
```

An optional seven-field presentation block is available in firmware 1.0.0; see [theme styling](themes.md). Style is stored per widget, parsed once and invalidates the drawing cache when configured. Precomputed mono strips retain one bitmap call per dotted separator. RGB color strings are packed to the display format only in the renderer. The analyzer, PCM observer, motion/gain controls and spectrum band mapping do not depend on theme files. Firmware builds hash the patch and native overlay only; each text pack has its own version, payload hashes and asset dependencies.

Animation targets at most 50 Hz on the ipod6g 100 Hz scheduler, prioritizes queued hardware input and skips unchanged bar frames. Dirty rectangles are combined into one LCD update. Stale capture decays to silence; seeks/rate changes reset capture. Audio-buffer pressure disables analysis until recovery. No audio/EQ or CPU-boost policy changes are introduced.

## Saved controls

Under **Settings → General Settings → Display**:

- **Spectrum Visualizer:** firmware default Off; spectrum theme presets enable it.
- **Spectrum Motion:** Fast3 default; Smooth, Punchy and Classic are alternatives.
- **Spectrum Auto Gain:** default Off; On changes visual sensitivity only.
- **Spectrum Lane Guides:** default On; one-pixel separators between adjacent lanes with dots four pixels apart (no outer vertical frame), plus one-pixel horizontal marker rows using the first row/column of the unfilled-bar 4×4 dot tile at 75% of the theme foreground channels. Bottom borders remain visible as idle markers. The 280×70 viewport and band mapping stay unchanged; bars retain a one-pixel horizontal inset per side and three vertical pixels per end. Guides fall back to plain bars when height is below eight pixels or lane pitch is below eight pixels.

Single-purpose `.cfg` files in `theme-packs/SpectrumPresets/.rockbox/` provide reversible motion/gain/guide toggles without changing audio settings. Pause and stop disable PCM capture while the UI falls away at 96 dB/s, settling within 750 ms from maximum; stop exit is bounded at 800 ms. Auto gain freezes during the tail. Resume accepts only new-generation capture. Hidden WPS, disabled backlight/LCD and audio-buffer pressure cancel the tail.

Timing counters are available at **Settings → System → Debug (Keep Out!) → Spectrum timing**. Center exports `/.rockbox/spectrum-timing.txt` on demand. Capture-to-submission age is not measured audible/display latency.

`benchmarks.csv` is an inherited unfilled measurement template with historical proposal labels; it does not report current frame rates, latency, runtime or hardware results.
