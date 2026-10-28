# -*- coding: utf-8 -*-
"""シネマ原稿アプリ（くれよん一宮の読み物「映画館が選ぶ 今月の1本。」）
シネマ担当者が入力 → PDFを作ってお客さんに確認 → 直しはその状態から → OKならPDFと原稿データを高橋さんへ。
決まりは secretary/notes/2026-10-28-decisions.md・engineering/cinema/README.md（YOU 2026-10-28）"""
import hmac
import io
import os
import unicodedata

import streamlit as st
from PIL import Image

import importlib

import cinema_ai as ai
import cinema_core as core
import cinema_io as cio
import ui_style as ui

# 部品のファイルが新しくなっていたら読み直す（Streamlit Cloud は更新しても部品を古いまま使い続け、
# 2026-10-28 に「DEFAULT_ORIENT が無い」で落ちた）
def _fresh(mod):
    try:
        t = os.path.getmtime(mod.__file__)
        if getattr(mod, "_loaded_mtime", None) not in (None, t):
            mod = importlib.reload(mod)
        mod._loaded_mtime = t
    except Exception:
        pass
    return mod

core, cio, ai, ui = _fresh(core), _fresh(cio), _fresh(ai), _fresh(ui)

st.set_page_config(page_title="シネマ原稿アプリ", page_icon="🎬", layout="wide")
ui.apply()  # 見た目をシネマの原稿に合わせる

KEYS = cio.KEYS
HALLS = core.HALLS
FIELDS = ["title", "date", "director_name", "cast_kind", "cast_name", "body", "copy"]
SHORT = {"kiso": "木曽川", "kaka": "各務原", "gifu": "岐阜", "ina": "稲沢"}

# ---------------------------------------------------------------- 状態
# 上映作品の表は、1作品＝1行の普通の入力欄で持つ（YOU 2026-10-28「Enterおすと消えちゃう」：
# 表の形の入力欄 data_editor は、日本語の変換中のEnterで入力が閉じる・中身を渡し直すと消えることがあった）
def init():
    ss = st.session_state
    ss.setdefault("issue", "")
    ss.setdefault("images", {})
    ss.setdefault("row_ids", [0])
    ss.setdefault("next_id", 1)
    for k in KEYS:
        for f in FIELDS:
            ss.setdefault(f"{k}_{f}", "出演" if f == "cast_kind" else "")
        ss.setdefault(f"{k}_orient", core.DEFAULT_ORIENT[k])
    for rid in ss["row_ids"]:
        init_row(rid)

def init_row(rid, r=None):
    ss = st.session_state
    r = r or {}
    ss.setdefault(f"r{rid}_date", r.get("date", ""))
    ss.setdefault(f"r{rid}_title", r.get("title", ""))
    for k in KEYS:
        ss.setdefault(f"r{rid}_{k}", bool(r.get("dots", {}).get(k)))

def set_rows(rows):
    ss = st.session_state
    for rid in ss.get("row_ids", []):
        for f in ["date", "title"] + KEYS:
            ss.pop(f"r{rid}_{f}", None)
    ids = list(range(ss.get("next_id", 1), ss.get("next_id", 1) + max(1, len(rows))))
    ss["row_ids"], ss["next_id"] = ids, ids[-1] + 1
    for rid, r in zip(ids, rows or [{}]):
        init_row(rid, r)

def sorted_by_date(rows):
    """公開日順に並べ直す（YOU 2026-10-28）。公開日の入った行から次の公開日までを1つのまとまりとして動かす。
    同じ日付のまとまりは1つにまとめ、日付は最初の行だけに残す。12月と1月がまたがるときは1月を後ろに"""
    import re as _re
    groups, cur = [], None
    for r in rows:
        if (r.get("date") or "").strip() or cur is None:
            cur = {"date": (r.get("date") or "").strip(), "rows": []}; groups.append(cur)
        cur["rows"].append(r)
    def md(g):
        m = _re.match(r"\s*(\d{1,2})\s*[/／]\s*(\d{1,2})", unicodedata.normalize("NFKC", g["date"]))
        return (int(m.group(1)), int(m.group(2))) if m else None
    months = [md(g)[0] for g in groups if md(g)]
    def key(g):
        v = md(g)
        if not v: return (-1, 0)               # 日付のないまとまりは先頭のまま
        mo = v[0] + (12 if months and max(months) - v[0] > 6 else 0)
        return (mo, v[1])
    merged = {}
    order = []
    for g in sorted(groups, key=key):
        k = key(g)
        if k in merged and k != (-1, 0):
            merged[k]["rows"].extend(g["rows"]); continue
        merged[k] = g; order.append(g)
    out = []
    for g in order:
        for i, r in enumerate(g["rows"]):
            out.append({**r, "date": g["date"] if i == 0 else ""})
    return out

def load_into_state(data, images=None):
    """data（cinema_core の形）を画面に入れる"""
    ss = st.session_state
    if data.get("issue"):
        ss["issue"] = data["issue"]
    for k, t in data.get("theaters", {}).items():
        if k not in KEYS:
            continue
        ss[f"{k}_title"] = t.get("title", "")
        ss[f"{k}_date"] = t.get("date", "")
        ss[f"{k}_director_name"] = (t.get("director") or "").replace("監督／", "", 1)
        cast = t.get("cast") or ""
        ss[f"{k}_cast_kind"] = "声の出演" if cast.startswith("声の出演") else "出演"
        ss[f"{k}_cast_name"] = cast.split("／", 1)[1] if "／" in cast else cast
        ss[f"{k}_body"] = t.get("body", "")
        ss[f"{k}_copy"] = t.get("copy", "")
        ss[f"{k}_orient"] = t.get("orient") or core.DEFAULT_ORIENT[k]
    if data.get("table"):
        set_rows(data["table"])
    if images:
        ss["images"].update(images)

def collect():
    """画面の中身 → data（そろえる前）"""
    ss = st.session_state
    th = {}
    for k in KEYS:
        th[k] = {"title": ss[f"{k}_title"], "date": ss[f"{k}_date"],
                 "director": "監督／" + ss[f"{k}_director_name"].strip(),
                 "cast": ss[f"{k}_cast_kind"] + "／" + ss[f"{k}_cast_name"].strip(),
                 "body": ss[f"{k}_body"], "copy": ss[f"{k}_copy"], "orient": ss[f"{k}_orient"]}
    table = []
    for rid in ss["row_ids"]:
        title = (ss.get(f"r{rid}_title") or "").strip()
        if not title:
            continue
        table.append({"date": ss.get(f"r{rid}_date") or "", "title": title,
                      "dots": {k: bool(ss.get(f"r{rid}_{k}")) for k in KEYS}})
    return {"issue": ss["issue"], "theaters": th, "table": table}

def reset():
    for key in list(st.session_state.keys()):
        if key != "_ok":
            del st.session_state[key]

def to_jpeg(b):
    im = Image.open(io.BytesIO(b))
    im = im.convert("RGB")
    out = io.BytesIO(); im.save(out, "JPEG", quality=92)
    return out.getvalue()

# ---------------------------------------------------------------- 合言葉
# Streamlitの無料枠で非公開にできるアプリは1つだけ（アタ原が使用中）→ 公開の枠に置き、合言葉で守る（YOU 2026-10-28）
def app_password():
    try:
        p = st.secrets.get("APP_PASSWORD", "")
        if p:
            return str(p)
    except Exception:
        pass
    return os.environ.get("CINEMA_APP_PASSWORD", "")

def _kana(t):
    """全角半角をそろえ、ひらがなはカタカナにして比べる（ぽっぷこーん＝ポップコーン）"""
    t = unicodedata.normalize("NFKC", t).strip()
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in t)

def gate():
    pw = app_password()
    if st.session_state.get("_ok"):
        return
    if not pw:
        if os.environ.get("CINEMA_APP_DEV") == "1":  # 手元で動かすときだけ合言葉なし
            return
        ui.header()
        st.error("合言葉がまだ設定されていません（高橋さんに連絡してください）")
        st.stop()
    ui.header()
    # パスワード欄（type="password"）だとブラウザが日本語入力を止めるので、普通の欄にする（YOU 2026-10-28）
    v = st.text_input("合言葉を入れてください（ひらがな・カタカナどちらでもOK）")
    if v:
        if hmac.compare_digest(_kana(v).encode("utf-8"), _kana(pw).encode("utf-8")):  # 日本語の合言葉でも比べられるようにbytesで
            st.session_state["_ok"] = True
            st.rerun()
        st.error("合言葉がちがいます")
    st.stop()

gate()
init()
ss = st.session_state
# 読み込んだ中身は、画面（入力欄）を作る前に入れる（作った後に書き換えるとStreamlitがエラーになる）
if "_pending" in ss:
    _d, _i, _msg = ss.pop("_pending")
    load_into_state(_d, _i)
    st.toast(_msg, icon="✅")

# ---------------------------------------------------------------- 最初の画面（YOU 2026-10-28「続きから修正」「新しい号の作成」）
ui.header()
if not ss.get("_started"):
    st.markdown("<div class='cine-note'>入力すると、くれよん「映画館が選ぶ 今月の1本。」のページの形でPDFができます</div>", unsafe_allow_html=True)
    st.write("")
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("<div class='start-card'><div class='start-title'>📂 続きから修正</div>前にダウンロードした【原稿データ】（.zip）を入れると、その続きから直せます</div>", unsafe_allow_html=True)
        z = st.file_uploader("原稿データ（.zip）", type=["zip"], key="start_zip")
        if z and st.button("続きから修正する", type="primary", width="stretch"):
            data, imgs = cio.from_zip(z.getvalue())
            ss["_pending"] = (data, imgs, "原稿データを読み込みました。続きから直せます。")
            ss["_started"] = True; st.rerun()
    with s2:
        st.markdown("<div class='start-card'><div class='start-title'>🆕 新しい号の作成</div>空の状態から作ります（翌月の新しい原稿）。テキストとスケジュールのファイルは、次の画面で読み込めます</div>", unsafe_allow_html=True)
        st.write("")
        if st.button("新しい号を作る", type="primary", width="stretch"):
            reset(); ss["_started"] = True; st.rerun()
    st.stop()

# ---------------------------------------------------------------- 上：号と読み込み
st.markdown("<div class='cine-note'>入力すると、くれよん「映画館が選ぶ 今月の1本。」のページの形でPDFができます</div>", unsafe_allow_html=True)
st.write("")

c1, c2 = st.columns([1, 3])
with c1:
    st.text_input("号（例：2612）", key="issue", max_chars=4)
with c2:
    with st.expander("📂 シネマ担当者のテキスト・スケジュールを読み込む"):
        up_docx = st.file_uploader("4作品のテキスト（.docx）", type=["docx"], key="up_docx")
        if up_docx and st.button("テキストを読み込む"):
            ss["_pending"] = ({"theaters": cio.read_docx(up_docx.getvalue())}, None, "4作品のテキストを入れました。"); st.rerun()
        up_xlsx = st.file_uploader("上映スケジュール（.xlsx）", type=["xlsx"], key="up_xlsx")
        if up_xlsx and st.button("スケジュールを読み込む"):
            ss["_pending"] = ({"table": cio.read_xlsx(up_xlsx.getvalue())}, None, "上映作品の表を入れました。"); st.rerun()

with st.popover("🏠 最初の画面にもどる"):
    st.write("入力した中身と画像は消えます。**先に原稿データをダウンロードしてから**にしてください。")
    if st.button("もどる", type="primary"):
        reset(); st.rerun()

tabs = st.tabs(["① 木曽川", "② 各務原", "③ 岐阜", "④ 稲沢", "⑤ 上映作品の表", "⑥ 確認・ダウンロード"])

# ---------------------------------------------------------------- 4館
for i, k in enumerate(KEYS):
    with tabs[i]:
        ui.hall(k, HALLS[k])
        left, right = st.columns([3, 2])
        with left:
            st.text_input("作品名", key=f"{k}_title", help="スペースは自動で全角になります。（午前十時の映画祭16）は自動で小さくなります")
            st.text_input("公開日（例：12/25）", key=f"{k}_date")
            st.text_input("監督", key=f"{k}_director_name", help="例：瀬々敬久")
            cc1, cc2 = st.columns([1, 3])
            with cc1:
                st.radio("出演の種類", ["出演", "声の出演"], key=f"{k}_cast_kind", help="アニメなどで声優さんのときは「声の出演」")
            with cc2:
                st.text_input("出演者（2人・間は全角スペース）", key=f"{k}_cast_name", help="例：岡田准一　松坂桃李")
            st.text_area("映画の紹介文", key=f"{k}_body", height=160,
                         help="“ ”は自動で『』になります。枠からあふれたら長体95%まで自動で縮め、それでも入らないときは赤で知らせます")
            st.caption(f"いま {len(cio.norm_body(ss[f'{k}_body']))} 文字")
            st.text_input("©（コピーライト）", key=f"{k}_copy", help="例：©2026 映画「○○」製作委員会")
        with right:
            img = st.file_uploader("画像（縦長か横長かを自動で読み取り、その形の枠で組みます）", type=["jpg", "jpeg", "png"], key=f"{k}_img_up")
            if img is not None:
                b = img.getvalue()
                if ss.get(f"{k}_img_sig") != (img.name, len(b)):       # 新しい画像のときだけ向きを読み取る
                    ss[f"{k}_img_sig"] = (img.name, len(b))
                    ss["images"][k] = to_jpeg(b)
                    w, h = Image.open(io.BytesIO(b)).size
                    ss[f"{k}_orient"] = "yoko" if w > h * 1.05 else "tate"
            st.radio("枠の形", ["tate", "yoko"], key=f"{k}_orient", horizontal=True,
                     format_func=lambda o: "📱 縦長の枠" if o == "tate" else "🖼 横長の枠",
                     help="画像を入れると自動で選びます。変えたいときはここで選び直せます")
            if ss["images"].get(k):
                st.image(ss["images"][k], width="stretch")
                if st.button("画像を外す", key=f"{k}_img_rm"):
                    ss["images"].pop(k, None); ss.pop(f"{k}_img_up", None); ss.pop(f"{k}_img_sig", None); st.rerun()

# ---------------------------------------------------------------- 表
with tabs[4]:
    ui.band("上映作品名")
    st.markdown("公開日は、その日の**最初の作品の行だけ**に入れます（例：12/4(金)）。25作品まで。作品の数だけ段ができます。")
    st.caption("「～12/10(木)」のような上映終了日は自動で取ります。スペースは自動で全角（長すぎる作品は半角）になります。")
    w = [1.3, 5, .8, .8, .8, .8, .6]
    h = st.columns(w)
    for col, lab in zip(h, ["公開日", "作品名"] + [SHORT[k] for k in KEYS] + [""]):
        col.markdown(f"**{lab}**")
    for n, rid in enumerate(list(ss["row_ids"]), 1):
        c = st.columns(w, vertical_alignment="center")
        c[0].text_input(f"公開日{n}", key=f"r{rid}_date", label_visibility="collapsed")
        c[1].text_input(f"作品名{n}", key=f"r{rid}_title", label_visibility="collapsed")
        for j, k in enumerate(KEYS):
            c[2 + j].checkbox(f"{SHORT[k]}{n}", key=f"r{rid}_{k}", label_visibility="collapsed")
        if c[6].button("✕", key=f"r{rid}_del", help="この行を消す"):
            ss["row_ids"].remove(rid); st.rerun()
    b1, b2, _ = st.columns([1, 1, 2])
    if b2.button("📅 公開日順に並べ直す", width="stretch", help="公開日を入れた行から次の公開日までを1つのまとまりとして、日付の順に並べます"):
        rows = [{"date": ss.get(f"r{rid}_date") or "", "title": ss.get(f"r{rid}_title") or "",
                 "dots": {k: bool(ss.get(f"r{rid}_{k}")) for k in KEYS}} for rid in ss["row_ids"]]
        ss["_pending"] = ({"table": sorted_by_date(rows)}, None, "公開日順に並べ直しました"); st.rerun()
    if b1.button("＋ 作品を1行足す", width="stretch"):
        rid = ss["next_id"]; ss["next_id"] += 1; ss["row_ids"].append(rid); init_row(rid); st.rerun()
    n = sum(1 for rid in ss["row_ids"] if (ss.get(f"r{rid}_title") or "").strip())
    (st.error if n > 25 else st.caption)(f"いま {n} 作品" + ("（25作品までにしてください）" if n > 25 else ""))

# ---------------------------------------------------------------- 確認・ダウンロード
with tabs[5]:
    ui.band("確認・ダウンロード")
    data = cio.normalize(collect())
    try:
        pdf, report = core.build(data, ss["images"])
    except Exception as e:
        st.error(f"PDFを作れませんでした：{e}")
        st.stop()
    overs = [m for kind, m in report if kind == "over"]
    infos = [m for kind, m in report if kind == "info"]
    missing = [HALLS[k] for k in KEYS if not ss["images"].get(k)]
    for m in overs:
        st.markdown(f"<div style='color:#d00000;font-weight:bold;font-size:1.1em'>🔴 {m}</div>", unsafe_allow_html=True)
    if missing:
        st.warning("画像がまだ入っていません：" + "、".join(missing))
    if not overs:
        st.success("あふれている所はありません。")
    if infos:
        with st.expander("自動で調整した所（長体など）"):
            for m in infos:
                st.write("・" + m)
    name = f"{data['issue'] or '0000'}シネマ"
    d1, d2 = st.columns(2)
    with d1:
        st.download_button("📄 PDFをダウンロード（お客さん確認用）", pdf, file_name=f"{name}.pdf", mime="application/pdf",
                           width="stretch", on_click="ignore")
    with d2:
        st.download_button("💾 原稿データをダウンロード（直しの続き・高橋さんへ）", cio.to_zip(data, ss["images"]),
                           file_name=f"{name}_原稿データ.zip", mime="application/zip", width="stretch", on_click="ignore")
    st.caption("OKになったら、PDFと原稿データの2つを高橋さんにメールしてください。")

    # ---- AIチェック（お知らせ。自動では直さない・失敗してもPDFには関係ない）
    st.divider()
    st.subheader("🔍 AIチェック（お知らせ）")
    if not ai.enabled():
        st.info("AIの鍵が設定されていないため、AIチェックは使えません（PDFづくりには関係ありません）。")
    else:
        sig = repr(data)
        a1, a2 = st.columns(2)
        with a1:
            if st.button("✏️ 文字の校正をする（1分ほど）", width="stretch"):
                with st.spinner("AIが校正しています…"):
                    try:
                        ss["ai_proof"] = (sig, ai.proofread(data), None)
                    except Exception as e:
                        ss["ai_proof"] = (sig, [], str(e))
        with a2:
            if st.button("🎞 映画の情報を確かめる（映画.comと照合・1分ほど）", width="stretch"):
                with st.spinner("映画.comのページを読んで、AIが照らし合わせています…"):
                    try:
                        ss["ai_verify"] = (sig, ai.verify_movies(data), None)
                    except Exception as e:
                        ss["ai_verify"] = (sig, {}, str(e))
        if "ai_proof" in ss:
            psig, items, err = ss["ai_proof"]
            st.markdown("#### ✏️ 文字の校正")
            if psig != sig: st.caption("※ 校正したあとに原稿が変わっています。もう一度押すと今の原稿で校正します。")
            if err: st.warning(f"AIにつながりませんでした：{err}")
            elif not items: st.success("気になる所はありませんでした。")
            for it in items:
                must = it.get("level") != "参考"
                color = "#d00000" if must else "#666"
                st.markdown(f"<div style='color:{color}'>{'🔴 要修正' if must else '💬 参考'}｜{it.get('where','')}：「{it.get('original','')}」→「{it.get('suggestion','')}」<br><small>{it.get('reason','')}</small></div>", unsafe_allow_html=True)
        if "ai_verify" in ss:
            vsig, res, err = ss["ai_verify"]
            st.markdown("#### 🎞 映画の情報（映画.comとの照合）")
            st.caption("AIの読みまちがいや、公開前で情報が変わることもあります。最後は映画館の確認が正です。")
            if vsig != sig: st.caption("※ 照合したあとに原稿が変わっています。もう一度押すと今の原稿で照合します。")
            if err: st.warning(f"照合できませんでした：{err}")
            mark = {"ok": "✅", "ng": "🔴", "unknown": "⚪"}
            for k in KEYS:
                if k not in res: continue
                r = res[k]
                st.markdown(f"**{HALLS[k]}**")
                if r.get("error"): st.warning(r["error"]); continue
                if r.get("note"): st.info(r["note"])
                for it in r.get("items", []):
                    stt = it.get("status", "unknown")
                    line = f"{mark.get(stt,'⚪')} {it.get('field','')}"
                    if stt == "ok":
                        st.markdown(f"<span style='color:#2a7a2a'>{line}：合っています</span>", unsafe_allow_html=True)
                    else:
                        c = "#d00000" if stt == "ng" else "#666"
                        st.markdown(f"<div style='color:{c}'>{line}{'：確かめてください' if stt=='ng' else '：わかりませんでした'}<br><small>原稿「{str(it.get('manuscript',''))[:40]}{'…' if len(str(it.get('manuscript','')))>40 else ''}」／映画.com「{str(it.get('web',''))[:80]}」　{it.get('note','')}</small></div>", unsafe_allow_html=True)
                for s_ in r.get("sources", []):
                    st.markdown(f"<small>出どころ：<a href='{s_['url']}' target='_blank'>{s_['title']} {s_['url']}</a></small>", unsafe_allow_html=True)
    st.divider()
    st.image(core.preview_png(pdf, 110), width="stretch")
