#!/usr/bin/env python3
"""Run real Rockbox checkwps parser tests (pass its executable as argument)."""
import argparse,json,subprocess,tempfile
from pathlib import Path
VALID=['0,0,280,30,16,bars,mono','0,0,320,100,32,lines,classic','0,0,16,2,8,bars,mono']
VALID += ['0,0,280,70,16,bars,mono,dots,auto,4,lanes,auto,auto,1',
          '0,0,320,240,8,bars,classic,solid,ABCDEF,16,frame,123456,ffffff,3',
          '0,0,280,70,16,bars,mono,off,000000,2,baseline,00ff00,ffffff,1']
INVALID=['-1,0,280,30,16,bars,mono','0,0,321,30,16,bars,mono','0,230,280,30,16,bars,mono','0,0,280,30,12,bars,mono','0,0,31,30,16,bars,mono','0,0,280,0,16,bars,mono','0,0,280,30,16,milkdrop,mono','0,0,280,30,16,bars,rainbow','0,0,280,30,16,bars','0,0,280,30,16,-,mono','0,0,280%,30,16,bars,mono']
INVALID += ['0,0,280,70,16,bars,mono,' + suffix for suffix in [
    'dots', 'dots,auto,4,lanes,auto,auto', 'dots,auto,4,lanes,auto,auto,1,extra',
    'dots,auto,4,lanes,auto,auto,-', 'dots,auto,4,lanes,auto,auto,0',
    'dots,auto,4,lanes,auto,auto,4', 'dots,auto,1,lanes,auto,auto,1',
    'dots,auto,17,lanes,auto,auto,1', 'dense,auto,4,lanes,auto,auto,1',
    'dots,auto,4,unknown,auto,auto,1', 'dots,GGFFFF,4,lanes,auto,auto,1',
    'dots,auto,4,lanes,fff,auto,1', 'dots,auto,4,lanes,auto,ffffff0,1']]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('checkwps',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
 with tempfile.TemporaryDirectory(prefix='spectrum-parser-') as temp:
  for expected,values in [(True,VALID),(False,INVALID)]:
   for index,value in enumerate(values):
    f=Path(temp)/('test-'+str(expected)+'-'+str(index)+'.wps');f.write_text('%V(0,0,320,240,-)\n%pF('+value+')\n')
    result=subprocess.run([str(a.checkwps),str(f)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    assert (result.returncode==0)==expected,(value,result.stdout.decode())
 result={'valid_cases':len(VALID),'rejected_cases':len(INVALID),'result':'passed'};print(json.dumps(result,indent=2))
 if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
