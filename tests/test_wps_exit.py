#!/usr/bin/env python3
"""Execute the added WPS exit gate; preserve non-Stop exits and input dispatch."""
import json,subprocess,tempfile
from pathlib import Path
from test_service_render import CORE,STUB
patch=(CORE.parents[3]/'patches/0001-native-spectrum.patch').read_text()
start=patch.index('+            if (!spectrum_exit_started) {')
end=patch.index('\n         }',start)
block='\n'.join(line[1:] for line in patch[start:end].splitlines() if line.startswith('+') or line.startswith(' '))
block=block.replace('#endif','')
code=r'''
#include "SERVICE_SOURCE"
#include <assert.h>
#include <stdio.h>
#define ACTION_NONE 0
#define ACTION_WPS_STOP 7
#define ACTION_WPS_REC 8
#define WPS 0
#define SCREEN_MAIN 0
struct data {bool spectrum_visible;};
struct gwps {struct data *data;};
static struct data data={true};
static struct gwps gwps={&data};
static struct gwps *skin_get_gwps(int a,int b){(void)a;(void)b;return &gwps;}
static unsigned paused, exits;
static void audio_pause(void){paused++;audio_state|=AUDIO_STATUS_PAUSE;}
static void update_non_static(void){}
static int do_wps_exit(long button,bool bookmark){(void)bookmark;exits++;return (int)button+100;}
static int pass(long *action,bool *started,uint32_t *tick){
 bool spectrum_exit_started=*started,bookmark=true;
 uint32_t spectrum_exit_tick=*tick;
 long button=*action;
 EXIT_BLOCK
 *action=button;*started=spectrum_exit_started;*tick=spectrum_exit_tick;
 return -1; /* Normal input wait/switch follows, never bypassed by a tail. */
}
int main(void){
 global_settings.spectrum_enabled=true;current_tick=1000;
 assert(spectrum_set_visible(true));
 bool started=false;uint32_t tick=0;long button=ACTION_WPS_STOP;
 assert(pass(&button,&started,&tick)==-1);assert(started&&button==ACTION_NONE);
 assert(paused==1&&!capture.enabled&&!observer_registered);
 current_tick+=20;button=ACTION_WPS_STOP;assert(pass(&button,&started,&tick)==-1);
 button=ACTION_NONE;
 current_tick+=SPECTRUM_FADE_TICKS;assert(pass(&button,&started,&tick)==100);assert(exits==1);
 /* Recording's original exit action survives; it does not enter optional fade. */
 started=false;button=ACTION_WPS_REC;
 assert(pass(&button,&started,&tick)==108);assert(!started&&paused==1);
 /* A handled hardware action on the following pass ends the tail immediately. */
 audio_state=AUDIO_STATUS_PLAY;assert(spectrum_set_visible(true));
 started=false;button=ACTION_WPS_STOP;assert(pass(&button,&started,&tick)==-1);
 button=42;assert(pass(&button,&started,&tick)==142);
 assert(exits==3);puts("Stop tail bound, normal dispatch and recording exit passed");
}
'''
with tempfile.TemporaryDirectory(prefix='spectrum-exit-') as directory:
 tmp=Path(directory)
 for name in ('config','screen_access','kernel','thread','pcm','pcm_mixer','audio','settings','backlight','lcd','pcmbuf','system'):(tmp/(name+'.h')).write_text(STUB)
 c=tmp/'exit.c';exe=tmp/'exit';c.write_text(code.replace('SERVICE_SOURCE',str(CORE/'service.c')).replace('EXIT_BLOCK',block))
 subprocess.run(['cc','-std=c99','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I',str(tmp),'-I',str(CORE),str(c),str(CORE/'capture.c'),str(CORE/'analyzer.c'),str(CORE/'visualizer.c'),'-o',str(exe)],check=True)
 result=subprocess.check_output([str(exe)],text=True)
 print(json.dumps({'result':'passed','actual_patched_exit_gate':True,'checks':result.strip(),'sanitizers':['address','undefined']},indent=2))
