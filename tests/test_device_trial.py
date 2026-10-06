"""Exercise installation and rollback against a disposable directory, never an iPod."""
import hashlib, importlib.util, json, tempfile, unittest, zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from types import SimpleNamespace
TOOL=Path(__file__).resolve().parents[1]/'tools/device-trial.py'
spec=importlib.util.spec_from_file_location('trial',TOOL);trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)
class DeviceTrial(unittest.TestCase):
 def test_file_transaction_and_rollback(self):
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);volume=tmp/'volume';active=volume/'.rockbox';active.mkdir(parents=True)
   files={'rockbox-info.txt':'Target: ipod6g\nVersion: 4.0\n','rockbox.ipod':'original','config.cfg':'wps: /.rockbox/wps/CrazyBitMono.wps\n','rocks/custom.rock':'old executable','rocks/custom.cfg':'keep settings','codecs/old.codec':'old codec','wps/user-theme.wps':'keep theme'}
   for name,data in files.items():
    path=active/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(data)
   (volume/'music.mp3').write_bytes(b'music untouched');(volume/'bootloader-sentinel').write_bytes(b'untouched')
   before=trial.manifest(active);package=tmp/'trial.zip'
   with zipfile.ZipFile(package,'w') as z:
    for name,data in {'rockbox-info.txt':'Target: ipod6g\nVersion: 4.0-spectrum-1.0.0-e094c599fa\n','rockbox.ipod':'custom','codecs/mpa.codec':'new codec','rocks/demos/fft.rock':'new plugin'}.items():z.writestr('.rockbox/'+name,data)
   backup=tmp/'backup';args=SimpleNamespace(action='install',volume=volume,backup=backup,package=package,sha256=trial.sha(package),apply=False)
   trial.run(args);self.assertFalse(backup.exists());self.assertEqual(trial.manifest(active),before)
   args.apply=True;trial.run(args)
   self.assertEqual((active/'rockbox.ipod').read_text(),'custom');self.assertFalse((active/'rocks/custom.rock').exists());self.assertFalse((active/'codecs/old.codec').exists());self.assertEqual((active/'rocks/custom.cfg').read_text(),'keep settings');self.assertIn('spectrum enabled: off',(active/'config.cfg').read_text());self.assertFalse((active/'themes/CrazyBitSpectrum.cfg').exists());self.assertEqual((active/'wps/user-theme.wps').read_text(),'keep theme');trial.verify(backup/'.rockbox',before)
   args.action='rollback';args.apply=False;trial.run(args);self.assertEqual((active/'rockbox.ipod').read_text(),'custom')
   args.apply=True;trial.run(args);trial.verify(active,before)
   self.assertEqual((volume/'music.mp3').read_bytes(),b'music untouched');self.assertEqual((volume/'bootloader-sentinel').read_bytes(),b'untouched')
   self.assertEqual(json.loads((backup/'trial.json').read_text())['file_verification'],'passed')
 def test_package_rejections(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'bad.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr('../escape','bad')
   with self.assertRaises(ValueError):trial.validate_package(p,trial.sha(p))
   with self.assertRaises(ValueError):trial.validate_package(p,'wrong fingerprint')
if __name__=='__main__':unittest.main()
