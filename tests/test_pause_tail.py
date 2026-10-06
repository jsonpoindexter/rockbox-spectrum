#!/usr/bin/env python3
"""Actual service pause/stop tails, resume, seek, observer gating and dot pixels."""
import json, subprocess, tempfile
from pathlib import Path
from test_service_render import STUB, CORE
HARNESS = r'''

#include "SERVICE_SOURCE"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static uint32_t pixels[240][320];
static unsigned foreground=LCD_RGBPACK(255,255,255), calls;
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
 struct screen screen={viewport,get_color,color,drawmode,rectangle,line,diagonal,mono};
 struct viewport vp;
 unsigned cases=0, intermediate=0;
 global_settings.spectrum_enabled=true; global_settings.spectrum_guides=true;
 for(int profile=0;profile<4;profile++)for(int lines=0;lines<2;lines++)
 for(int stopped=0;stopped<2;stopped++)for(int wrap=0;wrap<2;wrap++) {
  struct spectrum_widget w;
  assert(spectrum_widget_configure(&w,20,0,280,70,16,lines?"lines":"bars","classic",320,240));
  global_settings.spectrum_motion=profile;
  current_tick=wrap?UINT32_MAX-30:1000;
  audio_state=AUDIO_STATUS_PLAY;assert(spectrum_set_visible(true));
  latest_valid=true; latest.generation=capture.generation;latest.tick=current_tick;
  for(int i=0;i<32;i++) latest.db[i]=0;
  spectrum_draw(&screen,&w,&vp);
  for(int i=0;i<16;i++){w.level[i]=-(i%4)*12*256;w.peak[i]=0;}w.cache_valid=false;
  spectrum_draw(&screen,&w,&vp);
  audio_state=stopped?0:AUDIO_STATUS_PLAY|AUDIO_STATUS_PAUSE;
  if(stopped)spectrum_reset(); /* playback-thread buffer reset */
  uint32_t start=current_tick, windows=capture.windows;
  assert(spectrum_set_visible(true)); assert(!capture.enabled&&!observer_registered);
  int previous=w.level[0],peak=w.peak[0];
  for(unsigned tick=0;tick<=SPECTRUM_FADE_TICKS;tick+=2) {
   current_tick=start+tick; bool active=spectrum_set_visible(true);
   spectrum_draw(&screen,&w,&vp);
   assert(!capture.enabled&&!observer_registered&&capture.windows==windows);
   assert(w.level[0]<=previous&&w.peak[0]<=peak);
   if(tick>0&&tick<30)assert(w.peak[3]>w.level[3]); /* retained separate cap */
   if(tick==0)assert(w.level[0]==previous&&w.peak[0]==peak); /* no snap */
   if(tick>0&&tick<70){assert(w.level[0]>SPECTRUM_FLOOR);intermediate++;}
   if(tick>=76)assert(w.level[0]==SPECTRUM_FLOOR&&w.peak[0]==SPECTRUM_FLOOR);
   assert(active==(tick<SPECTRUM_FADE_TICKS));
   previous=w.level[0];peak=w.peak[0];
  }
  assert(!spectrum_set_visible(true));
  spectrum_draw(&screen,&w,&vp);
  /* Independent uniform dim-dot guide mask for every settled pixel.
   * One row/column of dots four pixels apart, with matching dim color.
   * Also forces full repaint to compare dirty restores. */
  if(!lines)for(int repaint=0;repaint<2;repaint++) {
   if(repaint){w.cache_valid=false;spectrum_draw(&screen,&w,&vp);}
   for(int y=0;y<70;y++)for(int x=0;x<280;x++) {
    int bar=0;while((bar+1)*280/16<=x)bar++;
    int local=x-bar*280/16;
    int width=(bar+1)*280/16-bar*280/16-1;
    bool dot=local<width && ((y<3||y>=67) ?
        ((y==0||y==68)&&local%4==0) :
        (bar>0&&local==0&&y%4==0));
    assert(pixels[y][20+x]==(dot?EXPECTED_GUIDE_WHITE:0));
   }
  }
  /* Restart from floor with only new-generation data. */
  audio_state=AUDIO_STATUS_PLAY;assert(spectrum_set_visible(true));
  assert(!get_frame(&latest));
  latest_valid=true;latest.generation=capture.generation;latest.tick=current_tick;
  for(int i=0;i<32;i++)latest.db[i]=0;
  current_tick+=2;spectrum_draw(&screen,&w,&vp);assert(w.level[0]>SPECTRUM_FLOOR);
  /* Resume midway preserves level until a new frame arrives; gain freezes. */
  w.level[0]=-10*256;w.peak[0]=0;w.visual_gain=256;
  w.auto_gain=global_settings.spectrum_auto_gain=true;
  audio_state=AUDIO_STATUS_PLAY|AUDIO_STATUS_PAUSE;assert(spectrum_set_visible(true));
  current_tick+=10;spectrum_draw(&screen,&w,&vp);int remaining=w.level[0];
  assert(w.visual_gain==256);
  audio_state=AUDIO_STATUS_PLAY;assert(spectrum_set_visible(true));
  spectrum_draw(&screen,&w,&vp);assert(w.level[0]==remaining&&w.visual_gain==256);
  /* Explicit seek still clears display; hidden/backlight states don't animate. */
  spectrum_reset();assert(spectrum_set_visible(true));spectrum_draw(&screen,&w,&vp);
  assert(w.level[0]==SPECTRUM_FLOOR);
  audio_state=AUDIO_STATUS_PLAY|AUDIO_STATUS_PAUSE;assert(spectrum_set_visible(true));
  backlight=false;assert(!spectrum_set_visible(true));assert(!capture.enabled);
  backlight=true;assert(!spectrum_set_visible(false));
  cases++;
 }
 /* A non-neutral theme must keep its hue while dimming only guides. */
 foreground=LCD_RGBPACK(64,128,192);
 unsigned original=foreground;
 struct spectrum_widget tint;
 assert(spectrum_widget_configure(&tint,20,0,280,70,16,"bars","mono",320,240));
 audio_state=AUDIO_STATUS_PLAY;latest_valid=false;current_tick+=100;
 assert(spectrum_set_visible(true));spectrum_draw(&screen,&tint,&vp);
 assert(pixels[4][37]==EXPECTED_GUIDE_TINT);
 assert(pixels[0][20]==EXPECTED_GUIDE_TINT&&pixels[68][20]==EXPECTED_GUIDE_TINT);
 assert(pixels[2][22]==0&&foreground==original);
 global_settings.spectrum_guides=false;spectrum_draw(&screen,&tint,&vp);
 assert(pixels[4][37]==0&&foreground==original);
 /* Independently check every pixel for custom dotted/solid/off guides,
  * borders and pitch. Run in both actual display color formats. */
 global_settings.spectrum_guides=true;global_settings.spectrum_auto_gain=false;
 for(int style=0;style<3;style++)for(int border=0;border<3;border++) {
  struct spectrum_widget themed;
  assert(spectrum_widget_configure(&themed,20,0,280,70,16,"bars","mono",320,240));
  assert(spectrum_widget_style(&themed,style==0?"dots":style==1?"solid":"off",
      "306090",3,border==0?"lanes":border==1?"frame":"baseline","00ff80","ff8040",2));
  latest_valid=false;spectrum_draw(&screen,&themed,&vp);
  for(int y=0;y<70;y++)for(int x=0;x<280;x++) {
   int bar=0;while((bar+1)*280/16<=x)bar++;
   int local=x-bar*280/16;
   int width=(bar+1)*280/16-bar*280/16-1;
   bool horizontal=local<width && (y==68 || (y==0 && border!=2)) &&
       (style==1 || local%3==0);
   bool vertical=border!=2 && y>=3 && y<67 &&
       ((local==0 && (bar>0||border==1)) || (border==1&&bar==15&&local==width-1)) &&
       (style==1 || y%3==0);
   bool guide=style!=2 && (horizontal||vertical);
   assert(pixels[y][20+x]==(guide?LCD_RGBPACK(48,96,144):0));
  }
  assert(foreground==original);
  if(style!=2) {
   global_settings.spectrum_motion=SPECTRUM_MOTION_CLASSIC;
   latest_valid=true;latest.generation=capture.generation;
   current_tick+=2;latest.tick=current_tick;
   for(int i=0;i<32;i++)latest.db[i]=0;
   spectrum_draw(&screen,&themed,&vp);
   assert(pixels[5][23]==LCD_RGBPACK(0,255,128));
   assert(pixels[3][23]==LCD_RGBPACK(255,128,64));
   assert(foreground==original);
  }
 }
 fprintf(stderr,"tail cases=%u intermediate frames=%u; native guide colors/toggle and 9 theme style masks passed\n",cases,intermediate);
 return 0;
}
'''
# Golden colors check both the host RGB888 representation and ipod6g RGB565.
STUB_565 = STUB.replace('#define LCD_RGBPACK(r,g,b) (((r)<<16)|((g)<<8)|(b))',
    '#define LCD_RGBPACK(r,g,b) ((((r)>>3)<<11)|(((g)>>2)<<5)|((b)>>3))').replace(
    '#define RGB_UNPACK_RED(c) (((c)>>16)&255)',
    '#define RGB_UNPACK_RED(c) ((((c)>>8)&0xf8)|(((c)>>13)&7))').replace(
    '#define RGB_UNPACK_GREEN(c) (((c)>>8)&255)',
    '#define RGB_UNPACK_GREEN(c) ((((c)>>3)&0xfc)|(((c)>>9)&3))').replace(
    '#define RGB_UNPACK_BLUE(c) ((c)&255)',
    '#define RGB_UNPACK_BLUE(c) ((((c)<<3)&0xf8)|(((c)>>2)&7))')
results=[]
for label,stub,white,tint in [('RGB888',STUB,'0xbfbfbf','0x306090'),
                              ('RGB565',STUB_565,'0xbdf7','0x3312')]:
 with tempfile.TemporaryDirectory(prefix='spectrum-tail-') as directory:
  tmp=Path(directory)
  stub += '\n#define EXPECTED_GUIDE_WHITE '+white+'\n#define EXPECTED_GUIDE_TINT '+tint+'\n'
  for name in ('config','screen_access','kernel','thread','pcm','pcm_mixer','audio','settings','backlight','lcd','pcmbuf','system'):
   (tmp/(name+'.h')).write_text(stub)
  c=tmp/'tail.c';c.write_text(HARNESS.replace('SERVICE_SOURCE',str(CORE/'service.c')));exe=tmp/'tail'
  subprocess.run(['cc','-std=c99','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(tmp),'-I',str(CORE),str(c),str(CORE/'capture.c'),str(CORE/'analyzer.c'),'-o',str(exe)],check=True)
  run=subprocess.run([str(exe)],capture_output=True,text=True)
  if run.returncode:raise RuntimeError(run.stderr)
  results.append({'pixel_format':label,'checks':run.stderr.strip()})
print(json.dumps({'result':'passed','formats':results,'sanitizers':['address','undefined'],'actual_service':True,'hardware_tests':'not performed'},indent=2))
