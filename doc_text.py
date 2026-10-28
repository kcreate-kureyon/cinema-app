# -*- coding: utf-8 -*-
"""古い形式の Word（.doc）から文字だけを取り出す（映画館から .doc で届くため・YOU 2026-10-28）
クラウド（Linux）には Word も textutil も無いので、.doc の中の「文字のつながり表（piece table）」を自分で読む"""
import io, struct

import olefile


def doc_to_text(b):
    ole = olefile.OleFileIO(io.BytesIO(b))
    wd = ole.openstream("WordDocument").read()
    flags = struct.unpack_from("<H", wd, 0x0A)[0]
    table = ole.openstream("1Table" if flags & 0x0200 else "0Table").read()
    fc_clx, lcb_clx = struct.unpack_from("<II", wd, 0x01A2)
    clx = table[fc_clx:fc_clx + lcb_clx]
    i = 0
    while i < len(clx) and clx[i] == 0x01:          # Prc（書式の情報）は飛ばす
        cb = struct.unpack_from("<H", clx, i + 1)[0]
        i += 3 + cb
    if i >= len(clx) or clx[i] != 0x02:
        raise ValueError("Wordの文字を読み取れませんでした")
    lcb = struct.unpack_from("<I", clx, i + 1)[0]
    plc = clx[i + 5:i + 5 + lcb]
    n = (lcb - 4) // 12
    cps = struct.unpack_from("<%dI" % (n + 1), plc, 0)
    out = []
    for k in range(n):
        pcd = plc[4 * (n + 1) + 8 * k: 4 * (n + 1) + 8 * (k + 1)]
        fc = struct.unpack_from("<I", pcd, 2)[0]
        cnt = cps[k + 1] - cps[k]
        if fc & 0x40000000:                       # 1バイトの文字
            off = (fc & ~0x40000000) // 2
            out.append(wd[off:off + cnt].decode("cp1252", "replace"))
        else:                                     # 2バイトの文字（日本語）
            out.append(wd[fc:fc + 2 * cnt].decode("utf-16-le", "replace"))
    t = "".join(out)
    t = t.replace("\r\x07", "\n").replace("\x07", "\n").replace("\r", "\n").replace("\x0b", "\n").replace("\x0c", "\n")
    return "".join(c for c in t if c >= " " or c == "\n")


# 読み込んだときのファイルの時刻（streamlit_app._fresh が古い部品を読み直すのに使う）
import os
_loaded_mtime = os.path.getmtime(__file__)
