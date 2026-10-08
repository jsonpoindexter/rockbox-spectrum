#!/usr/bin/env python3
"""Exercise actual service compositing and gating with an odd-sized viewport."""
import subprocess
import tempfile
from pathlib import Path
from test_service_render import STUB, HARNESS, CORE
prefix = HARNESS[:HARNESS.index('int main(void)')]
body = r'''
static void bitmap(const fb_data *src,int sx,int sy,int stride,int x,int y,int w,int h) {
 assert(x>=0&&y>=0&&x+w<=320&&y+h<=240&&h<=2);
 for(int row=0;row<h;row++)for(int col=0;col<w;col++)pixels[y+row][x+col]=src[(sy+row)*stride+sx+col];
}
int main(void) {
 struct screen screen={viewport,get_color,color,drawmode,rectangle,line,diagonal,mono,bitmap};
 struct viewport vp;struct spectrum_widget w;
 assert(visualization_widget_configure(&w,9,11,301,219,"ribbons","071019","44ffaa","ff44bb",320,240));
 initialized=latest_valid=true;worker_id=1;global_settings.spectrum_enabled=true;
 current_tick=1000;assert(spectrum_set_visible(true));
 for(int y=0;y<240;y++)for(int x=0;x<320;x++)pixels[y][x]=0x123456;
 for(unsigned n=0;n<100;n++) {
  current_tick=1000+n*4;latest.generation=capture.generation;latest.tick=current_tick;latest.sequence=n+1;
  latest.capture_us=spectrum_clock_us();
  for(int i=0;i<32;i++)latest.db[i]=-10*256;
  for(int i=0;i<3;i++)latest.energy[i]=-10*256;
  if(n==30)global_settings.visualization_effect=1;
  if(n==60)global_settings.visualization_effect=2;
  spectrum_draw(&screen,&w,&vp);spectrum_record_submission(1000);
  for(int y=0;y<240;y++)for(int x=0;x<320;x++) {
   if(x<9||x>=310||y<11||y>=230)assert(pixels[y][x]==0x123456);
   else assert(pixels[y][x]==theme_rgb(visualization_pixel(&visual,(x-9)/2,(y-11)/2)));
  }
 }
 audio_state=AUDIO_STATUS_PLAY|AUDIO_STATUS_PAUSE;
 assert(spectrum_set_visible(true));assert(!observer_registered);
 for(int n=0;n<20;n++){current_tick+=4;spectrum_set_visible(true);spectrum_draw(&screen,&w,&vp);}
 for(int y=11;y<230;y++)for(int x=9;x<310;x++)assert(pixels[y][x]==theme_rgb(0x071019));
 audio_state=AUDIO_STATUS_PLAY;assert(spectrum_set_visible(true));
 lowdata=true;assert(!spectrum_set_visible(true));assert(!capture.enabled);
 backlight=false;assert(!spectrum_set_visible(true));
 puts("Actual service: viewport isolation, scaling, settings, pause, pressure and backlight passed");
}
'''
with tempfile.TemporaryDirectory(prefix='visual-service-') as directory:
    root = Path(directory)
    for name in ('config','screen_access','kernel','thread','pcm','pcm_mixer','audio','settings','backlight','lcd','pcmbuf','system'):
        (root / (name + '.h')).write_text(STUB)
    src = root / 'test.c'
    src.write_text((prefix + body).replace('SERVICE_SOURCE', str(CORE / 'service.c')))
    exe = root / 'test'
    subprocess.run(['cc', '-std=c99', '-O1', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I', str(root), '-I', str(CORE),
        str(src), str(CORE / 'capture.c'), str(CORE / 'analyzer.c'), str(CORE / 'visualizer.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
