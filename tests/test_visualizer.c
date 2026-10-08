/* Rendering invariants, music response, lifecycle and overload regression. */
#include "visualizer.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct visualization engine;
static struct spectrum_widget widget;
static struct spectrum_frame frame;
static uint64_t hash(void) {
    uint64_t value=1469598103934665603ULL;
    for(int y=0;y<engine.height;y++) for(int x=0;x<engine.width;x++) {
        value^=visualization_pixel(&engine,x,y);value*=1099511628211ULL;
    }
    return value;
}
int main(void) {
    assert(sizeof(engine)<256*1024);
    assert(!visualization_widget_configure(&widget,0,0,321,240,"feedback","000000","00ff88","ff44bb",320,240));
    assert(!visualization_widget_configure(&widget,0,0,320,240,"invalid","000000","00ff88","ff44bb",320,240));
    assert(!visualization_widget_configure(&widget,0,0,320,240,"feedback","auto","00ff88","ff44bb",320,240));
    uint64_t effects[3]; unsigned rendered=0;
    for(int effect=0;effect<3;effect++) {
        assert(visualization_widget_configure(&widget,0,0,320,240,"feedback","071019","44ffaa","ff44bb",320,240));
        widget.effect=effect; memset(&engine,0,sizeof(engine)); memset(&frame,0,sizeof(frame));
        for(int i=0;i<128;i++) {frame.wave[i][0]=(i-64)*450;frame.wave[i][1]=(64-i)*350;}
        for(unsigned n=0;n<160;n++) {
            for(int i=0;i<3;i++) frame.energy[i]=-(12+(n+i)%22)*256;
            frame.onset=n%10==0?4096:0;
            assert(visualization_render(&engine,&widget,&frame,true,false,0,0,1,n*4+1,100,false));
            rendered++;
        }
        effects[effect]=hash();
        assert(!visualization_render(&engine,&widget,&frame,true,false,0,0,1,638,100,false));
        assert(visualization_render(&engine,&widget,&frame,true,false,0,0,1,638,100,true));
        assert(hash()==effects[effect]); /* forced repaint does not step twice */
        visualization_render(&engine,&widget,&frame,false,false,0,0,1,641,100,false);
        bool visible=false;
        for(int y=0;y<120;y++)for(int x=0;x<160;x++)if(visualization_pixel(&engine,x,y)!=0x071019)visible=true;
        assert(visible); /* stale data decays rather than abruptly blanking */
        visualization_render(&engine,&widget,&frame,true,false,0,0,1,645,100,false);
        for(unsigned tick=649;tick<729;tick+=4)
            visualization_render(&engine,&widget,&frame,false,true,0,0,1,tick,100,false);
        assert(hash()!=effects[effect]);
        for(int y=0;y<120;y++)for(int x=0;x<160;x++)assert(visualization_pixel(&engine,x,y)==0x071019);
        visualization_render(&engine,&widget,&frame,false,false,0,0,2,733,100,true);
        for(int i=0;i<8;i++)visualization_cost(&engine,35000);
        assert(engine.interval==8);
        for(int i=0;i<100;i++)visualization_cost(&engine,10000);
        assert(engine.interval==4);
    }
    assert(effects[0]!=effects[1] && effects[1]!=effects[2] && effects[0]!=effects[2]);
    /* Quiet input, odd viewport geometry, manual selection, auto transitions,
       generation reset and tick rollover all remain bounded under sanitizers. */
    assert(visualization_widget_configure(&widget,3,5,317,235,"ribbons","f6f5f4","3584e4","b47bda",320,240));
    memset(&engine,0,sizeof(engine));
    for(unsigned n=0;n<2000;n++) {
        for(int i=0;i<3;i++)frame.energy[i]=(n%200<100?-60:-6)*256;
        visualization_render(&engine,&widget,&frame,true,false,n%2?4608:0,4,3,n*4+1,100,false);
        assert(engine.effect>=0&&engine.effect<3);rendered++;
    }
    assert(engine.effect==1); /* signature2, then0, then1 at60s */
    visualization_render(&engine,&widget,&frame,true,false,0,2,3,8005,100,false);
    assert(engine.effect==1 && engine.selection==2);
    visualization_render(&engine,&widget,&frame,true,false,0,1,4,UINT32_MAX-5,100,false);
    visualization_render(&engine,&widget,&frame,true,false,0,1,4,3,100,false);
    assert(engine.effect==0);
    printf("%u music animation frames, distinct effects, fade, cadence, selection, bounds and rollover passed\n",rendered);
}
