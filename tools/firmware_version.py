"""Public firmware versions and legacy compatibility. GPL-2.0-or-later."""
import re
from collections import namedtuple
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_REVISION = 'e094c599fa60236527f9e272e0b8309d7696e399'
Firmware = namedtuple('Firmware', 'release legacy_fast plugin_api skin_api')


def semver(text):
    if not isinstance(text, str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', text):
        raise ValueError('Expected major.minor.patch version')
    return tuple(int(part) for part in text.split('.'))


def current_version():
    release = (ROOT / 'VERSION').read_text().strip()
    if semver(release)[0] != 1:
        raise ValueError('New firmware major requires explicit ABI compatibility rules')
    return '4.0-spectrum-' + release + '-' + UPSTREAM_REVISION[:10]


def firmware(info):
    """Require one ipod6g target/version; do not mistake stock for custom firmware."""
    info = info.replace('\r\n', '\n')
    targets = re.findall(r'^Target: ([^\r\n]+)$', info, re.M)
    versions = re.findall(r'^Version: ([^\r\n]+)$', info, re.M)
    if targets != ['ipod6g'] or len(versions) != 1:
        raise ValueError('Expected one ipod6g firmware target/version')
    version = versions[0]
    public = re.fullmatch(r'4\.0-spectrum-([0-9]+\.[0-9]+\.[0-9]+)-[0-9a-f]{10}', version)
    if public:
        release = semver(public.group(1))
        if release[0] != 1:
            raise ValueError('Unsupported spectrum major version')
        return Firmware(release, None, 275, 2)
    legacy = re.fullmatch(r'4\.0-spectrum-v1-(?:fast([1-9][0-9]*)-)?[0-9a-f]{10}', version)
    if legacy:
        fast = int(legacy.group(1) or 0)
        return Firmware(None, fast, 275 if fast >= 4 else 274, 2 if fast >= 10 else 1)
    raise ValueError('Unrecognized spectrum firmware version')


def theme_compatible(info, meta):
    installed = firmware(info)
    # Existing independently built schema1 ZIPs remain readable/installable.
    if meta['schema'] == 1:
        minimum = meta['minimum_firmware_fast']
        return installed.legacy_fast >= minimum if installed.release is None else True
    if installed.release is not None:
        return installed.release >= semver(meta['minimum_firmware_version']) and installed.skin_api >= meta['required_skin_api']
    # Legacy controls arrived at fast4; styled WPS at fast10. Do not pretend a
    # development label is an officially released semantic version.
    return meta['minimum_firmware_version'] == '1.0.0' and installed.plugin_api == 275 and installed.skin_api >= meta['required_skin_api']
