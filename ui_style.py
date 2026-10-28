# -*- coding: utf-8 -*-
"""アプリの見た目を、シネマの原稿（くれよん一宮「映画館が選ぶ 今月の1本。」）に合わせる（YOU 2026-10-28）
わら半紙の背景・本物の見出し（台紙から切り出し）・4館の色・表の茶色・丸ゴシック"""
import base64, os

import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))

# 台紙の色（CMYK → だいたいのRGB）
BROWN = "#855a37"      # 表の見出し・ケイ線 C35 M60 Y80 K25
CREAM = "#f7f0dc"      # 表のしま C3 M5 Y15
INK = "#3a3a3a"        # 文字 K90
RED = "#c8463c"        # 確認・ダウンロードのタブ
HALL_COLOR = {"kiso": "#4e628c", "kaka": "#b45a71", "gifu": "#3e876d", "ina": "#b7693e"}  # 4館の色
HALL_INFO = {
    "kiso": "◎「イオンモール木曽川」内　◎水曜 TOHOウェンズデイ",
    "kaka": "◎「イオンモール各務原インター」内　◎月曜 ハッピーマンデー",
    "gifu": "◎「カラフルタウン岐阜」内　◎水曜 TOHOウェンズデイ",
    "ina": "◎「アピタ稲沢店」内　◎木曜サービスデー",
}


def _b64(name):
    with open(os.path.join(HERE, "static", name), "rb") as f:
        return base64.b64encode(f.read()).decode()


def apply():
    paper = _b64("paper.jpg")
    cinema = _b64("cinema.png")  # 台紙の「CINEMA」の文字だけ（背景が透けた画像）
    k, ka, g, i = (HALL_COLOR[x] for x in ("kiso", "kaka", "gifu", "ina"))
    st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@500;700&display=swap" rel="stylesheet">
<style>
.stApp {{ background: url(data:image/png;base64,{cinema}) center 46% / 96vw auto no-repeat fixed,
                      url(data:image/jpeg;base64,{paper}) center top / cover fixed, #f1e3dc; color: {INK}; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ max-width: 1150px; padding-top: 1.2rem; }}
h1, h2, h3, h4, .app-title, [data-baseweb="tab"] p, .stButton button p, .stDownloadButton button p, .hall, .band {{
  font-family: "Zen Maru Gothic", "Hiragino Maru Gothic ProN", sans-serif !important; }}
/* タブ＝ボタン。4館はその館の色・上映作品の表は茶色・確認とダウンロードは赤（YOU 2026-10-28）。選んでいるタブは大きく＋下に線 */
[data-baseweb="tab-list"] {{ gap: 8px; border-bottom: 3px solid {BROWN}; padding: 6px 8px 8px; flex-wrap: wrap; overflow: visible; }}
[data-baseweb="tab"] {{ border-radius: 999px; padding: 8px 18px !important; opacity: .82; box-shadow: 0 2px 0 rgba(0,0,0,.15); transition: all .1s; }}
[data-baseweb="tab"] p {{ font-weight: 700; font-size: 15px; color: #fff !important; }}
[data-baseweb="tab"]:nth-child(1) {{ background: {k}; }}
[data-baseweb="tab"]:nth-child(2) {{ background: {ka}; }}
[data-baseweb="tab"]:nth-child(3) {{ background: {g}; }}
[data-baseweb="tab"]:nth-child(4) {{ background: {i}; }}
[data-baseweb="tab"]:nth-child(5) {{ background: {BROWN}; }}
[data-baseweb="tab"]:nth-child(6) {{ background: {RED}; }}
[data-baseweb="tab"]:hover {{ opacity: 1; }}
[data-baseweb="tab"]:first-child {{ margin-left: 8px; }}
[data-baseweb="tab-list"] {{ overflow: visible !important; }}
[data-baseweb="tab"][aria-selected="true"] {{ opacity: 1; transform: scale(1.08); box-shadow: 0 0 0 3px #fff, 0 0 0 5px {INK}; }}
[data-baseweb="tab-highlight"] {{ display: none; }}
/* 入力欄・枠 */
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="base-input"] {{ background: #fff !important; border-color: #d9c6b4 !important; }}
[data-testid="stExpander"], [data-testid="stFileUploaderDropzone"] {{ background: rgba(255,255,255,.7); border-radius: 10px; }}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ background: #fff; border: 1px solid {BROWN}; border-radius: 4px; }}
/* ボタン＝茶色の丸 */
.stButton button, .stDownloadButton button, [data-testid="stPopover"] button {{
  border-radius: 999px; border: 2px solid {BROWN}; color: {BROWN}; background: #fff; }}
.stDownloadButton button {{ background: {BROWN}; color: #fff; }}
.stDownloadButton button p {{ color: #fff; }}
.stButton button:hover, .stDownloadButton button:hover {{ filter: brightness(1.08); border-color: {BROWN}; }}
/* 館名（台紙と同じ丸ゴシック・館の色）と、表の見出しのような茶色の帯 */
.hall {{ font-size: 30px; font-weight: 700; letter-spacing: .02em; line-height: 1.2; margin: 6px 0 0; }}
.hall-info {{ font-size: 13px; color: {INK}; margin: 2px 0 10px; }}
.band {{ background: {BROWN}; color: #fff; font-weight: 700; padding: 6px 14px; border-radius: 4px; margin: 4px 0 10px; display: inline-block; }}
.app-title {{ font-family: 'Zen Maru Gothic', sans-serif; font-size: 34px; font-weight: 700; color: {BROWN}; margin: 4px 0 8px; }}

.start-card {{ background: rgba(255,255,255,.8); border: 2px solid {BROWN}; border-radius: 14px; padding: 16px 18px; min-height: 110px; font-size: 15px; }}
.start-title {{ font-family: 'Zen Maru Gothic', sans-serif; font-size: 24px; font-weight: 700; color: {BROWN}; margin-bottom: 6px; }}
.cine-note {{ background: {CREAM}; border-left: 6px solid {BROWN}; padding: 8px 12px; border-radius: 4px; font-size: 14px; }}
</style>
""", unsafe_allow_html=True)


def header():
    """アプリの名前（見出しの画像はなし・背景に大きく CINEMA ／YOU 2026-10-28）"""
    st.markdown("<div class='app-title'>🎬 シネマ原稿アプリ</div>", unsafe_allow_html=True)


def hall(key, name):
    st.markdown(f"<div class='hall' style='color:{HALL_COLOR[key]}'>{name}</div>"
                f"<div class='hall-info'>{HALL_INFO[key]}</div>", unsafe_allow_html=True)


def band(text):
    st.markdown(f"<div class='band'>{text}</div>", unsafe_allow_html=True)
