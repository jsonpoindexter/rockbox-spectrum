# Build and test

## Firmware version

`VERSION` is the single source for our semantic firmware version, initially **1.0.0**. Custom firmware, simulator and checkwps builds use `4.0-spectrum-1.0.0-e094c599fa`: the Rockbox base, our release and pinned upstream source. Build manifests record the release and VERSION-file hash. A baseline build keeps its distinct `4.0-baseline-e094c599fa` label.

Package/installer checks use the shared `tools/firmware_version.py` parser. Version 1.x uses plugin API275, codec API50 and spectrum skin API2 (optional styling). A new major requires an explicit compatibility update. Minor/patch versions must preserve those interfaces. Theme packs declare minimum semantic firmware and required skin API independently of their theme version.

Legacy `4.0-spectrum-v1[-fastN]-e094c599fa` development names are recognized only for compatibility and recovery: fast4+ has the controls/API275, and fast10+ has styled skin API2. They are not mapped to a published semantic release. New builds always use VERSION. Original tests, motion preset names, provenance and device history retain their historical labels.

## Pinned inputs

Rockbox revision `e094c599fa60236527f9e272e0b8309d7696e399`, source SHA-256 `5539d4bd5b8de5f3ebf1f470b637c57b13ddeab995a1972981909087a37f1abd`, the Dockerfile ARM64 Ubuntu 18.04 digest, and GCC 4.9.4/binutils 2.26.1 are retained from the accepted build recipe. [toolchain-inputs.json](../toolchain-inputs.json) locks all six toolchain archives and the official 4.0 verification ZIP.

The bootstrap fetches every archive over HTTPS and verifies SHA-256 before invoking the pinned upstream toolchain recipe. A reused cache must match its input fingerprint, installation prefix and every recorded file/symlink. Mismatches fail rather than using an unknown compiler. To recover from a failed partial bootstrap, use a fresh toolchain volume and fresh container/work directories; do not delete an existing recovery archive.

The recipe is repeatable from identified inputs. Ubuntu packages, compiler-generated timestamps and ZIP metadata mean bit-identical output is not promised.

## Shared commands

On a host with Python 3.8+, `cc` supporting ASan/UBSan, and ImageMagick:

```sh
python3 tools/test.py --output reports/portable
```

Inside the pinned container:

```sh
python3 /project/tools/bootstrap-toolchain.py
python3 /project/tools/build.py --work /work/custom-1 --jobs 4
python3 /project/tools/build.py --work /work/simulator-1 --kind simulator --jobs 4
python3 /project/tools/build.py --work /work/checkwps-1 --kind checkwps --jobs 4
python3 /project/tools/build.py --work /work/baseline-1 --baseline --jobs 4
```

Or run all targets, spectrum/theme parser checks, and independent package verification:

```sh
python3 /project/tools/ci-build.py --work /work/run-1 --reports /work/reports/run-1 --jobs 4
```

`build.py` requires fresh source/build destinations. `ci-build.py` requires a nonexistent work directory. The same read-only project mount and command run in GitHub CI. Actions execute on Ubuntu 24.04 hosts; compiler/build commands execute inside the older pinned container.

## Local output

Using the named work volume from the README, copy outputs through a temporary stopped container:

```sh
docker create --name rockbox-spectrum-output \
  --mount type=volume,src=rockbox-spectrum-work,dst=/work \
  rockbox-spectrum-builder
docker cp rockbox-spectrum-output:/work/reports/run-1 ./reports-run-1
docker cp rockbox-spectrum-output:/work/run-1/spectrum-firmware/spectrum-firmware/rockbox.zip ./rockbox-local.zip
docker rm rockbox-spectrum-output
```

Keep the complete ZIP and its build manifest together locally. The generated manifest identifies upstream source, patch, overlay and firmware package hashes; theme files are excluded from firmware inputs. The wrapper additionally preserves compiler-input/output manifests and individual build logs. Device checks are explicitly marked `not performed`.

## CI checks

Portable checks cover numeric FFT reference accuracy, immutable PCM/capture ownership, default/profile motion, auto gain, per-pixel renderer equivalence, cadence/input priority, pause/stop tails, WPS exit, saved-capture verifier negative cases, and disposable installation/rollback transactions. Build-support tests reject corrupted downloads, mismatched caches and unsafe source archive paths.

The ARM64 job performs a baseline firmware build plus custom firmware, simulator and checkwps builds. Parser cases test valid/invalid spectrum tags; all three theme WPS files are also parsed and all four independent packs are built and verified. Package verification checks target/CRC, plugin/codec APIs, absence of custom theme/preset files and preservation of existing English language IDs against the fingerprinted official ZIP. These checks do not establish full-theme appearance or hardware boot/recovery reliability.

The CI workflow uploads only reports/logs/manifests for seven days. [Release publication](releases.md) is a separate explicit process using verified packages. No firmware ZIP, compiler tree, source archive or device data is uploaded as a workflow artifact. Toolchain cache keys use exact architecture/build-input hashes without broad fallback keys.

Theme syntax checks use generated temporary solid-color BMPs, preserving sprite frame counts and rebasing only asset paths in a temporary WPS copy. No original bitmap/font packs are fetched or included. The original WPS fingerprint is recorded; artwork/font metrics and full appearance are not verified by this check.

Saved-capture manifests default to a black background. An explicit `background_rgb` may describe a separately observed fixture/control background; text visibility and blankness checks exclude that exact color. The complete guide mask still checks dot positions, foreground and every background pixel. Do not derive the expected background from the failing spectrum region.
