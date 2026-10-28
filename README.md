# シネマ原稿アプリ（くれよん一宮の読み物「映画館が選ぶ 今月の1本。」）

シネマ担当者が入力 → PDFでお客さん（映画館）に確認 → 直しは原稿データ(.zip)を戻して続きから →
OKならPDFと原稿データを高橋さんへメール → 高橋さんの手元でイラレに組み上げ（engineering/cinema/）。
YOUの依頼・決まり：secretary/notes/2026-10-28-decisions.md（シネマの節）。アタ原アプリとは別のアプリ。

## ファイル
| ファイル | 役割 |
|---|---|
| streamlit_app.py | 画面 |
| cinema_core.py | PDFを組む（背景＋座標＋決まり） |
| cinema_io.py | docx/xlsxの読み込み・表記のそろえ・原稿データzip |
| template/background_app.pdf | 背景（ベースから変わる所を消したもの・軽くした版） |
| template/layout.json | 置く場所の座標（mm） |
| tools/extract_layout.jsx | ベースが変わったら、これで座標と背景を作り直す |

## 手元で動かす
```
CINEMA_APP_DEV=1 /Users/kc02/.company/engineering/atagen-app/gradio/.venv/bin/streamlit run streamlit_app.py --server.port 8531
```

## ベースが変わったとき
1. 新しい シネマ.ai を template/シネマ_base.ai にコピー
2. tools/extract_layout.jsx をイラレで流す → layout_raw.json（→ layout.json にコピー）
3. 開いたままの書類を「[高品質印刷]」でPDF保存 → 軽くして background_app.pdf（notes 10/28 の手順）
