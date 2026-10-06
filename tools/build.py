#!/usr/bin/env python3
"""Fetch pinned source, apply the patch, and build matching ipod6g components."""
import argparse, hashlib, json, os, subprocess, tarfile, urllib.request
from pathlib import Path
from firmware_version import current_version, UPSTREAM_REVISION
ROOT=Path(__file__).resolve().parents[1]
REVISION=UPSTREAM_REVISION
ARCHIVE_SHA='5539d4bd5b8de5f3ebf1f470b637c57b13ddeab995a1972981909087a37f1abd'
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--baseline',action='store_true');p.add_argument('--kind',choices=['firmware','simulator','checkwps'],default='firmware');p.add_argument('--jobs',type=int,default=8);a=p.parse_args()
    work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
    archive=work/'rockbox-4.0-source.tar.gz'
    if not archive.exists():
        with urllib.request.urlopen('https://codeload.github.com/Rockbox/rockbox/tar.gz/'+REVISION) as response, archive.open('xb') as out:
            import shutil
            shutil.copyfileobj(response,out)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=ARCHIVE_SHA:raise SystemExit('Source archive fingerprint mismatch')
    variant='baseline' if a.baseline else 'spectrum'
    source=work/(variant+'-source');build=work/(variant+'-'+a.kind)
    if source.exists() or build.exists():raise SystemExit('Use a fresh work directory; source/build destinations already exist')
    source.mkdir()
    with tarfile.open(str(archive)) as tar:
        prefix='rockbox-'+REVISION+'/'
        for member in tar.getmembers():
            if member.name == prefix[:-1]:continue
            if not member.name.startswith(prefix):raise SystemExit('Unexpected archive prefix')
            member.name=member.name[len(prefix):]
            if member.islnk() or member.isdev():raise SystemExit('Unexpected source hard link/special file')
            if member.issym():
                target=(source/member.name).parent/member.linkname
                if Path(member.linkname).is_absolute() or source not in target.resolve().parents:raise SystemExit('Unsafe source symlink')
            if not member.name or Path(member.name).is_absolute() or '..' in Path(member.name).parts:raise SystemExit('Unsafe archive path')
            tar.extract(member,str(source))
    if not a.baseline:subprocess.run(['python3',str(ROOT/'tools/apply-patch.py'),str(source)],check=True)
    version='4.0-baseline-e094c599fa' if a.baseline else current_version()
    (source/'docs/VERSION').write_text(version+'\n');build.mkdir()
    env=dict(os.environ);env['VERSION']=version
    commands=[[str(source/'tools/configure'),'--target=ipod6g','--type='+{'firmware':'n','simulator':'s','checkwps':'c'}[a.kind]],['make','-j'+str(a.jobs)]]
    if a.kind=='firmware':commands.append(['make','zip'])
    if a.kind=='simulator':commands.append(['make','install'])
    for i,cmd in enumerate(commands):
        print(' '.join(cmd),flush=True)
        with (build/('step-'+str(i)+'.log')).open('w') as log:subprocess.run(cmd,cwd=str(build),env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    manifest={'upstream_revision':REVISION,'source_archive_sha256':ARCHIVE_SHA,'variant':variant,'kind':a.kind,'version':version,'patch_sha256':None if a.baseline else hashlib.sha256((ROOT/'patches/0001-native-spectrum.patch').read_bytes()).hexdigest(),'firmware_release':None if a.baseline else (ROOT/'VERSION').read_text().strip(),'version_file_sha256':None if a.baseline else hashlib.sha256((ROOT/'VERSION').read_bytes()).hexdigest(),'package_role':'firmware','theme_packs_included':False,'device_tests':'not performed'}
    if not a.baseline:
        for label in ('overlay',):
            manifest[label+'_sha256']={item.relative_to(ROOT/label).as_posix():hashlib.sha256(item.read_bytes()).hexdigest() for item in sorted((ROOT/label).rglob('*')) if item.is_file()}
    package=build/'rockbox.zip'
    if package.exists():
        manifest['rockbox_zip_sha256']=hashlib.sha256(package.read_bytes()).hexdigest()
    (build/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
