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
    k, ka, g, i = (HALL_COLOR[x] for x in ("kiso", "kaka", "gifu", "ina"))
    st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@500;700&display=swap" rel="stylesheet">
<style>
.stApp {{ background: url(data:image/jpeg;base64,{paper}) center top / cover fixed, #f1e3dc; color: {INK}; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ max-width: 1150px; padding-top: 1.2rem; }}
h1, h2, h3, h4, [data-baseweb="tab"] p, .stButton button p, .stDownloadButton button p, .hall, .band {{
  font-family: "Zen Maru Gothic", "Hiragino Maru Gothic ProN", sans-serif !important; }}
/* タブ＝4館の色。選んだタブはその館の色の帯 */
[data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 3px solid {BROWN}; }}
[data-baseweb="tab"] {{ background: rgba(255,255,255,.65); border-radius: 10px 10px 0 0; padding: 6px 14px !important; }}
[data-baseweb="tab"] p {{ font-weight: 700; font-size: 15px; }}
[data-baseweb="tab"]:nth-child(1) p {{ color: {k}; }}
[data-baseweb="tab"]:nth-child(2) p {{ color: {ka}; }}
[data-baseweb="tab"]:nth-child(3) p {{ color: {g}; }}
[data-baseweb="tab"]:nth-child(4) p {{ color: {i}; }}
[data-baseweb="tab"]:nth-child(5) p, [data-baseweb="tab"]:nth-child(6) p {{ color: {BROWN}; }}
[data-baseweb="tab"][aria-selected="true"]:nth-child(1) {{ background: {k}; }}
[data-baseweb="tab"][aria-selected="true"]:nth-child(2) {{ background: {ka}; }}
[data-baseweb="tab"][aria-selected="true"]:nth-child(3) {{ background: {g}; }}
[data-baseweb="tab"][aria-selected="true"]:nth-child(4) {{ background: {i}; }}
[data-baseweb="tab"][aria-selected="true"]:nth-child(5), [data-baseweb="tab"][aria-selected="true"]:nth-child(6) {{ background: {BROWN}; }}
[data-baseweb="tab"][aria-selected="true"] p {{ color: #fff !important; }}
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
.header-img {{ width: 100%; max-width: 1150px; display: block; margin: 0 auto 4px; }}
.cine-note {{ background: {CREAM}; border-left: 6px solid {BROWN}; padding: 8px 12px; border-radius: 4px; font-size: 14px; }}
</style>
""", unsafe_allow_html=True)


def header():
    """台紙の見出し（CINEMA／映画館が選ぶ 今月の1本。）をそのまま出す"""
    st.markdown(f"<img class='header-img' src='data:image/jpeg;base64,{_b64('header.jpg')}' alt='映画館が選ぶ 今月の1本。'>",
                unsafe_allow_html=True)


def hall(key, name):
    st.markdown(f"<div class='hall' style='color:{HALL_COLOR[key]}'>{name}</div>"
                f"<div class='hall-info'>{HALL_INFO[key]}</div>", unsafe_allow_html=True)


def band(text):
    st.markdown(f"<div class='band'>{text}</div>", unsafe_allow_html=True)
