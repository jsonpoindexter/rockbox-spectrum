# Releases and independent versions

Packages are available on [GitHub Releases](https://github.com/jsonpoindexter/rockbox-spectrum/releases). All initial packages are experimental pre-releases. The exact 1.0.0 firmware and new styled theme packs have passed host and CI validation; physical installation/boot/audio/appearance of these exact packages is not established. Earlier development builds have separate device observations.

| Component | Version | Fixed release tag |
| --- | --- | --- |
| Firmware, matching plugins/codecs | 1.0.0 | [v1.0.0](https://github.com/jsonpoindexter/rockbox-spectrum/releases/tag/v1.0.0) |
| ClassicSpectrum | 1.3 | [theme-classicspectrum-v1.3](https://github.com/jsonpoindexter/rockbox-spectrum/releases/tag/theme-classicspectrum-v1.3) |
| CrazyBitSpectrum | 2.0 | [theme-crazybitspectrum-v2.0](https://github.com/jsonpoindexter/rockbox-spectrum/releases/tag/theme-crazybitspectrum-v2.0) |
| CrazyBitSpectrumColor | 2.0 | [theme-crazybitspectrumcolor-v2.0](https://github.com/jsonpoindexter/rockbox-spectrum/releases/tag/theme-crazybitspectrumcolor-v2.0) |
| SpectrumPresets | 1.0 | [presets-spectrum-v1.0](https://github.com/jsonpoindexter/rockbox-spectrum/releases/tag/presets-spectrum-v1.0) |
| WinampSpectrum (Detail + Visualizer) | 1.0 | [theme-winampspectrum-v1.0](https://github.com/jsonpoindexter/rockbox-spectrum/releases/tag/theme-winampspectrum-v1.0) |
| StudioSpectrum (Detail + Visualizer) | 1.0 | [theme-studiospectrum-v1.0](https://github.com/jsonpoindexter/rockbox-spectrum/releases/tag/theme-studiospectrum-v1.0) |
| AdwaitaSpectrum (Detail + Visualizer) | 1.0 | [theme-adwaitaspectrum-v1.0](https://github.com/jsonpoindexter/rockbox-spectrum/releases/tag/theme-adwaitaspectrum-v1.0) |

The original five tags point to source commit `2858ce13d01a95092376e43e37c103d0296b8ba2`, whose [portable and ARM64 CI jobs passed](https://github.com/jsonpoindexter/rockbox-spectrum/actions/runs/37539005995). The firmware build identifier is `4.0-spectrum-1.0.0-e094c599fa`. Documentation added after that commit does not change the compiled release.

## Download and install

Download the component ZIP, `SHA256SUMS` and its installation guide from the same release. In a directory containing all listed assets, verify:

```sh
shasum -a 256 -c SHA256SUMS
```

The firmware release includes the build manifest, validation summary, notices, GPL terms and corresponding source bundle (pinned upstream source plus the exact patch/build project). GitHub's automatic source archives contain the patch/build project only. Theme ZIPs contain their own manifest, source text and notices. Theme releases include their manifest and validation summary separately for inspection.

Firmware requires an existing ipod6g Rockbox installation/bootloader. Install the complete matching firmware/plugin/codec ZIP using the [file-only installation and recovery guide](device-trial.md). Installation defaults to a dry run; preserve the recorded previous tree and recovery session. This is not a bootloader installer or an Apple firmware restore package.

Styled theme packs require custom firmware 1.0.0 or newer with the declared skin API. ClassicSpectrum and the two CrazyBitSpectrum packs additionally require separately installed original CrazyBitMono assets/fonts; SpectrumPresets has no artwork dependency. WinampSpectrum, StudioSpectrum and AdwaitaSpectrum are complete packs with two layouts each, including their own assets. Use the [theme guide](themes.md), then select the theme/preset on the device. Copying pack files does not select them. Firmware updates do not install custom theme packs.

## Publish a future release

1. Bump `VERSION` for native firmware changes, or the affected pack's `pack.json` version for theme/preset changes. Keep component versions independent. Commit the candidate and record its full source SHA.
2. Run affected checks from [the build guide](build.md). Firmware needs portable, complete build/parser/package gates and matching source fingerprints. Theme text needs pack verification and WPS parser checks. Record actual hardware observations separately; host checks alone retain experimental status.
3. Prepare a fresh local staging directory outside tracked source. For firmware, copy the complete ZIP and matching build manifest, check the package SHA and manifest VERSION/patch/overlay hashes against the candidate commit, and verify it with `tools/verify-package.py` against the pinned official ZIP. Include corresponding source: the fingerprinted upstream archive, exact project snapshot and build instructions. For a pack, run `tools/theme-pack.py verify` and compare every payload plus notices/licenses to that commit's source.
4. Add component-specific installation/recovery instructions, a validation summary identifying the exact source SHA and successful CI run, and license/attribution notices. Exclude device records, personal paths/settings, music, backups and unrelated reports. Generate checksums of all download assets except `SHA256SUMS` itself. Notes stay outside the asset set.
5. Confirm the new tag/release does not exist. Create a draft targeting the **full verified source SHA**, attach all staged assets, and inspect metadata. For example, using concrete values for `TAG`, `SOURCE_SHA` and `ASSET_DIR`:

```sh
gh release create TAG --repo jsonpoindexter/rockbox-spectrum \
  --target SOURCE_SHA --draft --prerelease --latest=false \
  --title 'COMPONENT VERSION (experimental)' --notes-file /path/to/release-notes.md \
  /path/to/ASSET_DIR/*
```

6. Download the draft assets into a fresh directory with `gh release download TAG --dir /path/to/fresh-readback`; compare every checksum, asset count, manifest and target. Publish only after those checks pass:

```sh
gh release edit TAG --repo jsonpoindexter/rockbox-spectrum \
  --draft=false --prerelease --latest=false
```

7. Verify public downloads and the remote tag's resolved commit again. Record URLs, asset hashes, source SHA and hardware status. Promotion to stable requires evidence for that exact version; theme releases should not become the repository's misleading latest firmware release.

Published tags and assets remain fixed by project policy. Do not squash or force-push history containing released tags. Corrections and new behavior get a new component version and release. Keep earlier releases available for recovery. Routine CI retains reports only and never publishes packages or accesses an iPod volume.
