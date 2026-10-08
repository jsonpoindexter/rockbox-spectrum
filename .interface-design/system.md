# iPod music player design system

Audience: one person listening on a 320×240 clickwheel player. Read the track
quickly, operate by familiar physical controls, or watch music-reactive motion.
Design approval checkpoint: actual animated simulator captures before release or installation.

Domain: transport decks, album sleeves, phosphor instruments, equalizers,
feedback trails, clickwheel navigation and restrained status lights.
Color world: charcoal casing, LED green, electric blue, magenta trails,
amber phosphor, pale album paper and muted violet.

Signatures and composition:
- Winamp: beveled compact deck, inset animation beside elapsed time, title ticker,
  LED green status and electric blue/magenta feedback. Pixel typography.
- Studio: amber instrument panel with a left information rail and right phosphor
  orbit, bottom track identification. Pixel typography and understated dividers.
- Adwaita: centered album sleeve, large title/artist, pale surfaces, blue/violet
  ribbons and generous whitespace. Cantarell typography.

Replace the shared metadata/spectrum/footer grid with these three compositions.
Use actual font heights, not font filename sizes (Lana07 17px, Lana14 28px;
Cantarell18 23px, Cantarell20Bold 21px). Use 4px spacing where it fits font metrics.
Keep text/art regions disjoint from animated viewports. Details never scroll
into animation. Immersive mode uses minimal track/time information, with a
bottom transport deck, side instrument rail or airy caption region respectively.

Hold screens and menus retain the same typography, color hierarchy and spatial
identity. Theme cfgs own appearance only. No audio, effect, gain, navigation or
backlight overrides. Frozen/disabled animation preserves track information.
