/* GPL-2.0-or-later. Functional tests, run with ASan + UBSan. */
#include "analyzer.h"
#include "capture.h"
#include "widget.h"
#include "widget_fast3.h"
#include <assert.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static struct spectrum_analyzer analyzer;
static int16_t pcm[SPECTRUM_SAMPLES * 2];
static struct spectrum_frame frame;
static void tone(int amplitude, int polarity, int bin)
{
    for (int i=0;i<SPECTRUM_SAMPLES;i++) {
        int16_t sample = lround(amplitude * sin(2 * 3.141592653589793 * bin * i / SPECTRUM_SAMPLES));
        pcm[2*i]=sample; pcm[2*i+1]=polarity == 0 ? 0 : sample*polarity;
    }
}
static int maximum(void) {
    int v=SPECTRUM_FLOOR;
    for(int i=0;i<32;i++) if(frame.db[i]>v) v=frame.db[i];
    return v;
}
static void analyze(unsigned rate) { spectrum_analyze(&analyzer, pcm, rate, &frame); }
static void test_analysis(void)
{
    memset(pcm,0,sizeof(pcm)); analyze(44100); assert(maximum()==SPECTRUM_FLOOR);
    for(int i=0;i<2048;i++)pcm[i]=INT16_MIN;
    analyze(48000);assert(maximum()==SPECTRUM_FLOOR); /* DC removed */
    tone(32760,1,23); analyze(44100); assert(abs(maximum()) < 32);
    int16_t in_phase[32];memcpy(in_phase,frame.db,sizeof(in_phase));
    tone(32760,-1,23);analyze(44100);
    for(int i=0;i<32;i++) assert(abs(frame.db[i]-in_phase[i])<8);
    tone(16380,1,23);analyze(44100);assert(abs(maximum()+1541)<24); /* -6.02dB */
    tone(32760,0,23);analyze(44100);assert(abs(maximum()+771)<24); /* -3.01dB */
    for(int i=0;i<2048;i++) pcm[i]=(i/2%2) ? INT16_MAX: INT16_MIN;
    analyze(48000);
    for(int i=0;i<32;i++) assert(frame.db[i]>=SPECTRUM_FLOOR && frame.db[i]<=0);
    for(int i=0;i<SPECTRUM_SAMPLES;i++) {
        pcm[2*i]=i==511?INT16_MIN:30000;
        pcm[2*i+1]=i==512?INT16_MIN:32000;
    }
    analyze(44100); /* large DC offsets/near full-range window values */
    for(int i=0;i<32;i++)assert(frame.db[i]>=SPECTRUM_FLOOR&&frame.db[i]<=0);
    unsigned seed=123;
    for(int n=0;n<200;n++) {
        for(int i=0;i<2048;i++) {seed=1664525*seed+1013904223;pcm[i]=(int16_t)(seed>>16);}
        analyze(n%2?44100:48000);
        for(int i=0;i<32;i++) assert(frame.db[i]>=SPECTRUM_FLOOR && frame.db[i]<=0);
    }
}
static void test_visual_features(void)
{
    frame.generation=42;memset(pcm,0,sizeof(pcm));analyze(44100);
    for(int i=0;i<3;i++)assert(frame.energy[i]==SPECTRUM_FLOOR);
    for(int i=0;i<128;i++)for(int c=0;c<2;c++)assert(frame.wave[i][c]==0);
    tone(20000,-1,8);analyze(44100);assert(frame.onset>0);
    for(int i=0;i<128;i++)assert(abs(frame.wave[i][0]+frame.wave[i][1])<=1);
    analyze(44100);assert(frame.onset==0);
    frame.generation++;tone(30000,1,80);analyze(44100);assert(frame.onset==0);
    for(int i=0;i<2048;i++)pcm[i]=30000;
    analyze(44100);for(int i=0;i<128;i++)assert(frame.wave[i][0]==0&&frame.wave[i][1]==0);
}
static void test_capture(void)
{
    struct spectrum_capture c;spectrum_capture_init(&c,5);
    assert(!spectrum_capture_submit(&c,pcm,1024,44100,1));
    spectrum_capture_enable(&c,true);
    for(int i=0;i<2048;i++)pcm[i]=i;
    for(unsigned chunk=0;chunk<4;chunk++) {
        bool ready=spectrum_capture_submit(&c,pcm+chunk*512,256,44100,1+chunk);
        assert(ready==(chunk==3));
    }
    int a=spectrum_capture_acquire(&c);assert(a>=0);
    assert(!memcmp(c.slots[a].pcm,pcm,sizeof(pcm)));
    uint32_t generation=c.slots[a].generation;
    memset(pcm,0,sizeof(pcm)); /* borrowed source modified; owned window unchanged */
    assert(c.slots[a].pcm[100]==100);
    assert(spectrum_capture_submit(&c,pcm,1024,44100,9));
    assert(spectrum_capture_submit(&c,pcm,1024,44100,14));assert(c.drops==1);
    spectrum_capture_reset(&c);assert(c.generation!=generation);
    assert(c.slots[a].state==SPEC_READING && c.slots[a].pcm[100]==100);
    spectrum_capture_release(&c,a);
    assert(spectrum_capture_submit(&c,pcm,1024,48000,12));
    int b=spectrum_capture_acquire(&c);assert(b>=0 && c.slots[b].rate==48000);
    spectrum_capture_release(&c,b);
    spectrum_capture_enable(&c,false);assert(!spectrum_capture_submit(&c,pcm,1024,48000,20));
    spectrum_capture_enable(&c,true);
    assert(spectrum_capture_submit(&c,pcm,1024,48000,UINT32_MAX-2));
    spectrum_capture_release(&c,spectrum_capture_acquire(&c));
    assert(!spectrum_capture_submit(&c,pcm,1024,48000,UINT32_MAX));
    assert(spectrum_capture_submit(&c,pcm,1024,48000,3)); /* wrapping clock */
    spectrum_capture_reset(&c);
    assert(spectrum_capture_submit(&c,pcm,1024,48000,UINT32_MAX-4));
    spectrum_capture_release(&c,spectrum_capture_acquire(&c));
    assert(!spectrum_capture_submit(&c,pcm,1024,48000,UINT32_MAX-3)); /* deadline zero */
    assert(spectrum_capture_submit(&c,pcm,1024,48000,0));
    spectrum_capture_reset(&c);
    assert(!spectrum_capture_submit(&c,pcm,512,44100,4));
    uint32_t old_generation=c.generation;
    for(int i=0;i<2048;i++)pcm[i]=7;
    assert(spectrum_capture_submit(&c,pcm,1024,48000,5));
    b=spectrum_capture_acquire(&c);
    assert(c.generation!=old_generation && c.slots[b].rate==48000);
    for(int i=0;i<2048;i++)assert(c.slots[b].pcm[i]==7);
    spectrum_capture_release(&c,b);
    spectrum_capture_reset(&c);
    /* newest wins and the older READY slot is reclaimed */
    spectrum_capture_release(&c,spectrum_capture_acquire(&c));
    assert(spectrum_capture_submit(&c,pcm,1024,48000,8));
    assert(spectrum_capture_submit(&c,pcm,1024,48000,13));
    b=spectrum_capture_acquire(&c);assert(b>=0 && c.slots[b].tick==13);
    assert(c.slots[1-b].state==SPEC_FREE);
}
static void test_rolling(void)
{
    struct spectrum_capture c; spectrum_capture_init(&c,2);
    spectrum_capture_enable(&c,true);
    int16_t input[6000], original[6000], expected[2048];
    for (int i=0;i<6000;i++) input[i]=(int16_t)i;
    memcpy(original,input,sizeof(input));
    unsigned sizes[]={13,257,119,401,234,17,256,511,1,100,2000};
    unsigned total=0;
    for(unsigned n=0;n<sizeof(sizes)/sizeof(sizes[0]);n++) {
        unsigned size=sizes[n];
        /* Restart the source pattern but retain a chronological reference. */
        for(unsigned j=0;j<size;j++) {
            memmove(expected,expected+2,(2048-2)*sizeof(*expected));
            expected[2046]=input[2*j];expected[2047]=input[2*j+1];
        }
        total+=size;
        bool ready=spectrum_capture_submit(&c,input,size,44100,n*2);
        assert(ready==(total>=1024));
        if(ready) {
            int slot=spectrum_capture_acquire(&c);assert(slot>=0);
            assert(!memcmp(expected,c.slots[slot].pcm,sizeof(expected)));
            spectrum_capture_release(&c,slot);
        }
        assert(!memcmp(input,original,sizeof(input)));
    }
    assert(spectrum_capture_submit(&c,input,1024,44100,100));
    int reading=spectrum_capture_acquire(&c); int16_t held[2048];
    memcpy(held,c.slots[reading].pcm,sizeof(held));
    for(unsigned tick=102;tick<120;tick+=2)
        assert(spectrum_capture_submit(&c,input+2,1024,44100,tick));
    assert(!memcmp(held,c.slots[reading].pcm,sizeof(held)));
    int newest=spectrum_capture_acquire(&c);assert(newest!=reading && c.slots[newest].tick==118);
    assert(!spectrum_capture_submit(&c,input,1024,44100,120)); /* both reading */
    spectrum_capture_reset(&c);
    assert(!memcmp(held,c.slots[reading].pcm,sizeof(held)));
    spectrum_capture_release(&c,reading);spectrum_capture_release(&c,newest);
    assert(!spectrum_capture_submit(&c,input,1,48000,122)); /* must refill after rate change */
    assert(!spectrum_capture_submit(&c,NULL,1024,48000,124));
    assert(!spectrum_capture_submit(&c,input,1024,0,124));
}
static void test_widget(void)
{
    struct spectrum_widget w;
    assert(spectrum_widget_configure(&w,0,0,280,30,16,"bars","mono",280,30));
    for(int i=0;i<32;i++)assert(w.level[i]==SPECTRUM_FLOOR && w.peak[i]==SPECTRUM_FLOOR);
    assert(spectrum_widget_configure(&w,1,2,64,12,32,"lines","classic",100,30));
    assert(!spectrum_widget_configure(&w,-1,0,280,30,16,"bars","mono",280,30));
    assert(!spectrum_widget_configure(&w,0,0,280,31,16,"bars","mono",280,30));
    assert(!spectrum_widget_configure(&w,0,0,31,30,16,"bars","mono",280,30));
    assert(!spectrum_widget_configure(&w,0,0,280,30,12,"bars","mono",280,30));
    assert(!spectrum_widget_configure(&w,INT_MAX,0,280,30,16,"bars","mono",280,30));
    assert(!spectrum_widget_configure(&w,0,0,280,30,16,"milkdrop","mono",280,30));
    assert(!spectrum_widget_configure(&w,0,0,280,30,16,"bars","rainbow",280,30));
}
static void test_presentation(void)
{
    struct spectrum_widget w, split;
    assert(spectrum_widget_configure(&w,0,0,280,70,16,"bars","classic",280,70));
    split = w;
    spectrum_widget_step(&w,0,0,2,2,100);
    assert(w.level[0] > -36*256 && w.level[0] < -20*256); /* quick onset, no full jump */
    spectrum_widget_step(&w,0,0,3,5,100);
    assert(w.level[0] > -8*256 && w.level[0] < 0); /* >90% height by50ms */
    for(unsigned tick=1;tick<=5;tick++) spectrum_widget_step(&split,0,0,1,tick,100);
    assert(w.level[0]==split.level[0]); /* partition/cadence independent rise */
    spectrum_widget_step(&w,0,INT_MAX,100,105,100);
    assert(w.level[0]==0 && w.peak[0]==0); /* no overshoot; bounded input */
    spectrum_widget_step(&w,0,-72*256,10,115,100);
    assert(w.level[0]==-6*256 && w.peak[0]==0);
    spectrum_widget_step(&w,0,-72*256,5,120,100);
    assert(w.level[0]==-9*256 && w.peak[0]==-153); /* only1tick past140ms hold */
    for(unsigned tick=125;tick<=255;tick+=5) spectrum_widget_step(&w,0,INT_MIN,5,tick,100);
    assert(w.level[0]==-72*256 && w.peak[0]==-72*256);
    w.level[0]=w.peak[0]=-6*256;w.peak_tick[0]=UINT32_MAX-4;
    spectrum_widget_step(&w,0,-72*256,10,5,100);
    assert(w.peak[0]==-6*256); /* wrapping clock, still within140ms */
    spectrum_widget_step(&w,0,-72*256,6,11,100);
    assert(w.peak[0] < -6*256);
    w.level[0]=w.peak[0]=0; w.peak_tick[0]=0;w.fall_fraction[0]=w.peak_fraction[0]=0;
    split=w;
    spectrum_widget_step(&w,0,-72*256,40,40,100);
    for(unsigned tick=1;tick<=40;tick++) spectrum_widget_step(&split,0,-72*256,1,tick,100);
    assert(w.level[0]==split.level[0] && w.peak[0]==split.peak[0]);
    int old=w.level[0];spectrum_widget_step(&w,0,0,0,40,100);assert(w.level[0]==old);
}
static void test_fast3_regression(void)
{
    struct spectrum_widget w;struct reference_widget ref;
    assert(spectrum_widget_configure(&w,0,0,280,70,16,"bars","classic",280,70));
    assert(reference_widget_configure(&ref,0,0,280,70,16,"bars","classic",280,70));
    uint32_t seed=47,now=UINT32_MAX-100;
    for(unsigned n=0;n<10000;n++) {
        seed=seed*1664525u+1013904223u;
        uint32_t dt=n%101; now+=dt;
        int target=-(int)(seed%(72*256+1));
        spectrum_widget_step(&w,0,target,dt,now,100);
        reference_widget_step(&ref,0,target,dt,now,100);
        assert(w.level[0]==ref.level[0] && w.peak[0]==ref.peak[0]);
        assert(w.fall_fraction[0]==ref.fall_fraction[0] && w.peak_fraction[0]==ref.peak_fraction[0]);
    }
}
static void test_profiles_and_gain(void)
{
    struct spectrum_widget w, split;
    for (int profile = 0; profile < SPECTRUM_MOTION_COUNT; profile++) {
        assert(spectrum_widget_configure(&w,0,0,280,70,16,"bars","classic",280,70));
        spectrum_widget_motion(&w,profile,0);
        spectrum_widget_step(&w,0,0,0,0,100);
        assert(w.level[0]==-72*256);
        split=w;
        spectrum_widget_step(&w,0,0,10,10,100);
        for (unsigned tick=1;tick<=10;tick++) spectrum_widget_step(&split,0,0,1,tick,100);
        assert(w.level[0]==split.level[0] && w.peak[0]==split.peak[0]);
        /* Reset peak origin identically for a held peak then accelerating fall. */
        w.level[0]=w.peak[0]=0;w.peak_tick[0]=0;
        w.peak_speed[0]=spectrum_motion_policy(profile)->peak_start_db*256;
        w.fall_fraction[0]=w.peak_fraction[0]=w.peak_accel_fraction[0]=0;split=w;
        spectrum_widget_step(&w,0,-72*256,100,100,100);
        for (unsigned tick=1;tick<=100;tick++) spectrum_widget_step(&split,0,-72*256,1,tick,100);
        assert(w.level[0]==split.level[0] && w.peak[0]==split.peak[0]);
        assert(w.peak[0]>=w.level[0] && w.peak[0]<=0);
        assert(w.peak_speed[0]<=spectrum_motion_policy(profile)->peak_max_db*256);
        if (profile) assert(w.peak_speed[0]>spectrum_motion_policy(profile)->peak_start_db*256);
        spectrum_widget_motion(&w,99,100);assert(w.motion==0);
    }
    assert(spectrum_widget_configure(&w,0,0,280,70,16,"bars","classic",280,70));split=w;
    spectrum_widget_gain(&w,true,true,-40*256,100,100);
    for(unsigned i=0;i<100;i++)spectrum_widget_gain(&split,true,true,-40*256,1,100);
    assert(w.visual_gain==384 && w.visual_gain==split.visual_gain);
    for(unsigned i=0;i<20;i++)spectrum_widget_gain(&w,true,true,-40*256,100,100);
    assert(w.visual_gain==18*256);
    spectrum_widget_gain(&w,true,true,-72*256,100,100);assert(w.visual_gain==18*256);
    spectrum_widget_gain(&w,true,false,0,100,100);assert(w.visual_gain==18*256);
    spectrum_widget_gain(&w,true,true,0,100,100);assert(w.visual_gain==-6*256);
    spectrum_widget_gain(&w,false,true,-40*256,100,100);assert(w.visual_gain==0);
    spectrum_widget_gain(&w,true,true,-20*256,10,100);assert(w.visual_gain>0&&w.visual_gain<256);
}
int main(void) {
    test_analysis();test_visual_features();test_capture();test_rolling();test_widget();test_presentation();test_profiles_and_gain();test_fast3_regression();
    printf("PASS: numeric FFT, stereo phase, clipping, capture ownership/reset/drop/timing, widget bounds, presentation attack/release/hold/wrap\n");
    printf("RAM: analyzer=%zu capture=%zu widget=%zu frame=%zu bytes\n",sizeof(analyzer),sizeof(struct spectrum_capture),sizeof(struct spectrum_widget),sizeof(frame));
}
