# -*- coding: utf-8 -*-
"""シネマ原稿のAIチェック（YOU 2026-10-28 依頼）
① proofread：文字の校正（誤字脱字・言い回し・表記ゆれ）。直すかどうかは担当者が決める（自動では直さない）
② verify_movies：映画.comの作品ページを読んで、作品名の表記・公開日・監督・出演を照らし合わせる（出どころURLつき）
どちらも「お知らせ」。失敗してもアプリ本体（入力→PDF→ダウンロード）は止めない。
AIは アタ原アプリと同じ Gemini（鍵も同じ探し方）。"""
import json, os, re, urllib.error, urllib.request

MODELS = ["gemini-flash-latest", "gemini-3.6-flash", "gemini-flash-lite-latest"]
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}"
HALLS = {"kiso": "TOHOシネマズ木曽川", "kaka": "イオンシネマ各務原", "gifu": "TOHOシネマズ岐阜", "ina": "ユナイテッド・シネマ稲沢"}


def api_key():
    """StreamlitのSecrets → 環境変数 → ローカルの設定ファイル（アタ原と同じ）"""
    try:
        import streamlit as st
        k = st.secrets.get("GEMINI_API_KEY", "")
        if k:
            return k
    except Exception:
        pass
    k = os.environ.get("GEMINI_API_KEY", "")
    if k:
        return k
    try:
        for line in open(os.path.join(os.path.expanduser("~"), ".config", "atagen-app", "gemini.env")):
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def enabled():
    return bool(api_key())


def _call(prompt, search=False, timeout=45):
    """search=True のときは Google 検索つき（JSON指定は使えないので本文からJSONを取り出す）"""
    key = api_key()
    if not key:
        raise RuntimeError("AIの鍵が設定されていません")
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1}}
    if search:
        body["tools"] = [{"google_search": {}}]
    else:
        body["generationConfig"]["responseMimeType"] = "application/json"
    data = json.dumps(body).encode()
    last = None
    for model in MODELS:
        req = urllib.request.Request(ENDPOINT.format(model, key), data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode())
            cand = d["candidates"][0]
            text = "".join(p.get("text", "") for p in cand["content"]["parts"])
            sources = []
            for ch in (cand.get("groundingMetadata") or {}).get("groundingChunks", []):
                w = ch.get("web") or {}
                if w.get("uri"):
                    sources.append({"title": w.get("title", ""), "url": w["uri"]})
            return text, sources
        except urllib.error.HTTPError as e:
            last = f"{e.code} {e.reason}"
            continue
        except Exception as e:
            last = str(e)
            continue
    raise RuntimeError(last or "AIにつながりませんでした")


def _json(text):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    a, b = text.find("["), text.rfind("]")
    if a >= 0 and b > a and (text.find("{") < 0 or a < text.find("{")):
        return json.loads(text[a:b + 1])
    a, b = text.find("{"), text.rfind("}")
    return json.loads(text[a:b + 1])


# ---------------------------------------------------------------- ① 文字の校正
PROOF_RULES = """あなたは地域情報誌「くれよん」の校正担当です。映画紹介ページの原稿を校正してください。
指摘するもの：誤字脱字・変換ミス・助詞の誤り・不自然な言い回し・文の途中で切れている所・同じ原稿内の表記ゆれ（漢字とかなの混在など）・数字や記号の打ち間違い。
指摘しないもの（アプリが自動で直すので）：スペースの全角/半角、“”と『』、（午前十時の映画祭16）の大きさ、「～12/10(木)」のような上映終了日。
映画の内容（あらすじの事実）や作品名・人名の正しさはここでは判断しない（別のチェックで調べる）。迷ったら指摘する。
紹介文は映画会社の公式の文をそのまま使うことが多いので、言い回しの好みは level を "参考" にする。誤字脱字・変換ミス・意味が通らない所・表記ゆれは "要修正"。
結果はJSONの配列だけで返す：[{"level":"要修正|参考","where":"場所（例：TOHOシネマズ木曽川の紹介文）","original":"原稿の該当部分（短く）","suggestion":"直し案","reason":"理由（短く・やさしい言葉で）"}]
指摘がなければ [] を返す。"""


def proofread(data):
    lines = []
    for k, t in data.get("theaters", {}).items():
        h = HALLS.get(k, k)
        lines.append(f"【{h}】作品名：{t.get('title','')}／公開日：{t.get('date','')}／{t.get('director','')}／{t.get('cast','')}")
        lines.append(f"【{h}の紹介文】{t.get('body','')}")
        lines.append(f"【{h}の©】{t.get('copy','')}")
    lines.append("【上映作品の表】" + "／".join(r.get("title", "") for r in data.get("table", [])))
    text, _ = _call(PROOF_RULES + "\n\n# 原稿\n" + "\n".join(lines))
    out = _json(text)
    return out if isinstance(out, list) else []


# ---------------------------------------------------------------- ② 映画の情報の照合
# Googleの検索つきAIは、いまの無料の鍵では使えない（2026-10-28 実測：429・上限0回）。
# → アプリが映画.com（eiga.com）の作品ページを読み、その中身とAIに比べさせる（お金はかからない）
import html as _html, urllib.parse
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}

def _get(url, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read().decode("utf-8", "ignore")

def _plain(h):
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", "\n", h)
    t = _html.unescape(h)
    t = re.sub(r"[ \t\u3000]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()

def find_eiga(title):
    """映画.comで作品ページを探す（作品名のスペース・映画祭の注記を外して検索）"""
    q = re.sub(r"（午前十時の映画祭\d*）", "", title).replace("　", " ").strip()
    h = _get("https://eiga.com/search/" + urllib.parse.quote(q) + "/")
    m = re.search(r'href="(/movie/\d+/)"', h)
    if not m:
        return None, ""
    url = "https://eiga.com" + m.group(1)
    t = _plain(_get(url))
    a = t.find("作品情報") if "作品情報" in t else 0
    return url, t[max(0, a - 3000):a + 4000][:7000]

VERIFY = """映画情報サイト（映画.com）の作品ページの文章と、くれよんの原稿を比べて、食い違いがないか確かめてください。
確かめること：作品名の表記（記号・スペースの有無は気にしない。字の違いだけ）、日本での公開日（原稿は月/日だけ）、監督、出演者（声の出演のときは声優）、紹介文のあらすじの大きな事実（人物名・年代など）。
- サイトに書いていないことは "unknown"。断定しない。
- サイトのページが別の作品のようなら、全部 "unknown" にして note に「別の作品のページかもしれません」。
結果はJSONだけで返す：{{"items":[{{"field":"作品名|公開日|監督|出演|紹介文","status":"ok|ng|unknown","manuscript":"原稿の内容","web":"サイトの内容","note":"ひとこと"}}]}}

# 原稿
作品名：{title}
公開日：{date}
{director}
{cast}
紹介文：{body}

# 映画.comの作品ページ（{url}）
{page}"""

def verify_movie(t):
    try:
        url, page = find_eiga(t.get("title", ""))
    except Exception as e:
        return {"error": f"映画.comを読めませんでした（{e}）"}
    if not url:
        return {"items": [], "sources": [], "note": "映画.comで作品が見つかりませんでした（作品名を確かめてください）"}
    p = VERIFY.format(title=t.get("title", ""), date=t.get("date", ""), director=t.get("director", ""),
                      cast=t.get("cast", ""), body=t.get("body", ""), url=url, page=page)
    text, _ = _call(p)
    try:
        res = _json(text)
        items = res.get("items", []) if isinstance(res, dict) else res
    except Exception:
        items = [{"field": "全体", "status": "unknown", "manuscript": "", "web": "", "note": "AIの答えを読み取れませんでした"}]
    return {"items": items, "sources": [{"title": "映画.com", "url": url}]}

def verify_movies(data):
    """4作品を同時に調べる（1作品ずつだと3分ほどかかった）"""
    from concurrent.futures import ThreadPoolExecutor
    todo = {k: t for k, t in data.get("theaters", {}).items() if (t.get("title") or "").strip()}
    def one(t):
        try:
            return verify_movie(t)
        except Exception as e:
            return {"error": str(e)}
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = dict(zip(todo.keys(), ex.map(one, todo.values())))
    return res


# 読み込んだときのファイルの時刻（streamlit_app._fresh が古い部品を読み直すのに使う）
_loaded_mtime = os.path.getmtime(__file__)
