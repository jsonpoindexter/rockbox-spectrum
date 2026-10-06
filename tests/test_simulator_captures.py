#!/usr/bin/env python3
"""Regression checks for saved-pixel validation (requires ImageMagick)."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('captures', Path(__file__).resolve().parents[1] / 'tools/verify-simulator-captures.py')
captures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(captures)


class CaptureTests(unittest.TestCase):
    def test_visible_text_blank_text_and_zoom(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = bytearray(320 * 240 * 3)
            for y in range(10, 20):
                for x in range(10, 20):
                    data[(y * 320 + x) * 3:(y * 320 + x) * 3 + 3] = b'\xff\xff\xff'
            # Independent nonmetadata content keeps a damaged frame nonblank.
            for y in range(100, 120):
                for x in range(100, 120):
                    data[(y * 320 + x) * 3:(y * 320 + x) * 3 + 3] = b'\x00\xff\x00'
            (root / 'reference.ppm').write_bytes(b'P6\n320 240\n255\n' + data)
            subprocess.run(['convert', str(root / 'reference.ppm'), '-filter', 'point', '-resize', '640x480!', str(root / 'zoom.png')], check=True)
            manifest = {'reference': 'reference.ppm', 'regions': {'text': [10, 10, 20, 20]},
                        'captures': [{'file': 'zoom.png', 'state': '2x', 'regions': ['text']}]}
            path = root / 'manifest.json'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            self.assertEqual(captures.verify(path)['result'], 'passed')
            for y in range(10, 20):
                data[(y * 320 + 10) * 3:(y * 320 + 20) * 3] = b'\0' * 30
            (root / 'damaged.ppm').write_bytes(b'P6\n320 240\n255\n' + data)
            manifest['captures'][0]['file'] = 'damaged.ppm'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Metadata differs'):
                captures.verify(path)
            manifest['reference'] = 'damaged.ppm'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'insufficient text'):
                captures.verify(path)

            manifest['reference'] = 'reference.ppm'
            manifest['captures'][0] = {'file': 'zoom.png', 'state': '2x', 'regions': []}
            path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'never checked'):
                captures.verify(path)
            manifest['captures'][0]['regions'] = ['text']
            manifest['animation_pairs'] = [{'files': ['zoom.png', 'zoom.png'], 'bounds': [100, 100, 120, 120]}]
            path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Animation did not change'):
                captures.verify(path)

    def test_unfilled_bar_guide_mask(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = bytearray(320*240*3)
            for y in range(10,20):
                for x in range(10,20):
                    data[(y*320+x)*3:(y*320+x)*3+3] = b'\xff'*3
            # Independent explicit tile, including the staggered second row.
            tile = ((1,0,0,0),(0,0,0,0),(0,0,1,0),(0,0,0,0))
            for lane in range(16):
                left = lane*280//16
                width = (lane+1)*280//16-left-1
                for y in range(70):
                    for x in range(width):
                        if (x<3 or x>=width-3 or y<3 or y>=67) and tile[y%4][x%4]:
                            offset = ((y+122)*320+20+left+x)*3
                            data[offset:offset+3] = b'\xff'*3
            frame = root/'paused.ppm'
            frame.write_bytes(b'P6\n320 240\n255\n'+data)
            manifest = {'reference':'paused.ppm','regions':{'text':[10,10,20,20]},
                'captures':[{'file':'paused.ppm','state':'paused','regions':['text']}],
                'spectrum_bounds':[20,122,300,192],'guided_silence':['paused.ppm'],
                'guide_bands':16,'guide_pattern':'unfilled-bar-dots'}
            path = root/'manifest.json'; path.write_text(json.dumps(manifest))
            self.assertEqual(captures.verify(path)['result'],'passed')
            # Removing the second-row offset must fail, as must a gray dot.
            offset = ((122+2)*320+20+2)*3
            for damaged in (b'\0'*3,b'\x20'*3):
                broken = data[:];broken[offset:offset+3]=damaged
                frame.write_bytes(b'P6\n320 240\n255\n'+broken)
                with self.assertRaisesRegex(ValueError,'independent lane/baseline mask'):
                    captures.verify(path)

            # A separately observed host-renderer background is explicit;
            # all background pixels must still match it exactly.
            manifest['background_rgb'] = [8,0,8]
            path.write_text(json.dumps(manifest))
            frame.write_bytes(b'P6\n320 240\n255\n'+data)
            with self.assertRaisesRegex(ValueError,'independent lane/baseline mask'):
                captures.verify(path)
            tinted = data[:]
            for i in range(0,len(tinted),3):
                if tinted[i:i+3] == b'\0'*3:
                    tinted[i:i+3] = bytes([8,0,8])
            frame.write_bytes(b'P6\n320 240\n255\n'+tinted)
            self.assertEqual(captures.verify(path)['result'],'passed')
            blank = tinted[:]
            for y in range(10,20):
                for x in range(10,20):
                    blank[(y*320+x)*3:(y*320+x)*3+3] = bytes([8,0,8])
            frame.write_bytes(b'P6\n320 240\n255\n'+blank)
            with self.assertRaisesRegex(ValueError,'insufficient text'):
                captures.verify(path)
            frame.write_bytes(b'P6\n320 240\n255\n'+tinted)
            manifest['background_rgb'] = [8,0,256]
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'Invalid explicit background'):
                captures.verify(path)

    def test_thin_guides_reject_dense_edges(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = bytearray(320*240*3)
            for y in range(10,20):
                for x in range(10,20):
                    data[(y*320+x)*3:(y*320+x)*3+3] = b'\xff'*3
            tile = ((1,0,0,0),(0,0,0,0),(0,0,1,0),(0,0,0,0))
            thin_count = dense_count = 0
            for lane in range(16):
                left = lane*280//16
                width = (lane+1)*280//16-left-1
                for y in range(70):
                    for x in range(width):
                        if 3 <= y < 67:
                            thin = (x == 0 and y % 4 == 0) or (x == width-1 and y % 4 == 2)
                            thin_count += thin
                            dense_count += (x<3 or x>=width-3) and tile[y%4][x%4]
                        else:
                            thin = tile[y%4][x%4]
                        if thin:
                            offset = ((y+122)*320+20+left+x)*3
                            data[offset:offset+3] = b'\xff'*3
            self.assertEqual(thin_count,512)
            self.assertEqual(dense_count,896)
            frame = root/'paused.ppm'
            frame.write_bytes(b'P6\n320 240\n255\n'+data)
            manifest = {'reference':'paused.ppm','regions':{'text':[10,10,20,20]},
                'captures':[{'file':'paused.ppm','state':'paused','regions':['text']}],
                'spectrum_bounds':[20,122,300,192],'guided_silence':['paused.ppm'],
                'guide_bands':16,'guide_pattern':'thin-unfilled-bar-dots'}
            path = root/'manifest.json';path.write_text(json.dumps(manifest))
            self.assertEqual(captures.verify(path)['result'],'passed')
            # Reject an extra interior-column dot from the dense old border,
            # a missing left edge dot, and a wrong-phase right edge dot.
            for x,y,pixel in ((2,6,b'\xff'*3),(0,4,b'\0'*3),(15,4,b'\xff'*3)):
                broken = data[:];offset = ((122+y)*320+20+x)*3
                broken[offset:offset+3] = pixel
                frame.write_bytes(b'P6\n320 240\n255\n'+broken)
                with self.assertRaisesRegex(ValueError,'independent lane/baseline mask'):
                    captures.verify(path)

    def test_single_separators_reject_paired_edges(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = bytearray(320*240*3)
            for y in range(10,20):
                for x in range(10,20):
                    data[(y*320+x)*3:(y*320+x)*3+3] = b'\xff'*3
            tile = ((1,0,0,0),(0,0,0,0),(0,0,1,0),(0,0,0,0))
            thin_count = paired_count = 0
            for lane in range(16):
                left = lane*280//16
                width = (lane+1)*280//16-left-1
                for y in range(70):
                    for x in range(width):
                        if 3 <= y < 67:
                            thin = lane > 0 and x == 0 and y % 4 == 0
                            thin_count += thin
                            paired_count += (x == 0 and y % 4 == 0) or (x == width-1 and y % 4 == 2)
                        else:
                            thin = tile[y%4][x%4]
                        if thin:
                            offset = ((y+122)*320+20+left+x)*3
                            data[offset:offset+3] = b'\xff'*3
            self.assertEqual(thin_count,240)
            self.assertEqual(paired_count,512)
            frame = root/'paused.ppm'
            frame.write_bytes(b'P6\n320 240\n255\n'+data)
            manifest = {'reference':'paused.ppm','regions':{'text':[10,10,20,20]},
                'captures':[{'file':'paused.ppm','state':'paused','regions':['text']}],
                'spectrum_bounds':[20,122,300,192],'guided_silence':['paused.ppm'],
                'guide_bands':16,'guide_pattern':'single-separator-dots'}
            path = root/'manifest.json';path.write_text(json.dumps(manifest))
            self.assertEqual(captures.verify(path)['result'],'passed')
            # Reject an outer edge, a former right edge, a missing separator,
            # and a wrong-phase separator dot.
            for x,y,pixel in ((0,4,b'\xff'*3),(15,6,b'\xff'*3),(17,4,b'\0'*3),(17,6,b'\xff'*3)):
                broken = data[:];offset = ((122+y)*320+20+x)*3
                broken[offset:offset+3] = pixel
                frame.write_bytes(b'P6\n320 240\n255\n'+broken)
                with self.assertRaisesRegex(ValueError,'independent lane/baseline mask'):
                    captures.verify(path)

    def test_uniform_dim_guides_reject_staggered_bright_dots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = bytearray(320*240*3)
            for y in range(10,20):
                for x in range(10,20):
                    data[(y*320+x)*3:(y*320+x)*3+3] = b'\xff'*3
            tile = ((1,0,0,0),(0,0,0,0),(0,0,1,0),(0,0,0,0))
            thin_count = paired_count = 0
            for lane in range(16):
                left = lane*280//16
                width = (lane+1)*280//16-left-1
                for y in range(70):
                    for x in range(width):
                        if 3 <= y < 67:
                            thin = lane > 0 and x == 0 and y % 4 == 0
                            thin_count += thin
                            paired_count += (x == 0 and y % 4 == 0) or (x == width-1 and y % 4 == 2)
                        else:
                            thin = y in (0,68) and x%4 == 0
                        if thin:
                            offset = ((y+122)*320+20+left+x)*3
                            data[offset:offset+3] = bytes([189,190,189])
            self.assertEqual(thin_count,240)
            self.assertEqual(paired_count,512)
            frame = root/'paused.ppm'
            frame.write_bytes(b'P6\n320 240\n255\n'+data)
            manifest = {'reference':'paused.ppm','regions':{'text':[10,10,20,20]},
                'captures':[{'file':'paused.ppm','state':'paused','regions':['text']}],
                'spectrum_bounds':[20,122,300,192],'guided_silence':['paused.ppm'],
                'guide_bands':16,'guide_pattern':'uniform-dim-dots'}
            path = root/'manifest.json';path.write_text(json.dumps(manifest))
            self.assertEqual(captures.verify(path)['result'],'passed')
            # Reject the former second top row, bright guides, a missing bottom
            # marker and a phase-shifted horizontal dot.
            for x,y,pixel in ((2,2,bytes([189,190,189])),(17,4,b'\xff'*3),(0,68,b'\0'*3),(2,0,bytes([189,190,189]))):
                broken = data[:];offset = ((122+y)*320+20+x)*3
                broken[offset:offset+3] = pixel
                frame.write_bytes(b'P6\n320 240\n255\n'+broken)
                with self.assertRaisesRegex(ValueError,'independent lane/baseline mask'):
                    captures.verify(path)

    def test_pause_requires_intermediate_decay(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            items=[]
            for index,height in enumerate((20,10,0)):
                data=bytearray(320*240*3)
                for y in range(10,30):
                    for x in range(10,30):
                        data[(y*320+x)*3:(y*320+x)*3+3]=b'\xff\xff\xff'
                for y in range(100,100+height):
                    for x in range(100,120):
                        data[(y*320+x)*3:(y*320+x)*3+3]=b'\0\xff\0'
                name=str(index)+'.ppm';(root/name).write_bytes(b'P6\n320 240\n255\n'+data)
                items.append({'file':name,'state':'paused','regions':['text']})
            manifest={'reference':'0.ppm','regions':{'text':[10,10,30,30]},
                'captures':items,'spectrum_bounds':[100,100,120,120],
                'pause_decay':['0.ppm','1.ppm','2.ppm']}
            path=root/'manifest.json';path.write_text(json.dumps(manifest))
            self.assertEqual([d['colored_bar_pixels'] for d in captures.verify(path)['pause_decay']],[400,200,0])
            for bad in (['0.ppm','0.ppm','2.ppm'],['1.ppm','0.ppm','2.ppm'],['0.ppm','1.ppm','1.ppm']):
                manifest['pause_decay']=bad;path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError,'Pause sequence'):
                    captures.verify(path)


if __name__ == '__main__':
    unittest.main()
