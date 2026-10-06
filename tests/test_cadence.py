#!/usr/bin/env python3
"""Execute the actual patched UI loop with deterministic draw/input timing."""
import json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
patch=(ROOT/'patches/0001-native-spectrum.patch').read_text()
start=patch.index('+    static bool spectrum_was_active;')
end=patch.index('+#endif',start)
block='\n'.join(line[1:] for line in patch[start:end].splitlines() if line.startswith('+'))
assert 'button_queue_post' not in patch
code=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#define HZ 100
#define WPS 1
#define SCREEN_MAIN 0
#define ACTION_NONE 0
#define SKIN_REFRESH_PEAK_METER 1
#define MIN(a,b) ((a)<(b)?(a):(b))
#define TIME_BEFORE(a,b) ((int32_t)((uint32_t)(a)-(uint32_t)(b))<0)
REFRESH_DEFINE
static long current_tick;
static unsigned calls, draw_cost;
static long starts[100];
static long hardware_tick=-1;
static unsigned hardware_taken;
static bool visible=true;
struct data {bool spectrum_visible;};
struct gwps {struct data *data;};
static struct data data={true};
static struct gwps gwps={&data};
static struct gwps *skin_get_gwps(int s,int d){(void)s;(void)d;return &gwps;}
static bool spectrum_set_visible(bool v){return v&&visible;}
static void skin_request_full_update(int s){(void)s;}
static void peak_meter_peek(void){}
static void skin_update(int s,int d,int f){(void)s;(void)d;(void)f;}
static void skin_render_spectrum(struct gwps *g){(void)g;starts[calls++]=current_tick;current_tick+=draw_cost;}
static int get_action(int context,long wait){
 (void)context;
 if(hardware_tick>=0&&current_tick>=hardware_tick&&!hardware_taken){hardware_taken++;return 7;}
 if(wait>0)current_tick+=wait;
 return ACTION_NONE;
}
static int run(long timeout){
 int skin=WPS,context=0,button=ACTION_NONE;
 bool pm=false;
 UI_BLOCK
 return button;
}
int main(int argc,char **argv){
 assert(argc==2);draw_cost=atoi(argv[1]);
 if(draw_cost==9){draw_cost=1;hardware_tick=0;assert(run(10)==7);assert(calls==0);}
 else if(draw_cost==8){draw_cost=1;hardware_tick=4;assert(run(10)==7);assert(calls==2&&starts[0]==0&&starts[1]==2);}
 else {
  run(12);
  assert(calls>=3);
  for(unsigned i=1;i<calls;i++){
   long expected=draw_cost<=1?2:draw_cost+1;
   assert(starts[i]-starts[i-1]==expected);
  }
 }
 visible=false;run(1);
 for(unsigned i=0;i<calls;i++)printf("%ld%s",starts[i],i+1==calls?"\n":",");
 return 0;
}
'''
refresh=next(line for line in (ROOT/'overlay/apps/gui/spectrum/service.h').read_text().splitlines() if line.startswith('#define SPECTRUM_REFRESH_TICKS'))
with tempfile.TemporaryDirectory(prefix='spectrum-cadence-') as tmp:
 tmp=Path(tmp);c=tmp/'test.c';exe=tmp/'test'
 c.write_text(code.replace('REFRESH_DEFINE',refresh).replace('UI_BLOCK',block))
 subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(c),'-o',str(exe)],check=True)
 cases={}
 for cost in (0,1,3,8,9):cases[str(cost)]=subprocess.check_output([str(exe),str(cost)],text=True).strip()
 print(json.dumps({'result':'passed','actual_patched_loop':True,'start_ticks_by_draw_cost':cases,'pending_input_before_draw':'passed','overrun_catchup_bursts':False,'device_cadence':'not measured'},indent=2))
