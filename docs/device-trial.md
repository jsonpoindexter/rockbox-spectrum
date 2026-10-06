# File-only trial and recovery

This project does not distribute firmware releases in this phase. Build and verify a complete local package first. Install matching custom firmware, plugins and codecs together; plugin API 275 cannot be mixed with stock 4.0 plugins. The firmware helper requires an existing ipod6g Rockbox installation. It has no theme or CrazyBitMono asset requirement. Existing theme files stay in the staged current tree; custom themes are installed separately using the [theme pack tool](themes.md).

The helper does not install bootloaders, write partitions or change music outside `.rockbox`. All operations are dry-run unless `--apply` is supplied:

```sh
python3 tools/device-trial.py --help
python3 tools/device-trial.py install --help
python3 tools/device-trial.py rollback --help
```

## First local trial

Choose your mounted iPod path, complete ZIP, verified package SHA-256 and a fresh host backup directory. Use an explicit path appropriate to your host; no device mount is inferred.

```sh
python3 tools/device-trial.py install \
  --volume /path/to/ipod --package /path/to/rockbox-local.zip \
  --sha256 PACKAGE_SHA256 --backup /path/to/new-backup
```

Review the dry-run, then repeat with `--apply` to perform the transaction. This original backup route starts spectrum Off; select a spectrum preset and enable it afterward. The helper stages and verifies content, switches directories, retains the old tree on-device and records evidence. Preserve the host snapshot/session and recorded retained directory.

## Settings-preserving subsequent trial

With an existing verified backup, use a new session directory:

```sh
python3 tools/device-trial.py install \
  --volume /path/to/ipod --package /path/to/rockbox-local.zip \
  --sha256 PACKAGE_SHA256 --reuse-backup /path/to/existing-backup \
  --preserve-config --session /path/to/new-session
```

The snapshot is reverified; current settings are preserved byte-for-byte and the exact current directory is retained. Adding `--apply` activates the staged candidate. Neither a successful fixture test nor readback proves physical boot/audio recovery.

## Restore the exact previous state

Use the retained directory and session actually recorded by that installation:

```sh
python3 tools/device-trial.py rollback \
  --volume /path/to/ipod --retained-tree /path/to/ipod/.rockbox-before-spectrum-RECORDED_ID \
  --session /path/to/recorded-session
```

Dry-run verifies the before-state; repeat with `--apply` to restore it. The retired candidate is retained, not deleted. Do not guess retained-directory names. The older `--backup` rollback route intentionally restores the specified host snapshot instead.

Safely eject after verification before disconnecting. Existing Apple/Rockbox boot selection comes from your already installed bootloader; this project neither changes nor establishes that behavior. To disable the visualizer, turn Spectrum Visualizer Off and/or select the original theme. Record actual attempts and results in your own device journal; this development repository contains no personal device record.
