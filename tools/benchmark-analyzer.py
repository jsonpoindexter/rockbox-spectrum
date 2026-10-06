#!/usr/bin/env python3
"""Compare analyzer-only host timing with a supplied original C source; no device I/O."""
import argparse, ctypes, hashlib, importlib.util, json, platform, statistics, subprocess, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'overlay/apps/gui/spectrum'
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('numeric_tests',ROOT/'tools/run-tests.py');types=importlib.util.module_from_spec(spec);spec.loader.exec_module(types)
    source=CORE/'analyzer.c';results=[]
    pcm=(ctypes.c_int16*2048)(*[(i*4711)%65536-32768 for i in range(2048)])
    with tempfile.TemporaryDirectory(prefix='spectrum-timing-') as tmp:
        for name,file in [('original_two_ffts',a.reference),('packed_one_fft',source)]:
            lib=Path(tmp)/(name+'.so')
            subprocess.run(['cc','-std=c99','-O2','-shared','-fPIC','-I',str(CORE),str(file),'-o',str(lib)],check=True)
            api=ctypes.CDLL(str(lib));api.spectrum_analyze.argtypes=[ctypes.POINTER(types.Analyzer),ctypes.POINTER(ctypes.c_int16),ctypes.c_uint32,ctypes.POINTER(types.Frame)]
            analyzer=types.Analyzer();frame=types.Frame();samples=[]
            for _ in range(20):api.spectrum_analyze(ctypes.byref(analyzer),pcm,44100,ctypes.byref(frame))
            for repeat in range(5):
                start=time.perf_counter()
                for _ in range(2000):api.spectrum_analyze(ctypes.byref(analyzer),pcm,44100,ctypes.byref(frame))
                samples.append((time.perf_counter()-start)*1000/2000)
            results.append({'variant':name,'source_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'median_ms_per_analysis':statistics.median(samples),'runs_ms_per_analysis':samples,'calls_per_run':2000})
    report={'scope':'analyzer-only host microbenchmark including identical ctypes overhead; not iPod timing or CPU usage','host':platform.platform(),'machine':platform.machine(),'compiler':subprocess.check_output(['cc','--version'],text=True).splitlines()[0],'optimization':'-O2','sample_rate':44100,'results':results,'speedup':results[0]['median_ms_per_analysis']/results[1]['median_ms_per_analysis'],'device_timing':'not measured'}
    text=json.dumps(report,indent=2)+'\n';print(text,end='')
    if a.output:a.output.write_text(text)
if __name__=='__main__':main()
