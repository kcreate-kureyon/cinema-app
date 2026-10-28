# -*- coding: utf-8 -*-
"""シネマアプリの読み書き：シネマ担当者のテキスト(.docx)・スケジュール(.xlsx)の読み込み、
表記のそろえ（YOU 2026-10-28 の決まり）、原稿データ(.zip)の保存と読み込み。"""
import html, io, json, re, unicodedata, zipfile

KEYS = ["kiso", "kaka", "gifu", "ina"]
KAN = {"木曽川": "kiso", "各務原": "kaka", "岐阜": "gifu", "稲沢": "ina"}
FEST = re.compile(r"[（(]午前十時の映画祭\s*(\d*)[）)]")

def nfc(s):
    return unicodedata.normalize("NFC", s or "")

# ---------------------------------------------------------------- 表記のそろえ
def zen_space(s):
    """タイトルのスペースは全角にそろえる"""
    return re.sub(r"[  　]+", "　", nfc(s).strip())

def cut_made(s):
    """「～12/10(木)」のような「〜0/0まで」は取る"""
    return re.sub(r"[ 　]*[～〜~][ 　]*\d{1,2}[/／]\d{1,2}[（(][^）)]*[）)]", "", s)

def fest_norm(s):
    return FEST.sub(lambda m: "（午前十時の映画祭" + m.group(1) + "）", s)

def norm_title(s):
    return fest_norm(zen_space(cut_made(nfc(s))))

def norm_body(s):
    """“ ”はできるだけ『』に"""
    s = nfc(s).strip().replace("“", "『").replace("”", "』")
    return re.sub(r"\s*\n\s*", "", s)

def norm_date(s):
    """公開日（丸の中）：12/25 の形"""
    s = nfc(s).strip().replace("／", "/")
    m = re.match(r"(\d{1,2})\s*/\s*(\d{1,2})", s)
    return f"{int(m.group(1))}/{int(m.group(2))}" if m else s

def norm_table_date(s):
    """表の公開予定日：12／4（金） の形（テンプレの 00／00（　）に合わせる）"""
    s = nfc(s).strip()
    if not s:
        return ""
    m = re.match(r"(\d{1,2})\s*[/／]\s*(\d{1,2})\s*[（(]?\s*([月火水木金土日祝])?", s)
    if not m:
        return s
    w = m.group(3)
    return f"{int(m.group(1))}／{int(m.group(2))}" + (f"（{w}）" if w else "")

def normalize(data):
    out = {"issue": nfc(data.get("issue", "")).strip(), "theaters": {}, "table": []}
    for k in KEYS:
        t = dict(data.get("theaters", {}).get(k, {}))
        t["title"] = norm_title(t.get("title", ""))
        t["date"] = norm_date(t.get("date", ""))
        t["body"] = norm_body(t.get("body", ""))
        for f in ("director", "cast", "copy"):
            t[f] = nfc(t.get(f, "")).strip()
        out["theaters"][k] = t
    for r in data.get("table", []):
        title = norm_title(r.get("title", ""))
        if not title:
            continue
        out["table"].append({"date": norm_table_date(r.get("date", "")), "title": title,
                             "dots": {k: bool(r.get("dots", {}).get(k)) for k in KEYS}})
    return out

# ---------------------------------------------------------------- シネマ担当者のファイル
def read_docx(b):
    """テキスト.docx → theaters（【館名】作品／タイトル　12／25公開・監督／・出演／・本文・©）"""
    d = zipfile.ZipFile(io.BytesIO(b)).read("word/document.xml").decode()
    paras = [nfc(html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))))
             for p in re.findall(r"<w:p[ >].*?</w:p>", d, re.S)]
    th, cur = {}, None
    for p in paras:
        s = p.strip()
        m = re.match(r"【(.+)】", s)
        if m:
            key = next((v for k, v in KAN.items() if k in m.group(1)), None)
            cur = th.setdefault(key, {"body": []}) if key else None
            continue
        if cur is None or not s:
            continue
        if s.startswith("作品／"):
            m = re.match(r"作品／(.+?)[ 　]+(\d{1,2})[／/](\d{1,2})\s*公開$", s)
            if m:
                cur["title"], cur["date"] = m.group(1), f"{m.group(2)}/{m.group(3)}"
            else:
                cur["title"] = s[3:]
        elif s.startswith("監督／"):
            cur["director"] = s
        elif s.startswith("出演／") or s.startswith("声の出演／"):
            cur["cast"] = s
        elif s.startswith("©"):
            cur["copy"] = s
        else:
            cur["body"].append(s)
    for t in th.values():
        t["body"] = "".join(t["body"])
    return th

def read_xlsx(b):
    """スケジュール.xlsx → table（公開日／作品名／4館の●）。★の行（メモ）は読まない"""
    z = zipfile.ZipFile(io.BytesIO(b))
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        ss = [html.unescape("".join(re.findall(r"<t[^>]*>([^<]*)</t>", si)))
              for si in re.findall(r"<si>.*?</si>", z.read("xl/sharedStrings.xml").decode(), re.S)]
    s = z.read("xl/worksheets/sheet1.xml").decode()
    rows = []
    for row in re.findall(r"<row [^>]*>(.*?)</row>", s, re.S):
        cells = {}
        for ref, attrs, body in re.findall(r'<c r="([A-Z]+)\d+"([^>/]*)(?:/>|>(.*?)</c>)', row, re.S):
            v = re.search(r"<v>([^<]*)</v>", body or "") or re.search(r"<t[^>]*>([^<]*)</t>", body or "")
            if v:
                cells[ref] = nfc(ss[int(v.group(1))] if 't="s"' in attrs else v.group(1))
        rows.append(cells)
    if not rows:
        return []
    cols = {}
    for c, v in rows[0].items():
        for k, key in KAN.items():
            if k in v:
                cols[key] = c
    table = []
    for r in rows[1:]:
        t = r.get("B", "").strip()
        if not t or t.startswith("★"):
            continue
        table.append({"date": r.get("A", "").strip(), "title": t,
                      "dots": {k: r.get(c, "").strip() in ("●", "○", "〇", "1") for k, c in cols.items()}})
    return table

# ---------------------------------------------------------------- 原稿データ(.zip)
def to_zip(data, images):
    """data.json ＋ images/{館}.jpg。YOUの手元のイラレ組み上げ（engineering/cinema/）にもこのまま渡す"""
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("data.json", json.dumps(data, ensure_ascii=False, indent=1))
        for k, img in (images or {}).items():
            if img:
                z.writestr(f"images/{k}.jpg", img)
    return b.getvalue()

def from_zip(b):
    z = zipfile.ZipFile(io.BytesIO(b))
    data = json.loads(z.read("data.json").decode("utf-8"))
    images = {}
    for k in KEYS:
        n = f"images/{k}.jpg"
        if n in z.namelist():
            images[k] = z.read(n)
    return data, images
