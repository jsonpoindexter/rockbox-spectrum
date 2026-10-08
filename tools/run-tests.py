#!/usr/bin/env python3
"""Test the portable capture, analyzer, and widget code. No device access."""
import argparse, ctypes, json, math, random, subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'overlay/apps/gui/spectrum'
class Analyzer(ctypes.Structure):
    _fields_ = [('real', ctypes.c_int32 * 1024), ('imag', ctypes.c_int32 * 1024), ('power', ctypes.c_uint64 * 512), ('cached_rate', ctypes.c_uint32), ('generation', ctypes.c_uint32), ('previous_energy', ctypes.c_int16 * 3), ('lo', ctypes.c_uint16 * 32), ('hi', ctypes.c_uint16 * 32)]
class Frame(ctypes.Structure):
    _fields_ = [('generation', ctypes.c_uint32), ('sequence', ctypes.c_uint32), ('sample_rate', ctypes.c_uint32), ('tick', ctypes.c_uint32), ('capture_us', ctypes.c_uint32), ('wave', (ctypes.c_int16 * 2) * 128), ('energy', ctypes.c_int16 * 3), ('onset', ctypes.c_int16), ('db', ctypes.c_int16 * 32)]
def fft(data):
    values = list(data); n=len(values);j=0
    for i in range(1,n):
        bit=n//2
        while j & bit: j^=bit;bit//=2
        j^=bit
        if i<j: values[i],values[j]=values[j],values[i]
    length=2
    while length<=n:
        half=length//2
        for start in range(0,n,length):
            for j in range(half):
                t=complex(math.cos(-2*math.pi*j/length),math.sin(-2*math.pi*j/length))*values[start+j+half]
                u=values[start+j];values[start+j]=u+t;values[start+j+half]=u-t
        length*=2
    return [v/n for v in values]
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='rockbox-spectrum-tests-') as tmp:
        tmp=Path(tmp); exe=tmp/'test-core';lib=tmp/'analysis.so'
        subprocess.run(['cc','-std=c99','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-g','-I',str(CORE),str(ROOT/'tests/test_core.c'),str(CORE/'analyzer.c'),str(CORE/'capture.c'),'-lm','-o',str(exe)],check=True)
        core=subprocess.check_output([str(exe)],universal_newlines=True);print(core,end='')
        subprocess.run(['cc','-std=c99','-O2','-shared','-fPIC',str(CORE/'analyzer.c'),str(ROOT/'tests/analyzer_uncached.c'),'-I',str(CORE),'-o',str(lib)],check=True)
        api=ctypes.CDLL(str(lib));api.spectrum_analyze.argtypes=[ctypes.POINTER(Analyzer),ctypes.POINTER(ctypes.c_int16),ctypes.c_uint32,ctypes.POINTER(Frame)]
        api.spectrum_analyze_uncached.argtypes=api.spectrum_analyze.argtypes
        cached=Analyzer()
        rng=random.Random(471);worst=0;compared=0
        for rate in (44100,48000,96000):
            for kind in ('noise','antiphase','unequal','clipped','quadrature','biased_impulse'):
                pairs=[]
                for i in range(1024):
                    sine=round(30000*math.sin(2*math.pi*23*i/1024))
                    if kind=='quadrature':
                        pairs.append((sine,round(30000*math.cos(2*math.pi*23*i/1024))))
                    elif kind=='biased_impulse':
                        pairs.append((-32768 if i==511 else 30000,-32768 if i==512 else 32000))
                    else:
                        pairs.append((rng.randrange(-32768,32768),rng.randrange(-32768,32768)) if kind=='noise' else (sine,-sine) if kind=='antiphase' else (sine,sine//3) if kind=='unequal' else (32767 if i%7<3 else -32768,32767 if i%11<5 else -32768))
                buffer=(ctypes.c_int16*2048)(*[v for pair in pairs for v in pair]);a=Analyzer();f=Frame();api.spectrum_analyze(ctypes.byref(a),buffer,rate,ctypes.byref(f))
                original=bytes(buffer); uncached=Analyzer(); old=Frame()
                api.spectrum_analyze_uncached(ctypes.byref(uncached),buffer,rate,ctypes.byref(old))
                api.spectrum_analyze(ctypes.byref(cached),buffer,rate,ctypes.byref(f))
                assert list(old.db)==list(f.db) and list(uncached.power)==list(cached.power)
                assert bytes(buffer)==original
                power=[0.0]*512
                for channel in range(2):
                    samples=[p[channel] for p in pairs];mean=math.trunc(sum(samples)/1024)
                    values=fft([(x-mean)*round(32767*(0.5-0.5*math.cos(2*math.pi*i/1024))) for i,x in enumerate(samples)])
                    for k in range(1,512):power[k]+=abs(values[k])**2/2
                for k in range(1,512):
                    # Compare meaningful bins; below -60dBFS integer noise dominates.
                    if power[k]<268419072**2*1e-6:continue
                    error=abs(10*math.log10(a.power[k]/power[k]));worst=max(worst,error);compared+=1
                    assert error<0.15,(rate,kind,k,error)
        result={'portable_tests':'passed','sanitizers':['address','undefined'],'float_reference_cases':18,'compared_fft_bins':compared,'maximum_power_error_db':round(worst,6),'sample_rates':[44100,48000,96000],'core_output':core.strip(),'device_tests':'not performed'}
        print(json.dumps(result,indent=2))
        if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
