#!/usr/bin/env python3
"""Build a self-contained review gallery from actual simulator captures."""
import argparse
import base64
import html
from pathlib import Path

PACKS = [('WinampSpectrum','Winamp','Feedback Tunnel','Compact transport deck · LED green · mirrored blue/magenta trails'),
         ('StudioSpectrum','Studio','Phosphor Orbit','Asymmetrical instrument panel · amber type · stereo afterglow'),
         ('AdwaitaSpectrum','Adwaita','Flowing Ribbons','Centered album sleeve · spacious type · blue/violet color fields')]

def data(path, kind):
    return 'data:'+kind+';base64,'+base64.b64encode(path.read_bytes()).decode()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    normal=args.reports/'preview-final-normal'
    parts=['''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>iPod visualizer previews</title><style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#101215;color:#e8eaed}
*{box-sizing:border-box}body{max-width:1112px;margin:auto;padding:38px 28px 72px}h1{font-size:30px;letter-spacing:-1px;margin:8px 0 12px}h2{font-size:21px;margin:0 0 8px}h3{font-size:14px;font-weight:500;color:#b7bec8;margin:24px 0 8px}p{line-height:1.5;color:#aab2bd;max-width:780px}.eyebrow{font-size:11px;letter-spacing:2px;color:#8cbcff}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px;margin-top:36px}.identity{height:116px;border-top:1px solid #3c424c;padding-top:17px}.identity p{font-size:12px;margin:0}.effect{font-size:12px;color:#8cbcff;display:block;margin-bottom:8px}figure{margin:0}video,img{width:100%;aspect-ratio:4/3;object-fit:contain;background:#080a0d;display:block;image-rendering:pixelated}video:focus{outline:2px solid #8cbcff}button{font:inherit;font-size:13px;border:1px solid #4b5260;background:#20252d;color:#edf2f9;padding:9px 15px;border-radius:5px;cursor:pointer;margin-right:7px}button:hover{background:#303744}button:focus-visible{outline:2px solid #8cbcff}small{display:block;color:#939dab;margin-top:10px;font-size:11px;line-height:1.5}details{border-top:1px solid #3c424c;margin-top:38px;padding-top:20px}summary{cursor:pointer;font-size:15px}.still-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px;margin-top:20px}.still-grid p{font-size:12px;margin:5px 0 10px}.footer{font-size:12px;margin-top:36px;border-top:1px solid #3c424c;padding-top:16px}@media(max-width:850px){.grid,.still-grid{grid-template-columns:1fr;max-width:480px}.identity{height:auto;padding-bottom:10px}body{padding:24px 18px}.grid{gap:38px}}
</style><body><div class="eyebrow">IPOD CLASSIC / LOCAL DESIGN REVIEW</div><h1>Three players. Three kinds of motion.</h1><p>Firmware 1.1.0 candidate · Theme packs 2.0. Each theme has a Detail player and an Immersive layout. These are actual simulator recordings using the same generated audio fixture.</p><button id="toggle" type="button">Pause all</button><button id="restart" type="button">Restart all</button><small>Video capture: 25 frames/second. This shows appearance; physical iPod frame rate and audio performance remain unmeasured. Nothing has been published or installed.</small><div class="grid">''']
    for ident,label,effect,description in PACKS:
        parts.append('<section><div class="identity"><h2>'+label+'</h2><span class="effect">'+effect+'</span><p>'+description+'</p></div>')
        for variant,title in [('Detail','Detail'),('Visualizer','Immersive')]:
            folder=normal/(ident+'-'+variant)
            parts.append('<h3>'+title+'</h3><figure><video autoplay loop muted playsinline controls preload="auto" aria-label="'+label+' '+title+' animation" poster="'+data(folder/'playing.png','image/png')+'"><source src="'+data(folder/'playing.mp4','video/mp4')+'" type="video/mp4"></video></figure>')
        parts.append('</section>')
    parts.append('</div>')
    for heading,scenario,states in [
        ('Hold, menu and settled pause','normal',['hold','root-menu','paused']),
        ('Long metadata','long-metadata',['playing']),
        ('Missing metadata and artwork','missing-metadata',['playing']),
        ('Visualization disabled','spectrum-off',['playing'])]:
        parts.append('<details><summary>'+heading+'</summary><div class="still-grid">')
        for ident,label,_,_ in PACKS:
            for variant in ['Detail','Visualizer']:
                for state in states:
                    path=args.reports/('preview-final-'+scenario)/(ident+'-'+variant)/(state+'.png')
                    caption=label+' · '+('Immersive' if variant=='Visualizer' else variant)+' · '+state.replace('-',' ')
                    parts.append('<figure><p>'+html.escape(caption)+'</p><img alt="'+html.escape(caption)+'" loading="lazy" src="'+data(path,'image/png')+'"></figure>')
        parts.append('</div></details>')
    parts.append('''<p class="footer">On the iPod, effect selection will support Theme Default, individual effects and optional Auto Cycle. Theme Default uses the signature above. Existing bar-spectrum themes remain available. Menu screenshots use stock simulator labels; your Music/Extras labels come from the separate personal language configuration.</p><script>
const videos=[...document.querySelectorAll('video')], toggle=document.getElementById('toggle');
let paused=matchMedia('(prefers-reduced-motion: reduce)').matches;
function apply(){videos.forEach(v=>paused?v.pause():v.play().catch(()=>{}));toggle.textContent=paused?'Play all':'Pause all';}
toggle.addEventListener('click',()=>{paused=!paused;apply()});document.getElementById('restart').addEventListener('click',()=>{videos.forEach(v=>v.currentTime=0);paused=false;apply()});apply();
</script></body></html>''')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text('\n'.join(parts))
    print(args.output)

if __name__=='__main__':main()
