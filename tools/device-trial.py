#!/usr/bin/env python3
"""Preview, install, or roll back a file-only spectrum trial; dry-run by default.

No bootloader, partitions, or music outside .rockbox are written. An explicit
--apply is required for writes. Keep USB connected until verification/ejection.
"""
import argparse, hashlib, json, os, re, shutil, struct, uuid
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
from firmware_version import firmware
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def manifest(root):
    result={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():raise ValueError('Symlink refused: '+str(p))
        if p.is_file():result[p.relative_to(root).as_posix()]=sha(p)
        elif not p.is_dir():raise ValueError('Special file refused: '+str(p))
    return result
def verify(root,expected):
    actual=manifest(root)
    if actual!=expected:raise ValueError('File manifest verification failed: '+str(root))
def verify_staged_current(root,expected):
    """All original bytes must match; allow bounded FAT metadata sidecars only."""
    actual=manifest(root)
    if any(actual.get(name)!=digest for name,digest in expected.items()):
        raise ValueError('Staging changed/missed an original file')
    extras=sorted(set(actual)-set(expected))
    for name in extras:
        p=root/name
        owner=p.with_name(p.name[2:]) if p.name.startswith('._') else None
        if not owner or owner.relative_to(root).as_posix() not in expected or not owner.is_file():
            raise ValueError('Unexpected staging file: '+name)
        data=p.read_bytes()
        if len(data)<26 or len(data)>65536:raise ValueError('Invalid AppleDouble size')
        magic,version,_,count=struct.unpack('>II16sH',data[:26])
        if magic!=0x51607 or version!=0x20000 or not 1<=count<=2 or len(data)<26+12*count:
            raise ValueError('Invalid AppleDouble header')
        entries=[struct.unpack('>III',data[26+12*i:38+12*i]) for i in range(count)]
        ids=set();ranges=[]
        for ident,offset,length in entries:
            if ident not in (2,9) or ident in ids or offset<26+12*count or offset+length>len(data):
                raise ValueError('Invalid AppleDouble entry')
            if ident==9 and length<32:raise ValueError('Invalid FinderInfo entry')
            if any(offset<end and offset+length>start for start,end in ranges):
                raise ValueError('Overlapping AppleDouble entries')
            ids.add(ident);ranges.append((offset,offset+length))
        if 9 not in ids:raise ValueError('Missing FinderInfo entry')
    return extras

def copy_content_tree(source,target):
    """Stage bytes only; macOS copy2/xattrs can rewrite FAT AppleDouble files."""
    target.mkdir()
    for item in sorted(source.rglob('*')):
        destination=target/item.relative_to(source)
        if item.is_symlink():raise ValueError('Symlink refused while staging')
        if item.is_dir():destination.mkdir()
        elif item.is_file():
            # Even macOS fcopyfile(COPYFILE_DATA) can create AppleDouble entries.
            # Plain buffered IO avoids both the native fast-copy and metadata APIs.
            with item.open('rb') as incoming, destination.open('xb') as outgoing:
                shutil.copyfileobj(incoming,outgoing,1024*1024)
        else:raise ValueError('Special file refused while staging')

def validate_volume(volume):
    rockbox=volume/'.rockbox'
    if volume.is_symlink() or rockbox.is_symlink():raise ValueError('Volume/.rockbox must not be a symlink')
    info=(rockbox/'rockbox-info.txt').read_text(encoding='utf8')
    if not re.search(r'^Target: ipod6g\s*$',info,re.M):raise ValueError('Expected existing ipod6g firmware')
    if not (rockbox/'rockbox.ipod').is_file():raise ValueError('Missing current firmware file')
    return rockbox

def validate_package(path,expected):
    if sha(path)!=expected:raise ValueError('Package SHA-256 mismatch')
    with ZipFile(path) as archive:
        bad=archive.testzip()
        if bad:raise ValueError('ZIP CRC failure: '+bad)
        seen=set()
        for item in archive.infolist():
            parts=PurePosixPath(item.filename).parts
            if not parts or parts[0]!='.rockbox' or '..' in parts or '\\' in item.filename or item.filename.startswith('/') or item.filename in seen:raise ValueError('Unsafe/duplicate package member')
            if (item.external_attr>>16)&0o170000==0o120000:raise ValueError('ZIP symlink refused')
            seen.add(item.filename)
        info=archive.read('.rockbox/rockbox-info.txt').decode()
        firmware(info)
        required={'.rockbox/rockbox.ipod','.rockbox/codecs/mpa.codec','.rockbox/rocks/demos/fft.rock'}
        if not required.issubset(seen):raise ValueError('Package lacks matching firmware/codecs/plugins')
        return seen

def switch(volume,stage,old):
    active=volume/'.rockbox'
    active.rename(old)
    try:stage.rename(active)
    except BaseException:
        old.rename(active)
        raise
    # Old tree remains on the device as a second recovery copy. No delete.
    os.sync() if hasattr(os,'sync') else None

def run(args):
    volume=args.volume.absolute()
    active=validate_volume(volume)
    before=manifest(active)
    reuse=getattr(args, 'reuse_backup', None)
    retained=getattr(args, 'retained_tree', None)
    session=getattr(args, 'session', None)
    preserve=getattr(args, 'preserve_config', False)
    backup=(reuse or args.backup).absolute() if (reuse or args.backup) else None
    if session:
        session=session.absolute()
        if session.resolve()==volume.resolve() or volume.resolve() in session.resolve().parents:
            raise ValueError('Session must be outside the iPod volume')
    if reuse:
        if args.action!='install' or not preserve or not session or args.backup:
            raise ValueError('--reuse-backup requires install, --preserve-config, --session and no --backup')
        expected_backup=json.loads((backup/'manifest.json').read_text())
        verify(backup/'.rockbox',expected_backup)
    if retained:
        if args.action!='rollback' or not session or backup:
            raise ValueError('--retained-tree requires rollback with --session and no --backup')
        retained=retained.absolute()
        report=json.loads((session/'trial.json').read_text())
        if str(retained)!=report['retained_device_backup'] or retained.parent!=volume or retained.is_symlink() or not retained.name.startswith('.rockbox-before-spectrum-'):
            raise ValueError('Retained tree must be the recorded directory on this volume')
        expected=json.loads((session/'before.json').read_text())
        verify(retained,expected)
        print(json.dumps({'action':'rollback','apply':args.apply,'retained_tree':str(retained),'restored_files':len(expected)},indent=2))
        if not args.apply:return
        verify(active,before); verify(retained,expected)
        old=volume/('.rockbox-retired-spectrum-'+uuid.uuid4().hex[:12])
        switch(volume,retained,old)
        try:verify(active,expected)
        except BaseException:
            active.rename(retained);old.rename(active);raise
        (session/'rollback.json').write_text(json.dumps({'file_verification':'passed','retained_trial':str(old),'device_boot_tests':'not performed'},indent=2)+'\n')
        return
    if not backup:raise ValueError('Specify --backup or --reuse-backup (install), or --retained-tree (rollback)')
    if volume.resolve()==backup.resolve() or volume.resolve() in backup.resolve().parents:raise ValueError('Backup must be outside the iPod volume')
    if args.action=='install':
        if not args.package or not args.sha256:raise ValueError('Install requires --package and --sha256')
        members=validate_package(args.package,args.sha256)
        print(json.dumps({'action':'install','apply':args.apply,'volume':str(volume),'backup':str(backup),'current_files':len(before),'package_members':len(members),'bootloader_changes':False},indent=2))
        if not args.apply:return
        required=sum(p.stat().st_size for p in active.rglob("*") if p.is_file()) + args.package.stat().st_size * 4 + 8*1024*1024
        if shutil.disk_usage(volume).free < required:raise ValueError("Insufficient staging space")
        if not reuse and backup.exists():raise ValueError('Backup destination already exists; choose a fresh path')
        if session and session.exists():raise ValueError('Session destination already exists')
        if not reuse:
            backup.mkdir(parents=True)
            shutil.copytree(active,backup/'.rockbox');verify(backup/'.rockbox',before)
            (backup/'manifest.json').write_text(json.dumps(before,indent=2)+'\n')
        if session:
            session.mkdir(parents=True)
            (session/'before.json').write_text(json.dumps(before,indent=2)+'\n')
        token=uuid.uuid4().hex[:12];container=volume/('.spectrum-stage-'+token);container.mkdir()
        stage=container/'.rockbox';copy_content_tree(active if reuse else backup/'.rockbox',stage)
        metadata_extras=verify_staged_current(stage,before)
        # Keep plugin data, but replace all compiled plugins/codecs as a unit.
        for folder in ('rocks','codecs'):
            for p in (stage/folder).rglob('*'):
                if p.is_file() and p.suffix in ('.rock','.ovl','.codec'):p.unlink()
        validate_package(args.package,args.sha256)
        with ZipFile(args.package) as archive:archive.extractall(container)
        cfg=stage/'config.cfg'
        if preserve:
            if ('config.cfg' in before) != cfg.is_file() or (cfg.is_file() and sha(cfg)!=before['config.cfg']):
                raise ValueError('Package changed saved config; refusing activation')
        else:
            text=cfg.read_text(encoding='utf8') if cfg.exists() else ''
            text=re.sub(r'^spectrum enabled:.*\n?', '',text,flags=re.M)
            cfg.write_text(text.rstrip()+'\nspectrum enabled: off\n',encoding='utf8')
        expected=manifest(stage);old=volume/('.rockbox-before-spectrum-'+token)
        verify(active,before) # Detect any device/settings change during staging.
        verify(stage,expected)
        if session:
            (session/'after.json').write_text(json.dumps(expected,indent=2)+'\n')
            (session/'trial.json').write_text(json.dumps({'retained_device_backup':str(old),'activation':'pending'},indent=2)+'\n')
        try:
            switch(volume,stage,old)
            verify(active,expected)
            verify(old,before)
        except BaseException:
            # Restore before-state without deleting the failed trial tree.
            if old.exists():
                failed=volume/('.rockbox-failed-spectrum-'+token)
                if active.exists():active.rename(failed)
                old.rename(active)
            raise
        container.rmdir()
        report={'action':'install','before_files':len(before),'after_files':len(expected),'package_sha256':args.sha256,'retained_device_backup':str(old),'file_verification':'passed','device_boot_tests':'not performed','validated_staging_metadata':metadata_extras}
        ((session or backup)/'trial.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    else:
        expected=json.loads((backup/'manifest.json').read_text());verify(backup/'.rockbox',expected)
        print(json.dumps({'action':'rollback','apply':args.apply,'backup':str(backup),'restored_files':len(expected)},indent=2))
        if not args.apply:return
        token=uuid.uuid4().hex[:12];stage=volume/('.spectrum-restore-'+token)
        shutil.copytree(backup/'.rockbox',stage);verify(stage,expected)
        old=volume/('.rockbox-retired-spectrum-'+token);switch(volume,stage,old)
        try:verify(active,expected)
        except BaseException:
            failed=volume/(".rockbox-failed-restore-"+token);active.rename(failed);old.rename(active);raise
        (backup/('rollback-'+token+'.json')).write_text(json.dumps({'action':'rollback','file_verification':'passed','retained_trial':str(old),'device_boot_tests':'not performed'},indent=2)+'\n')
        print('Rollback files verified; reboot checks still required.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['install','rollback']);p.add_argument('--volume',type=Path,required=True);p.add_argument('--backup',type=Path);p.add_argument('--reuse-backup',type=Path);p.add_argument('--preserve-config',action='store_true');p.add_argument('--session',type=Path);p.add_argument('--retained-tree',type=Path);p.add_argument('--package',type=Path);p.add_argument('--sha256');p.add_argument('--apply',action='store_true');args=p.parse_args()
    try:run(args)
    except (OSError,ValueError,KeyError) as e:raise SystemExit(str(e))
if __name__=='__main__':main()
