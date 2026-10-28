// シネマのベース（コピー）から、アプリが文字・画像を置く場所を書き出し、それらを消した背景PDFを作る
// 座標はすべて mm・アートボード左上が原点・下向きが+
var K=2.83465, OUT="/Users/kc02/.company/engineering/cinema-app/template/";
for (var d=app.documents.length-1;d>=0;d--){ if (app.documents[d].name.indexOf("_base")>0) app.documents[d].close(SaveOptions.DONOTSAVECHANGES); }
var doc=app.open(new File(OUT+"シネマ_base.ai"));
var ab=doc.artboards[0].artboardRect, MIDX=(ab[0]+ab[2])/2;
function r2(v){ return Math.round(v*1000)/1000; }
function box(it){ var b=it.geometricBounds; return {x:r2(b[0]/K), y:r2(-b[1]/K), w:r2((b[2]-b[0])/K), h:r2((b[1]-b[3])/K)}; }
function onAB(it){ var b=it.geometricBounds; return b[0]>=ab[0]-1 && b[2]<=ab[2]+1 && b[3]>=ab[3]-1; }
function keyOf(it){ var b=it.geometricBounds, cx=(b[0]+b[2])/2; if (-b[1]/K<103) return (cx<MIDX)?"kiso":"kaka"; return (cx<MIDX)?"gifu":"ina"; }
function col(c){ try{ if(c.typename=="CMYKColor") return {cmyk:[c.cyan,c.magenta,c.yellow,c.black]}; if(c.typename=="SpotColor"){ var s=c.spot.color; return {cmyk:[s.cyan,s.magenta,s.yellow,s.black], tint:c.tint, spot:c.spot.name}; } return {t:c.typename}; }catch(e){ return {t:"?"}; } }
function sty(t){ var a=t.characters[0].characterAttributes, pa=t.paragraphs[0].paragraphAttributes; var o={font:a.textFont.name, size:r2(a.size), hs:r2(a.horizontalScale), tracking:a.tracking, color:col(a.fillColor), just:String(pa.justification)};
  try{ o.leading=r2(a.leading/K); }catch(e){} try{ o.anchor={x:r2(t.anchor[0]/K), y:r2(-t.anchor[1]/K)}; }catch(e){} o.kind=String(t.kind); o.box=box(t); return o; }
function J(v){ // 簡易JSON
  if (v===null||v===undefined) return "null"; if (typeof v=="number") return String(v); if (typeof v=="boolean") return v?"true":"false";
  if (typeof v=="string") return '"'+v.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r/g,"\\r").replace(/\n/g,"\\n")+'"';
  if (v instanceof Array){ var a=[]; for (var i=0;i<v.length;i++) a.push(J(v[i])); return "["+a.join(",")+"]"; }
  var a=[]; for (var k in v) a.push(J(k)+":"+J(v[k])); return "{"+a.join(",")+"}"; }
var L={theaters:{kiso:{},kaka:{},gifu:{},ina:{}}, table:{}}, del=[];
for (var i=0;i<doc.textFrames.length;i++){ var t=doc.textFrames[i]; if (!onAB(t)) continue; var c=t.contents, b=t.geometricBounds, top=-b[1]/K;
  if (c=="消す"){ del.push(t); continue; }
  if (top>165){ // 表
    if (c.indexOf("作品名が入ります")>=0){ L.table.title=sty(t); del.push(t); }
    else if (c.indexOf("00／00")==0){ L.table.date=sty(t); del.push(t); }
    else if (c.indexOf("●\r●")==0){ var s=sty(t); var ax=s.anchor.x; var k=(ax<150)?"kiso":(ax<167)?"kaka":(ax<182)?"gifu":"ina"; L.table["dot_"+k]=s; del.push(t); }
    continue; }
  var k=keyOf(t), T=L.theaters[k];
  if (c.indexOf("公開")>0 && c.length<12){ T.date=sty(t); T.date.line2=sty2(t); del.push(t); }
  else if (c.indexOf("●監督")==0){ T.credit=sty(t); del.push(t); }
  else if (c.charAt(0)=="©"){ T.copy=sty(t); del.push(t); }
  else if (t.kind==TextType.AREATEXT && c.indexOf("□")>=0){ T.body=sty(t); del.push(t); }
  else if (t.kind==TextType.POINTTEXT && c.indexOf("□□□")==0){ T.title=sty(t); T.title.lines=c.split("\r").length; del.push(t); }
  else if (t.kind==TextType.POINTTEXT && c.indexOf("◎")==0 && c.indexOf("内")>0){ T.info=sty(t); T.info.text=c; }
  else if (t.kind==TextType.POINTTEXT && t.characters[0].characterAttributes.size>=14){ T.hall=sty(t); T.hall.text=c; } }
function sty2(t){ var p=t.paragraphs[1]; var a=p.characters[0].characterAttributes; return {text:p.contents, size:r2(a.size), font:a.textFont.name}; }
// 画像の枠
for (var i=doc.rasterItems.length-1;i>=0;i--){ var r=doc.rasterItems[i]; if (!onAB(r)) continue; if (r.name.indexOf("シネマイメ")!=0) continue; var k=keyOf(r); L.theaters[k].image=box(r); L.theaters[k].image.orient=(r.name.indexOf("2")>0)?"yoko":"tate"; del.push(r); }
// 表の段（見える段）と「消す」の赤帯
var cols=[11.51,30.9,136.1,151.7,167.3,182.9], rows={};
for (var i=0;i<doc.pathItems.length;i++){ var p=doc.pathItems[i]; if (!onAB(p)) continue; var b=box(p);
  if (p.filled && p.fillColor.typename=="CMYKColor" && p.fillColor.magenta==100 && p.fillColor.yellow==100 && p.fillColor.cyan==0 && b.y>185 && b.y<200){ del.push(p); continue; }
  if (b.y<178 || b.y>295 || Math.abs(b.h-4.71)>0.1) continue; var ok=-1; for (var c=0;c<cols.length;c++) if (Math.abs(b.x-cols[c])<0.2) ok=c; if (ok<0) continue;
  if (p.filled||p.stroked){ var idx=Math.round((b.y-178.85)/4.705); if (!rows[idx]) rows[idx]={y:b.y,cells:[]}; rows[idx].cells.push({x:b.x,w:b.w,fill:p.filled?col(p.fillColor):null,stroke:p.stroked?col(p.strokeColor):null,sw:p.stroked?r2(p.strokeWidth/K):0}); }
  del.push(p); }
var rl=[]; for (var k in rows) rl.push(rows[k]); rl.sort(function(a,b){return a.y-b.y;}); L.table.rows=rl.slice(0,2); L.table.top=178.85; L.table.visible_rows=rl.length; L.table.body_h=r2(rl.length*4.705);
var n=del.length; for (var i=0;i<del.length;i++){ try{ del[i].remove(); }catch(e){} }
var f=new File(OUT+"layout_raw.json"); f.encoding="UTF-8"; f.open("w"); f.write(J(L)); f.close();
"消した "+n+"・見える段 "+rl.length;
