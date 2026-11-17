"""Construit la page de synthese visuelle a partir de results/visuel.json.

Les courbes sont dessinees en SVG depuis les donnees, pas exportees en
image : plus leger, net a toute echelle, et les couleurs suivent le theme.
"""
from pathlib import Path
import json

ICI = Path(__file__).resolve().parent
SORTIE = ICI / "illustrations" / "synthese_dcm.html"

GABARIT = """<title>Premier étage boost — architecture DCM retenue</title>
<style>
:root{
  --fond:#F6F4EF; --panneau:#FFFFFF; --encre:#111A20; --encre-pale:#5A6872;
  --filet:#DED9D0; --accent:#B87A1C; --accent-doux:#F0E2C8;
  --ch1:#2E7DAE; --ch2:#C14A3E; --ch3:#3F8C56;
  --ok:#3F8C56; --alerte:#B87A1C; --grave:#C14A3E;
  --ombre:0 1px 2px rgba(17,26,32,.06), 0 8px 24px rgba(17,26,32,.05);
}
@media (prefers-color-scheme: dark){
  :root{
    --fond:#0D1317; --panneau:#141E25; --encre:#DBE4EA; --encre-pale:#7B8C98;
    --filet:#22313A; --accent:#E0A33C; --accent-doux:#2A2113;
    --ch1:#5BA7D4; --ch2:#D96B5F; --ch3:#6FB573;
    --ok:#6FB573; --alerte:#E0A33C; --grave:#D96B5F;
    --ombre:0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.3);
  }
}
:root[data-theme="dark"]{
  --fond:#0D1317; --panneau:#141E25; --encre:#DBE4EA; --encre-pale:#7B8C98;
  --filet:#22313A; --accent:#E0A33C; --accent-doux:#2A2113;
  --ch1:#5BA7D4; --ch2:#D96B5F; --ch3:#6FB573;
  --ok:#6FB573; --alerte:#E0A33C; --grave:#D96B5F;
  --ombre:0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.3);
}
:root[data-theme="light"]{
  --fond:#F6F4EF; --panneau:#FFFFFF; --encre:#111A20; --encre-pale:#5A6872;
  --filet:#DED9D0; --accent:#B87A1C; --accent-doux:#F0E2C8;
  --ch1:#2E7DAE; --ch2:#C14A3E; --ch3:#3F8C56;
  --ok:#3F8C56; --alerte:#B87A1C; --grave:#C14A3E;
  --ombre:0 1px 2px rgba(17,26,32,.06), 0 8px 24px rgba(17,26,32,.05);
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--fond); color:var(--encre);
  font-family:ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.55; -webkit-font-smoothing:antialiased;
}
.chiffre,.mono{
  font-family:ui-monospace,"SF Mono","Cascadia Mono",Consolas,"Liberation Mono",monospace;
  font-variant-numeric:tabular-nums; font-feature-settings:"tnum" 1;
}
.page{max-width:1180px; margin:0 auto; padding:clamp(24px,4vw,56px) clamp(16px,3vw,32px) 80px}
header{border-bottom:2px solid var(--encre); padding-bottom:28px; margin-bottom:40px}
.surtitre{
  font-size:11px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--encre-pale); margin:0 0 14px;
  font-family:ui-monospace,Consolas,monospace;
}
h1{
  font-size:clamp(28px,4.4vw,46px); line-height:1.08; margin:0 0 18px;
  letter-spacing:-.022em; font-weight:700; text-wrap:balance; max-width:20ch;
}
.chapo{max-width:62ch; color:var(--encre-pale); margin:0; font-size:16.5px}
.verdict{
  display:inline-flex; align-items:baseline; gap:10px; margin:22px 0 0;
  padding:7px 14px; border:1px solid var(--accent); border-radius:2px;
  background:var(--accent-doux);
}
.verdict b{font-size:13px; letter-spacing:.06em; text-transform:uppercase; color:var(--accent)}
.verdict span{font-size:13px; color:var(--encre-pale)}
.cles{display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:1px; background:var(--filet); border:1px solid var(--filet); margin:34px 0 0}
.cle{background:var(--panneau); padding:16px 18px}
.cle .v{font-size:27px; font-weight:600; letter-spacing:-.02em; display:block}
.cle .l{font-size:11px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--encre-pale); margin-top:5px; display:block}
h2{
  font-size:13px; letter-spacing:.13em; text-transform:uppercase; font-weight:600;
  color:var(--encre-pale); margin:0 0 6px;
  font-family:ui-monospace,Consolas,monospace;
}
section{margin-top:64px}
.intro{max-width:64ch; margin:0 0 26px; font-size:15.5px}
.grille{display:grid; grid-template-columns:repeat(3,1fr); gap:14px}
@media(max-width:780px){.grille{grid-template-columns:1fr}}
.carte{
  background:var(--panneau); border:1px solid var(--filet); border-radius:3px;
  padding:13px 14px 9px; box-shadow:var(--ombre);
}
.carte h3{
  margin:0 0 2px; font-size:14px; font-weight:600; letter-spacing:-.01em;
  display:flex; justify-content:space-between; align-items:baseline; gap:8px;
}
.pill{
  font-size:10px; letter-spacing:.08em; padding:2px 7px; border-radius:2px;
  font-family:ui-monospace,Consolas,monospace; font-weight:600;
  background:var(--accent-doux); color:var(--accent);
}
.sous{font-size:11.5px; color:var(--encre-pale); margin:0 0 9px}
.legende{display:flex; gap:13px; flex-wrap:wrap; font-size:11px;
  color:var(--encre-pale); margin:18px 0 0}
.legende i{display:inline-block; width:15px; height:2px; vertical-align:middle;
  margin-right:5px; border-radius:1px}
table{border-collapse:collapse; width:100%; font-size:14px}
.tableau{overflow-x:auto; border:1px solid var(--filet); background:var(--panneau)}
th,td{padding:9px 13px; text-align:right; border-bottom:1px solid var(--filet); white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{
  font-size:10.5px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--encre-pale); font-weight:600; background:var(--fond);
}
tbody tr:last-child td{border-bottom:none}
tr.total td{font-weight:700; border-top:2px solid var(--encre)}
.bon{color:var(--ok)} .mauvais{color:var(--grave)} .att{color:var(--alerte)}
.note{
  margin-top:22px; padding:15px 18px; border-left:3px solid var(--accent);
  background:var(--panneau); font-size:14.5px; max-width:66ch;
}
.note b{color:var(--accent)}
footer{margin-top:70px; padding-top:22px; border-top:1px solid var(--filet);
  font-size:12.5px; color:var(--encre-pale)}
svg{display:block; width:100%; height:auto; overflow:visible}
.ax{font-size:9px; fill:var(--encre-pale);
  font-family:ui-monospace,Consolas,monospace}
@media(prefers-reduced-motion:no-preference){
  .carte{transition:border-color .15s ease}
}
.carte:hover{border-color:var(--encre-pale)}
</style>

<div class="page">
<header>
  <p class="surtitre">Convertisseur deux étages · premier étage 12–25 V → 80 V · 400 kHz</p>
  <h1>Le premier étage fonctionne en conduction discontinue</h1>
  <p class="chapo">Neuf points d'exploitation simulés sous LTspice avec les modèles
  constructeur du GaN, du MOSFET et de la diode. Bilans de pertes établis par
  éléments dissipatifs, convergence vérifiée en divisant le pas de temps par deux.</p>
  <div class="verdict"><b>DCM retenu</b><span>le CCM sera rouvert aux simulations EMI</span></div>
  <div class="cles" id="cles"></div>
</header>

<section>
  <h2>Formes d'onde · trois périodes en régime établi</h2>
  <p class="intro">Une carte par point d'exploitation. Les lignes correspondent aux
  trois tensions d'entrée, les colonnes à une puissance croissante — c'est le plan
  d'essai réel. <strong>Le courant revient à zéro à chaque période sur les neuf
  points</strong> : le mode discontinu tient sur toute la plage, sans transition.</p>
  <div class="grille" id="formes"></div>
  <div class="legende">
    <span><i style="background:var(--ch1)"></i>tension du nœud de commutation</span>
    <span><i style="background:var(--ch2)"></i>courant dans l'inductance</span>
    <span><i style="background:var(--ch3)"></i>tension aux bornes de la diode</span>
  </div>
</section>

<section>
  <h2>Ce qui a décidé · tension inverse sur la diode</h2>
  <p class="intro">En DCM le courant est <em>déjà nul</em> quand le transistor s'amorce :
  la diode se bloque naturellement, rien ne résonne. En CCM elle est coupée en pleine
  conduction et sa charge se déverse dans l'inductance de maille.</p>
  <div id="diode"></div>
</section>

<section>
  <h2>Bilan de pertes à ~48 W</h2>
  <p class="intro">Mesuré par éléments dissipatifs, pertes fer ajoutées depuis le
  calculateur constructeur. Le bouclage énergétique ferme à 1,7 %.</p>
  <div id="bilans"></div>
</section>

<section>
  <h2>Choix de l'inductance · 4,7 µH imposés par la tenue du mode</h2>
  <p class="intro">Pertes totales mesurées par Coilcraft à 400 kHz et 2,6 A continus.
  Les deux candidates ont la même inductance, donc la même marge de mode : elles ne se
  départagent que par l'échauffement et la résonance propre.</p>
  <div id="inductances"></div>
</section>

<footer>
  Simulations LTspice 26.1.1 · modèles constructeur EPC, Infineon OptiMOS 3, Vishay
  V8PA22, Coilcraft doc 267-28 · bilans par éléments dissipatifs, convergence vérifiée
  à pas divisé par deux (0,02 %) · pertes fer : calculateur Coilcraft, ajustement
  Steinmetz de résidu 1,8 % sur 1,0–6,3 A.
</footer>
</div>

<script id="donnees" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('donnees').textContent);
const E = (t,a,k) => { const n = document.createElementNS('http://www.w3.org/2000/svg',t);
  for (const p in a) n.setAttribute(p,a[p]); (k||[]).forEach(c=>n.appendChild(c)); return n; };

function chemin(pts, x0,x1, y0,y1, W,H, pad){
  const sx = v => pad.l + (v-x0)/(x1-x0)*(W-pad.l-pad.r);
  const sy = v => pad.t + (y1-v)/(y1-y0)*(H-pad.t-pad.b);
  return pts.map((p,i)=>(i?'L':'M')+sx(p[0]).toFixed(1)+' '+sy(p[1]).toFixed(1)).join('');
}

function trace(pts, couleur, unite, H){
  const W=320, pad={l:30,r:4,t:7,b:7};
  let y0=Math.min(...pts.map(p=>p[1])), y1=Math.max(...pts.map(p=>p[1]));
  const marge=(y1-y0)*0.12||1; y0-=marge; y1+=marge;
  if(y0>0) y0=0;            // signal positif : ligne de base a zero
  const x0=pts[0][0], x1=pts[pts.length-1][0];
  const sy = v => pad.t + (y1-v)/(y1-y0)*(H-pad.t-pad.b);
  const kids=[];
  for(let k=1;k<3;k++){ const x=pad.l+(k/3)*(W-pad.l-pad.r);
    kids.push(E('line',{x1:x,x2:x,y1:pad.t,y2:H-pad.b,stroke:'var(--filet)','stroke-width':1})); }
  if(y0<0&&y1>0) kids.push(E('line',{x1:pad.l,x2:W-pad.r,y1:sy(0),y2:sy(0),
    stroke:'var(--filet)','stroke-width':1,'stroke-dasharray':'2 3'}));
  kids.push(E('path',{d:chemin(pts,x0,x1,y0,y1,W,H,pad),fill:'none',
    stroke:couleur,'stroke-width':1.3,'stroke-linejoin':'round'}));
  const t1=E('text',{x:0,y:sy(y1)+7,class:'ax'}); t1.textContent=fmt(y1)+unite;
  const t0=E('text',{x:0,y:sy(y0)-1,class:'ax'}); t0.textContent=fmt(y0);
  kids.push(t1,t0);
  return E('svg',{viewBox:`0 0 ${W} ${H}`,role:'img'},kids);
}
const fmt = v => Math.abs(v)>=100?v.toFixed(0):Math.abs(v)>=10?v.toFixed(0):v.toFixed(1);

// --- chiffres cles
const cles=[['97,06 %','rendement à 47,4 W'],['−99 V','tension inverse diode'],
  ['9 / 9','points en mode discontinu'],['46 °C','inductance SER2013-472']];
document.getElementById('cles').innerHTML = cles.map(([v,l])=>
  `<div class="cle"><span class="v chiffre">${v}</span><span class="l">${l}</span></div>`).join('');

// --- formes d'onde
const hote=document.getElementById('formes');
D.formes.forEach(f=>{
  const c=document.createElement('div'); c.className='carte';
  c.innerHTML=`<h3>${f.vin} V · ${f.pout} W<span class="pill">${f.mode}</span></h3>
    <p class="sous chiffre">I crête ${f.ipk} A · V nœud ${f.vswpk} V · V diode ${f.vdrev} V</p>`;
  c.appendChild(trace(f.vsw,'var(--ch1)',' V',58));
  c.appendChild(trace(f.il,'var(--ch2)',' A',58));
  c.appendChild(trace(f.vd,'var(--ch3)',' V',58));
  const ax=document.createElement('p'); ax.className='sous'; ax.style.margin='4px 0 0';
  ax.style.textAlign='right'; ax.textContent='7,5 µs';
  c.appendChild(ax); hote.appendChild(c);
});

// --- diode : comparaison des contraintes
const CAL=200;
document.getElementById('diode').innerHTML=`<div class="tableau"><table>
<thead><tr><th>architecture</th><th>mécanisme au blocage</th>
<th>tension inverse</th><th>marge sur 200 V</th><th>conséquence</th></tr></thead>
<tbody>
<tr><td><strong>DCM</strong></td><td style="text-align:left">courant nul à l'amorçage</td>
<td class="chiffre bon">−99 V</td><td class="chiffre bon">+50 %</td>
<td style="text-align:left">aucun snubber</td></tr>
<tr><td>CCM</td><td style="text-align:left">coupure sous 2,8 A</td>
<td class="chiffre mauvais">−385 V</td><td class="chiffre mauvais">−93 %</td>
<td style="text-align:left" class="mauvais">avalanche 400 000 ×/s</td></tr>
</tbody></table></div>
<div class="note"><b>Sans solution catalogue.</b> Le claquage réel de la V8PA22 est à
220 V : la résonance l'y plaque à chaque cycle, pour 244 mW. Il n'existe pas de diode
Schottky au-dessus de 200 V — le défaut ne se corrige par aucun choix de composant.</div>`;

// --- bilans
function bilan(k){
  const b=D.bilans[k], tot=b.postes.reduce((s,p)=>s+p[1],0);
  const cou=['var(--ch2)','var(--ch1)','var(--ch3)','var(--accent)','var(--encre-pale)'];
  let x=0; const seg=b.postes.map((p,i)=>{
    const w=p[1]/tot*100, s=`<div title="${p[0]} : ${p[1].toFixed(0)} mW" style="width:${w}%;
      background:${cou[i]};height:100%"></div>`; x+=w; return s;}).join('');
  const li=b.postes.map((p,i)=>`<tr><td><span style="display:inline-block;width:9px;
    height:9px;background:${cou[i]};margin-right:8px;border-radius:1px"></span>${p[0]}</td>
    <td class="chiffre">${p[1].toFixed(1)}</td></tr>`).join('');
  return `<div class="carte" style="${b.retenue?'border-color:var(--accent);border-width:2px':''}">
    <h3>${b.titre}${b.retenue?'<span class="pill">retenue</span>':''}</h3>
    <p class="sous chiffre">${b.pout.toFixed(2)} W en sortie · rendement ${b.rendement.toFixed(2)} %</p>
    <div style="display:flex;height:17px;border-radius:2px;overflow:hidden;margin:10px 0 14px">${seg}</div>
    <table><tbody>${li}
    <tr class="total"><td>Total</td><td class="chiffre">${tot.toFixed(1)} mW</td></tr>
    </tbody></table></div>`;
}
document.getElementById('bilans').innerHTML=
  `<div class="grille" style="grid-template-columns:repeat(2,1fr)">
   ${bilan('archi1')}${bilan('archi2')}</div>`;

// --- courbes inductances
(function(){
  const W=640,H=270,pad={l:52,r:16,t:14,b:36};
  const noms=Object.keys(D.inductances);
  const tout=noms.flatMap(n=>D.inductances[n].pertes);
  const x0=1,x1=6.3,y0=0,y1=Math.max(...tout)*1.08;
  const sx=v=>pad.l+(v-x0)/(x1-x0)*(W-pad.l-pad.r);
  const sy=v=>pad.t+(y1-v)/(y1-y0)*(H-pad.t-pad.b);
  const k=[];
  for(let g=0;g<=4;g++){const v=y1*g/4;
    k.push(E('line',{x1:pad.l,x2:W-pad.r,y1:sy(v),y2:sy(v),stroke:'var(--filet)','stroke-width':1}));
    const t=E('text',{x:pad.l-8,y:sy(v)+3,class:'ax','text-anchor':'end'});
    t.textContent=v.toFixed(0); k.push(t);}
  [1,2,3,4,5,6].forEach(v=>{const t=E('text',{x:sx(v),y:H-pad.b+15,class:'ax','text-anchor':'middle'});
    t.textContent=v; k.push(t);});
  const lx=E('text',{x:(pad.l+W-pad.r)/2,y:H-4,class:'ax','text-anchor':'middle'});
  lx.textContent='ondulation crête-à-crête (A)'; k.push(lx);
  const ly=E('text',{x:pad.l-8,y:pad.t-4,class:'ax','text-anchor':'end'});
  ly.textContent='mW'; k.push(ly);
  k.push(E('line',{x1:sx(6.27),x2:sx(6.27),y1:pad.t,y2:H-pad.b,stroke:'var(--accent)',
    'stroke-width':1.5,'stroke-dasharray':'4 3'}));
  const lp=E('text',{x:sx(6.27)-7,y:pad.t+11,class:'ax','text-anchor':'end'});
  lp.setAttribute('fill','var(--accent)'); lp.textContent='point 50 W'; k.push(lp);
  const cou={'SER2915L-472':'var(--ch1)','SER2013-472':'var(--ch3)'};
  noms.forEach(n=>{const d=D.inductances[n];
    const pts=d.di.map((v,i)=>[v,d.pertes[i]]);
    k.push(E('path',{d:chemin(pts,x0,x1,y0,y1,W,H,pad),fill:'none',
      stroke:cou[n],'stroke-width':2,'stroke-linejoin':'round'}));
    const last=pts[pts.length-1];
    k.push(E('circle',{cx:sx(last[0]),cy:sy(last[1]),r:3.5,fill:cou[n]}));
    const t=E('text',{x:sx(last[0])-8,y:sy(last[1])-9,class:'ax','text-anchor':'end'});
    t.setAttribute('fill',cou[n]); t.setAttribute('font-size','11');
    t.textContent=n+' · '+last[1]+' mW'; k.push(t);});
  const svg=E('svg',{viewBox:`0 0 ${W} ${H}`,role:'img'},k);
  const box=document.createElement('div'); box.className='carte';
  box.appendChild(svg);
  box.insertAdjacentHTML('beforeend',`<div class="note" style="margin-top:16px;border:0;
    padding:0 0 0 14px"><b>SER2013-472 retenue</b> malgré 271 mW de plus : la SER2915L
    n'a pas de modèle SPICE publié, donc sa résonance propre est inconnue — et l'EMI
    passe avant les pertes. La SER2013 résonne à 27,1 MHz, mesuré.</div>`);
  document.getElementById('inductances').appendChild(box);
})();
</script>
"""

if __name__ == "__main__":
    data = (ICI / "results/visuel.json").read_text(encoding="ascii")
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(GABARIT.replace("__DATA__", data), encoding="utf-8")
    print(f"{SORTIE}  ({SORTIE.stat().st_size/1024:.0f} ko)")
