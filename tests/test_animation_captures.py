#!/usr/bin/env python3
"""Regression checks for overpainted titles, frozen motion and unsettled pauses."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('animation_captures',ROOT/'tools/verify-animation-previews.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class CaptureTests(unittest.TestCase):
    def test_motion_text_pause_and_disabled_regressions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'Example';folder.mkdir()
            regions={'Example':((0,10,16,16),[(0,0,16,8)])}
            def draw(name, motion=0, text=True, painted=False):
                data=bytearray(320*240*3)
                if text:data[0:3]=b'\xff\xff\xff'
                if motion:data[(12*320+4)*3:(12*320+4)*3+3]=bytes((motion,90,180))
                if painted:data[3:6]=b'\xff\x00\x00'
                (folder/name).write_bytes(b'P6\n320 240\n255\n'+data)
            draw('playing.png',1)
            for i in range(24):draw('animation-%02d.png'%i,i+1)
            for name in ['paused.png','paused-later.png']:draw(name)
            with patch.object(module,'REGIONS',regions):
                self.assertEqual(module.verify(root,'normal')['result'],'passed')
                draw('playing.png',1,text=False)
                with self.assertRaisesRegex(ValueError,'Blank track'):module.verify(root,'normal')
                draw('playing.png',1)
                draw('animation-02.png',3,painted=True)
                with self.assertRaisesRegex(ValueError,'overwrote'):module.verify(root,'normal')
                draw('animation-02.png',3)
                draw('paused.png',1)
                with self.assertRaisesRegex(ValueError,'settle'):module.verify(root,'normal')
                draw('paused.png')
                for i in range(24):draw('animation-%02d.png'%i,1)
                with self.assertRaisesRegex(ValueError,'move'):module.verify(root,'normal')
                with self.assertRaisesRegex(ValueError,'Disabled'):module.verify(root,'spectrum-off')
                draw('playing.png')
                self.assertEqual(module.verify(root,'spectrum-off')['result'],'passed')
if __name__=='__main__':unittest.main()
