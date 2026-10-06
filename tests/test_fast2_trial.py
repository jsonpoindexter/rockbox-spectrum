"""Disposable fast2 transactions, including exact-current recovery and failures."""
import hashlib, importlib.util, json, shutil, struct, tempfile, unittest, zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from types import SimpleNamespace
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('trial',Path(__file__).resolve().parents[1]/'tools/device-trial.py')
trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)
class Fast2Trial(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.volume=self.root/'volume';active=self.volume/'.rockbox';active.mkdir(parents=True)
  files={'rockbox-info.txt':'Target: ipod6g\nVersion: 4.0-spectrum-v1-e094c599fa\n','rockbox.ipod':'v1','config.cfg':'volume: -37\nspectrum enabled: on\n','rocks/extra.rock':'obsolete','rocks/extra.cfg':'saved','codecs/extra.codec':'obsolete','wps/CrazyBitMono.sbs':'asset','wps/ClassicSpectrum.wps':'1.0'}
  for name in ('battery','playmodes','progressbar_backdrop','pl','plbg','pr','prbg','vol','volbg','progressbar','usb'):files['wps/CrazyBitMono/'+name+'.bmp']='asset'
  for name in ('modone','modone_viewer'):files['icons/'+name+'.bmp']='asset'
  for name in ('47-SquareDotCombined','14-LanaPixel','10-Sazanami-Mincho','07-LanaPixel','21-LanaPixel','20-digital7mono'):files['fonts/'+name+'.fnt']='asset'
  for name,data in files.items():
   p=active/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
  self.backup=self.root/'existing';self.backup.mkdir();shutil.copytree(active,self.backup/'.rockbox')
  (self.backup/'manifest.json').write_text(json.dumps(trial.manifest(active)))
  # Existing snapshot is intentionally older: staging/rollback must use current.
  (active/'config.cfg').write_bytes(b'volume: -41\nspectrum enabled: on\neq enabled: on\nwps: /.rockbox/wps/ClassicSpectrum.wps\n')
  (active/'wps/ClassicSpectrum.wps').write_text('1.2')
  self.before=trial.manifest(active);self.active=active
  (self.volume/'music.mp3').write_bytes(b'sentinel')
  self.package=self.root/'fast2.zip'
  with zipfile.ZipFile(self.package,'w') as z:
   for name,data in {'rockbox-info.txt':'Target: ipod6g\nVersion: 4.0-spectrum-v1-fast2-e094c599fa\n','rockbox.ipod':'fast2','codecs/mpa.codec':'matching','rocks/demos/fft.rock':'matching'}.items():z.writestr('.rockbox/'+name,data)
  self.args=SimpleNamespace(action='install',volume=self.volume,backup=None,reuse_backup=self.backup,preserve_config=True,session=self.root/'session',retained_tree=None,package=self.package,sha256=trial.sha(self.package),apply=True)
 def apply(self):trial.run(self.args)
 def test_exact_current_and_rollback(self):
  snapshot=trial.manifest(self.backup)
  self.args.apply=False;self.apply();self.assertFalse(self.args.session.exists());self.assertEqual(trial.manifest(self.active),self.before)
  self.args.apply=True;self.apply();trial.verify(self.backup,snapshot)
  self.assertEqual(trial.sha(self.active/'config.cfg'),self.before['config.cfg']);self.assertEqual((self.active/'wps/ClassicSpectrum.wps').read_text(),'1.2')
  self.assertFalse((self.active/'rocks/extra.rock').exists());self.assertEqual((self.active/'rocks/extra.cfg').read_text(),'saved')
  report=json.loads((self.args.session/'trial.json').read_text());retained=Path(report['retained_device_backup']);trial.verify(retained,self.before)
  self.args.action='rollback';self.args.reuse_backup=None;self.args.retained_tree=retained
  self.args.apply=False;self.apply();self.assertEqual((self.active/'rockbox.ipod').read_text(),'fast2')
  self.args.apply=True;self.apply();trial.verify(self.active,self.before)
  self.assertEqual((self.volume/'music.mp3').read_bytes(),b'sentinel')
 def test_no_metadata_copy_in_reuse_stage(self):
  with patch.object(trial.shutil,'copyfile',side_effect=AssertionError('native copy refused')), patch.object(trial.shutil,'copy2',side_effect=AssertionError('metadata copy refused')), patch.object(trial.shutil,'copystat',side_effect=AssertionError('metadata copy refused')):
   self.apply()
  self.assertEqual(trial.sha(self.active/'config.cfg'),self.before['config.cfg'])
 def test_staged_metadata_policy(self):
  stage=self.root/'stage';trial.copy_content_tree(self.active,stage)
  header=struct.pack('>II16sH',0x51607,0x20000,b'\0'*16,1)
  data=header+struct.pack('>III',9,38,32)+b'\0'*32
  sidecar=stage/'._config.cfg';sidecar.write_bytes(data)
  self.assertEqual(trial.verify_staged_current(stage,self.before),['._config.cfg'])
  sidecar.write_bytes(b'garbage')
  with self.assertRaises(ValueError):trial.verify_staged_current(stage,self.before)
  sidecar.unlink();(stage/'unexpected').write_text('extra')
  with self.assertRaises(ValueError):trial.verify_staged_current(stage,self.before)
  (stage/'unexpected').unlink();(stage/'._missing').write_bytes(data)
  with self.assertRaises(ValueError):trial.verify_staged_current(stage,self.before)
  (stage/'._missing').unlink();(stage/'config.cfg').write_text('changed')
  with self.assertRaises(ValueError):trial.verify_staged_current(stage,self.before)
 def test_bad_snapshot(self):
  (self.backup/'.rockbox/rockbox.ipod').write_text('bad')
  with self.assertRaises(ValueError):self.apply()
  trial.verify(self.active,self.before);self.assertFalse(self.args.session.exists())
 def test_package_cannot_change_config(self):
  with zipfile.ZipFile(self.package,'a') as z:z.writestr('.rockbox/config.cfg','spectrum enabled: off\n')
  self.args.sha256=trial.sha(self.package)
  with self.assertRaisesRegex(ValueError,'saved config'):self.apply()
  trial.verify(self.active,self.before)
 def test_low_space(self):
  with patch.object(trial.shutil,'disk_usage',return_value=SimpleNamespace(free=0)):
   with self.assertRaisesRegex(ValueError,'space'):self.apply()
  self.assertFalse(self.args.session.exists());trial.verify(self.active,self.before)
 def test_changes_during_staging_refused(self):
  copy=trial.copy_content_tree
  def changed(source,destination,*a,**kw):
   result=copy(source,destination,*a,**kw)
   if source==self.active:(self.active/'config.cfg').write_text('new device save')
   return result
  with patch.object(trial,'copy_content_tree',side_effect=changed):
   with self.assertRaises(ValueError):self.apply()
  self.assertEqual((self.active/'rockbox.ipod').read_text(),'v1')
 def test_activation_rename_failure_restores_current(self):
  rename=Path.rename
  def fail(path,destination):
   if path.parent.name.startswith('.spectrum-stage-'):raise OSError('injected activation failure')
   return rename(path,destination)
  with patch.object(Path,'rename',fail):
   with self.assertRaisesRegex(OSError,'injected'):self.apply()
  trial.verify(self.active,self.before)
 def test_readback_failure_restores_current(self):
  verify=trial.verify;calls=0
  def fail(root,expected):
   nonlocal calls
   if root==self.active:
    calls+=1
    if calls==2:raise ValueError('injected readback failure')
   return verify(root,expected)
  with patch.object(trial,'verify',side_effect=fail):
   with self.assertRaisesRegex(ValueError,'injected'):self.apply()
  trial.verify(self.active,self.before);self.assertEqual(len(list(self.volume.glob('.rockbox-failed-spectrum-*'))),1)
 def test_retained_corruption_refused(self):
  self.apply();report=json.loads((self.args.session/'trial.json').read_text());retained=Path(report['retained_device_backup'])
  (retained/'rockbox.ipod').write_text('bad')
  self.args.action='rollback';self.args.reuse_backup=None;self.args.retained_tree=retained
  with self.assertRaises(ValueError):self.apply()
  self.assertEqual((self.active/'rockbox.ipod').read_text(),'fast2')
if __name__=='__main__':unittest.main()
