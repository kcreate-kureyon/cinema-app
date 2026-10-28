# -*- coding: utf-8 -*-
"""シネマ（くれよん一宮の読み物1P）の原稿PDFを組む。

背景（template/background_app.pdf）＝ベースの シネマ.ai から毎月変わる所を抜いたもの。
置く場所（template/layout.json）＝同じベースから測った座標（mm・左上原点・下が+）。
決まりは YOU 2026-10-28（secretary/notes/2026-10-28-decisions.md・engineering/cinema/README.md）。

データの形は engineering/cinema/build_data.py と同じ（イラレ用の fill_cinema.jsx にそのまま渡せる）:
  {"issue": "2612",
   "theaters": {"kiso": {"title","date","director","cast","copy","body"}, "kaka":…, "gifu":…, "ina":…},
   "table": [{"date": "12／4（金）" or "", "title": "…", "dots": {"kiso":bool,…}}]}
"""
import io, json, os, re

import fitz
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MM = 2.83465
LAYOUT = json.load(open(os.path.join(HERE, "template", "layout.json"), encoding="utf-8"))
BG = os.path.join(HERE, "template", "background_app.pdf")
KEYS = ["kiso", "kaka", "gifu", "ina"]
HALLS = {"kiso": "TOHOシネマズ木曽川", "kaka": "イオンシネマ各務原", "gifu": "TOHOシネマズ岐阜", "ina": "ユナイテッド・シネマ稲沢"}

_FONTS = {}
def font(weight):
    """テンプレのモリサワ／ヒラギノは使えないので Noto Sans JP で近い太さ（アタ原と同じ考え方）"""
    if weight not in _FONTS:
        _FONTS[weight] = fitz.Font(fontfile=os.path.join(HERE, "fonts", f"NotoSansJP-{weight}.ttf"))
    return _FONTS[weight]

K90 = (0, 0, 0, 0.9)
WHITE = (0, 0, 0, 0)
RED = (0, 1, 1, 0)
FEST_RE = re.compile(r"（午前十時の映画祭\s*\d*）")
NO_START = set("、。，．・：；？！ー」』）】〕〉》ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ々…‥〜～!?)]},.%")
NO_END = set("「『（【〔〈《([{")
HANG = set("、。，．")

# ---------------------------------------------------------------- 文字のかたまり
# 1文字＝(文字, 大きさpt)。長体 hs（%）とトラッキング（1/1000em）は行ごと
def runs(text, size, fest=True):
    """（午前十時の映画祭16）の部分は75%（YOU 10/28）"""
    out, m = [], FEST_RE.search(text) if fest else None
    for i, ch in enumerate(text):
        small = m is not None and m.start() <= i < m.end()
        out.append((ch, size * 0.75 if small else size))
    return out

# 約物の半角（イラレの文字組みと同じく「、。「」（）・」を半分の幅で組む）
HALF_OPEN = set("「『（【〔〈《")
HALF_CLOSE = set("」』）】〕〉》、。，．")
HALF_MID = set("・：；")

# テンプレのヒラギノは自動カーニングで、かなが少し詰まる。2612のイラレの改行から割り出した幅（2026-10-28）
KANA_HIRA, KANA_KATA = 0.92, 0.88

def kana_rate(ch):
    if "\u3041" <= ch <= "\u309f": return KANA_HIRA
    if "\u30a0" <= ch <= "\u30ff" and ch not in "・ー": return KANA_KATA
    return None

def base_adv(ch, sz, f):
    if ch in HALF_OPEN or ch in HALF_CLOSE or ch in HALF_MID:
        return sz * 0.5
    r = kana_rate(ch)
    if r: return sz * r
    return f.text_length(ch, fontsize=sz)

def glyph_shift(ch, sz):
    """詰めた文字の、字形を置く位置のずらし（長体をかける前の単位）"""
    if ch in HALF_OPEN: return -sz * 0.5
    if ch in HALF_MID: return -sz * 0.25
    r = kana_rate(ch)
    if r: return -sz * (1 - r) / 2
    return 0.0

def adv(ch, sz, f, hs, trk):
    return base_adv(ch, sz, f) * hs / 100 + trk / 1000 * sz

def width(items, f, hs=100, trk=0, last_trk=False):
    w = sum(adv(c, s, f, hs, trk) for c, s in items)
    if items and not last_trk:
        w -= trk / 1000 * items[-1][1]
    return w

def draw(page, items, x, base, f, color, hs=100, trk=0, align="left", spread=None):
    """1行を置く。x は align=left なら左端、center なら真ん中（pt）。spread=行の幅に両端そろえ。
    長体は字形ごと細くする（行の左端を軸に横だけ縮める）"""
    if not items:
        return
    w = width(items, f, hs, trk)
    gap = 0
    if spread and len(items) > 1:
        gap = max(0, (spread - w) / (len(items) - 1))
    x0 = x - w / 2 if align == "center" else x
    s = hs / 100
    tw = fitz.TextWriter(page.rect, color=color)
    cu = 0.0  # 長体をかける前の単位で進める
    for c, sz in items:
        tw.append((x0 + cu + glyph_shift(c, sz), base), c, font=f, fontsize=sz)
        cu += base_adv(c, sz, f) + (trk / 1000 * sz + gap) / s
    tw.write_text(page, color=color, morph=(fitz.Point(x0, base), fitz.Matrix(s, 1)))

def hs_fit(items, f, maxw, trk=0):
    w = width(items, f, 100, trk)
    return 100 if w <= maxw else max(1, int(maxw / w * 100))

# ---------------------------------------------------------------- 折り返し（紹介文）
def tokens(text):
    """英数字のまとまりは途中で切らない"""
    return re.findall(r"[A-Za-z0-9.,'’\-/&:%]+|.", text, re.S)

def wrap(text, size, f, boxw, hs, trk):
    lines, cur, curw = [], [], 0.0
    for tk in tokens(text):
        tw = sum(adv(c, size, f, hs, trk) for c in tk)
        if cur and curw + tw - trk / 1000 * size > boxw and tk in HANG:
            # ぶら下げ：句読点は枠の外に出して同じ行に入れる（イラレの標準）
            cur.append(tk); lines.append(cur); cur, curw = [], 0.0; continue
        if cur and curw + tw - trk / 1000 * size > boxw:
            # 行頭禁則：次の行の頭が禁則文字なら、ぶら下げずに前の1文字ごと送る（追い出し）
            if tk[0] in NO_START and len(cur) > 1:
                prev = cur.pop()
                curw -= sum(adv(c, size, f, hs, trk) for c in prev)
                lines.append(cur); cur, curw = [prev], sum(adv(c, size, f, hs, trk) for c in prev)
            elif cur[-1] and cur[-1][-1] in NO_END:
                prev = cur.pop(); lines.append(cur)
                cur, curw = [prev], sum(adv(c, size, f, hs, trk) for c in prev)
            else:
                lines.append(cur); cur, curw = [], 0.0
        cur.append(tk); curw += tw
    if cur:
        lines.append(cur)
    return ["".join(l) for l in lines]

# ---------------------------------------------------------------- 4館
def cmyk(c):
    v = [x / 100 for x in c["cmyk"]]
    t = c.get("tint", 100) / 100
    return tuple(x * t for x in v)

def put_image(page, rect_mm, img_bytes):
    """枠と同じ縦横比に真ん中で切って置く（PSDと同じ切り方）"""
    x, y, w, h = rect_mm["x"], rect_mm["y"], rect_mm["w"], rect_mm["h"]
    im = Image.open(io.BytesIO(img_bytes))
    im = im.convert("RGB")
    ratio = w / h
    iw, ih = im.size
    if iw / ih > ratio:
        nw = round(ih * ratio); l = (iw - nw) // 2; im = im.crop((l, 0, l + nw, ih))
    else:
        nh = round(iw / ratio); t = (ih - nh) // 2; im = im.crop((0, t, iw, t + nh))
    tgt = round(w / 25.4 * 250)  # 確認用PDFなので250dpi相当（イラレ用のPSDは別に350dpiで作る）
    if im.width > tgt:
        im = im.resize((tgt, round(tgt / ratio)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=88)
    page.insert_image(fitz.Rect(x * MM, y * MM, (x + w) * MM, (y + h) * MM), stream=b.getvalue())

def gray_box(page, rect_mm):
    r = fitz.Rect(rect_mm["x"] * MM, rect_mm["y"] * MM, (rect_mm["x"] + rect_mm["w"]) * MM, (rect_mm["y"] + rect_mm["h"]) * MM)
    page.draw_rect(r, color=None, fill=(0, 0, 0, 0.35))

TITLE_MAXW = {"kiso": 41, "kaka": 41, "ina": 41, "gifu": 76}  # mm（右はケイ線の手前まで）
CREDIT_RIGHT = {"kiso": 100.0, "kaka": 198.5, "gifu": 56.5, "ina": 198.5}  # 監督・出演の右端mm（岐阜は紹介文の左まで）

def theater(page, key, d, img, report):
    L = LAYOUT["theaters"][key]
    bold, med = font("Bold"), font("Medium")
    # 画像
    if img:
        put_image(page, L["image"], img)
    else:
        gray_box(page, L["image"])
    # タイトル（縦の枠は2行まで。1行で入らなければ全角スペースで2行に。1行なら2行分の真ん中へ）
    T = L["title"]; sz = T["size"]; trk = T["tracking"]; maxw = TITLE_MAXW[key] * MM
    lead = T["leading"] * MM
    title = (d.get("title") or "").strip()
    lines = [title]
    if T["lines"] >= 2 and width(runs(title, sz), bold, 100, trk) > maxw and "　" in title:
        parts = title.split("　"); best, bd = 1, 1e9
        for s in range(1, len(parts)):
            a, b = len("　".join(parts[:s])), len("　".join(parts[s:]))
            if abs(a - b) < bd: bd, best = abs(a - b), s
        lines = ["　".join(parts[:best]), "　".join(parts[best:])]
    base = T["anchor"]["y"] * MM
    if T["lines"] >= 2 and len(lines) == 1:
        base += lead / 2
    for i, ln in enumerate(lines[:2]):
        it = runs(ln, sz); hs = hs_fit(it, bold, maxw, trk)
        if hs < 100: report.append(("info", f"{HALLS[key]}：タイトル「{ln}」に長体{hs}%"))
        draw(page, it, T["anchor"]["x"] * MM, base + i * lead, bold, K90, hs, trk)
    # 公開日（丸の中）
    D = L["date"]
    date = (d.get("date") or "").strip()
    draw(page, runs(date, D["size"], False), D["anchor"]["x"] * MM, D["anchor"]["y"] * MM, bold, WHITE,
         hs_fit(runs(date, D["size"], False), bold, 6.2 * MM, D["tracking"]), D["tracking"], align="center")
    draw(page, runs("公開", D["line2"]["size"], False), D["anchor"]["x"] * MM, D["anchor"]["y"] * MM + D["leading"] * MM,
         bold, WHITE, 100, D["tracking"], align="center")
    # 監督・出演
    C = L["credit"]
    cr = ["●" + (d.get("director") or "監督／"), "●" + (d.get("cast") or "出演／")]
    cmax = (CREDIT_RIGHT[key] - C["anchor"]["x"]) * MM
    for i, ln in enumerate(cr):
        it = runs(ln, C["size"], False); hs = hs_fit(it, med, cmax, C["tracking"])
        if hs < 100: report.append(("info", f"{HALLS[key]}：「{ln}」に長体{hs}%"))
        draw(page, it, C["anchor"]["x"] * MM, C["anchor"]["y"] * MM + i * C["leading"] * MM, med, cmyk(C["color"]), hs, C["tracking"])
    # 紹介文：あふれたら長体99→95%（YOU 10/28）。95%でも入らなければ、あふれた行を赤で枠の下に出す
    B = L["body"]; bx, by, bw, bh = (B["box"][k] * MM for k in ("x", "y", "w", "h"))
    body = (d.get("body") or "").replace("“", "『").replace("”", "』")
    sz, trk, lead = B["size"], B["tracking"], B["leading"] * MM
    maxlines = int((bh - sz * 0.88) // lead) + 1
    for hs in range(100, 94, -1):
        ls = wrap(body, sz, med, bw, hs, trk)
        if len(ls) <= maxlines: break
    over = len(ls) - maxlines
    if hs < 100 and over <= 0: report.append(("info", f"{HALLS[key]}：紹介文に長体{hs}%"))
    if over > 0:
        n = sum(len(l) for l in ls[maxlines:])
        report.append(("over", f"{HALLS[key]}：紹介文が {n}文字 あふれています（長体95%でも入りません）。文章を短くしてください"))
    for i, ln in enumerate(ls):
        last = (i == len(ls) - 1) or (i == maxlines - 1 and over <= 0)
        it = runs(ln, sz, False)
        color = RED if i >= maxlines else cmyk(B["color"])
        sp = bw + (adv(ln[-1], sz, med, hs, trk) if ln and ln[-1] in HANG and width(it, med, hs, trk) > bw else 0)
        draw(page, it, bx, by + sz * 0.88 + i * lead, med, color, hs, trk, spread=None if last else sp)
    # ©
    P = L["copy"]
    draw(page, runs(d.get("copy") or "", P["size"], False), P["anchor"]["x"] * MM, P["anchor"]["y"] * MM, med, cmyk(P["color"]), P["hs"], P["tracking"])

# ---------------------------------------------------------------- 表
def date_size(n):   # YOU 10/28
    if n <= 17: return 7.8
    if n <= 19: return 7.6
    if n <= 21: return 7.3
    if n <= 23: return 7.0
    return 6.8

def title_size(n):  # YOU 10/28
    if n <= 17: return 9.0
    if n <= 19: return 8.7
    if n <= 22: return 8.5
    return 8.0

TABLE_MAXW = 99.735 * MM
DOT_X = {"kiso": 143.897, "kaka": 159.497, "gifu": 175.097, "ina": 190.696}
DOT_COLOR = {"kiso": (0.75, 0.60, 0.30, 0), "kaka": (0.30, 0.75, 0.40, 0), "gifu": (0.75, 0.30, 0.65, 0), "ina": (0.30, 0.65, 0.80, 0)}

def fit_table_title(title, base, f):
    """基本の大きさ→入らなければ8pt→90%を下回るなら全角スペース→半角→長体→70%以下なら7.5pt。
    余裕があればトラッキング60、長体の作品はテンプレの20のまま（YOU 10/28）"""
    sz, line = base, title
    if width(runs(line, sz), f, 100, 20) > TABLE_MAXW and base > 8:
        sz = 8.0
    def ratio(l, s): return TABLE_MAXW / width(runs(l, s), f, 100, 20)
    if ratio(line, sz) < 1 and ratio(line, sz) < 0.90 and "　" in line:
        line = line.replace("　", " ")
    hs = min(100, int(ratio(line, sz) * 100))
    if hs <= 70:
        sz = 7.5
        if ratio(line, sz) < 0.90 and "　" in line:
            line = line.replace("　", " ")
        hs = min(100, int(ratio(line, sz) * 100))
    trk = 60 if hs == 100 and width(runs(line, sz), f, 100, 60) <= TABLE_MAXW else 20
    return line, sz, hs, trk

def table(page, rows, report):
    t = LAYOUT["table"]; med = font("Medium"); bold = font("Bold")
    n = len(rows)
    if n == 0:
        return
    if n > 25:
        report.append(("over", f"表が {n}作品 あります。25作品までにしてください"))
    top, total = t["top"], t["body_h"]
    h = total / max(n, 1)
    cream = cmyk(t["rows"][0]["cells"][0]["fill"]); white = (0, 0, 0, 0)
    line_c = cmyk(t["rows"][0]["cells"][0]["stroke"]); sw = t["rows"][0]["cells"][0]["sw"] * MM
    cols = sorted([(c["x"], c["w"]) for c in t["rows"][0]["cells"]])
    for i in range(n):
        y = (top + i * h) * MM
        for x, w in cols:
            page.draw_rect(fitz.Rect(x * MM, y, (x + w) * MM, y + h * MM), color=line_c, fill=cream if i % 2 == 0 else white, width=sw)
    dsz, tsz = date_size(n), title_size(n)
    for i, r in enumerate(rows):
        mid = (top + i * h + h / 2) * MM
        if r.get("date"):
            draw(page, runs(r["date"], dsz, False), t["date"]["anchor"]["x"] * MM, mid + dsz * 0.4, med, K90, 100, 20, align="center")
        line, sz, hs, trk = fit_table_title(r.get("title", ""), tsz, med)
        if hs < 100 or sz != tsz or line != r.get("title", ""):
            report.append(("info", f"表「{r.get('title','')}」→ {sz}pt" + ("・半角スペース" if line != r.get("title", "") else "") + (f"・長体{hs}%" if hs < 100 else "")))
        draw(page, runs(line, sz), t["title"]["anchor"]["x"] * MM, mid + sz * 0.45, med, K90, hs, trk, align="center")
        for k in KEYS:
            if r.get("dots", {}).get(k):
                page.draw_circle(fitz.Point(DOT_X[k] * MM, mid), 1.25 * MM, color=None, fill=DOT_COLOR[k])

# ---------------------------------------------------------------- 全体
def build(data, images=None):
    """data → (PDFのbytes, report)。report＝[("over"|"info", 文)]。over は赤で知らせる"""
    images = images or {}
    report = []
    src = fitz.open(BG)
    doc = fitz.open()
    page = doc.new_page(width=src[0].rect.width, height=src[0].rect.height)
    page.show_pdf_page(page.rect, src, 0)
    for k in KEYS:
        theater(page, k, data.get("theaters", {}).get(k, {}), images.get(k), report)
    table(page, data.get("table", []), report)
    doc.subset_fonts()  # 使った文字だけ埋め込む（丸ごとだと7MB超え）
    return doc.tobytes(garbage=3, deflate=True), report

def preview_png(pdf_bytes, dpi=110):
    d = fitz.open(stream=pdf_bytes, filetype="pdf")
    return d[0].get_pixmap(dpi=dpi).tobytes("png")
