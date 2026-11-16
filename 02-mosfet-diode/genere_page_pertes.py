"""Chapitre 2 (extension) -- assemble pertes-3d.html depuis le CSV du
balayage double-pulse.

Surfaces (perte) = f(frequence, puissance), une par MECANISME :
  Rds     conduction du switch        (mesure SPICE)
  Vf      conduction de la diode      (mesure SPICE)
  DCR     conduction de l'inductance  (mesure SPICE)
  Coss    energie de sortie du switch (modele analytique datasheet)
  grille  Qg x Vgs x fsw              (modele analytique datasheet)
  total   somme des cinq

La distinction mesure/modele est portee DANS la page (pastille sur chaque
bouton) : un lecteur doit pouvoir voir d'un coup d'oeil quelle surface
vient du simulateur et laquelle vient d'une integrale de datasheet.

Page autonome : pas de CDN, pas de dependance, s'ouvre au double-clic.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_boost2_dpt as g  # noqa: E402  -- matrice iso-mode (L et DCR par fsw)

ICI = Path(__file__).resolve().parent
CSV = ICI / "results" / "stage1_dpt_sweep.csv"
HTML = ICI / "pertes-3d.html"

MECANISMES = [
    ("p_cond_sw", "Rds — conduction switch", "spice"),
    ("p_cond_diode", "Vf — conduction diode", "spice"),
    ("p_dcr", "DCR — conduction inductance", "spice"),
    ("p_coss", "Coss — énergie de sortie", "modele"),
    ("p_gate", "Grille — Qg·Vgs·fsw", "modele"),
    ("p_total", "TOTAL", "mixte"),
]

BOITIERS = {
    "Si": "TO-252 (DPAK) · ROHM RD3P04BBKHRB · 30 mΩ",
    "FDT86113LZ": "SOT-223 · onsemi FDT86113LZ · 75 mΩ",
    "BSC070N10NS5": "SuperSO8 · Infineon OptiMOS 5 · 7 mΩ",
    "EPC2007C": "BGA chip-scale · EPC2007C (GaN) · 30 mΩ",
    "EPC2052": "BGA 1,5×1,5 mm · EPC2052 (GaN) · 13,5 mΩ",
}


def charge() -> dict:
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    fsw = sorted({float(r["fsw_khz"]) for r in rows})
    pout = sorted({float(r["pout_w"]) for r in rows})
    switches = [s for s in BOITIERS if any(r["switch"] == s for r in rows)]
    diodes = sorted({r["diode"] for r in rows})

    # grille [switch][diode][mecanisme] -> matrice [i_pout][j_fsw], None si trou
    data: dict = {}
    for s in switches:
        data[s] = {}
        for d in diodes:
            data[s][d] = {}
            idx = {(float(r["fsw_khz"]), float(r["pout_w"])): r
                   for r in rows if r["switch"] == s and r["diode"] == d}
            for cle, _, _ in MECANISMES:
                data[s][d][cle] = [
                    [float(idx[(f, p)][cle]) * 1e3 if (f, p) in idx else None
                     for f in fsw] for p in pout]
            data[s][d]["mode"] = [
                [idx[(f, p)]["mode"] if (f, p) in idx else None
                 for f in fsw] for p in pout]
            data[s][d]["eta"] = [
                [float(idx[(f, p)]["eta_pct"]) if (f, p) in idx else None
                 for f in fsw] for p in pout]
            # Irms de l'inductance : permet de RECALCULER la perte DCR a
            # une resistance de reference (P = Irms^2 R) sans resimuler.
            # Legitime parce que le point de fonctionnement est tenu fixe
            # par le reglage du rapport cyclique a la puissance visee : le
            # courant ne bouge pas quand on change la valeur de DCR.
            data[s][d]["il_rms"] = [
                [float(idx[(f, p)]["il_rms"]) if (f, p) in idx else None
                 for f in fsw] for p in pout]
    # SEUIL ET INDUCTANCE SONT DES TABLEAUX, INDEXES COMME `fsw` -- jamais
    # des dictionnaires keyes par la frequence.
    #
    # Un dict Python {200.0: ...} se serialise en JSON {"200.0": ...}, alors
    # que D.fsw[j] vaut le NOMBRE 200 cote JS, qui s'indexe en "200" : la
    # cle ne correspond pas et la lecture rend undefined. Le defaut est
    # silencieux tant qu'on ne fait qu'arithmetiser le resultat (un NaN ne
    # trace rien), et devient une TypeError fatale des qu'on lit un champ
    # dessus -- page entierement blanche. Indexer par position supprime la
    # classe de bug au lieu de la contourner.
    par_f = {}
    for r in rows:
        par_f.setdefault(float(r["fsw_khz"]), r)
    dcr_par_fsw = {f * 1e-3: d for f, _, d, _, _, _ in g.MATRICE_ISO_MODE}

    seuil = [float(par_f[f]["p_seuil_w"]) for f in fsw]
    lind = [dict(ref=par_f[f]["l_ref"],
                 l_uh=float(par_f[f]["l_uh"]),
                 dcr_mohm=round(dcr_par_fsw.get(f, 0.0) * 1e3, 2))
            for f in fsw]

    return dict(fsw=fsw, pout=pout, switches=switches, diodes=diodes,
                data=data, seuil=seuil, lind=lind,
                mecanismes=[[k, lab, src] for k, lab, src in MECANISMES],
                boitiers=BOITIERS)


PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pertes par mécanisme — boost 20→80 V</title>
<style>
:root{--bg:#11141a;--pan:#1a1f28;--gr:#2b3240;--tx:#e6e9ef;--tx2:#9aa4b5;
      --ac:#3ddc84;--wa:#ffb13d;--er:#ff6b6b;--bl:#4da3ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);
     font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:18px 22px 10px;border-bottom:1px solid var(--gr)}
h1{margin:0 0 4px;font-size:19px;font-weight:650}
.sub{color:var(--tx2);font-size:13px}
.wrap{display:flex;flex-wrap:wrap;gap:18px;padding:16px 22px 28px}
.side{flex:0 0 268px;min-width:238px}
.main{flex:1 1 560px;min-width:320px}
.grp{margin-bottom:16px}
.grp h2{font-size:11px;letter-spacing:.09em;text-transform:uppercase;
        color:var(--tx2);margin:0 0 7px;font-weight:600}
button{display:block;width:100%;text-align:left;margin:0 0 4px;padding:7px 10px;
       background:var(--pan);color:var(--tx);border:1px solid var(--gr);
       border-radius:6px;cursor:pointer;font:inherit;font-size:12.5px}
button:hover{border-color:#3d4657}
button.on{background:#223042;border-color:var(--ac);color:#fff}
.pill{float:right;font-size:9.5px;padding:1px 6px;border-radius:9px;
      text-transform:uppercase;letter-spacing:.05em;opacity:.85}
.pill.spice{background:#1d3a56;color:#8fc7ff}
.pill.modele{background:#4a3317;color:#ffc98a}
.pill.mixte{background:#2f3a24;color:#bfe08a}
.row{display:flex;gap:5px}.row button{margin-bottom:0}
canvas{width:100%;height:auto;display:block;background:var(--bg);
       border:1px solid var(--gr);border-radius:8px;touch-action:none}
.note{color:var(--tx2);font-size:12px;margin-top:10px}
.note b{color:var(--tx);font-weight:600}
#tip{position:fixed;pointer-events:none;opacity:0;transition:opacity .12s;
     background:#0c0f14;border:1px solid var(--gr);border-radius:7px;
     padding:8px 11px;font-size:12px;z-index:9;max-width:260px;
     box-shadow:0 6px 22px #0009}
#tip b{color:var(--ac)}
table{border-collapse:collapse;font-size:12px;margin-top:4px;width:100%}
td,th{border:1px solid var(--gr);padding:3px 7px;text-align:right}
th{color:var(--tx2);font-weight:600}td:first-child,th:first-child{text-align:left}
.tcap{margin-top:16px;font-size:13px;color:var(--tx)}
.tcap .tu{float:right;color:var(--tx2);font-size:12px}
.tsub{color:#6c7689;font-size:10.5px;font-weight:400}
td.dcm{background:#16202c;color:#8fc7ff}
td.vide{color:#5a6475}
.tleg{color:var(--tx2);font-size:11.5px;margin-top:5px}
.tleg b{color:var(--tx)}
</style></head><body>
<header>
  <h1>Pertes par mécanisme — boost 20 V → 80 V</h1>
  <div class="sub">Surface = perte en fonction de la fréquence et de la
  puissance de sortie. Balayage <b>iso-mode</b> : l'inductance est choisie à
  chaque fréquence pour placer la frontière DCM/CCM à ~15 W, donc la bascule
  de mode se produit au même endroit partout — <b>mais l'inductance n'est
  donc pas la même d'une fréquence à l'autre</b> (valeur, référence et DCR
  rappelés sous l'axe des fréquences et dans le tableau de gauche).</div>
</header>
<div class="wrap">
  <div class="side">
    <div class="grp"><h2>Mécanisme</h2><div id="bm"></div></div>
    <div class="grp"><h2>Transistor</h2><div id="bs"></div></div>
    <div class="grp"><h2>Diode</h2><div id="bd"></div></div>
    <div class="grp"><h2>Résistance d'inductance</h2>
      <button id="dreel" class="on">DCR réel de chaque pièce</button>
      <button id="dcst">DCR constant 10 mΩ</button></div>
    <div class="grp"><h2>Unité de l'axe Z</h2>
      <button id="umw" class="on">mW — perte absolue</button>
      <button id="upc">% de P<sub>out</sub> — perte relative</button>
      <button id="uet">η % — rendement</button></div>
    <div class="grp"><h2>Échelle Z</h2><div class="row">
      <button id="zlin" class="on">linéaire</button>
      <button id="zlog">log</button></div>
      <div class="row" style="margin-top:4px">
      <button id="eglob" class="on">globale</button>
      <button id="eloc">locale</button></div>
      <div class="row" style="margin-top:4px">
      <button id="ecr" class="on">écrêtée p95</button>
      <button id="ebrut">pleine</button></div></div>
    <div class="grp"><h2>Vue</h2><div class="row">
      <button id="v34" class="on">3/4</button>
      <button id="vface">face</button>
      <button id="vtop">dessus</button></div></div>
    <div class="note" id="info"></div>
  </div>
  <div class="main">
    <canvas id="c" width="1120" height="760"></canvas>
    <div class="note">
      <b>Pastille bleue</b> = mesuré par SPICE (300 à 1800 runs ngspice,
      topologie double-pulse à sortie raide). <b>Pastille orange</b> = calculé
      depuis la fiche constructeur : la perte Coss vient de l'intégrale
      ∫C<sub>oss</sub>(v)·v·dv sur la courbe du datasheet, et la perte de
      grille de Q<sub>g</sub>·V<sub>gs</sub>·f<sub>sw</sub> — deux mécanismes
      que cette netlist ne peut pas mesurer (un condensateur linéaire en SPICE
      donnerait le mauvais C<sub>oss</sub>, et la grille y est pilotée par une
      source idéale).
      <br><b>Glisser</b> pour tourner · <b>molette</b> pour zoomer ·
      <b>survol</b> pour le détail chiffré (les trois unités à la fois).
    </div>
    <div id="tab"></div>
  </div>
</div>
<div id="tip"></div>
<script>
const D = __DATA__;
let mec = "p_total", sw = D.switches[0], dio = D.diodes[0], zlog = false;
let unite = "mw";   // mw | pc | et
let echGlobale = true;
let ecrete = true;
let az = -0.62, el = 0.52, drag = null;

// Valeur affichee, selon l'unite choisie.
//   mw : perte absolue, telle que mesuree/calculee        (mW)
//   pc : la MEME perte rapportee a la puissance de sortie (%)
//   et : le rendement, qui ne depend PAS du mecanisme     (%)
// En rendement, plus c'est haut mieux c'est : l'echelle de couleur est
// donc inversee, pour que le vert reste toujours "bon".
const DCR_REF = 0.010;     // Ohm, au milieu de la plage reelle 3,15-21 mOhm
let dcrConst = false;

// Perte d'un mecanisme en mW, DCR substitue si demande.
// L'inductance CHANGE a chaque frequence (balayage iso-mode) et son DCR
// va de 3,15 a 21 mOhm : a 40 W cela represente 0,19 point de rendement,
// soit l'ordre de grandeur de l'effet de technologie recherche. Ramener
// toutes les frequences au MEME DCR retire ce biais et rend la tendance
// en frequence lisible. Les comparaisons ENTRE PIECES, elles, n'en ont
// pas besoin : a frequence donnee elles partagent la meme inductance.
function mWmec(i, j, cle, s, d){
  s = s || sw; d = d || dio;
  const v = D.data[s][d][cle][i][j];
  if(v == null) return null;
  if(!dcrConst) return v;
  const irms = D.data[s][d].il_rms[i][j];
  const dref = irms*irms*DCR_REF*1e3;
  if(cle === "p_dcr") return dref;
  if(cle === "p_total") return v - D.data[s][d].p_dcr[i][j] + dref;
  return v;
}
function etaAj(i, j, s, d){
  s = s || sw; d = d || dio;
  const e = D.data[s][d].eta[i][j];
  if(e == null || !dcrConst) return e;
  const tot = mWmec(i, j, "p_total", s, d);
  return 100 * D.pout[i] / (D.pout[i] + tot/1e3);
}
function val(i, j, s, d){
  if(unite === "et") return etaAj(i, j, s, d);
  const v = mWmec(i, j, mec, s, d);
  if(v == null) return null;
  return unite === "pc" ? v / (D.pout[i] * 10) : v;
}
const uniteLabel = () => unite === "mw" ? "mW" : "%";
const sensInverse = () => unite === "et";

const $ = s => document.querySelector(s);
const cv = $("#c"), cx = cv.getContext("2d");

function mk(host, items, cur, onpick){
  host.innerHTML = "";
  for(const it of items){
    const b = document.createElement("button");
    b.innerHTML = it.lab + (it.pill ? `<span class="pill ${it.pill}">${it.pill==="spice"?"mesuré":it.pill==="modele"?"modèle":"mixte"}</span>` : "");
    if(it.id === cur) b.className = "on";
    b.onclick = () => { onpick(it.id); build(); draw(); };
    host.appendChild(b);
  }
}
function build(){
  mk($("#bm"), D.mecanismes.map(([k,l,s]) => ({id:k, lab:l, pill:s})), mec, v => mec = v);
  mk($("#bs"), D.switches.map(s => ({id:s, lab:D.boitiers[s]})), sw, v => sw = v);
  mk($("#bd"), D.diodes.map(s => ({id:s, lab:s})), dio, v => dio = v);
  $("#zlin").className = zlog ? "" : "on";
  $("#zlog").className = zlog ? "on" : "";
  $("#ecr").className   = ecrete ? "on" : "";
  $("#ebrut").className = ecrete ? "" : "on";
  $("#eglob").className = echGlobale ? "on" : "";
  $("#eloc").className  = echGlobale ? "" : "on";
  $("#dreel").className = dcrConst ? "" : "on";
  $("#dcst").className  = dcrConst ? "on" : "";
  $("#umw").className = unite==="mw" ? "on" : "";
  $("#upc").className = unite==="pc" ? "on" : "";
  $("#uet").className = unite==="et" ? "on" : "";
}
// Matrice des valeurs AFFICHEES : tout l'aval (bornes, surface, survol,
// tableau) travaille dessus sans se soucier de l'unite choisie.
const grille = () => D.pout.map((_, i) => D.fsw.map((_, j) => val(i, j)));

// ECHELLE GLOBALE PAR DEFAUT : bornes calculees sur TOUTES les
// combinaisons transistor x diode, pas sur la seule affichee. Une echelle
// qui se recadre a chaque changement de piece fait paraitre semblables
// deux surfaces tres inegales -- c'est la vue qui ment, pas la donnee.
// L'echelle locale reste accessible pour detailler une piece isolee.
function bornes(){
  let lo = Infinity, hi = -Infinity;
  const combis = echGlobale
    ? [].concat(...D.switches.map(s => D.diodes.map(d => [s, d])))
    : [[sw, dio]];
  for(const [s, d] of combis)
    for(let i=0;i<D.pout.length;i++) for(let j=0;j<D.fsw.length;j++){
      const v = val(i, j, s, d);
      if(v != null){ lo = Math.min(lo,v); hi = Math.max(hi,v); }
    }
  // RENDEMENT : fenetre FIXE 85-100 %. Les pertes s'etalant sur un facteur
  // 40 entre 5 et 60 W, une echelle automatique ecrase la zone utile ou se
  // joue la comparaison (94-99 %).
  if(unite === "et") return [85, 100];
  // PERTES : ecretage au 95e centile. Le maximum reel (3449 mW, SOT-223 +
  // ultrafast a 800 kHz / 60 W) est physique, mais il ecrase les points a
  // faible charge. Les surfaces au-dela sont DECOUPEES A L'AFFICHAGE, pas
  // retirees des donnees -- le survol et le tableau donnent toujours la
  // valeur vraie.
  if(!ecrete){ /* bornes brutes */ }
  else {
    const tous = [];
    for(const [s2, d2] of combis)
      for(let i=0;i<D.pout.length;i++) for(let j=0;j<D.fsw.length;j++){
        const v = val(i, j, s2, d2); if(v != null) tous.push(v);
      }
    if(tous.length > 8){
      tous.sort((a,b)=>a-b);
      hi = tous[Math.floor(0.95*(tous.length-1))];
    }
  }
  if(!isFinite(lo)){ lo = 0; hi = 1; }
  if(zlog){ lo = Math.max(lo, 1e-3); }
  if(hi === lo) hi = lo + 1;
  return [lo, hi];
}
const zt0 = (v, lo, hi) => zlog
  ? (Math.log10(Math.max(v,1e-3)) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo))
  : (v - lo) / (hi - lo);
// borne a [0,1] : une valeur au-dela de l'ecretage se pose sur le plafond
// au lieu de sortir du volume
const zt = (v, lo, hi) => Math.max(0, Math.min(1, zt0(v, lo, hi)));

function coul(t){
  t = Math.max(0, Math.min(1, t));
  const stops = [[0,[61,220,132]],[.5,[255,177,61]],[1,[255,107,107]]];
  for(let i=0;i<stops.length-1;i++){
    const [a,ca]=stops[i], [b,cb]=stops[i+1];
    if(t<=b){ const u=(t-a)/(b-a);
      return `rgb(${ca.map((c,k)=>Math.round(c+(cb[k]-c)*u)).join(",")})`; }
  }
  return "rgb(255,107,107)";
}

const W = cv.width, H = cv.height, CX = W*0.52, CY = H*0.56, S = Math.min(W,H)*0.46;
let zoom = 1.0;

// Projection : rotation d'azimut autour de la verticale, puis basculement
// d'elevation, puis perspective legere.
//   y_ecran = -(pz*cos(el) - Y*sin(el))
// La HAUTEUR doit venir en premier terme. Avec la forme inverse
// (Y*cos - pz*sin), les Z croissants partent vers le BAS de l'ecran,
// puisque l'axe y d'un canvas est oriente vers le bas -- la surface se
// retrouve retournee.
function proj(x, y, z){           // x,y,z dans [0,1]
  const px = (x-.5), py = (y-.5), pz = (z-.5);
  const ca=Math.cos(az), sa=Math.sin(az);
  const X = px*ca - py*sa, Y = px*sa + py*ca;
  const ce=Math.cos(el), se=Math.sin(el);
  const haut  = pz*ce - Y*se;     // vers le HAUT de l'ecran
  const prof  = Y*ce + pz*se;     // profondeur, pour le peintre
  const d = 3.2, k = d/(d - prof*0.55);
  const s = S*k*zoom*1.25;
  return [CX + X*s, CY - haut*s, prof];
}

let quads = [], pts2d = [], sel2d = null, epingle = false;
function draw(){
  cx.clearRect(0,0,W,H);
  const g = grille(), [lo,hi] = bornes();
  const nf = D.fsw.length, np = D.pout.length;
  const gx = j => nf===1?0.5:j/(nf-1), gy = i => np===1?0.5:i/(np-1);

  // --- plancher + graduations
  cx.strokeStyle = "#2b3240"; cx.lineWidth = 1; cx.font = "12px system-ui";
  for(let j=0;j<nf;j++){
    const a=proj(gx(j),0,0), b=proj(gx(j),1,0);
    cx.beginPath(); cx.moveTo(a[0],a[1]); cx.lineTo(b[0],b[1]); cx.stroke();
    const t=proj(gx(j),-0.07,0), dy = (j%2?16:0);
    cx.textAlign="center";
    cx.fillStyle="#9aa4b5"; cx.font="12px system-ui";
    cx.fillText(D.fsw[j]+" kHz", t[0], t[1]+dy);
    // L'inductance accompagne TOUJOURS la frequence : elle change a chaque
    // pas du balayage iso-mode, et c'est elle qui porte la variation de la
    // surface DCR. L'afficher ailleurs reviendrait a la cacher.
    const li = D.lind[j];
    cx.fillStyle = mec==="p_dcr" ? "#ffb13d" : "#6c7689";
    cx.font = (mec==="p_dcr" ? "600 " : "") + "11px system-ui";
    cx.fillText(li.l_uh.toFixed(0)+" µH · "
                +(dcrConst ? (DCR_REF*1e3).toFixed(2)+" mΩ*" : li.dcr_mohm.toFixed(2)+" mΩ"),
                t[0], t[1]+dy+13);
  }
  for(let i=0;i<np;i++){
    const a=proj(0,gy(i),0), b=proj(1,gy(i),0);
    cx.beginPath(); cx.moveTo(a[0],a[1]); cx.lineTo(b[0],b[1]); cx.stroke();
    const t=proj(-0.08,gy(i),0);
    cx.fillStyle="#9aa4b5"; cx.textAlign="right";
    cx.fillText(D.pout[i]+" W", t[0], t[1]+4);
  }
  // --- frontiere DCM/CCM : la puissance de seuil, projetee au sol
  cx.strokeStyle="#4da3ff"; cx.lineWidth=2; cx.setLineDash([5,4]); cx.beginPath();
  for(let j=0;j<nf;j++){
    const ps=D.seuil[j];
    const u=(ps-D.pout[0])/(D.pout[np-1]-D.pout[0]);
    const p=proj(gx(j), Math.max(0,Math.min(1,u)), 0);
    j?cx.lineTo(p[0],p[1]):cx.moveTo(p[0],p[1]);
  }
  cx.stroke(); cx.setLineDash([]);

  // --- CELLULES ABSENTES, marquees au sol. Une tuile exige ses QUATRE
  // sommets : une cellule manquante en supprime jusqu'a quatre, d'ou des
  // trous bien plus larges que les donnees absentes. Sans marque, le
  // lecteur ne peut pas distinguer un trou de donnees d'un creux reel.
  for(let i=0;i<np;i++) for(let j=0;j<nf;j++){
    if(g[i][j] != null) continue;
    const p = proj(gx(j), gy(i), 0);
    cx.strokeStyle = "#7a8398"; cx.lineWidth = 1.6;
    cx.beginPath();
    cx.moveTo(p[0]-5,p[1]-5); cx.lineTo(p[0]+5,p[1]+5);
    cx.moveTo(p[0]+5,p[1]-5); cx.lineTo(p[0]-5,p[1]+5);
    cx.stroke();
  }

  // --- surface, peintre (du fond vers l'avant)
  quads = [];
  for(let i=0;i<np-1;i++) for(let j=0;j<nf-1;j++){
    const vs=[g[i][j],g[i][j+1],g[i+1][j+1],g[i+1][j]];
    if(vs.some(v=>v==null)) continue;
    const cs=[[gx(j),gy(i)],[gx(j+1),gy(i)],[gx(j+1),gy(i+1)],[gx(j),gy(i+1)]];
    const pts=cs.map((c,k)=>proj(c[0],c[1],zt(vs[k],lo,hi)));
    quads.push({pts, z:pts.reduce((s,p)=>s+p[2],0)/4,
                v:vs.reduce((s,x)=>s+x,0)/4, i, j});
  }
  quads.sort((a,b)=>a.z-b.z);
  for(const q of quads){
    cx.beginPath(); q.pts.forEach((p,k)=>k?cx.lineTo(p[0],p[1]):cx.moveTo(p[0],p[1]));
    cx.closePath();
    const tq=zt(q.v,lo,hi); cx.fillStyle=coul(sensInverse()?1-tq:tq);
    cx.globalAlpha=.9; cx.fill();
    cx.globalAlpha=1; cx.strokeStyle="#0d1016"; cx.lineWidth=.8; cx.stroke();
  }
  // --- points, marques selon le mode. On MEMORISE leur position ecran :
  // c'est elle qui sert a la selection au survol (recherche du point le
  // plus proche), et non un test d'appartenance a un quadrilatere -- ce
  // dernier ne designe pas un point et rate les trous de la grille.
  const md=D.data[sw][dio].mode;
  pts2d = [];
  for(let i=0;i<np;i++) for(let j=0;j<nf;j++){
    if(g[i][j]==null) continue;
    const p=proj(gx(j),gy(i),zt(g[i][j],lo,hi));
    pts2d.push({x:p[0], y:p[1], i, j});
    const sel = (sel2d && sel2d.i===i && sel2d.j===j);
    cx.beginPath(); cx.arc(p[0],p[1],sel?7:(md[i][j]==="DCM"?4.5:3),0,7);
    cx.fillStyle=sel?"#3ddc84":(md[i][j]==="DCM"?"#11141a":"#e6e9ef");
    cx.strokeStyle=sel?"#3ddc84":"#e6e9ef"; cx.lineWidth=sel?2.4:1.4;
    cx.fill(); cx.stroke();
    if(sel){   // ligne de rappel vers le sol, pour situer le point
      const s0=proj(gx(j),gy(i),0);
      cx.setLineDash([3,3]); cx.strokeStyle="#3ddc84"; cx.lineWidth=1.2;
      cx.beginPath(); cx.moveTo(p[0],p[1]); cx.lineTo(s0[0],s0[1]); cx.stroke();
      cx.setLineDash([]);
    }
  }
  // --- AXE Z VERTICAL, avec graduations chiffrees. Sans lui une surface
  // 3D n'est pas lisible : on voit un relief mais aucune valeur.
  const nd = v => v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(2);
  const ticks = [];
  if(zlog){
    const a=Math.floor(Math.log10(lo)), b=Math.ceil(Math.log10(hi));
    for(let e=a;e<=b;e++) for(const m of [1,2,5]){
      const v=m*Math.pow(10,e); if(v>=lo&&v<=hi) ticks.push(v);
    }
  } else {
    const pas=Math.pow(10,Math.floor(Math.log10(hi-lo)));
    const st=(hi-lo)/pas>5?pas*2:(hi-lo)/pas>2?pas:pas/2;
    for(let v=Math.ceil(lo/st)*st; v<=hi; v+=st) ticks.push(v);
  }
  cx.strokeStyle="#4b566b"; cx.lineWidth=1.3;
  const z0=proj(0,0,0), z1=proj(0,0,1);
  cx.beginPath(); cx.moveTo(z0[0],z0[1]); cx.lineTo(z1[0],z1[1]); cx.stroke();
  cx.font="11.5px system-ui"; cx.textAlign="right";
  for(const v of ticks.slice(0,9)){
    const p=proj(0,0,zt(v,lo,hi)), q=proj(-0.035,0,zt(v,lo,hi));
    cx.strokeStyle="#4b566b"; cx.beginPath();
    cx.moveTo(p[0],p[1]); cx.lineTo(q[0],q[1]); cx.stroke();
    cx.fillStyle="#c3cad6"; cx.fillText(nd(v), q[0]-3, q[1]+4);
  }
  const zt_lab=proj(-0.035,0,1.06);
  cx.fillStyle="#e6e9ef"; cx.font="600 12px system-ui"; cx.textAlign="center";
  cx.fillText(uniteLabel(), zt_lab[0], zt_lab[1]);

  // --- barre de couleur
  cx.font="12px system-ui"; cx.textAlign="left";
  cx.fillStyle="#9aa4b5";
  cx.fillText(`${nd(lo)} ${uniteLabel()}`, 16, H-18);
  cx.fillText(`${nd(hi)} ${uniteLabel()}`, 16, 26);
  for(let k=0;k<60;k++){
    const t=1-k/59; cx.fillStyle=coul(sensInverse()?1-t:t);
    cx.fillRect(16,34+k*((H-62)/60),13,((H-62)/60)+1);
  }
  cx.fillStyle="#e6e9ef"; cx.font="600 13px system-ui";
  const lab = unite==="et" ? "Rendement η"
            : D.mecanismes.find(m=>m[0]===mec)[1]
              + (unite==="pc" ? " — en % de Pout" : " — perte absolue");
  cx.fillText(`${lab} — ${sw} / diode ${dio}`, 46, 26);
  cx.font="12px system-ui"; cx.fillStyle="#9aa4b5";
  cx.fillText("cercle plein = CCM · cercle creux = DCM · tireté bleu = seuil DCM/CCM"
    + " · échelle " + (echGlobale ? "GLOBALE (comparable entre pièces)"
                                  : "LOCALE (⚠ non comparable)"), 46, 44);
  if(unite==="et"){
    cx.fillStyle="#ffb13d";
    cx.fillText("η est global : il ne dépend pas du mécanisme sélectionné.", 46, 62);
  } else if(dcrConst && (mec==="p_total" || unite==="et")){
    cx.fillStyle="#ffb13d";
    cx.fillText("DCR imposé à " + (DCR_REF*1e3).toFixed(0) + " mΩ sur toutes les"
      + " fréquences : tendance en fréquence lisible, mais ce n'est plus le rendement"
      + " d'un montage réel.", 46, 62);
  } else if(mec==="p_dcr"){
    // sans cet avertissement on lirait un "effet de frequence" la ou il
    // n'y a qu'un changement de piece
    cx.fillStyle="#ffb13d";
    cx.fillText(dcrConst
      ? "DCR ramené à " + (DCR_REF*1e3).toFixed(0) + " mΩ partout : la surface ne"
        + " montre plus que l'effet du COURANT, le changement de pièce est neutralisé."
      : "⚠ L'inductance CHANGE à chaque fréquence (voir sous l'axe) :"
        + " la variation en fréquence est un changement de pièce, pas un effet de fréquence.",
      46, 62);
  }
  tableau();
}

function tableau(){
  const g=grille(), md=D.data[sw][dio].mode;
  const lab = unite==="et" ? "Rendement η"
            : D.mecanismes.find(m=>m[0]===mec)[1];
  // Un tableau de chiffres sans titre ni unite n'est pas une donnee, c'est
  // une devinette : les deux sont rappeles ici, ainsi que le sens des deux
  // marques employees dans les cellules.
  let h = `<div class="tcap"><b>${lab}</b> — ${sw} / diode ${dio}`
        + `<span class="tu">valeurs en ${uniteLabel()}</span></div>`
        + `<table><tr><th>P<sub>out</sub> \\ f<sub>sw</sub></th>`
        + D.fsw.map((f,j)=>`<th>${f} kHz<br><span class="tsub">${D.lind[j].l_uh.toFixed(0)} µH</span></th>`).join("")
        + "</tr>";
  for(let i=D.pout.length-1;i>=0;i--){
    h+=`<tr><td>${D.pout[i]} W</td>`;
    for(let j=0;j<D.fsw.length;j++){
      const v=g[i][j];
      if(v==null){
        h+='<td class="vide" title="cellule non résolue : la puissance visée '
          +'n\\'a pas pu être encadrée">—</td>';
      } else {
        const dcm = md[i][j]==="DCM";
        h+=`<td class="${dcm?"dcm":""}" title="${D.fsw[j]} kHz · ${D.pout[i]} W`
          +` — mode ${md[i][j]} · η ${etaAj(i,j).toFixed(2)} %">`
          +`${v.toFixed(v<10?2:0)}${dcm?"°":""}</td>`;
      }
    }
    h+="</tr>";
  }
  h += '</table><div class="tleg">'
     + "<b>°</b> et fond bleuté = point en <b>conduction discontinue (DCM)</b>, "
     + "sous le seuil de ~15 W · <b>—</b> = cellule non résolue "
     + "(17 sur 360, au coin 5-8 W) · survol d'une cellule pour le mode et η."
     + "<br><b>✕ au sol</b> = cellule absente. Une tuile exige ses quatre "
     + "sommets, donc une cellule manquante en supprime jusqu'à quatre : "
     + "les trous sont plus larges que les données absentes."
     + (ecrete && unite !== "et"
        ? " · Échelle <b>écrêtée au 95ᵉ centile</b> : les sommets au-delà sont "
          + "aplatis au plafond, le survol et le tableau donnent la valeur vraie."
        : "") + "</div>";
  $("#tab").innerHTML = h;
  const nd = md.flat().filter(x=>x==="DCM").length, nt = md.flat().filter(x=>x).length;
  // L'inductance EST une donnee du balayage, pas un detail de legende :
  // une valeur differente a chaque frequence, chacune avec son DCR.
  const linds = D.fsw.map((f,j)=>{
    const l=D.lind[j];
    return `<tr><td>${f}k</td><td>${l.l_uh.toFixed(0)} µH</td>`+
           `<td>${l.dcr_mohm.toFixed(2)} mΩ</td>`+
           `<td style="text-align:left;font-size:11px">${l.ref}</td></tr>`;
  }).join("");
  $("#info").innerHTML =
    `<b>${nt}</b> points exploités pour cette combinaison, dont `+
    `<b>${nd}</b> en DCM.`+
    `<div class="tcap" style="margin-top:12px">Inductance par fréquence`+
    `<span class="tu">balayage iso-mode</span></div>`+
    `<table><tr><th>f<sub>sw</sub></th><th>L</th><th>DCR typ</th>`+
    `<th style="text-align:left">référence</th></tr>${linds}</table>`;
}

// --- interaction
cv.addEventListener("pointerdown", e=>{drag=[e.clientX,e.clientY]; cv.setPointerCapture(e.pointerId);});
for(const ev of ["pointerup","pointercancel","lostpointercapture"])
  cv.addEventListener(ev, ()=>drag=null);
// molette = zoom
cv.addEventListener("wheel", e=>{
  e.preventDefault();
  zoom = Math.max(0.45, Math.min(3.5, zoom * (e.deltaY < 0 ? 1.12 : 1/1.12)));
  draw();
}, {passive:false});
cv.addEventListener("pointermove", e=>{
  const r=cv.getBoundingClientRect(), sx=cv.width/r.width;
  if(drag){
    // L'ORIGINE DU GLISSEMENT EST REMISE A JOUR A CHAQUE DEPLACEMENT.
    // En la gardant fixe, l'elevation accumule contre sa butee : une fois
    // celle-ci atteinte, il faut re-parcourir toute la distance en sens
    // inverse avant que la vue ne bouge a nouveau -- ce qui se ressent
    // exactement comme une rotation bloquee.
    az += (e.clientX-drag[0])*0.009*sx;
    el  = Math.max(0.08, Math.min(1.40, el - (e.clientY-drag[1])*0.008*sx));
    drag = [e.clientX, e.clientY];
    draw(); return;
  }
  if(epingle) return;                       // point epingle : on n'ecoute plus le survol
  const mx=(e.clientX-r.left)*sx, my=(e.clientY-r.top)*sx;
  const p = plusProche(mx, my);
  // ne redessiner que si la SELECTION change : sinon on repeindrait toute
  // la scene a chaque pixel parcouru par la souris
  const change = (p ? p.i+","+p.j : null) !== (sel2d ? sel2d.i+","+sel2d.j : null);
  if(p){ sel2d = p; bulle(p, e.clientX, e.clientY); }
  else { sel2d = null; $("#tip").style.opacity = 0; }
  if(change) draw();
});

// Point le plus proche du curseur, dans un rayon de tolerance. Travaille
// en coordonnees ECRAN : indifferent a l'orientation de la vue et aux
// trous de la grille, contrairement a un test d'appartenance de surface.
function plusProche(mx, my){
  let best = null, bd = 26 * 26;
  for(const p of pts2d){
    const d = (p.x-mx)*(p.x-mx) + (p.y-my)*(p.y-my);
    if(d < bd){ bd = d; best = p; }
  }
  return best;
}

function bulle(p, cxp, cyp){
  const i = p.i, j = p.j;
  const md = D.data[sw][dio].mode;
  const mw = mWmec(i, j, mec), eta = etaAj(i, j);
  const tip = $("#tip");
  // la bulle donne les TROIS unites d'un coup, quelle que soit celle qui
  // pilote la surface -- c'est la question qu'on se pose en regardant un point
  tip.innerHTML = `<b>${D.fsw[j]} kHz · ${D.pout[i]} W</b> — ${sw} / ${dio}<br>`+
    `<span style="color:#9aa4b5">${D.mecanismes.find(m=>m[0]===mec)[1]}</span><br>`+
    `perte <b>${mw.toFixed(2)} mW</b> = <b>${(mw/(D.pout[i]*10)).toFixed(3)} %</b> de P<sub>out</sub><br>`+
    `η global <b>${eta.toFixed(2)} %</b> · mode <b>${md[i][j]}</b><br>`+
    `<span style="color:#9aa4b5">seuil DCM/CCM ${D.seuil[j].toFixed(1)} W</span><br>`+
    `<span style="color:#9aa4b5">inductance <b style="color:#e6e9ef">${D.lind[j].ref}</b>`+
    ` — ${D.lind[j].l_uh.toFixed(0)} µH, DCR `+
    (dcrConst ? `<b style="color:#ffb13d">${(DCR_REF*1e3).toFixed(2)} mΩ imposé</b>`
              : `${D.lind[j].dcr_mohm.toFixed(2)} mΩ typ`)+`</span>`+
    (epingle ? `<br><span style="color:#ffb13d">épinglé — recliquer pour libérer</span>` : "");
  const dx = cxp > window.innerWidth - 300 ? -270 : 16;
  tip.style.left = (cxp+dx)+"px"; tip.style.top = (cyp+14)+"px";
  tip.style.opacity = 1;
}

// clic = epingler / liberer le point courant
cv.addEventListener("click", e=>{
  const r=cv.getBoundingClientRect(), sx=cv.width/r.width;
  const p = plusProche((e.clientX-r.left)*sx, (e.clientY-r.top)*sx);
  if(!p){ epingle=false; sel2d=null; $("#tip").style.opacity=0; draw(); return; }
  epingle = !(epingle && sel2d && sel2d.i===p.i && sel2d.j===p.j);
  sel2d = p; bulle(p, e.clientX, e.clientY); draw();
});
cv.addEventListener("pointerleave",()=>{
  if(!epingle){ sel2d=null; $("#tip").style.opacity=0; draw(); }
});
$("#zlin").onclick=()=>{zlog=false;build();draw();};
$("#zlog").onclick=()=>{zlog=true;build();draw();};
// le rendement varie de ~96 a ~99 % : une echelle log n'y a aucun sens,
// on repasse donc en lineaire d'office
$("#ecr").onclick  =()=>{ecrete=true; build();draw();};
$("#ebrut").onclick=()=>{ecrete=false;build();draw();};
$("#eglob").onclick=()=>{echGlobale=true; build();draw();};
$("#eloc").onclick =()=>{echGlobale=false;build();draw();};
$("#dreel").onclick=()=>{dcrConst=false;build();draw();};
$("#dcst").onclick =()=>{dcrConst=true; build();draw();};
$("#umw").onclick=()=>{unite="mw";build();draw();};
$("#upc").onclick=()=>{unite="pc";build();draw();};
$("#uet").onclick=()=>{unite="et";zlog=false;build();draw();};
$("#v34").onclick=()=>{az=-0.62;el=0.52;zoom=1;draw();};
$("#vface").onclick=()=>{az=0;el=0.14;zoom=1;draw();};
$("#vtop").onclick=()=>{az=0;el=1.38;zoom=1;draw();};
build(); draw();
</script></body></html>
"""


def verifie(d: dict) -> list[str]:
    """Rejoue les acces aux donnees que fera draw() cote navigateur.

    Raison d'etre : un acces qui rend None ici rend `undefined` la-bas, et
    toute lecture de champ dessus leve une TypeError qui tue la fonction
    entiere -- page blanche, sans message visible pour qui ouvre le fichier.
    C'est exactement ce qui est arrive en indexant `seuil`/`lind` par la
    frequence : un dict Python {200.0: ...} devient {"200.0": ...} en JSON,
    alors que D.fsw[j] vaut le NOMBRE 200, qui s'indexe en "200". Le defaut
    restait muet tant qu'on ne faisait qu'arithmetiser le resultat (un NaN
    ne trace rien), puis est devenu fatal des la premiere lecture de champ.
    Un controle de SYNTAXE ne voit rien de tout cela.
    """
    pb: list[str] = []
    mecs = [m[0] for m in d["mecanismes"]]
    nf, np_ = len(d["fsw"]), len(d["pout"])

    for nom in ("seuil", "lind"):
        if not isinstance(d[nom], list):
            pb.append(f"{nom} doit etre un TABLEAU indexe comme fsw, pas un dict "
                      f"(keye par la frequence, les cles JSON ne correspondraient pas)")
        elif len(d[nom]) != nf:
            pb.append(f"{nom} mal dimensionne ({len(d[nom])} != {nf})")
    if pb:
        return pb        # structure fausse : inutile d'aller plus loin
    for j in range(nf):
        for k in ("ref", "l_uh", "dcr_mohm"):
            if d["lind"][j].get(k) is None:
                pb.append(f"lind[{j}].{k} vide")

    for sw in d["switches"]:
        if not d["boitiers"].get(sw):
            pb.append(f"boitiers[{sw}] vide")
        for dio in d["diodes"]:
            g = d["data"].get(sw, {}).get(dio)
            if g is None:
                pb.append(f"data[{sw}][{dio}] absent")
                continue
            for cle in mecs + ["mode", "eta", "il_rms"]:
                if cle not in g:
                    pb.append(f"data[{sw}][{dio}].{cle} absent")
                elif len(g[cle]) != np_ or len(g[cle][0]) != nf:
                    pb.append(f"data[{sw}][{dio}].{cle} mal dimensionne")
            # la substitution a DCR constant exige il_rms partout ou il y a
            # un total : sans lui le recalcul rendrait NaN
            for i in range(np_):
                for j in range(nf):
                    if g["p_total"][i][j] is not None:
                        for cle in ("il_rms", "eta", "mode"):
                            if g[cle][i][j] is None:
                                pb.append(f"{cle} manquant en {sw}/{dio}/{i},{j}")
    return pb


# node embarque par CCStudio (application Electron). Sans moteur JS, on ne
# peut verifier QUE la syntaxe a la main -- et un controle d'equilibre des
# delimiteurs ecrit a la main NE VOIT PAS une chaine fermee trop tot :
#     h += "</table><div class="tleg">"
# y passe pour equilibree alors que `tleg` y devient un identifiant nu. Ce
# defaut a laisse la page entierement morte (HTML statique affiche, aucun
# script execute) a travers plusieurs passes de verification maison.
NODE = Path(r"C:/ti/ccs2100/ccs/tools/node/node.exe")

HARNESS = r"""
const noop = () => {};
const ctx = new Proxy({}, { get: (t, p) =>
  p === "measureText" ? (() => ({width: 10}))
  : p === "isPointInPath" ? (() => false) : noop, set: () => true });
const mkEl = () => new Proxy({ style:{} }, {
  get: (t, p) => p in t ? t[p]
      : p === "appendChild" || p === "addEventListener"
        || p === "setPointerCapture" ? noop
      : p === "getContext" ? (() => ctx)
      : p === "getBoundingClientRect" ? (() => ({left:0,top:0,width:1120,height:760}))
      : p === "width" ? 1120 : p === "height" ? 760 : "",
  set: (t, p, v) => { t[p] = v; return true; } });
const els = {};
globalThis.document = { querySelector: s => (els[s] = els[s] || mkEl()),
                        createElement: () => mkEl() };
globalThis.window = { innerWidth: 1600, innerHeight: 900 };
require(process.argv[2]);
const t = els["#tab"];
if (!t || !t.innerHTML || t.innerHTML.length < 200)
  { console.error("draw() n'a pas rempli le tableau"); process.exit(1); }
console.log("OK " + t.innerHTML.length);
"""


def valide_js(html: Path) -> list[str]:
    """Verifie la SYNTAXE puis l'EXECUTION du script, avec un vrai moteur."""
    import re
    import subprocess
    import tempfile

    if not NODE.is_file():
        return ["node introuvable : validation JS NON FAITE (page non vérifiée)"]
    js = re.search(r"<script>(.*)</script>", html.read_text(encoding="utf-8"),
                   re.S).group(1)
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "page.js"
        f.write_text(js, encoding="utf-8")
        r = subprocess.run([str(NODE), "--check", str(f)],
                           capture_output=True, text=True)
        if r.returncode:
            return ["syntaxe : " + (r.stderr.strip().splitlines() or ["?"])[0]]
        h = Path(td) / "h.js"
        h.write_text(HARNESS, encoding="utf-8")
        r = subprocess.run([str(NODE), str(h), str(f)],
                           capture_output=True, text=True)
        if r.returncode:
            return ["exécution : " + (r.stderr.strip().splitlines() or ["?"])[-1]]
    return []


def main() -> int:
    if not CSV.is_file():
        print(f"CSV absent : {CSV}")
        return 1
    d = charge()
    pb = verifie(d)
    if pb:
        print(f"ABANDON -- {len(pb)} probleme(s) qui rendraient la page blanche :")
        for x in pb[:15]:
            print("   -", x)
        return 1
    HTML.write_text(PAGE.replace("__DATA__", json.dumps(d, ensure_ascii=False)),
                    encoding="utf-8")
    n = sum(1 for s in d["switches"] for di in d["diodes"]
            for r in d["data"][s][di]["p_total"] for v in r if v is not None)
    print(f"{HTML}  ({HTML.stat().st_size // 1024} ko, {n} points)")
    print(f"  acces aux donnees : OK ({n} points, {len(d['mecanismes'])} mecanismes)")

    pbjs = valide_js(HTML)
    if pbjs:
        print("  JS : ECHEC")
        for x in pbjs:
            print("     -", x)
        return 1
    print("  JS : OK (syntaxe + execution sous DOM simule)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
