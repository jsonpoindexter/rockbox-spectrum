/* CPU-rendered feedback, stereo phosphor and flowing ribbons.
 * Original implementation, GPL-2.0-or-later. No GPU, floats or preset VM. */
#include "visualizer.h"
#include "tables.h"
#include <stdlib.h>
#include <string.h>

static int sine(unsigned phase)
{
    phase &= 1023;
    return (phase < 512 ? -spectrum_sin[phase] : spectrum_sin[phase - 512]) / 128;
}
static int clamp(int value, int low, int high)
{ return value < low ? low : value > high ? high : value; }
static uint32_t mix(uint32_t a, uint32_t b, unsigned amount)
{
    unsigned r = (((a >> 16) & 255) * (256-amount) + ((b >> 16) & 255) * amount) >> 8;
    unsigned g = (((a >> 8) & 255) * (256-amount) + ((b >> 8) & 255) * amount) >> 8;
    unsigned c = ((a & 255) * (256-amount) + (b & 255) * amount) >> 8;
    return (r << 16) | (g << 8) | c;
}
static void dot(struct visualization *v, int x, int y, uint32_t color)
{
    if (x >= 0 && y >= 0 && x < v->width && y < v->height)
        v->pixels[v->page][y*v->width+x] = color;
}
static void line(struct visualization *v, int x, int y, int ex, int ey, uint32_t color)
{
    /* Endpoints are bounded before Bresenham, also bounding loop cost. */
    x=clamp(x,0,v->width-1); ex=clamp(ex,0,v->width-1);
    y=clamp(y,0,v->height-1); ey=clamp(ey,0,v->height-1);
    int dx=abs(ex-x), dy=-abs(ey-y), sx=x<ex?1:-1, sy=y<ey?1:-1, error=dx+dy;
    for (;;) {
        dot(v,x,y,color);
        if (x==ex && y==ey) break;
        int twice=2*error;
        if (twice>=dy) { error+=dy; x+=sx; }
        if (twice<=dx) { error+=dx; y+=sy; }
    }
}
static void traces(struct visualization *v, const struct spectrum_frame *f,
                   unsigned phase, int gain, bool feedback)
{
    int cx=v->width/2, cy=v->height/2;
    int radius=(v->width<v->height?v->width:v->height)*(72+v->envelope[0]/3)/256;
    int spin=sine(phase/2), co=sine(phase/2+256);
    int boost=clamp(256+gain/16,64,544);
    for (int ring=0;ring<(feedback?3:2);ring++) {
        int px=0,py=0;
        uint32_t tint=mix(v->colors[1],v->colors[2],ring?210:24);
        tint=mix(v->colors[0],tint,clamp(v->envelope[1]+v->pulse,0,256));
        for (int i=0;i<=128;i++) {
            int index=i%128;
            int a=(i*1024/128)+(int)phase*(ring+1)/3;
            int wave=f->wave[index][ring%2]*boost/32768;
            int r=radius*(180+wave/2+sine(a*3+phase)/5)/256;
            if (ring) r=r*3/4;
            int x=sine(a)*r/256, y=sine(a+256)*r/256;
            if (!feedback) {
                x += f->wave[index][0]*radius*boost/32768/1024;
                y += f->wave[index][1]*radius*boost/32768/1024;
            }
            int rx=cx+(x*co-y*spin)/256, ry=cy+(x*spin+y*co)/256;
            if (i) line(v,px,py,rx,ry,tint);
            px=rx; py=ry;
        }
    }
}
static void ribbons(struct visualization *v, unsigned phase)
{
    uint32_t *out=v->pixels[v->page];
    int widths[3], slopes[3]; uint32_t tints[3];
    for (int band=0;band<3;band++) {
        widths[band]=2+v->height/12+v->envelope[band]/32;
        slopes[band]=(110+v->envelope[band]/2)*256/widths[band];
        tints[band]=mix(v->colors[1],v->colors[2],band*100);
    }
    for (int x=0;x<v->width;x++) {
        int centers[3];
        for (int band=0;band<3;band++)
            centers[band]=v->height/2 + sine(x*5+phase*(band+1)/3+band*310)*v->height/900
                + sine(x*11-phase/2+band*170)*v->height*(80+v->envelope[band])/180000;
        for (int y=0;y<v->height;y++) {
            uint32_t color=v->colors[0];
            for (int band=0;band<3;band++) {
                int distance=abs(y-centers[band]);
                int intensity=clamp((widths[band]-distance)*slopes[band]/256,0,220);
                intensity=intensity*v->envelope[band]/255;
                color=mix(color,tints[band],intensity);
            }
            out[y*v->width+x]=color;
        }
    }
}
uint32_t visualization_pixel(const struct visualization *v, int x, int y)
{ return v->pixels[v->page][y*v->width+x]; }

bool visualization_render(struct visualization *v, const struct spectrum_widget *w,
    const struct spectrum_frame *frame, bool fresh, bool fading, int gain,
    int selection, uint32_t generation, uint32_t now, unsigned hz, bool force)
{
    if (!hz) return false;
    if (selection<0 || selection>4) selection=0;
    bool reset=!v->started || v->owner!=w || v->generation!=generation ||
        v->width!=(w->width+1)/2 || v->height!=(w->height+1)/2 ||
        v->signature!=w->effect || memcmp(v->colors,w->visual_colors,sizeof(v->colors));
    if (reset) {
        memset(v,0,sizeof(*v)); v->started=true; v->owner=w; v->generation=generation;
        v->width=(w->width+1)/2; v->height=(w->height+1)/2;
        v->signature=w->effect; v->selection=selection;
        memcpy(v->colors,w->visual_colors,sizeof(v->colors));
        v->effect=selection>=1&&selection<=3?selection-1:w->effect;
        v->interval=4; v->tick=now;
        for (int i=0;i<VIS_PIXELS;i++) v->pixels[0][i]=v->pixels[1][i]=v->transition[i]=v->colors[0];
    }
    uint32_t dt=now-v->tick;
    bool setting_change=selection!=v->selection;
    if (!reset && !setting_change && dt<hz*v->interval/100) return force;
    if (dt>hz/5) dt=hz/5;
    v->tick=now;
    if (fresh) {
        v->fade_remaining=hz*3/4;
        v->cycle_ticks+=dt; v->frame_sequence=frame->sequence; v->capture_us=frame->capture_us;
    }
    if (setting_change) v->cycle_ticks=0;
    int wanted=selection>=1&&selection<=3?selection-1:
        selection==4?(int)(((unsigned)w->effect+v->cycle_ticks/(30*hz))%3):w->effect;
    v->selection=selection;
    if (wanted!=v->effect) {
        memcpy(v->transition,v->pixels[v->page],sizeof(v->transition));
        v->effect=wanted; v->transition_tick=now; v->crossing=true;
    }
    int alpha=(int)(dt*256000/(hz*70+dt*1000));
    for (int i=0;i<3;i++) {
        int target=fresh?clamp((frame->energy[i]+gain+60*256)/60,0,255):0;
        v->envelope[i]+=(target-v->envelope[i])*alpha/256;
        if (!fresh) v->envelope[i]=clamp(v->envelope[i]-(int)(dt*400/hz),0,255);
    }
    v->pulse=fresh?clamp(frame->onset/12,0,100):0;
    int count=v->width*v->height, previous=v->page;
    v->page=1-v->page;
    unsigned phase=(uint32_t)((uint64_t)now*120/hz)%6144;
    int decay=clamp((int)(dt*(v->effect==0?90:190)/hz),1,256);
    if (fading) {
        decay=v->fade_remaining?clamp((int)(dt*256/v->fade_remaining),0,256):256;
        v->fade_remaining=dt<v->fade_remaining?v->fade_remaining-dt:0;
        v->crossing=false;
    }
    if (v->effect==0) {
        int co=256-(int)(dt*120/hz), spin=sine(phase/3)*(int)dt/(int)hz/5;
        for (int y=0;y<v->height;y++) for (int x=0;x<v->width;x++) {
            /* Fold then rotate a fractional feedback coordinate. Bilinear
             * sampling prevents nearest-neighbor staircases accumulating. */
            int dx=abs(x-v->width/2),dy=abs(y-v->height/2);
            int fx=clamp(v->width*128+dx*co-dy*spin,0,(v->width-1)*256);
            int fy=clamp(v->height*128+dy*co+dx*spin,0,(v->height-1)*256);
            int sx=fx/256, sy=fy/256;
            int nx=sx+1<v->width?sx+1:sx, ny=sy+1<v->height?sy+1:sy;
            uint32_t *oldpage=v->pixels[previous];
            uint32_t top=mix(oldpage[sy*v->width+sx],oldpage[sy*v->width+nx],fx&255);
            uint32_t bottom=mix(oldpage[ny*v->width+sx],oldpage[ny*v->width+nx],fx&255);
            uint32_t old=mix(top,bottom,fy&255);
            v->pixels[v->page][y*v->width+x]=mix(old,v->colors[0],decay);
        }
    } else for (int i=0;i<count;i++)
        v->pixels[v->page][i]=mix(v->pixels[previous][i],v->colors[0],decay);
    if (fresh) {
        if (v->effect==2) ribbons(v,phase);
        else traces(v,frame,phase,gain,v->effect==0);
    }
    if (v->crossing && fresh) {
        uint32_t age=now-v->transition_tick, duration=(hz*3)/4;
        if (age>=duration) v->crossing=false;
        else for (int i=0;i<count;i++)
            v->pixels[v->page][i]=mix(v->transition[i],v->pixels[v->page][i],age*256/duration);
    }
    return true;
}
void visualization_cost(struct visualization *v, uint32_t usecs)
{
    /* Hysteresis: 8 expensive frames lower cadence; 100 healthy frames recover.
     * No catch-up frames or CPU-boost policy changes. */
    if (usecs>30000) { v->healthy_frames=0; if (++v->slow_frames>=8) {v->interval=8;v->slow_frames=0;} }
    else if (usecs<15000) {v->slow_frames=0;if (++v->healthy_frames>=100) {v->interval=4;v->healthy_frames=0;} }
    else {v->slow_frames=v->healthy_frames=0;}
}
