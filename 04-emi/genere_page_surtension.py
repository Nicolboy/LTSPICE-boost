"""Assemble `surtension-3d.html` depuis la grille de 120 points.

Meme convention que `02-mosfet-diode/pertes-3d.html` : page AUTONOME, aucun
CDN, aucune dependance, s'ouvre au double-clic. Projection azimut/elevation
a la main sur un canvas, algorithme du peintre, survol a la souris.

QUATRE SURFACES, dV = f(Rg, L_boucle) :
    DCM / CCM  x  Schottky Si 200 V / SiC 650 V

TROIS GRANDEURS AU CHOIX, parce qu'elles ne se decident pas ensemble :
    dV      contrainte sur la diode   -> survie du composant
    dV/dt   contenu haute frequence   -> CEM
    di/dt   courant interrompu        -> ce qui cree la surtension

CE QUE LA PAGE DOIT DIRE SANS QU'ON AIT A LE DEMANDER. Une maille ECRETEE
n'est pas une mesure : la diode y est en avalanche, son altitude est le
niveau de claquage et non le pic reel. Elle est donc cerclee de rouge, et
l'infobulle le dit en toutes lettres.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
SRC = ICI / "results" / "surface" / "surface.json"
HTML = ICI / "surtension-3d.html"

RG = [1.0, 2.2, 4.7, 10.0, 22.0, 47.0]
LB = [2e-9, 5e-9, 10e-9, 20e-9, 40e-9]
CAS = [("4u7|si",  "DCM · Schottky Si 200 V", 220.0),
       ("4u7|inf", "DCM · SiC 650 V",         650.0),
       ("47u|si",  "CCM · Schottky Si 200 V", 220.0),
       ("47u|inf", "CCM · SiC 650 V",         650.0)]
GRANDEURS = [("dv", "ΔV — dépassement (V)", "V", "contrainte sur la diode"),
             ("dvdt", "dV/dt (V/ns)", "V/ns", "contenu haute fréquence · CEM"),
             ("didt", "di/dt (A/ns)", "A/ns", "courant interrompu")]


def charge():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    out = {}
    for cle, _, vbr in CAS:
        ind, dio = cle.split("|")
        m = []
        for rg in RG:
            ligne = []
            for lb in LB:
                e = d.get(f"{ind}|{dio}|{rg}|{lb}")
                ligne.append(None if e is None else
                             [round(e["dv"], 2), round(e["dvdt"], 2),
                              round(e["didt"], 3), round(e["av"], 1),
                              1 if e["ecrete"] else 0])
            m.append(ligne)
        out[cle] = m
    return out


PAGE = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Surtension inverse — surface 3D interactive</title>
<style>
:root{--bg:#11141a;--pan:#171b23;--bord:#2b3240;--txt:#e6e9ef;--txt2:#9aa4b5;
      --ko:#ff6b6b;--ok:#3ddc84}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
     font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:1.4rem 1.1rem 3rem}
h1{font-size:1.45rem;margin:.2rem 0 .3rem;font-weight:650}
.sous{color:var(--txt2);font-size:.93rem;margin:0 0 1.1rem}
.barre{display:flex;flex-wrap:wrap;gap:.45rem;margin:.7rem 0}
button{background:var(--pan);color:var(--txt);border:1px solid var(--bord);
       border-radius:7px;padding:.44rem .8rem;cursor:pointer;font-size:.88rem}
button:hover{border-color:#49546a}
button.on{background:#223049;border-color:#4d7fc1;color:#cfe2ff}
.lg{font-size:.78rem;color:var(--txt2);margin-left:.35rem}
#wrap{position:relative;border:1px solid var(--bord);border-radius:11px;
      background:var(--pan);overflow:hidden}
canvas{display:block;width:100%;height:auto;cursor:grab;touch-action:none}
canvas:active{cursor:grabbing}
#bulle{position:absolute;pointer-events:none;display:none;z-index:5;
  background:#0d1016;border:1px solid var(--bord);border-radius:8px;
  padding:.55rem .7rem;font-size:.82rem;line-height:1.5;max-width:270px;
  box-shadow:0 8px 26px #0009}
#bulle b{color:#cfe2ff}
.note{color:var(--txt2);font-size:.85rem;margin:.8rem 0 0}
.aide{background:#141821;border-left:3px solid #4d7fc1;border-radius:0 7px 7px 0;
      padding:.65rem .85rem;margin:1rem 0;font-size:.87rem;color:var(--txt2)}
table{border-collapse:collapse;margin-top:1rem;font-size:.85rem;width:100%}
th,td{border:1px solid var(--bord);padding:.32rem .55rem;text-align:right}
th{color:var(--txt2);font-weight:600}
td:first-child,th:first-child{text-align:left}
.ecr{color:var(--ko)}
</style></head><body><main>
<h1>Surtension inverse sur la diode — surface 3D</h1>
<p class="sous">boost 19 V → 80 V, 47 W, 400 kHz · EPC2207 GaN ·
<b>120 points simulés</b> (6 valeurs de R<sub>g</sub> × 5 d'inductance de
boucle × 2 diodes × 2 modes) · glisser pour tourner, molette pour zoomer</p>

<div class="barre" id="bCas"></div>
<div class="barre" id="bGrandeur"></div>

<div id="wrap">
  <canvas id="c" width="1140" height="660"></canvas>
  <div id="bulle"></div>
</div>
<p class="note" id="leg"></p>

<div class="aide" id="lecture"></div>
<div id="tab"></div>
</main>
<script>
const RG=/*RG*/, LB=/*LB*/, CAS=/*CAS*/, GR=/*GR*/, D=/*DATA*/;
const cv=document.getElementById("c"), cx=cv.getContext("2d");
const W=cv.width, H=cv.height, CX=W/2+10, CY=H/2+46, S=Math.min(W,H)*0.60;
let az=-0.72, el=0.50, zoom=1, cas=CAS[3][0], ig=0, pts=[];

/* Projection a la main : rotation azimut puis elevation, perspective
   faible, et la PROFONDEUR est rendue pour trier les faces (peintre). */
function proj(x,y,z){
  const px=x-.5, py=y-.5, pz=z-.5;
  const ca=Math.cos(az), sa=Math.sin(az);
  const X=px*ca-py*sa, Y=px*sa+py*ca;
  const ce=Math.cos(el), se=Math.sin(el);
  const haut=pz*ce-Y*se, prof=Y*ce+pz*se;
  const k=3.2/(3.2-prof*0.55), s=S*k*zoom*1.22;
  return [CX+X*s, CY-haut*s, prof];
}
function coul(t){
  t=Math.max(0,Math.min(1,t));
  const st=[[0,[38,92,96]],[.35,[61,200,150]],[.6,[214,214,96]],
            [.82,[240,150,70]],[1,[226,82,79]]];
  for(let i=0;i<st.length-1;i++){const [a,ca]=st[i],[b,cb]=st[i+1];
    if(t<=b){const u=(t-a)/(b-a||1);
      return "rgb("+ca.map((c,k)=>Math.round(c+(cb[k]-c)*u)).join(",")+")";}}
  return "rgb(226,82,79)";
}
/* L'echelle est COMMUNE aux quatre cas : sans cela on comparerait des
   reliefs dessines a des echelles differentes, ce qui est exactement
   l'erreur que la figure doit empecher. */
function bornes(){
  let hi=0;
  for(const [c] of CAS) for(const li of D[c]) for(const p of li)
    if(p && isFinite(p[ig])) hi=Math.max(hi,p[ig]);
  return [0,hi||1];
}
function draw(){
  cx.clearRect(0,0,W,H); pts=[];
  const m=D[cas], [lo,hi]=bornes();
  const gx=j=>j/(LB.length-1), gy=i=>i/(RG.length-1);
  const z=v=>(v-lo)/(hi-lo||1);

  cx.strokeStyle="#2b3240"; cx.lineWidth=1; cx.font="12px system-ui";
  cx.fillStyle="#9aa4b5"; cx.textAlign="center";
  for(let j=0;j<LB.length;j++){
    const a=proj(gx(j),0,0), b=proj(gx(j),1,0);
    cx.beginPath(); cx.moveTo(a[0],a[1]); cx.lineTo(b[0],b[1]); cx.stroke();
    const t=proj(gx(j),-0.09,0);
    cx.fillText((LB[j]*1e9).toFixed(0)+" nH", t[0], t[1]+4);
  }
  for(let i=0;i<RG.length;i++){
    const a=proj(0,gy(i),0), b=proj(1,gy(i),0);
    cx.beginPath(); cx.moveTo(a[0],a[1]); cx.lineTo(b[0],b[1]); cx.stroke();
    const t=proj(-0.09,gy(i),0);
    cx.fillText(RG[i]+" Ω", t[0], t[1]+4);
  }

  /* faces triees du plus loin au plus proche : sans ce tri, une maille
     arriere se dessine par-dessus une maille avant. */
  const faces=[];
  for(let i=0;i<RG.length-1;i++) for(let j=0;j<LB.length-1;j++){
    const q=[[i,j],[i,j+1],[i+1,j+1],[i+1,j]];
    if(q.some(([a,b])=>!m[a][b])) continue;
    const pr=q.map(([a,b])=>proj(gx(b),gy(a),z(m[a][b][ig])));
    const v=q.reduce((s,[a,b])=>s+m[a][b][ig],0)/4;
    faces.push({pr, prof:pr.reduce((s,p)=>s+p[2],0)/4, v,
                ecr:q.some(([a,b])=>m[a][b][4])});
  }
  faces.sort((a,b)=>a.prof-b.prof);
  for(const f of faces){
    cx.beginPath(); cx.moveTo(f.pr[0][0],f.pr[0][1]);
    for(let k=1;k<4;k++) cx.lineTo(f.pr[k][0],f.pr[k][1]);
    cx.closePath();
    cx.fillStyle=coul((f.v-lo)/(hi-lo||1)); cx.fill();
    cx.strokeStyle=f.ecr?"rgba(255,107,107,.75)":"#0d1016";
    cx.lineWidth=f.ecr?1.6:0.7; cx.stroke();
  }
  for(let i=0;i<RG.length;i++) for(let j=0;j<LB.length;j++){
    const p=m[i][j]; if(!p) continue;
    const q=proj(gx(j),gy(i),z(p[ig]));
    pts.push({x:q[0],y:q[1],i,j,p});
    if(p[4]){ cx.beginPath(); cx.arc(q[0],q[1],4.2,0,7); cx.fillStyle="#0d1016";
      cx.fill(); cx.strokeStyle="#ff6b6b"; cx.lineWidth=1.8; cx.stroke(); }
  }
  const g=GR[ig];
  document.getElementById("leg").innerHTML=
    "Couleur et relief : <b>"+g[1]+"</b> — "+g[3]+
    ". Échelle commune aux quatre cas, de 0 à "+hi.toFixed(1)+" "+g[2]+
    ". <span style='color:#ff6b6b'>⬤ cerclé</span> : diode écrêtée par son "+
    "claquage, l'altitude est un plancher et non une mesure.";
  resume();
}
function resume(){
  const m=D[cas], nav=m.flat().filter(p=>p&&p[4]).length;
  const vals=m.flat().filter(Boolean).map(p=>p[0]);
  const vbr=CAS.find(c=>c[0]===cas)[2];
  document.getElementById("lecture").innerHTML= nav
    ? "<b style='color:#ff6b6b'>"+nav+" mailles sur 30 en avalanche.</b> "+
      "La diode est écrêtée à "+vbr+" V : sur ces points le pic réel n'est "+
      "pas mesurable, seule la puissance dissipée l'est. Un composant qui "+
      "travaille là n'est pas dimensionné, il est protégé par son claquage."
    : "<b style='color:#3ddc84'>Aucune avalanche sur la grille.</b> "+
      "Dépassement de "+Math.min(...vals).toFixed(1)+" à "+
      Math.max(...vals).toFixed(1)+" V, pour un claquage à "+vbr+" V — "+
      "marge minimale "+(vbr-80-Math.max(...vals)).toFixed(0)+" V.";
  let t="<table><tr><th>R<sub>g</sub> \\ L<sub>σ</sub></th>"+
    LB.map(l=>"<th>"+(l*1e9).toFixed(0)+" nH</th>").join("")+"</tr>";
  for(let i=0;i<RG.length;i++){
    t+="<tr><td>"+RG[i]+" Ω</td>";
    for(let j=0;j<LB.length;j++){const p=m[i][j];
      t+=p?("<td"+(p[4]?" class='ecr'":"")+">"+p[ig].toFixed(ig===2?2:1)+
            (p[4]?" ⚠":"")+"</td>"):"<td>—</td>";}
    t+="</tr>";
  }
  document.getElementById("tab").innerHTML=t+"</table>";
}
/* --- survol --- */
const bulle=document.getElementById("bulle");
cv.addEventListener("mousemove",e=>{
  const r=cv.getBoundingClientRect(), k=W/r.width;
  const mx=(e.clientX-r.left)*k, my=(e.clientY-r.top)*k;
  if(glisse){ az-=(mx-lx)*0.006/k*k; el=Math.max(-0.2,Math.min(1.35,el+(my-ly)*0.004));
    lx=mx; ly=my; draw(); return; }
  let best=null, bd=22*22;
  for(const p of pts){const d=(p.x-mx)**2+(p.y-my)**2; if(d<bd){bd=d;best=p;}}
  if(!best){bulle.style.display="none";return;}
  const p=best.p, vbr=CAS.find(c=>c[0]===cas)[2];
  bulle.innerHTML="<b>R<sub>g</sub> = "+RG[best.i]+" Ω · L<sub>σ</sub> = "+
    (LB[best.j]*1e9).toFixed(0)+" nH</b><br>"+
    "dépassement <b>"+p[0].toFixed(1)+" V</b><br>"+
    "dV/dt "+p[1].toFixed(1)+" V/ns · di/dt "+p[2].toFixed(2)+" A/ns"+
    (p[4] ? "<br><span style='color:#ff6b6b'><b>ÉCRÊTÉ à "+vbr+" V</b> — "+
            p[3].toFixed(0)+" mW d'avalanche.<br>Le pic réel n'est pas "+
            "mesurable ici.</span>"
          : "<br><span style='color:#3ddc84'>marge "+
            (vbr-80-p[0]).toFixed(0)+" V</span>");
  bulle.style.display="block";
  const bw=bulle.offsetWidth, bh=bulle.offsetHeight;
  bulle.style.left=Math.min(best.x/k+14, r.width-bw-8)+"px";
  bulle.style.top=Math.max(best.y/k-bh-10, 6)+"px";
});
cv.addEventListener("mouseleave",()=>bulle.style.display="none");
let glisse=false, lx=0, ly=0;
cv.addEventListener("mousedown",e=>{const r=cv.getBoundingClientRect(),k=W/r.width;
  glisse=true; lx=(e.clientX-r.left)*k; ly=(e.clientY-r.top)*k; bulle.style.display="none";});
addEventListener("mouseup",()=>glisse=false);
cv.addEventListener("wheel",e=>{e.preventDefault();
  zoom=Math.max(.55,Math.min(2.4,zoom*(e.deltaY<0?1.1:0.9))); draw();},{passive:false});

/* --- boutons --- */
function boutons(id,liste,actif,cb){
  const d=document.getElementById(id);
  d.innerHTML=liste.map((x,k)=>
    "<button data-k='"+k+"'"+(actif(k)?" class='on'":"")+">"+x+"</button>").join("");
  d.querySelectorAll("button").forEach(b=>b.onclick=()=>{cb(+b.dataset.k);
    boutons(id,liste,actif,cb); draw();});
}
function maj(){
  boutons("bCas", CAS.map(c=>c[1]), k=>CAS[k][0]===cas, k=>cas=CAS[k][0]);
  boutons("bGrandeur", GR.map(g=>g[1]), k=>k===ig, k=>ig=k);
}
maj(); draw();
</script></body></html>
"""


def main():
    if not SRC.exists():
        raise SystemExit(f"grille absente : {SRC}")
    d = charge()
    n = sum(1 for c in d.values() for li in c for p in li if p)
    h = (PAGE.replace("/*RG*/", json.dumps(RG))
             .replace("/*LB*/", json.dumps(LB))
             .replace("/*CAS*/", json.dumps([[c, lib, v] for c, lib, v in CAS]))
             .replace("/*GR*/", json.dumps(GRANDEURS))
             .replace("/*DATA*/", json.dumps(d, separators=(",", ":"))))
    for marq in ("/*RG*/", "/*DATA*/", "/*CAS*/"):
        if marq in h:
            raise SystemExit(f"marqueur non remplace : {marq}")
    HTML.write_text(h, encoding="utf-8")
    print(f"{HTML}  ({HTML.stat().st_size/1024:.0f} ko, {n} points)")


if __name__ == "__main__":
    main()
