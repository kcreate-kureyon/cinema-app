# -*- coding: utf-8 -*-
"""シネマ原稿アプリ（くれよん一宮の読み物「映画館が選ぶ 今月の1本。」）
シネマ担当者が入力 → PDFを作ってお客さんに確認 → 直しはその状態から → OKならPDFと原稿データを高橋さんへ。
決まりは secretary/notes/2026-10-28-decisions.md・engineering/cinema/README.md（YOU 2026-10-28）"""
import hmac
import io
import os

import pandas as pd
import streamlit as st
from PIL import Image

import cinema_ai as ai
import cinema_core as core
import cinema_io as cio

st.set_page_config(page_title="シネマ原稿アプリ", page_icon="🎬", layout="wide")

KEYS = cio.KEYS
HALLS = core.HALLS
FIELDS = ["title", "date", "director_name", "cast_kind", "cast_name", "body", "copy"]
TABLE_COLS = ["公開日", "作品名", "木曽川", "各務原", "岐阜", "稲沢"]
COL2KEY = {"木曽川": "kiso", "各務原": "kaka", "岐阜": "gifu", "稲沢": "ina"}

# ---------------------------------------------------------------- 状態
def blank_table():
    return pd.DataFrame([{"公開日": "", "作品名": "", "木曽川": False, "各務原": False, "岐阜": False, "稲沢": False}])

def init():
    ss = st.session_state
    ss.setdefault("issue", "")
    ss.setdefault("images", {})
    ss.setdefault("table_df", blank_table())
    ss.setdefault("table_ver", 0)
    for k in KEYS:
        for f in FIELDS:
            ss.setdefault(f"{k}_{f}", "出演" if f == "cast_kind" else "")

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
    if data.get("table"):
        rows = [{"公開日": r.get("date", ""), "作品名": r.get("title", ""),
                 **{c: bool(r.get("dots", {}).get(COL2KEY[c])) for c in COL2KEY}} for r in data["table"]]
        ss["table_df"] = pd.DataFrame(rows, columns=TABLE_COLS)
        ss["table_ver"] += 1
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
                 "body": ss[f"{k}_body"], "copy": ss[f"{k}_copy"]}
    df = ss["table_df"]
    table = []
    for _, r in df.iterrows():
        title = str(r.get("作品名") or "").strip()
        if not title:
            continue
        table.append({"date": str(r.get("公開日") or ""), "title": title,
                      "dots": {COL2KEY[c]: bool(r.get(c)) for c in COL2KEY}})
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

def gate():
    pw = app_password()
    if st.session_state.get("_ok"):
        return
    if not pw:
        if os.environ.get("CINEMA_APP_DEV") == "1":  # 手元で動かすときだけ合言葉なし
            return
        st.title("🎬 シネマ原稿アプリ")
        st.error("合言葉がまだ設定されていません（高橋さんに連絡してください）")
        st.stop()
    st.title("🎬 シネマ原稿アプリ")
    v = st.text_input("合言葉を入れてください", type="password")
    if v:
        if hmac.compare_digest(v.strip().encode("utf-8"), pw.strip().encode("utf-8")):  # 日本語の合言葉でも比べられるようにbytesで
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

# ---------------------------------------------------------------- 上：号と読み込み
st.title("🎬 シネマ原稿アプリ")
st.caption("映画館が選ぶ 今月の1本。｜入力すると、くれよんのページの形でPDFができます")

c1, c2 = st.columns([1, 3])
with c1:
    st.text_input("号（例：2612）", key="issue", max_chars=4)
with c2:
    with st.expander("📂 ファイルから読み込む（前回の原稿データ／シネマ担当者のテキスト・スケジュール）"):
        up_zip = st.file_uploader("前回ダウンロードした【原稿データ】（.zip）…直しの続きから始めるとき", type=["zip"], key="up_zip")
        if up_zip and st.button("この原稿データを読み込む"):
            data, imgs = cio.from_zip(up_zip.getvalue())
            ss["_pending"] = (data, imgs, "原稿データを読み込みました。続きから直せます。"); st.rerun()
        up_docx = st.file_uploader("4作品のテキスト（.docx）", type=["docx"], key="up_docx")
        if up_docx and st.button("テキストを読み込む"):
            ss["_pending"] = ({"theaters": cio.read_docx(up_docx.getvalue())}, None, "4作品のテキストを入れました。"); st.rerun()
        up_xlsx = st.file_uploader("上映スケジュール（.xlsx）", type=["xlsx"], key="up_xlsx")
        if up_xlsx and st.button("スケジュールを読み込む"):
            ss["_pending"] = ({"table": cio.read_xlsx(up_xlsx.getvalue())}, None, "上映作品の表を入れました。"); st.rerun()

tabs = st.tabs([f"① {HALLS['kiso']}", f"② {HALLS['kaka']}", f"③ {HALLS['gifu']}", f"④ {HALLS['ina']}",
                "⑤ 上映作品の表", "✅ 確認・ダウンロード"])

# ---------------------------------------------------------------- 4館
for i, k in enumerate(KEYS):
    with tabs[i]:
        L = core.LAYOUT["theaters"][k]
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
            orient = "縦長" if L["image"]["orient"] == "tate" else "横長"
            img = st.file_uploader(f"画像（{orient}の枠・真ん中で自動トリミング）", type=["jpg", "jpeg", "png"], key=f"{k}_img_up")
            if img is not None:
                ss["images"][k] = to_jpeg(img.getvalue())
            if ss["images"].get(k):
                st.image(ss["images"][k], width="stretch")
                if st.button("画像を外す", key=f"{k}_img_rm"):
                    ss["images"].pop(k, None); ss.pop(f"{k}_img_up", None); st.rerun()

# ---------------------------------------------------------------- 表
with tabs[4]:
    st.markdown("公開日は、その日の**最初の作品の行だけ**に入れます（例：12/4(金)）。25作品まで。作品の数だけ段ができます。")
    st.caption("「～12/10(木)」のような上映終了日は自動で取ります。スペースは自動で全角（長すぎる作品は半角）になります。")
    df = st.data_editor(ss["table_df"], num_rows="dynamic", width="stretch", key=f"table_editor_{ss['table_ver']}",
                        column_config={"公開日": st.column_config.TextColumn(width="small"),
                                       "作品名": st.column_config.TextColumn(width="large"),
                                       **{c: st.column_config.CheckboxColumn(c, default=False) for c in COL2KEY}})
    ss["table_df"] = df
    n = sum(1 for t in df["作品名"].fillna("") if str(t).strip())
    (st.error if n > 25 else st.caption)(f"いま {n} 作品" + ("（25作品までにしてください）" if n > 25 else ""))

# ---------------------------------------------------------------- 確認・ダウンロード
with tabs[5]:
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
    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button("📄 PDFをダウンロード（お客さん確認用）", pdf, file_name=f"{name}.pdf", mime="application/pdf",
                           width="stretch", on_click="ignore")
    with d2:
        st.download_button("💾 原稿データをダウンロード（直しの続き・高橋さんへ）", cio.to_zip(data, ss["images"]),
                           file_name=f"{name}_原稿データ.zip", mime="application/zip", width="stretch", on_click="ignore")
    with d3:
        with st.popover("🗑 リセット（翌月の新しい原稿）", width="stretch"):
            st.write("入力した中身と画像を全部消します。**先に原稿データをダウンロードしてから**にしてください。")
            if st.button("全部消して新しく始める", type="primary"):
                reset(); st.rerun()
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
