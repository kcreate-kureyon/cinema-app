// ベースのコピーで、アートボードの外の部品（縦用・横用）と、4館の枠の中の飾り（カメラ・線）を調べる（読むだけ）
var K=2.83465, OUT="/Users/kc02/.company/engineering/cinema-app/template/";
for (var d=app.documents.length-1;d>=0;d--){ if (app.documents[d].name.indexOf("_base")>0) app.documents[d].close(SaveOptions.DONOTSAVECHANGES); }
var doc=app.open(new File(OUT+"シネマ_base.ai")), out=[];
function mm(v){ return Math.round(v/K*10)/10; }
function bb(it){ var b=it.geometricBounds; return "x"+mm(b[0])+" y"+mm(-b[1])+" w"+mm(b[2]-b[0])+" h"+mm(b[1]-b[3]); }
for (var l=0;l<doc.layers.length;l++){ var L=doc.layers[l]; out.push("## layer "+L.name);
  for (var i=0;i<L.pageItems.length;i++){ var it=L.pageItems[i]; var b=it.geometricBounds; var top=-b[1]/K;
    var s=it.typename+" "+bb(it)+" name="+it.name;
    if (it.typename=="GroupItem"){ var kinds={}; for (var j=0;j<it.pageItems.length;j++){ var t=it.pageItems[j].typename; kinds[t]=(kinds[t]||0)+1; } var ks=[]; for (var t in kinds) ks.push(t+":"+kinds[t]); s+=" ["+ks.join(",")+"]"+(it.clipped?" clip":""); }
    if (it.typename=="TextFrame") s+=" 「"+it.contents.substr(0,14).replace(/\r/g,"/")+"」";
    out.push(s); } }
doc.close(SaveOptions.DONOTSAVECHANGES);
out.join("\n");
