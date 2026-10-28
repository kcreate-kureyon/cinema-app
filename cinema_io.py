# -*- coding: utf-8 -*-
"""シネマアプリの読み書き：シネマ担当者のテキスト(.docx)・スケジュール(.xlsx)の読み込み、
表記のそろえ（YOU 2026-10-28 の決まり）、原稿データ(.zip)の保存と読み込み。"""
import html, io, json, os, re, unicodedata, zipfile

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

def _year_for(month, issue=""):
    """日付の年：号（2612＝2026年12月号）から。号の月より半年以上前の月なら翌年（12月号の1/5 → 2027年）"""
    import datetime
    iss = unicodedata.normalize("NFKC", issue or "").strip()
    if len(iss) == 4 and iss.isdigit():
        y, im = 2000 + int(iss[:2]), int(iss[2:])
    else:
        t = datetime.date.today(); y, im = t.year, t.month
    return y + 1 if im - month > 6 else (y - 1 if month - im > 6 else y)

def norm_table_date(s, issue=""):
    """表の公開予定日：12／4（金） の形（テンプレの 00／00（　）に合わせる）。曜日が無ければ号の年から付ける（YOU 2026-10-28）"""
    import datetime
    s = unicodedata.normalize("NFKC", nfc(s)).strip()
    if not s:
        return ""
    m = re.match(r"(\d{1,2})\s*[/／月]\s*(\d{1,2})\s*日?\s*[（(]?\s*([月火水木金土日祝])?", s)
    if not m:
        return s
    mo, da, w = int(m.group(1)), int(m.group(2)), m.group(3)
    if not w:
        try:
            w = "月火水木金土日"[datetime.date(_year_for(mo, issue), mo, da).weekday()]
        except ValueError:
            w = None
    return f"{mo}／{da}" + (f"（{w}）" if w else "")

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
        out["table"].append({"date": norm_table_date(r.get("date", ""), out["issue"]), "title": title,
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
        ss = _shared_strings(z)
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


# ---------------------------------------------------------------- PDFに原稿の中身を入れる（YOU 2026-10-28）
# 「続きから修正」はダウンロードしたPDFを入れるだけで戻せるように、PDFの添付ファイルとして
# data.json と画像を入れておく（zipを別に持たなくてよい）。高橋さんの手元の組み上げもこのPDFから読める
EMB_DATA = "cinema_data.json"

def embed_into_pdf(pdf_bytes, data, images):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    doc.embfile_add(EMB_DATA, json.dumps(data, ensure_ascii=False).encode("utf-8"), filename=EMB_DATA, desc="シネマ原稿アプリの原稿データ")
    for k, img in (images or {}).items():
        if img:
            n = f"cinema_img_{k}.jpg"
            doc.embfile_add(n, img, filename=n, desc=f"シネマ原稿アプリの画像（{k}）")
    return doc.tobytes(garbage=3, deflate=True)

def from_pdf(b):
    import fitz
    doc = fitz.open(stream=b, filetype="pdf")
    names = doc.embfile_names()
    if EMB_DATA not in names:
        raise ValueError("このPDFには原稿の中身が入っていません（このアプリでダウンロードしたPDFを入れてください）")
    data = json.loads(doc.embfile_get(EMB_DATA).decode("utf-8"))
    images = {k: doc.embfile_get(f"cinema_img_{k}.jpg") for k in KEYS if f"cinema_img_{k}.jpg" in names}
    return data, images

def from_file(name, b):
    """続きから修正：アプリでダウンロードしたPDF（または前の原稿データ.zip）"""
    if name.lower().endswith(".pdf") or b[:4] == b"%PDF":
        return from_pdf(b)
    return from_zip(b)


# ---------------------------------------------------------------- 映画館から届くファイル（YOU 2026-10-28）
# 例：【TOHO】公開予定作品.xlsx（公開日・作品名・ジャンル・配給・URL）／【各務原】2026年12月公開作品.xlsx（公開日・配給・作品名）
#     【各務原】くれよん2026年12月号紹介文.doc（【公開日】【タイトル】【画像クレジット】【配給】【監督】【出演】【ストーリー】）
import datetime as _dt
WEEK = "月火水木金土日"

def _shared_strings(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    x = z.read("xl/sharedStrings.xml").decode()
    out = []
    for si in re.findall(r"<si>.*?</si>", x, re.S):
        si = re.sub(r"<rPh.*?</rPh>", "", si, flags=re.S)   # ふりがなは読まない（「公開日コウカイビ」になるため）
        out.append(html.unescape("".join(re.findall(r"<t[^>]*>([^<]*)</t>", si))))
    return out

def xlsx_rows(b):
    """1枚目のシート → [{列: 値}]（ふりがなを除く）"""
    z = zipfile.ZipFile(io.BytesIO(b))
    ss = _shared_strings(z)
    s = z.read("xl/worksheets/sheet1.xml").decode()
    rows = []
    for row in re.findall(r"<row [^>]*>(.*?)</row>", s, re.S):
        cells = {}
        for ref, attrs, body in re.findall(r'<c r="([A-Z]+)\d+"([^>/]*)(?:/>|>(.*?)</c>)', row, re.S):
            v = re.search(r"<v>([^<]*)</v>", body or "") or re.search(r"<t[^>]*>([^<]*)</t>", body or "")
            if v:
                val = ss[int(v.group(1))] if 't="s"' in attrs else v.group(1)
                if val.strip():
                    cells[ref] = nfc(val).strip()
        rows.append(cells)
    return rows

def to_date(v):
    """Excelの日付の番号（46360）・「2026年12月11日」・「12/11」→ date（年がわからなければ None の年）"""
    v = nfc(str(v)).strip()
    if re.fullmatch(r"\d{5}(\.0+)?", v):
        return _dt.date(1899, 12, 30) + _dt.timedelta(days=int(float(v)))
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})", v) or re.search(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", v)
    if m:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{1,2})\s*[/／月]\s*(\d{1,2})", v)
    if m:
        return _dt.date(2000, int(m.group(1)), int(m.group(2)))
    return None

def table_date(d):
    return f"{d.month}／{d.day}（{WEEK[d.weekday()]}）" if d.year != 2000 else f"{d.month}／{d.day}"

def which_theater(*texts):
    t = nfc(" ".join(x or "" for x in texts))
    for k, key in KAN.items():
        if k in t:
            return key
    return None

def title_key(t):
    """同じ作品か見比べるための形（スペース・かぎかっこ・〜まで を外す）"""
    t = unicodedata.normalize("NFKC", cut_made(nfc(t)))
    t = FEST.sub("", t)
    return re.sub(r"[\s　『』「」【】〈〉/／・:：!！?？~～\-ー]", "", t).lower()   # 「／」もスペースと同じに（館で書き方が違う）

def _same(a, b):
    """同じ作品か：そろえた形が同じ、または短いほう（4文字以上）が長いほうにまるごと入っている"""
    if a == b:
        return True
    s_, l_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(s_) >= 4 and s_ in l_

def read_cinema_schedule(name, b, month=None):
    """映画館の上映作品の一覧（.xlsx）→ (館, [(date, 作品名)])。month を渡すとその月の作品だけ"""
    rows = xlsx_rows(b)
    head = " ".join(" ".join(r.values()) for r in rows[:2])
    key = which_theater(name, head)
    # 見出しの行から「公開日」「作品名」の列を探す
    cd = ct = None
    for r in rows[:6]:
        for c, v in r.items():
            if "公開日" in v: cd = c
            if "作品名" in v: ct = c
        if cd and ct:
            break
    if not (cd and ct):
        raise ValueError(f"{name}：公開日と作品名の列が見つかりませんでした")
    items, cur = [], None
    for r in rows:
        if r.get(ct, "") in ("", ) or "作品名" in r.get(ct, ""):
            if r.get(cd) and to_date(r[cd]): cur = to_date(r[cd])
            continue
        if r.get(cd) and to_date(r[cd]):
            cur = to_date(r[cd])
        if cur is None:
            continue
        if month and cur.month != month:
            continue
        items.append((cur, r[ct].strip()))
    return key, items

def read_cinema_intro(name, text):
    """映画館の紹介文（【公開日】【タイトル】…）→ (館, theaters の1館ぶん)"""
    blocks, cur = {}, None
    for line in nfc(text).splitlines():
        m = re.match(r"\s*【(.+?)】\s*(.*)$", line)
        if m:
            cur = m.group(1).strip(); blocks[cur] = [m.group(2)] if m.group(2).strip() else []
        elif cur is not None:
            blocks[cur].append(line)
    g = {k: "\n".join(v).strip() for k, v in blocks.items()}
    def pick(*keys):
        for k in keys:
            for bk in g:
                if k in bk:
                    return g[bk]
        return ""
    t = {}
    title = pick("タイトル", "作品名")
    if title: t["title"] = title
    d = to_date(pick("公開日"))
    if d: t["date"] = f"{d.month}/{d.day}"
    if pick("監督"): t["director"] = "監督／" + re.sub(r"\s*[／/、,]\s*", "　", pick("監督")).strip()
    voice = pick("声の出演")
    cast = voice or pick("出演", "キャスト")
    if cast:
        names = [x.strip() for x in re.split(r"[／/、,，\n]", re.sub(r"\s*ほか\s*$", "", cast)) if x.strip()]
        t["cast"] = ("声の出演／" if voice else "出演／") + "　".join(names[:2])   # 出演者は2人（YOU 10/28）
    cr = pick("クレジット", "コピーライト", "©")
    if cr:
        cr = re.sub(r"\[c\]|\(c\)|（c）", "", cr, flags=re.I)
        cr = re.sub(r"^\s*©\s*", "©", cr).strip()
        t["copy"] = cr if cr.startswith("©") else "©" + cr
    body = pick("ストーリー", "あらすじ", "紹介文", "解説")
    if body: t["body"] = norm_body(body)
    return which_theater(name, text), t

def doc_text_of(name, b):
    n = name.lower()
    if n.endswith(".docx"):
        d = zipfile.ZipFile(io.BytesIO(b)).read("word/document.xml").decode()
        return "\n".join(nfc(html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))))
                         for p in re.findall(r"<w:p[ >].*?</w:p>", d, re.S))
    if n.endswith(".doc"):
        import doc_text
        return doc_text.doc_to_text(b)
    return nfc(b.decode("utf-8", "ignore"))

def merge_schedule(table, key, items):
    """今の表に、映画館の一覧を足す。同じ作品があれば●を付けるだけ、なければ行を足す"""
    table = [dict(r, dots=dict(r.get("dots", {}))) for r in table if (r.get("title") or "").strip()]
    added = marked = 0
    for d, title in items:
        tk = title_key(title)
        hit = next((r for r in table if _same(title_key(r["title"]), tk)), None)
        if hit:
            if not hit["dots"].get(key): marked += 1
            hit["dots"][key] = True
            new, slash = zen_space(title), lambda t: ("／" in t or "/" in t)
            if not slash(new) and (slash(hit["title"]) or len(new) > len(hit["title"])):
                hit["title"] = new                     # 「／」なしの書き方・長い（正式な）作品名のほうを使う
            continue
        r = {"date": table_date(d), "title": zen_space(title), "dots": {k: (k == key) for k in KEYS}}
        table.append(r); added += 1
    return table, added, marked


# 読み込んだときのファイルの時刻（streamlit_app._fresh が古い部品を読み直すのに使う）
_loaded_mtime = os.path.getmtime(__file__)
