# シネマ担当者の テキスト.docx・スケジュール.xlsx → シネマ流し込み用データ(JSON)
import sys, zipfile, re, html, json, unicodedata
docx, xlsx, out = sys.argv[1:4]
KAN = {"木曽川":"kiso","各務原":"kaka","岐阜":"gifu","稲沢":"ina"}
FEST = re.compile(r'[（(]午前十時の映画祭\s*\d+[）)]')
def nfc(s): return unicodedata.normalize('NFC', s)
def zen_space(s): return re.sub(r'[  ]+', '　', s.strip())
def cut_made(s): return re.sub(r'[ 　]*[～〜~][ 　]*\d{1,2}/\d{1,2}[（(][^）)]*[）)]', '', s)
def fest_norm(s): return FEST.sub(lambda m: '（'+re.sub(r'[（()）\s]','',m.group(0))+'）', s)
def quotes(s): return s.replace('“','『').replace('”','』').replace('"','')
# --- docx
d = zipfile.ZipFile(docx).read('word/document.xml').decode()
paras = [nfc(html.unescape(''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p)))) for p in re.findall(r'<w:p[ >].*?</w:p>', d, re.S)]
theaters, cur = {}, None
for p in paras:
    m = re.match(r'【(.+)】', p.strip())
    if m:
        name = m.group(1); key = next(v for k,v in KAN.items() if k in name)
        cur = theaters.setdefault(key, {"hall":name, "body":[]}); continue
    if cur is None or not p.strip(): continue
    s = p.strip()
    if s.startswith('作品／'):
        m = re.match(r'作品／(.+?)[ 　]+(\d{1,2})／(\d{1,2})公開$', s)
        cur["title"] = fest_norm(zen_space(cut_made(m.group(1)))); cur["date"] = m.group(2)+"/"+m.group(3)
    elif s.startswith('監督／'): cur["director"] = s
    elif s.startswith('出演／') or s.startswith('声の出演／'): cur["cast"] = s
    elif s.startswith('©'): cur["copy"] = s
    else: cur["body"].append(quotes(s))
for t in theaters.values(): t["body"] = ''.join(t["body"])
# --- xlsx
z = zipfile.ZipFile(xlsx)
ss = [html.unescape(''.join(re.findall(r'<t[^>]*>([^<]*)</t>', si))) for si in re.findall(r'<si>.*?</si>', z.read('xl/sharedStrings.xml').decode(), re.S)]
s = z.read('xl/worksheets/sheet1.xml').decode()
rows = []
for row in re.findall(r'<row [^>]*>(.*?)</row>', s, re.S):
    cells = {}
    for ref, attrs, body in re.findall(r'<c r="([A-Z]+)\d+"([^>/]*)(?:/>|>(.*?)</c>)', row, re.S):
        v = re.search(r'<v>([^<]*)</v>', body or '')
        if v: cells[ref] = nfc(ss[int(v.group(1))] if 't="s"' in attrs else v.group(1))
    rows.append(cells)
header = rows[0]; cols = {}
for c, v in header.items():
    for k, key in KAN.items():
        if k in v: cols[key] = c
table = []
for r in rows[1:]:
    t = r.get('B','').strip()
    if not t or t.startswith('★'): continue
    date = r.get('A','').strip()
    if date:
        m = re.match(r'(\d{1,2})/(\d{1,2})\s*[（(](.)[）)]', date); date = f"{m.group(1)}／{m.group(2)}（{m.group(3)}）"
    table.append({"date":date, "title":fest_norm(zen_space(cut_made(t))), "dots":{k:(r.get(c,'').strip()=='●') for k,c in cols.items()}})
notes = [r['B'] for r in rows[1:] if r.get('B','').startswith('★')]
json.dump({"theaters":theaters, "table":table, "notes":notes, "has_schedule":{k:any(x["dots"][k] for x in table) for k in KAN.values()}}, open(out,'w'), ensure_ascii=False, indent=1)
print(json.dumps({"theaters":theaters, "table":table, "has_schedule":{k:any(x["dots"][k] for x in table) for k in KAN.values()}}, ensure_ascii=False, indent=1))
