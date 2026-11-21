"""Assemble `frontiere-3d.html` — la frontiere DCM/CCM comme SURFACE.

POURQUOI UNE SURFACE ET PAS UN NOMBRE.

    P_lim = Vin^2 (1 - Vin/Vout) . eta / (2 L f_sw)

La frontiere depend de Vin EN CARRE. Sur 12-25 V le terme Vin^2(1-Vin/Vout)
passe de 122 a 430, soit un facteur 3,51 : « transition a 15 W » n'a de sens
qu'a UNE tension d'entree. C'est une surface, pas un reglage.

AXES, tels que demandes :
    X = Vin (V)          Y = L (uH, vers le fond)        Z = P_out (W)
    Vout = 80 V, fixe.   f_sw au choix.

CE QUE LA PAGE DOIT DIRE SANS QU'ON LE DEMANDE. Le probleme n'est pas la
frontiere en soi, c'est qu'elle TOMBE DANS LA ZONE D'EMPLOI. Le plant de
regulation est discontinu a la traversee (cf. §10) : une boucle a
compensation fixe y chasse, et le cycle limite tombe dans la bande audible.
Les mailles dont l'altitude tombe dans la **fourchette privilegiee 5-10 W**
sont donc cerclees de rouge : ce sont celles a eviter.

Aucune simulation : tout est analytique et recoupe sur deux sources
independantes du depot (tableau mesure du ch.1 §5 et formule du ch.3 §12.1,
concordantes a 10,9 % pres).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ICI = Path(__file__).resolve().parent
HTML = ICI / "frontiere-3d.html"

VOUT, ETA = 80.0, 0.97
VIN = [12, 14, 16, 18, 20, 22, 25]
LS = [10, 12, 15, 22, 33, 47]
FSW = [150, 200, 300, 400]
P_BAS, P_HAUT = 5.0, 10.0            # fourchette privilegiee
P_REF = 8.0                          # point d'emploi median

NOTES = {
    10: "XAL1510-103 — modèle SPICE complet publié",
    12: "SER2211-123 — en stock",
    15: "XAL1510-153",
    22: "XAL1510-223 — retenu",
    33: "XAL1510-333 — fiche téléchargée",
    47: "SER2211-473 — en stock, Isat 4,4 A seulement",
}


def plim(vin, l_uh, f_khz):
    return vin ** 2 * (1 - vin / VOUT) * ETA / (2 * l_uh * 1e-6 * f_khz * 1e3)


def ondul(vin, l_uh, f_khz, p):
    """Ondulation crete-a-crete en CCM, courant crete en DCM."""
    lh, fh = l_uh * 1e-6, f_khz * 1e3
    if p > plim(vin, l_uh, f_khz):
        return vin * (1 - vin / VOUT) / (lh * fh)
    import math
    return vin * math.sqrt(2 * p * lh * fh * (VOUT - vin)
                           / (ETA * vin ** 2 * VOUT)) / (lh * fh)


def grille():
    """[f_khz][i_L][j_Vin] -> [P_lim, marge, ondulation, dans_la_zone]."""
    out = {}
    for f in FSW:
        m = []
        for l in LS:
            ligne = []
            for v in VIN:
                p = plim(v, l, f)
                ligne.append([round(p, 2),
                              round(p / P_REF, 3),
                              round(ondul(v, l, f, P_REF), 3),
                              1 if P_BAS <= p <= P_HAUT else 0])
            m.append(ligne)
        out[str(f)] = m
    return out


PAGE = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Frontière DCM/CCM — surface 3D interactive</title>
<style>
:root{--bg:#11141a;--pan:#171b23;--bord:#2b3240;--txt:#e6e9ef;--txt2:#9aa4b5;
      --ko:#ff6b6b;--ok:#3ddc84}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
     font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:1.4rem 1.1rem 3rem}
h1{font-size:1.45rem;margin:.2rem 0 .3rem;font-weight:650}
.sous{color:var(--txt2);font-size:.93rem;margin:0 0 1.1rem}
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
  padding:.55rem .7rem;font-size:.82rem;line-height:1.5;max-width:280px;
  box-shadow:0 8px 26px #0009}
#bulle b{color:#cfe2ff}
.note{color:var(--txt2);font-size:.85rem;margin:.8rem 0 0}
.aide{background:#141821;border-left:3px solid #4d7fc1;border-radius:0 7px 7px 0;
      padding:.65rem .85rem;margin:1rem 0;font-size:.87rem;color:var(--txt2)}
.aide.rouge{border-left-color:var(--ko)}
table{border-collapse:collapse;margin-top:1rem;font-size:.85rem;width:100%}
th,td{border:1px solid var(--bord);padding:.32rem .55rem;text-align:right}
th{color:var(--txt2);font-weight:600}
td:first-child,th:first-child{text-align:left}
.ko{color:var(--ko);font-weight:600}
</style></head><body><main>
<h1>Frontière DCM/CCM — surface <i>P</i>(V<sub>in</sub>, L)</h1>
<p class="sous">V<sub>out</sub> = 80 V · η = 0,97 ·
<b>la frontière dépend de V<sub>in</sub> au carré</b> : sur 12–25 V elle se
déplace d'un facteur 3,51, à L et f<sub>sw</sub> fixes · glisser pour
tourner, molette pour zoomer</p>

<div class="barre"><b>f<sub>sw</sub></b><span id="bF"></span></div>
<div class="barre"><b>grandeur</b><span id="bG"></span></div>

<div id="wrap">
  <canvas id="c" width="1140" height="660"></canvas>
  <div id="bulle"></div>
</div>
<p class="note" id="leg"></p>

<div class="aide rouge">
<b>Les mailles cerclées de rouge sont celles à éviter.</b> Leur frontière
tombe dans la fourchette privilégiée <b>5 à 10 W</b> — donc le convertisseur
travaille <i>sur</i> la transition à son point d'emploi. Le plant de
régulation y est discontinu : zéro à droite qui bondit, ordre qui change,
gain continu qui saute. Une boucle à compensation fixe y chasse, et le cycle
limite tombe dans la bande audible.
</div>

<div class="aide" id="lecture"></div>
<div id="tab"></div>
</main>
<script>
const VIN=/*VIN*/, LS=/*LS*/, FSW=/*FSW*/, NOTES=/*NOTES*/, D=/*DATA*/;
const GR=[["Frontière DCM/CCM (W)","W",0],
          ["Marge au point d'emploi — P_lim / 8 W","×",1],
          ["Ondulation à 8 W (A)","A",2]];
const cv=document.getElementById("c"), cx=cv.getContext("2d");
const W=cv.width,H=cv.height,CX=W/2+10,CY=H/2+46,S=Math.min(W,H)*0.60;
let az=-0.72, el=0.50, zoom=1, fi=1, ig=0, pts=[];

function proj(x,y,z){
  const X=(x-.5)*1.9, Y=(y-.5)*1.9, Z=(z-.5)*1.25;
  const ca=Math.cos(az), sa=Math.sin(az);
  const x1=X*ca-Y*sa, y1=X*sa+Y*ca;
  const ce=Math.cos(el), se=Math.sin(el);
  const y2=y1*ce-Z*se, z2=y1*se+Z*ce;
  const p=1/(1+y2*0.16);
  return [CX+x1*S*zoom*p, CY-z2*S*zoom*p, y2];
}
const gx=j=>j/(VIN.length-1), gy=i=>i/(LS.length-1);

function bornes(m){
  let lo=Infinity,hi=-Infinity;
  for(const r of m) for(const c of r){ const v=c[GR[ig][2]];
    if(v<lo)lo=v; if(v>hi)hi=v; }
  if(hi-lo<1e-9) hi=lo+1;
  return [lo,hi];
}
function coul(u,ecr){
  if(ecr) return "rgba(255,107,107,.30)";
  const h=215-150*Math.min(1,Math.max(0,u));
  return "hsla("+h+",62%,52%,.80)";
}

function dessine(){
  const m=D[FSW[fi]], [lo,hi]=bornes(m), q=GR[ig][2];
  const z=v=>(v-lo)/(hi-lo);
  cx.clearRect(0,0,W,H);

  /* socle */
  cx.strokeStyle="#2b3240"; cx.lineWidth=1;
  for(let i=0;i<LS.length;i++){
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
  for(let i=0;i<LS.length;i++){ const t=proj(-0.08,gy(i),0);
    cx.fillText(LS[i]+" µH",t[0],t[1]+4); }

  /* AXE VERTICAL au coin le plus ELOIGNE : ailleurs il passerait devant le
     relief. Recalcule a chaque rotation. Sans graduations en Z, la couleur
     seule ne donne pas une valeur -- le relief n'est pas mesurable. */
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
    cx.fillText(v.toFixed(hi<3?2:(hi<30?1:0)), p[0]+vers*11, p[1]+4);
    if(k>0&&k<5){
      const o=proj(coin.x, coin.x===coin.y?1-coin.y:coin.y, u);
      cx.strokeStyle="rgba(73,84,106,.35)";
      cx.beginPath(); cx.moveTo(p[0],p[1]); cx.lineTo(o[0],o[1]); cx.stroke();
    }
  }
  const mil=proj(coin.x,coin.y,0.5);
  cx.save(); cx.translate(mil[0]+vers*54,mil[1]); cx.rotate(-Math.PI/2);
  cx.textAlign="center"; cx.fillStyle="#e6e9ef"; cx.font="13px system-ui";
  cx.fillText(GR[ig][0],0,0); cx.restore();

  /* DALLE 5-10 W, uniquement sur la grandeur « frontiere » : elle montre ou
     la surface traverse la zone d'emploi. */
  if(q===0 && lo<P_HAUT && hi>P_BAS){
    for(const pw of [P_BAS,P_HAUT]){
      if(pw<lo||pw>hi) continue;
      const u=z(pw);
      cx.strokeStyle="rgba(255,107,107,.55)"; cx.lineWidth=1.2;
      cx.setLineDash([5,4]); cx.beginPath();
      const cs=[[0,0],[1,0],[1,1],[0,1]].map(([x,y])=>proj(x,y,u));
      cx.moveTo(cs[0][0],cs[0][1]);
      for(let k=1;k<4;k++) cx.lineTo(cs[k][0],cs[k][1]);
      cx.closePath(); cx.stroke(); cx.setLineDash([]);
    }
  }

  /* faces triees du plus loin au plus proche */
  const faces=[];
  for(let i=0;i<LS.length-1;i++) for(let j=0;j<VIN.length-1;j++){
    const qd=[[i,j],[i,j+1],[i+1,j+1],[i+1,j]];
    const pr=qd.map(([a,b])=>proj(gx(b),gy(a),z(m[a][b][q])));
    const v=qd.reduce((s,[a,b])=>s+m[a][b][q],0)/4;
    faces.push({pr, prof:pr.reduce((s,p)=>s+p[2],0)/4, v,
                ecr:qd.some(([a,b])=>m[a][b][3])});
  }
  faces.sort((a,b)=>b.prof-a.prof);
  for(const f of faces){
    cx.beginPath(); cx.moveTo(f.pr[0][0],f.pr[0][1]);
    for(let k=1;k<4;k++) cx.lineTo(f.pr[k][0],f.pr[k][1]);
    cx.closePath();
    cx.fillStyle=coul((f.v-lo)/(hi-lo), f.ecr&&q===0); cx.fill();
    cx.strokeStyle=f.ecr&&q===0?"rgba(255,107,107,.85)":"rgba(10,13,18,.55)";
    cx.lineWidth=f.ecr&&q===0?1.6:1; cx.stroke();
  }

  pts=[];
  for(let i=0;i<LS.length;i++) for(let j=0;j<VIN.length;j++){
    const c=m[i][j], p=proj(gx(j),gy(i),z(c[q]));
    pts.push({x:p[0],y:p[1],i,j,c});
    cx.beginPath(); cx.arc(p[0],p[1],c[3]&&q===0?4.2:2.8,0,7);
    cx.fillStyle=c[3]&&q===0?"#ff6b6b":"#0d1016";
    cx.strokeStyle=c[3]&&q===0?"#ff6b6b":"#cfe2ff";
    cx.lineWidth=1.2; cx.fill(); cx.stroke();
  }
  document.getElementById("leg").textContent=
    GR[ig][0]+" — de "+lo.toFixed(2)+" à "+hi.toFixed(2)+" "+GR[ig][1]
    +" · f_sw = "+FSW[fi]+" kHz · V_out = 80 V";
  tableau(m);
}

function tableau(m){
  let h="<table><tr><th>L</th>";
  for(const v of VIN) h+="<th>"+v+" V</th>";
  h+="</tr>";
  for(let i=0;i<LS.length;i++){
    h+="<tr><td>"+LS[i]+" µH</td>";
    for(let j=0;j<VIN.length;j++){
      const c=m[i][j];
      h+="<td"+(c[3]?' class="ko"':"")+">"+c[0].toFixed(1)+"</td>";
    }
    h+="</tr>";
  }
  h+="</table>";
  document.getElementById("tab").innerHTML=h;
  document.getElementById("lecture").innerHTML=
    "<b>Lecture.</b> Le tableau donne la frontière en watts. En rouge, les "
    +"cases où elle tombe entre 5 et 10 W. Plus l'inductance est grande, plus "
    +"la frontière descend — et plus elle risque de croiser la zone d'emploi. "
    +"Plus V<sub>in</sub> monte, plus elle remonte, en V<sub>in</sub>².";
}

function barres(){
  const bf=document.getElementById("bF"), bg=document.getElementById("bG");
  bf.innerHTML=""; bg.innerHTML="";
  FSW.forEach((f,k)=>{ const b=document.createElement("button");
    b.textContent=f+" kHz"; b.className=k===fi?"on":"";
    b.onclick=()=>{fi=k;barres();dessine();}; bf.appendChild(b); });
  GR.forEach((g,k)=>{ const b=document.createElement("button");
    b.textContent=g[0].split("—")[0].trim(); b.className=k===ig?"on":"";
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
    const c=best.c, L=LS[best.i], V=VIN[best.j];
    bulle.innerHTML="<b>"+L+" µH · V<sub>in</sub> "+V+" V · "+FSW[fi]
      +" kHz</b><br>frontière <b>"+c[0].toFixed(2)+" W</b><br>marge au point "
      +"d'emploi (8 W) : ×"+c[1].toFixed(2)+"<br>ondulation à 8 W : "
      +c[2].toFixed(2)+" A"
      +(c[3]?"<br><span style='color:#ff6b6b'><b>frontière DANS la zone "
        +"5–10 W</b> — la boucle y chasse</span>":"")
      +(NOTES[L]?"<br><span style='color:#9aa4b5'>"+NOTES[L]+"</span>":"");
    bulle.style.display="block";
    bulle.style.left=Math.min(r.width-290,(best.x/sx)+14)+"px";
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
const P_BAS=/*PBAS*/, P_HAUT=/*PHAUT*/;
barres(); dessine();
</script></body></html>
"""


def main():
    d = grille()
    h = (PAGE.replace("/*VIN*/", json.dumps(VIN))
             .replace("/*LS*/", json.dumps(LS))
             .replace("/*FSW*/", json.dumps(FSW))
             .replace("/*NOTES*/", json.dumps(NOTES, ensure_ascii=False))
             .replace("/*DATA*/", json.dumps(d))
             .replace("/*PBAS*/", str(P_BAS))
             .replace("/*PHAUT*/", str(P_HAUT)))
    HTML.write_text(h, encoding="utf-8")
    n = len(FSW) * len(LS) * len(VIN)
    print(f"{HTML.name} ecrit — {n} points ({len(FSW)} frequences x "
          f"{len(LS)} inductances x {len(VIN)} tensions)")
    # controle : combien de mailles tombent dans la zone a eviter
    for f in FSW:
        k = sum(c[3] for r in d[str(f)] for c in r)
        print(f"  {f:3d} kHz : {k:2d} / {len(LS)*len(VIN)} points ont leur "
              f"frontiere dans 5-10 W")


if __name__ == "__main__":
    main()
