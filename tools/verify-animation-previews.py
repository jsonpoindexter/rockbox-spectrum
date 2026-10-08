#!/usr/bin/env python3
"""Verify actual theme animation captures; no physical performance claim."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REGIONS = {
    'WinampSpectrum-Detail': ((118,26,190,100), [(12,137,296,28),(12,166,296,17)]),
    'WinampSpectrum-Visualizer': ((4,4,312,172), [(10,182,300,17),(10,201,196,17)]),
    'StudioSpectrum-Detail': ((128,30,180,156), [(12,203,296,17),(12,81,103,17)]),
    'StudioSpectrum-Visualizer': ((12,64,296,144), [(12,8,296,28),(12,40,232,17)]),
    'AdwaitaSpectrum-Detail': ((16,174,288,32), [(16,5,288,24),(16,32,288,23)]),
    'AdwaitaSpectrum-Visualizer': ((12,8,296,158), [(20,176,280,24),(20,203,280,23)]),
}

def pixels(path, rect):
    x,y,w,h = rect
    data = subprocess.check_output(['convert', str(path), '-crop', '%dx%d+%d+%d'%(w,h,x,y),
                                    '+repage', '-depth','8','rgb:-'])
    if len(data) != w*h*3:
        raise ValueError('Unexpected capture dimensions: '+str(path))
    return data

def colors(data):
    return len({data[i:i+3] for i in range(0,len(data),3)})

def verify(root, scenario):
    result=[]
    for name,(animation,texts) in REGIONS.items():
        folder=root/name
        playing=folder/'playing.png'
        if not playing.is_file():raise ValueError('Missing theme capture: '+name)
        # Both normal metadata regions must contain visible glyphs, including
        # the album-art layout's title, which previously got overpainted.
        for rect in texts:
            if colors(pixels(playing,rect))<2:raise ValueError('Blank track metadata: '+name)
        row={'theme':name,'scenario':scenario}
        if scenario=='normal':
            frames=sorted(folder.glob('animation-*.png'))
            if len(frames)!=24:raise ValueError('Expected24 sampled video frames: '+name)
            motion={hashlib.sha256(pixels(frame,animation)).hexdigest() for frame in frames}
            if len(motion)<18:raise ValueError('Animation did not move sufficiently: '+name)
            for rect in texts:
                reference=pixels(frames[0],rect)
                if any(pixels(frame,rect)!=reference for frame in frames[1:]):
                    raise ValueError('Animation overwrote fixed metadata: '+name)
            for state in ['paused','paused-later']:
                if colors(pixels(folder/(state+'.png'),animation))!=1:
                    raise ValueError('Animation failed to settle on pause: '+name)
            row['distinct_animation_frames']=len(motion)
            row['fixed_metadata']='stable'
            row['pause']='settled'
        elif scenario=='spectrum-off':
            if colors(pixels(playing,animation))!=1:
                raise ValueError('Disabled animation painted: '+name)
            row['disabled']='clear'
        result.append(row)
    return {'result':'passed','layouts':result,'device_tests':'not performed'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures',type=Path)
    parser.add_argument('--scenario',choices=['normal','spectrum-off','long-metadata','missing-metadata'],default='normal')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=verify(args.captures,args.scenario)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
