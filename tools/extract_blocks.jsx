// 縦・横の切り替え用（YOU 2026-10-28「縦長か横長か自動で読み取って、そっちの枠で」）
// ① 4館の枠の中身（カメラ・線・文字・画像）を消した背景 → background_noblock.pdf
// ② アートボード外の部品（縦用・横用）から、文字と画像を消した飾り → deco_tate.pdf／deco_yoko.pdf
// ③ 部品の位置 → blocks.json
var K=2.83465, OUT="/Users/kc02/.company/engineering/cinema-app/template/";
for (var d=app.documents.length-1;d>=0;d--){ if (app.documents[d].name.indexOf("_base")>0) app.documents[d].close(SaveOptions.DONOTSAVECHANGES); }
var doc=app.open(new File(OUT+"シネマ_base.ai"));
var ab=doc.artboards[0].artboardRect, L=doc.layers[0];
function mm(v){ return Math.round(v/K*1000)/1000; }
function box(it){ var b=it.geometricBounds; return {x:mm(b[0]),y:mm(-b[1]),w:mm(b[2]-b[0]),h:mm(b[1]-b[3])}; }
function J(o){ var a=[]; for (var k in o){ var v=o[k]; a.push('"'+k+'":'+(typeof v=="object"?J(v):v)); } return "{"+a.join(",")+"}"; }
// 部品と、アートボード上の左の枠（木曽川＝縦・岐阜＝横）
var spareT=null, spareY=null, kiso=null, gifu=null;
for (var i=0;i<L.groupItems.length;i++){ var g=L.groupItems[i]; var b=box(g);
  if (Math.abs(b.w-90.7)<0.3 && Math.abs(b.h-71.6)<0.3){ if (b.x<0) spareT=g; else kiso=g; }
  if (Math.abs(b.w-91.3)<0.3 && Math.abs(b.h-68.6)<0.3){ if (b.x<0) spareY=g; else gifu=g; } }
if (!spareT||!spareY||!kiso||!gifu){ "STOP 部品が見つからない "+[!!spareT,!!spareY,!!kiso,!!gifu]; } else {
var info={tate:box(spareT), yoko:box(spareY), kiso:box(kiso), gifu:box(gifu)};
// ① 背景：左の2つの枠（グループ）と、右の2つの枠の中身（ばらばらの項目）を消す
var del=[kiso,gifu];
for (var i=0;i<L.pageItems.length;i++){ var it=L.pageItems[i]; var b=box(it);
  if (b.x<105 || b.x>200) continue;                        // 右の列だけ
  var inRow1=(b.y>=48 && b.y+b.h<=100), inRow2=(b.y>=115 && b.y+b.h<=167);
  var frame=(Math.abs(b.w-90.5)<0.3 && Math.abs(b.h-62)<0.3); // 枠の目安の四角（見えない）
  if (inRow1||inRow2||frame) del.push(it); }
info.removed_right=del.length-2;
var keepT=spareT.duplicate(), keepY=spareY.duplicate();  // 飾り用に控え（消す前に）
for (var i=0;i<del.length;i++){ try{ del[i].remove(); }catch(e){} }
spareT.remove(); spareY.remove();
keepT.hidden=true; keepY.hidden=true;
var o=new PDFSaveOptions(); o.preserveEditability=false; o.generateThumbnails=false; o.viewAfterSaving=false;
doc.saveAs(new File(OUT+"background_noblock.pdf"), o);
// ② 飾り：ほかを全部消して、文字と画像を消し、部品の大きさのアートボードで保存
function strip(g){ for (var j=g.pageItems.length-1;j>=0;j--){ var c=g.pageItems[j];
    if (c.typename=="TextFrame" || c.typename=="RasterItem" || c.typename=="PlacedItem"){ c.remove(); continue; }
    if (c.typename=="GroupItem"){ if (c.clipped){ c.remove(); continue; } strip(c); } } }
for (var l=doc.layers.length-1;l>=0;l--){ var Ly=doc.layers[l]; Ly.locked=false; for (var i=Ly.pageItems.length-1;i>=0;i--){ var it=Ly.pageItems[i]; if (it!==keepT && it!==keepY){ try{ it.locked=false; it.remove(); }catch(e){} } } }
keepT.hidden=false; keepY.hidden=false; strip(keepT); strip(keepY);
function saveDeco(g, other, name){ other.hidden=true; g.hidden=false; doc.artboards[0].artboardRect=g.geometricBounds; doc.saveAs(new File(OUT+name), o); }
saveDeco(keepT, keepY, "deco_tate.pdf"); saveDeco(keepY, keepT, "deco_yoko.pdf");
doc.close(SaveOptions.DONOTSAVECHANGES);
var f=new File(OUT+"blocks.json"); f.encoding="UTF-8"; f.open("w"); f.write(J(info)); f.close();
"OK "+J(info); }
