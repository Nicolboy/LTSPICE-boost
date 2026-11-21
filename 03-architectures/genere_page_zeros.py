"""Assemble `zeros-3d.html` — le plant de regulation en surfaces.

POURQUOI CES AXES-LA, ET PAS CEUX DE `frontiere-3d.html`.

Le zero dans le demi-plan droit du boost en CCM se simplifie remarquablement :

    f_z = D'^2.R/(2.pi.L)   avec   D' = Vin/Vout   et   R = Vout^2/P

        f_z = Vin^2 / (2.pi.L.P_out)

**Vout disparait.** Les variables qui pilotent le zero sont Vin, L et P --
pas Vout. Mettre P en Z (comme sur la page frontiere) le cache, puisque P
est justement l'une des trois. D'ou :

    X = Vin (V)      Y = P_out (W, vers le fond)      Z = la grandeur
    L et C_out au choix.

QUATRE GRANDEURS, parce qu'elles ne se lisent pas ensemble :

    f_z       zero a droite          ce qui PLAFONNE le crossover
    f_z/3     plafond de crossover   la contrainte directe de conception
    f_0       double pole            ou demarre la pente a -40 dB/dec
    Q_eff     facteur de qualite     amorti par l'ESR du condensateur

CE QUE LA PAGE DOIT DIRE SANS QU'ON LE DEMANDE. En DCM l'inductance cesse
d'etre une variable d'etat : l'ordre tombe a un et le zero remonte d'environ
une decade. La formule CCM y donne donc une BORNE INFERIEURE -- le vrai
zero est plus haut, la lecture est conservatrice. Les mailles en DCM sont
marquees, pour qu'on ne lise pas un chiffre CCM comme s'il s'appliquait.

Aucune simulation : analytique, modeles canoniques du boost (Erickson,
ch. 7 et 11). Les valeurs sont CALCULEES, pas mesurees -- une reponse en
frequence du plant reste a faire.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
HTML = ICI / "zeros-3d.html"

VOUT, ETA = 80.0, 0.97
VIN = [12, 14, 16, 18, 20, 22, 25]
POUT = [5, 8, 12, 20, 30, 40, 50]
LS = [10, 12, 15, 22, 33, 47]
# (C_out, ESR) — apparies de facon realiste : l'ESR d'un aluminium decroit
# quand la capacite monte, dans une meme famille.
COUT = [(200, 0.150), (300, 0.100), (400, 0.080)]
FSW = 200e3
FC_VISE = 14.0e3          # crossover retenu au §10.3

NOTES = {10: "XAL1510-103", 12: "SER2211-123 — en stock",
         15: "XAL1510-153", 22: "XAL1510-223 — retenu",
         33: "XAL1510-333", 47: "SER2211-473 — en stock"}


def cellule(vin, p, l_uh, c_uf, esr):
    L, C = l_uh * 1e-6, c_uf * 1e-6
    dp = vin / VOUT
    plim = vin ** 2 * (1 - vin / VOUT) * ETA / (2 * L * FSW)
    dcm = p <= plim
    fz = vin ** 2 / (2 * math.pi * L * p)          # Vout se simplifie
    f0 = dp / (2 * math.pi * math.sqrt(L * C))
    q = dp * (VOUT ** 2 / p) * math.sqrt(C / L)
    zeta = 1 / (2 * q) + esr / 2 * math.sqrt(C / L)
    qeff = 1 / (2 * zeta)
    return [round(fz / 1e3, 2), round(fz / 3e3, 2), round(f0, 1),
            round(qeff, 2), 1 if dcm else 0,
            1 if fz / 3 < FC_VISE else 0]


def grille():
    out = {}
    for l in LS:
        for c, esr in COUT:
            m = [[cellule(v, p, l, c, esr) for v in VIN] for p in POUT]
            out[f"{l}|{c}"] = m
    return out


PAGE = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Zéros et plant de régulation — surfaces 3D</title>
<style>
:root{--bg:#11141a;--pan:#171b23;--bord:#2b3240;--txt:#e6e9ef;--txt2:#9aa4b5;
      --ko:#ff6b6b;--ok:#3ddc84;--dcm:#f0b23d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
     font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:1.4rem 1.1rem 3rem}
h1{font-size:1.45rem;margin:.2rem 0 .3rem;font-weight:650}
.sous{color:var(--txt2);font-size:.93rem;margin:0 0 1.1rem}
.f{background:#141821;border:1px solid var(--bord);border-radius:8px;
   padding:.5rem .8rem;margin:.6rem 0 1rem;font-size:.95rem;text-align:center}
.barre{display:flex;flex-wrap:wrap;gap:.45rem;margin:.7rem 0;align-items:center}
.barre b{font-size:.82rem;color:var(--txt2);margin-right:.2rem;font-weight:600}
button{background:var(--pan);color:var(--txt);border:1px solid var(--bord);
       border-radius:7px;padding:.44rem .8rem;cursor:pointer;font-size:.88rem}
button:hover{border-color:#49546a}
button.on{background:#223049;border-color:#4d7fc1;color:#cfe2ff}
#wrap{position:relative;border:1px solid var(--bord);border-radius:11px;
      background:var(--pan);overflow:hidden}
canvas{display:block;width:100%;height:auto;cursor:grab;touch-action:none}
canvas:active{cursor:grabbing}
#bulle{position:absolute;pointer-events:none;display:none;z-index:5;
  background:#0d1016;border:1px solid var(--bord);border-radius:8px;
  padding:.55rem .7rem;font-size:.82rem;line-height:1.5;max-width:290px;
  box-shadow:0 8px 26px #0009}
#bulle b{color:#cfe2ff}
.note{color:var(--txt2);font-size:.85rem;margin:.8rem 0 0}
.aide{background:#141821;border-left:3px solid #4d7fc1;border-radius:0 7px 7px 0;
      padding:.65rem .85rem;margin:1rem 0;font-size:.87rem;color:var(--txt2)}
.aide.or{border-left-color:var(--dcm)}
table{border-collapse:collapse;margin-top:1rem;font-size:.85rem;width:100%}
th,td{border:1px solid var(--bord);padding:.32rem .55rem;text-align:right}
th{color:var(--txt2);font-weight:600}
td:first-child,th:first-child{text-align:left}
.ko{color:var(--ko);font-weight:600}
.dcm{color:var(--dcm)}
</style></head><body><main>
<h1>Zéros et plant de régulation — surfaces 3D</h1>
<p class="sous">boost 20 V → 80 V · f<sub>sw</sub> = 200 kHz · glisser pour
tourner, molette pour zoomer</p>

<div class="f">
<b>f<sub>z</sub> = V<sub>in</sub>² / (2π·L·P<sub>out</sub>)</b> — le zéro à
droite ne dépend <i>pas</i> de V<sub>out</sub> : il se simplifie.
</div>

<div class="barre"><b>L</b><span id="bL"></span></div>
<div class="barre"><b>C<sub>out</sub></b><span id="bC"></span></div>
<div class="barre"><b>grandeur</b><span id="bG"></span></div>

<div id="wrap">
  <canvas id="c" width="1140" height="660"></canvas>
  <div id="bulle"></div>
</div>
<p class="note" id="leg"></p>

<div class="aide or">
<b>Les mailles en orange sont en DCM.</b> L'inductance y cesse d'être une
variable d'état : l'ordre du plant tombe à un et le zéro remonte d'environ
une décade. La formule CCM y donne donc une <b>borne inférieure</b> — le
vrai zéro est plus haut, la lecture est conservatrice. Les mailles cerclées
de <span class="ko">rouge</span> sont celles où le plafond f<sub>z</sub>/3
tombe <b>sous les 14 kHz</b> visés : ce sont elles qui fixent la
compensation.
</div>

<div class="aide" id="lecture"></div>
<div id="tab"></div>
</main>
<script>
const VIN=/*VIN*/, POUT=/*POUT*/, LS=/*LS*/, COUT=/*COUT*/,
      NOTES=/*NOTES*/, D=/*DATA*/, FC=/*FC*/;
const GR=[["Zéro à droite f_z (kHz)","kHz",0],
          ["Plafond de crossover f_z/3 (kHz)","kHz",1],
          ["Double pôle f_0 (Hz)","Hz",2],
          ["Q effectif (ESR comprise)","",3]];
const cv=document.getElementById("c"), cx=cv.getContext("2d");
const W=cv.width,H=cv.height,CX=W/2+10,CY=H/2+46,S=Math.min(W,H)*0.60;
let az=-0.72, el=0.50, zoom=1, li=3, ci=1, ig=1, pts=[];

function proj(x,y,z){
  const X=(x-.5)*1.9, Y=(y-.5)*1.9, Z=(z-.5)*1.25;
  const ca=Math.cos(az), sa=Math.sin(az);
  const x1=X*ca-Y*sa, y1=X*sa+Y*ca;
  const ce=Math.cos(el), se=Math.sin(el);
  const y2=y1*ce-Z*se, z2=y1*se+Z*ce;
  const p=1/(1+y2*0.16);
  return [CX+x1*S*zoom*p, CY-z2*S*zoom*p, y2];
}
const gx=j=>j/(VIN.length-1), gy=i=>i/(POUT.length-1);
const cle=()=>LS[li]+"|"+COUT[ci][0];

function bornes(m,q){
  let lo=Infinity,hi=-Infinity;
  for(const r of m) for(const c of r){ const v=c[q];
    if(v<lo)lo=v; if(v>hi)hi=v; }
  if(hi-lo<1e-9) hi=lo+1;
  return [lo,hi];
}

function dessine(){
  const m=D[cle()], q=GR[ig][2], [lo,hi]=bornes(m,q);
  const z=v=>(v-lo)/(hi-lo);
  cx.clearRect(0,0,W,H);

  cx.strokeStyle="#2b3240"; cx.lineWidth=1;
  for(let i=0;i<POUT.length;i++){
    const a=proj(0,gy(i),0), b=proj(1,gy(i),0);
    cx.beginPath(); cx.moveTo(a[0],a[1]); cx.lineTo(b[0],b[1]); cx.stroke();
  }
  for(let j=0;j<VIN.length;j++){
    const a=proj(gx(j),0,0), b=proj(gx(j),1,0);
    cx.beginPath(); cx.moveTo(a[0],a[1]); cx.lineTo(b[0],b[1]); cx.stroke();
  }
  cx.fillStyle="#9aa4b5"; cx.font="12px system-ui"; cx.textAlign="center";
  for(let j=0;j<VIN.length;j++){ const t=proj(gx(j),-0.10,0);
    cx.fillText(VIN[j]+" V",t[0],t[1]+4); }
  cx.textAlign="right";
  for(let i=0;i<POUT.length;i++){ const t=proj(-0.08,gy(i),0);
    cx.fillText(POUT[i]+" W",t[0],t[1]+4); }

  /* AXE VERTICAL au coin le plus ELOIGNE, recalcule a chaque rotation :
     ailleurs il passerait devant le relief. Sans graduations en Z, la
     couleur seule ne donne pas une valeur. */
  let coin=null;
  for(const [x,y] of [[0,0],[1,0],[1,1],[0,1]]){
    const p=proj(x,y,0); if(!coin||p[2]>coin.p[2]) coin={x,y,p};
  }
  const haut=proj(coin.x,coin.y,1);
  cx.strokeStyle="#49546a"; cx.lineWidth=1.3;
  cx.beginPath(); cx.moveTo(coin.p[0],coin.p[1]); cx.lineTo(haut[0],haut[1]);
  cx.stroke();
  const vers=coin.x<0.5?-1:1;
  cx.textAlign=vers<0?"right":"left";
  for(let k=0;k<=4;k++){
    const u=k/4, v=lo+(hi-lo)*u, p=proj(coin.x,coin.y,u);
    cx.strokeStyle="#49546a"; cx.lineWidth=1;
    cx.beginPath(); cx.moveTo(p[0],p[1]); cx.lineTo(p[0]+vers*7,p[1]); cx.stroke();
    cx.fillStyle="#9aa4b5"; cx.font="12px system-ui";
    cx.fillText(v.toFixed(hi<10?2:(hi<200?1:0)), p[0]+vers*11, p[1]+4);
    if(k>0&&k<5){
      const o=proj(coin.x, coin.x===coin.y?1-coin.y:coin.y, u);
      cx.strokeStyle="rgba(73,84,106,.35)";
      cx.beginPath(); cx.moveTo(p[0],p[1]); cx.lineTo(o[0],o[1]); cx.stroke();
    }
  }
  const mil=proj(coin.x,coin.y,0.5);
  cx.save(); cx.translate(mil[0]+vers*56,mil[1]); cx.rotate(-Math.PI/2);
  cx.textAlign="center"; cx.fillStyle="#e6e9ef"; cx.font="13px system-ui";
  cx.fillText(GR[ig][0],0,0); cx.restore();

  /* PLAN DU CROSSOVER VISE, sur les deux grandeurs en kHz : il montre d'un
     coup d'oeil ou la surface passe SOUS la cible. */
  const cible = q===0 ? FC*3/1000 : (q===1 ? FC/1000 : null);
  if(cible!==null && cible>lo && cible<hi){
    const u=z(cible);
    cx.strokeStyle="rgba(255,107,107,.6)"; cx.lineWidth=1.3;
    cx.setLineDash([5,4]); cx.beginPath();
    const cs=[[0,0],[1,0],[1,1],[0,1]].map(([x,y])=>proj(x,y,u));
    cx.moveTo(cs[0][0],cs[0][1]);
    for(let k=1;k<4;k++) cx.lineTo(cs[k][0],cs[k][1]);
    cx.closePath(); cx.stroke(); cx.setLineDash([]);
    const e=proj(1,1,u);
    cx.fillStyle="#ff6b6b"; cx.font="12px system-ui"; cx.textAlign="left";
    cx.fillText(q===1?"14 kHz visés":"3 × 14 kHz", e[0]+8, e[1]+4);
  }

  const faces=[];
  for(let i=0;i<POUT.length-1;i++) for(let j=0;j<VIN.length-1;j++){
    const qd=[[i,j],[i,j+1],[i+1,j+1],[i+1,j]];
    const pr=qd.map(([a,b])=>proj(gx(b),gy(a),z(m[a][b][q])));
    const v=qd.reduce((s,[a,b])=>s+m[a][b][q],0)/4;
    const ndcm=qd.filter(([a,b])=>m[a][b][4]).length;
    faces.push({pr, prof:pr.reduce((s,p)=>s+p[2],0)/4, v, dcm:ndcm>=2,
                ko:qd.some(([a,b])=>m[a][b][5])});
  }
  faces.sort((a,b)=>b.prof-a.prof);
  for(const f of faces){
    cx.beginPath(); cx.moveTo(f.pr[0][0],f.pr[0][1]);
    for(let k=1;k<4;k++) cx.lineTo(f.pr[k][0],f.pr[k][1]);
    cx.closePath();
    const u=Math.min(1,Math.max(0,(f.v-lo)/(hi-lo)));
    cx.fillStyle = f.dcm ? "hsla(38,70%,"+(34+24*u)+"%,.80)"
                         : "hsla("+(215-150*u)+",62%,52%,.80)";
    cx.fill();
    const bord = (f.ko && (q===0||q===1));
    cx.strokeStyle=bord?"rgba(255,107,107,.9)":"rgba(10,13,18,.55)";
    cx.lineWidth=bord?1.7:1; cx.stroke();
  }

  pts=[];
  for(let i=0;i<POUT.length;i++) for(let j=0;j<VIN.length;j++){
    const c=m[i][j], p=proj(gx(j),gy(i),z(c[q]));
    pts.push({x:p[0],y:p[1],i,j,c});
    const al=c[5]&&(q===0||q===1);
    cx.beginPath(); cx.arc(p[0],p[1],al?4.2:2.8,0,7);
    cx.fillStyle=al?"#ff6b6b":"#0d1016";
    cx.strokeStyle=al?"#ff6b6b":(c[4]?"#f0b23d":"#cfe2ff");
    cx.lineWidth=1.2; cx.fill(); cx.stroke();
  }
  document.getElementById("leg").textContent=
    GR[ig][0]+" — de "+lo.toFixed(2)+" à "+hi.toFixed(2)+" "+GR[ig][1]
    +" · L = "+LS[li]+" µH · C_out = "+COUT[ci][0]+" µF / ESR "
    +(COUT[ci][1]*1e3).toFixed(0)+" mΩ";
  tableau(m,q);
}

function tableau(m,q){
  let h="<table><tr><th>P \\ V<sub>in</sub></th>";
  for(const v of VIN) h+="<th>"+v+" V</th>";
  h+="</tr>";
  for(let i=0;i<POUT.length;i++){
    h+="<tr><td>"+POUT[i]+" W</td>";
    for(let j=0;j<VIN.length;j++){
      const c=m[i][j];
      const cl=c[5]&&(q===0||q===1)?"ko":(c[4]?"dcm":"");
      h+="<td"+(cl?' class="'+cl+'"':"")+">"+c[q].toFixed(q===3?2:1)+"</td>";
    }
    h+="</tr>";
  }
  h+="</table>";
  document.getElementById("tab").innerHTML=h;
  document.getElementById("lecture").innerHTML=
    "<b>Lecture.</b> f<sub>z</sub> = V<sub>in</sub>²/(2π·L·P) : le zéro "
    +"<b>descend</b> quand la charge monte et quand V<sub>in</sub> baisse. "
    +"Le pire cas est donc le <b>coin bas en pleine charge</b>, pas le point "
    +"nominal. En orange, les mailles en DCM — la valeur y est une borne "
    +"inférieure, le vrai zéro est plus haut. En rouge, celles où "
    +"f<sub>z</sub>/3 tombe sous les 14 kHz visés.";
}

function barres(){
  const bl=document.getElementById("bL"), bc=document.getElementById("bC"),
        bg=document.getElementById("bG");
  bl.innerHTML=""; bc.innerHTML=""; bg.innerHTML="";
  LS.forEach((l,k)=>{ const b=document.createElement("button");
    b.textContent=l+" µH"; b.className=k===li?"on":"";
    b.onclick=()=>{li=k;barres();dessine();}; bl.appendChild(b); });
  COUT.forEach((c,k)=>{ const b=document.createElement("button");
    b.textContent=c[0]+" µF · "+(c[1]*1e3).toFixed(0)+" mΩ";
    b.className=k===ci?"on":"";
    b.onclick=()=>{ci=k;barres();dessine();}; bc.appendChild(b); });
  GR.forEach((g,k)=>{ const b=document.createElement("button");
    b.textContent=g[0].split("(")[0].trim(); b.className=k===ig?"on":"";
    b.onclick=()=>{ig=k;barres();dessine();}; bg.appendChild(b); });
}

const bulle=document.getElementById("bulle");
cv.addEventListener("mousemove",e=>{
  const r=cv.getBoundingClientRect(), sx=cv.width/r.width;
  const mx=(e.clientX-r.left)*sx, my=(e.clientY-r.top)*sx;
  let best=null,bd=1e9;
  for(const p of pts){ const d=(p.x-mx)**2+(p.y-my)**2;
    if(d<bd){bd=d;best=p;} }
  if(best&&bd<420){
    const c=best.c;
    bulle.innerHTML="<b>V<sub>in</sub> "+VIN[best.j]+" V · "+POUT[best.i]
      +" W · "+LS[li]+" µH</b><br>zéro à droite <b>"+c[0].toFixed(1)
      +" kHz</b><br>plafond de crossover "+c[1].toFixed(1)+" kHz<br>"
      +"double pôle "+c[2].toFixed(0)+" Hz · Q<sub>eff</sub> "+c[3].toFixed(2)
      +(c[4]?"<br><span style='color:#f0b23d'><b>DCM</b> — ordre 1, le vrai "
        +"zéro est plus haut</span>":"")
      +(c[5]?"<br><span style='color:#ff6b6b'><b>plafond sous 14 kHz</b> — "
        +"c'est cette maille qui fixe la compensation</span>":"")
      +(NOTES[LS[li]]?"<br><span style='color:#9aa4b5'>"+NOTES[LS[li]]
        +"</span>":"");
    bulle.style.display="block";
    bulle.style.left=Math.min(r.width-300,(best.x/sx)+14)+"px";
    bulle.style.top=((best.y/sx)-10)+"px";
  } else bulle.style.display="none";
});
cv.addEventListener("mouseleave",()=>bulle.style.display="none");
let drag=null;
cv.addEventListener("pointerdown",e=>{drag=[e.clientX,e.clientY,az,el];
  cv.setPointerCapture(e.pointerId);});
cv.addEventListener("pointerup",()=>drag=null);
cv.addEventListener("pointermove",e=>{ if(!drag) return;
  az=drag[2]+(e.clientX-drag[0])*0.009;
  el=Math.max(-0.2,Math.min(1.35,drag[3]+(e.clientY-drag[1])*0.006));
  dessine(); });
cv.addEventListener("wheel",e=>{e.preventDefault();
  zoom=Math.max(.55,Math.min(2.4,zoom*(e.deltaY<0?1.1:0.91))); dessine();},
  {passive:false});
barres(); dessine();
</script></body></html>
"""


def main():
    d = grille()
    h = (PAGE.replace("/*VIN*/", json.dumps(VIN))
             .replace("/*POUT*/", json.dumps(POUT))
             .replace("/*LS*/", json.dumps(LS))
             .replace("/*COUT*/", json.dumps(COUT))
             .replace("/*NOTES*/", json.dumps(NOTES, ensure_ascii=False))
             .replace("/*DATA*/", json.dumps(d))
             .replace("/*FC*/", str(FC_VISE)))
    HTML.write_text(h, encoding="utf-8")
    n = len(LS) * len(COUT) * len(POUT) * len(VIN)
    print(f"{HTML.name} ecrit — {n} points "
          f"({len(LS)} inductances x {len(COUT)} condensateurs x "
          f"{len(POUT)} puissances x {len(VIN)} tensions)")
    for l in LS:
        m = d[f"{l}|300"]
        ko = sum(c[5] for r in m for c in r)
        dcm = sum(c[4] for r in m for c in r)
        fz = min(c[0] for r in m for c in r)
        print(f"  {l:2d} uH : f_z mini {fz:6.1f} kHz · {ko:2d}/49 mailles sous "
              f"le plafond de 14 kHz · {dcm:2d}/49 en DCM")


if __name__ == "__main__":
    main()
