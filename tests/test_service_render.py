#!/usr/bin/env python3
"""Compare multi-frame dirty pixels against forced-full independent per-row bars.
Also exercises stale frames, generation, color, repaint, pause and audio pressure.
"""
import hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'overlay/apps/gui/spectrum'
STUB = r'''
#ifndef SPEC_HOST_STUB
#define SPEC_HOST_STUB
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#define HZ 100
#define DEFAULT_STACK_SIZE 1024
#define TIMEOUT_BLOCK -1
#define AUDIO_STATUS_PLAY 1
#define AUDIO_STATUS_PAUSE 2
#define IF_PRIO(...)
#define IF_COP(...)
#define VP_FLAG_VP_SET_CLEAN 0
#define DRMODE_SOLID 0
#define DRMODE_INVERSEVID 1
#define LCD_RGBPACK(r,g,b) (((r)<<16)|((g)<<8)|(b))
#define RGB_UNPACK_RED(c) (((c)>>16)&255)
#define RGB_UNPACK_GREEN(c) (((c)>>8)&255)
#define RGB_UNPACK_BLUE(c) ((c)&255)
struct viewport {int unused;};
typedef uint32_t fb_data;
struct screen {
 void (*set_viewport_ex)(struct viewport *,int);
 unsigned (*get_foreground)(void);
 void (*set_foreground)(unsigned);
 void (*set_drawmode)(int);
 void (*fillrect)(int,int,int,int);
 void (*hline)(int,int,int);
 void (*drawline)(int,int,int,int);
 void (*mono_bitmap_part)(const unsigned char *,int,int,int,int,int,int,int);
 void (*bitmap_part)(const fb_data *,int,int,int,int,int,int,int);
};
struct semaphore {int unused;};
struct {bool spectrum_enabled; int spectrum_motion; bool spectrum_auto_gain; bool spectrum_guides; int visualization_effect;} global_settings;
uint32_t current_tick;
static bool lowdata, backlight=true;
static bool observer_registered;
static int audio_state=AUDIO_STATUS_PLAY;
static inline void pcm_play_lock(void) {}
static inline void pcm_play_unlock(void) {}
static inline void semaphore_release(struct semaphore *s) {(void)s;}
static inline void semaphore_wait(struct semaphore *s,int t) {(void)s;(void)t;}
static inline void semaphore_init(struct semaphore *s,int a,int b) {(void)s;(void)a;(void)b;}
static inline unsigned long create_thread(void (*f)(void),long *s,size_t n,int a,const char *b) {(void)f;(void)s;(void)n;(void)a;(void)b;return 1;}
static inline void yield(void) {}
static inline int audio_status(void) {return audio_state;}
static inline bool pcmbuf_is_lowdata(void) {return lowdata;}
static inline bool lcd_active(void) {return true;}
static inline bool is_backlight_on(bool b) {(void)b;return backlight;}
static inline void mixer_set_playback_observer(void (*f)(const int16_t *,unsigned,unsigned)) {observer_registered=f!=NULL;}
#endif
'''
HARNESS = r'''
#include "SERVICE_SOURCE"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static uint32_t pixels[240][320];
static unsigned foreground=0xffffff, calls;
static int mode;
static void viewport(struct viewport *v,int f) {(void)v;(void)f;}
static unsigned get_color(void) {return foreground;}
static void color(unsigned c) {foreground=c;}
static void drawmode(int m) {mode=m;}
static void rectangle(int x,int y,int w,int h) {
 assert(x>=0&&y>=0&&w>=0&&h>=0&&x+w<=320&&y+h<=240);
 calls++;
 for(int row=y;row<y+h;row++)for(int col=x;col<x+w;col++)
  pixels[row][col]=(mode&DRMODE_INVERSEVID)?0:foreground;
}
static void line(int x,int end,int y) {
 assert(x>=0&&end>=x&&end<320&&y>=0&&y<240);calls++;
 for(int col=x;col<=end;col++)pixels[y][col]=foreground;
}
static void diagonal(int x,int y,int end,int bottom) {
 int dx=abs(end-x),dy=-abs(bottom-y),sx=x<end?1:-1,sy=y<bottom?1:-1,e=dx+dy;
 calls++;
 for(;;) {assert(x>=0&&x<320&&y>=0&&y<240);pixels[y][x]=foreground;if(x==end&&y==bottom)break;int t=2*e;if(t>=dy){e+=dy;x+=sx;}if(t<=dx){e+=dx;y+=sy;}}
}
static void mono(const unsigned char *src,int sx,int sy,int stride,int x,int y,int w,int h) {
 assert(x>=0&&y>=0&&w>=0&&h>=0&&x+w<=320&&y+h<=240);calls++;
 for(int row=0;row<h;row++)for(int col=0;col<w;col++) {
  unsigned byte=src[((sy+row)/8)*stride+sx+col];
  pixels[y+row][x+col]=(byte&(1u<<((sy+row)%8)))?foreground:0;
 }
}
int main(void) {
 struct screen screen={viewport,get_color,color,drawmode,rectangle,line,diagonal,mono,NULL};
 struct viewport vp;
 int heights[]={2,3,7,30,59,240};
 initialized=latest_valid=capture.enabled=true;capture.generation=latest.generation=1;
 unsigned cases=0,unchanged=0;
 for(int h=0;h<6;h++)for(int bands=8;bands<=32;bands*=2)for(int classic=0;classic<2;classic++)for(int lines=0;lines<2;lines++)for(int style=0;style<4;style++) {
  memset(pixels,0,sizeof(pixels));foreground=0xffffff;
  struct spectrum_widget w;
  assert(spectrum_widget_configure(&w,20,0,280,heights[h],bands,lines?"lines":"bars",classic?"classic":"mono",320,240));
  if(style) assert(spectrum_widget_style(&w,style==3?"off":style==2?"solid":"dots",
      "306090",style==1?7:16,style==2?"frame":"baseline","00ff80","ff8040",style));
  for(unsigned n=0;n<60;n++) {
   current_tick=n*2+1; latest.tick=current_tick; latest.sequence=n+1;
   latest.capture_us=spectrum_clock_us();
   for(int i=0;i<32;i++) latest.db[i]=n<10?0:n<20?-72*256:-(int)((i*173+n*787)%18000);
   if(n==25)foreground=0x4080c0;
   if(n==30) latest.tick=current_tick-11; /* stale decays, not frozen */
   latest_valid=n!=35; /* missing frame decays */
   if(n==40) {capture.generation++;latest.generation=capture.generation;}
   global_settings.spectrum_motion=(n/15)%4;
   global_settings.spectrum_auto_gain=(n>=20 && n<50);
   global_settings.spectrum_guides=(n>=10 && n<55);
   if(n==45) {memset(pixels,0,sizeof(pixels));w.cache_valid=false;} /* ordinary skin repaint */
#ifdef FORCEFULL
   w.cache_valid=false;
#endif
   bool changed=spectrum_draw(&screen,&w,&vp);
   if(!changed)unchanged++;
   uint64_t hash=1469598103934665603ULL;
   for(unsigned y=0;y<240;y++)for(unsigned x=0;x<320;x++) {hash^=pixels[y][x];hash*=1099511628211ULL;}
   assert(fwrite(&hash,1,sizeof(hash),stdout)==sizeof(hash));cases++;
  }
 }
 worker_id=1; global_settings.spectrum_enabled=true;
 assert(spectrum_set_visible(true));
 lowdata=true; assert(!spectrum_set_visible(true)); assert(!capture.enabled);
 lowdata=false; current_tick=1000; assert(!spectrum_set_visible(true));
 current_tick=1199; assert(!spectrum_set_visible(true));
 current_tick=1200; assert(spectrum_set_visible(true));
 audio_state=AUDIO_STATUS_PLAY|AUDIO_STATUS_PAUSE; assert(spectrum_set_visible(true)); assert(!capture.enabled && !observer_registered);
 current_tick+=SPECTRUM_FADE_TICKS; assert(!spectrum_set_visible(true));
 audio_state=AUDIO_STATUS_PLAY; assert(spectrum_set_visible(true));
 assert(!spectrum_set_visible(false));
 fprintf(stderr,"%u %u %u\n",cases,calls,unchanged);
 return 0;
}
'''
def main():
 with tempfile.TemporaryDirectory(prefix='spectrum-render-') as directory:
  tmp=Path(directory)
  for name in ('config','screen_access','kernel','thread','pcm','pcm_mixer','audio','settings','backlight','lcd','pcmbuf','system'):
   (tmp/(name+'.h')).write_text(STUB)
  baseline=(CORE/'service.c').read_text()
  start=baseline.index('            /* Paint at most three color segments')
  end=baseline.index('            screen->set_foreground(peak_color);',start)
  reference="""            for (int row=0;row<h;row++) {
                unsigned color=bar_color;
                if(w->classic && w->bar_rgb == SPECTRUM_COLOR_AUTO) color=row*100>=plot_height*85?LCD_RGBPACK(255,48,32):
                    row*100>=plot_height*65?LCD_RGBPACK(255,220,32):LCD_RGBPACK(0,255,64);
                screen->set_foreground(color);
                screen->hline(draw_x,draw_x+draw_width-1,base_y-row);
            }
"""
  (tmp/'reference.c').write_text(baseline[:start]+reference+baseline[end:])
  results=[]
  for name,source,flags in [('full_per_row',tmp/'reference.c',['-DFORCEFULL']),('full_batched',CORE/'service.c',['-DFORCEFULL']),('dirty',CORE/'service.c',[])]:
   c=tmp/(name+'.c');c.write_text(HARNESS.replace('SERVICE_SOURCE',str(source)));exe=tmp/name
   subprocess.run(['cc','-std=c99','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I',str(tmp),'-I',str(CORE),*flags,str(c),str(CORE/'capture.c'),str(CORE/'analyzer.c'),str(CORE/'visualizer.c'),'-o',str(exe)],check=True)
   run=subprocess.run([str(exe)],capture_output=True)
   if run.returncode:raise RuntimeError(run.stderr.decode())
   count,calls,unchanged=map(int,run.stderr.split());assert len(run.stdout)==count*8
   # Extract style0 from each four-style group. This is the unchanged fast9
   # 4,320-frame fixture, whose checksum predates the styling implementation.
   defaults=b''.join(run.stdout[i:i+60*8] for i in range(0,len(run.stdout),4*60*8))
   assert hashlib.sha256(defaults).hexdigest()=='e8d07ba6f95381ca02a6f1c1712e85041a04d6a791fc18acac4433aa6e4d247a'

   results.append({'renderer':name,'frames':count,'drawing_calls':calls,'unchanged_draws':unchanged,'pixel_checksums_sha256':hashlib.sha256(run.stdout).hexdigest()})
  assert len({x['pixel_checksums_sha256'] for x in results})==1,results
  assert results[2]['drawing_calls']<results[0]['drawing_calls']
  assert results[2]['unchanged_draws']>0
  print(json.dumps({'result':'passed','sanitizers':['address','undefined'],'comparisons':results,'device_timing':'not measured'},indent=2))
if __name__=='__main__':main()
