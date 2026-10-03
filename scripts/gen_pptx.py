#!/usr/bin/env python3
"""生成 7 章授课 PPT(数据驱动,python-pptx)。

内容模块:scripts/ppt_content/ch{N}.py,各导出 META 与 PAGES。
页类型:
  ("SECTION:", 标题)            讲次分隔页(深蓝底)
  ("TOC:", [条目...])           目录页(双栏)
  ("QUIZ:", 标题, 正文)         自测页(琥珀边条)
  (标题, 正文, 备注|None)       标准内容页(备注进底部蓝条)
用法:uv run --with python-pptx python scripts/gen_pptx.py [章号模块名...]
"""

from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Pt

INK = RGBColor(0x0B, 0x1D, 0x3A)
BLUE = RGBColor(0x25, 0x63, 0xEB)
AMBER = RGBColor(0xF5, 0x9E, 0x0B)
GREY = RGBColor(0x47, 0x55, 0x69)
WHITE = RGBColor(255, 255, 255)
SILVER = RGBColor(0xCB, 0xD5, 0xE1)
FAINT = RGBColor(0x94, 0xA3, 0xB8)
LIGHT = RGBColor(0xF1, 0xF5, 0xF9)
FONT = "PingFang SC"
W, H = Emu(12192000), Emu(6858000)

OUT = Path(__file__).resolve().parents[3] / "03-课件PPT"
X0, XM = Emu(640000), Emu(700000)


def _text(shape, content: str, size: int, color=GREY, bold=False, align=PP_ALIGN.LEFT, spacing=1.0):
    tf = shape.text_frame
    tf.word_wrap = True
    first = True
    for line in content.split("\n"):
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.line_spacing = spacing
        r = p.add_run()
        r.text = line
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color


def _footer(slide, idx: int, total: int, chapter: str):
    box = slide.shapes.add_textbox(W - Emu(2300000), H - Emu(540000), Emu(1900000), Emu(340000))
    _text(box, f"第{chapter}章 · {idx}/{total}", 10, FAINT, align=PP_ALIGN.RIGHT)


def _cover(prs, no: str, title: str, subtitle: str):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(1, 0, 0, W, H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = INK
    band = s.shapes.add_shape(1, 0, H - Emu(260000), W, Emu(260000))
    band.fill.solid()
    band.fill.fore_color.rgb = AMBER
    _text(
        s.shapes.add_textbox(X0, Emu(1400000), W - 2 * X0, Emu(640000)),
        f"第 {no} 章",
        28,
        AMBER,
        True,
    )
    _text(s.shapes.add_textbox(X0, Emu(2000000), W - 2 * X0, Emu(1700000)), title, 42, WHITE, True)
    _text(s.shapes.add_textbox(X0, Emu(3750000), W - 2 * X0, Emu(900000)), subtitle, 18, SILVER)
    _text(
        s.shapes.add_textbox(X0, Emu(5200000), W - 2 * X0, Emu(500000)),
        "AI Agent 全栈工程师训练营 · Agent Engineering Platform",
        14,
        FAINT,
    )


def _section(prs, title: str):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(1, 0, 0, W, H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = INK
    tag = s.shapes.add_shape(1, X0, Emu(2600000), Emu(120000), Emu(1000000))
    tag.fill.solid()
    tag.fill.fore_color.rgb = AMBER
    _text(
        s.shapes.add_textbox(X0 + Emu(300000), Emu(2550000), W - 2 * X0, Emu(1200000)),
        title,
        32,
        WHITE,
        True,
    )


def _toc(prs, items: list):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bar = s.shapes.add_shape(1, 0, 0, W, Emu(1050000))
    bar.fill.solid()
    bar.fill.fore_color.rgb = INK
    _text(
        s.shapes.add_textbox(XM, Emu(180000), W - 2 * XM, Emu(720000)), "本章目录", 26, WHITE, True
    )
    half = (len(items) + 1) // 2
    for col, chunk in enumerate((items[:half], items[half:])):
        box = s.shapes.add_textbox(
            XM + col * Emu(5600000), Emu(1450000), Emu(5300000), Emu(4900000)
        )
        _text(
            box,
            "\n".join(f"{i + 1 + col * half}. {it}" for i, it in enumerate(chunk)),
            15,
            GREY,
            spacing=1.35,
        )


def _content(prs, title: str, body: str, note):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bar = s.shapes.add_shape(1, 0, 0, W, Emu(1050000))
    bar.fill.solid()
    bar.fill.fore_color.rgb = INK
    tag = s.shapes.add_shape(1, 0, 0, Emu(150000), Emu(1050000))
    tag.fill.solid()
    tag.fill.fore_color.rgb = AMBER
    _text(
        s.shapes.add_textbox(Emu(360000), Emu(160000), W - Emu(720000), Emu(740000)),
        title,
        24,
        WHITE,
        True,
    )
    n_lines = body.count("\n") + 1
    size = 16 if n_lines <= 7 else 13
    _text(
        s.shapes.add_textbox(XM, Emu(1450000), W - 2 * XM, Emu(4200000)),
        body,
        size,
        GREY,
        spacing=1.25,
    )
    if note:
        box = s.shapes.add_shape(1, XM, Emu(5600000), W - 2 * XM, Emu(820000))
        box.fill.solid()
        box.fill.fore_color.rgb = LIGHT
        tf = box.text_frame
        tf.word_wrap = True
        r = tf.paragraphs[0].add_run()
        r.text = "▶ " + note
        r.font.name = FONT
        r.font.size = Pt(12)
        r.font.color.rgb = BLUE


def _quiz(prs, title: str, body: str):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bar = s.shapes.add_shape(1, 0, 0, W, Emu(1050000))
    bar.fill.solid()
    bar.fill.fore_color.rgb = AMBER
    _text(
        s.shapes.add_textbox(Emu(360000), Emu(160000), W - Emu(720000), Emu(740000)),
        title,
        24,
        INK,
        True,
    )
    _text(
        s.shapes.add_textbox(XM, Emu(1450000), W - 2 * XM, Emu(4400000)),
        body,
        17,
        GREY,
        spacing=1.3,
    )


def _parse_txt(path: Path) -> tuple[dict, list]:
    """解析紧凑 DSL:首行 #META no=..|title=..|subtitle=..;块指令 #TOC/#SECTION/#PAGE/#QUIZ。"""
    meta: dict = {}
    pages: list = []
    kind = ""
    title = ""
    lines: list[str] = []
    note = ""

    def flush() -> None:
        nonlocal kind, title, lines, note
        if not kind:
            return
        if kind == "TOC":
            pages.append(("TOC:", list(lines)))
        elif kind == "CODE":
            pages.append(("CODE:", title))
        elif kind == "SECTION":
            pages.append(("SECTION:", title))
        elif kind == "QUIZ":
            pages.append(("QUIZ:", title, "\n".join(lines)))
        else:
            pages.append((title, "\n".join(lines), note or None))
        kind, title, lines, note = "", "", [], ""

    for raw in path.read_text().splitlines():
        line = raw.rstrip()
        if line.startswith("#META"):
            _, rest = line.split(" ", 1)
            parts = rest.split("|")
            meta = {"no": parts[0], "title": parts[1], "subtitle": parts[2]}
        elif line.startswith(("#TOC", "#SECTION", "#PAGE", "#QUIZ", "#CODE")):
            flush()
            kind, title = line[1:].split(" ", 1) if " " in line else (line[1:], "")
        elif line.startswith(">>"):
            note = line[2:].strip()
        elif line.strip():
            lines.append(line)
    flush()
    return meta, pages


_CODE_FONT_MONO = "/System/Library/Fonts/Menlo.ttc"
_CODE_FONT_CJK = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def _render_code_png(code: str, out_png: Path) -> tuple[int, int]:
    """把源码渲染为深底截图(ASCII 用 Menlo,含中文行用 PingFang)。"""
    from PIL import Image, ImageDraw, ImageFont

    lines = code.splitlines()
    size = (1760, max(220, 90 + 30 * len(lines) + 40))
    img = Image.new("RGB", size, (13, 27, 42))
    draw = ImageDraw.Draw(img)
    mono = ImageFont.truetype(_CODE_FONT_MONO, 19)
    cjk = ImageFont.truetype(_CODE_FONT_CJK, 19)
    gutter_font = ImageFont.truetype(_CODE_FONT_MONO, 15)
    y = 60
    for i, line in enumerate(lines, start=1):
        line = line[:96]
        draw.text((56, y), f"{i:>3}", font=gutter_font, fill=(94, 110, 130))
        font = cjk if any(ord(c) > 0x2E80 for c in line) else mono
        color = (200, 210, 225)
        s = line.lstrip()
        if s.startswith(("class ", "def ", "async def")):
            color = (120, 180, 255)
        elif s.startswith("#"):
            color = (120, 200, 140)
        draw.text((110, y), line, font=font, fill=color)
        y += 30
    img.save(out_png)
    return size


def _code_page(prs, title: str, spec: str, repo_root: Path):
    path_part, _, range_part = spec.partition(":")
    f = repo_root / path_part.strip()
    start, _, end = range_part.partition("-")
    src_lines = f.read_text().splitlines()
    a, b = int(start), int(end or start)
    code = "\n".join(src_lines[a - 1 : b])
    out_png = Path(tempfile.gettempdir()) / f"code_{abs(hash(spec))}.png"
    w, h = _render_code_png(code, out_png)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(1, 0, 0, W, H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = INK
    bar = s.shapes.add_shape(1, 0, 0, W, Emu(900000))
    bar.fill.solid()
    bar.fill.fore_color.rgb = RGBColor(0x14, 0x2A, 0x4C)
    _text(
        s.shapes.add_textbox(Emu(360000), Emu(120000), W - Emu(720000), Emu(660000)),
        f"{title}  ·  {path_part}:{a}-{b}",
        20,
        AMBER,
        True,
    )
    avail_h = int(H * 0.86)
    avail_w = int(W * 0.94)
    scale = min(avail_w / w, avail_h / h)
    pic_w, pic_h = int(w * scale), int(h * scale)
    s.shapes.add_picture(str(out_png), int((W - pic_w) / 2), Emu(1100000), pic_w, pic_h)


def build(module_name: str):
    txt = Path(__file__).parent / "ppt_content" / f"{module_name}.txt"
    if txt.exists():
        meta, pages = _parse_txt(txt)
    else:
        mod = importlib.import_module(f"ppt_content.{module_name}")
        meta, pages = mod.META, mod.PAGES
    total = len(pages) + 1
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    _cover(prs, meta["no"], meta["title"], meta["subtitle"])
    for i, page in enumerate(pages, start=2):
        kind = page[0]
        if kind == "CODE:":
            meta_title, _, code_spec = page[1].partition("|")
            _code_page(
                prs, meta_title.strip(), code_spec.strip(), Path(__file__).resolve().parents[1]
            )
        elif kind == "SECTION:":
            _section(prs, page[1])
        elif kind == "TOC:":
            _toc(prs, page[1])
        elif kind == "QUIZ:":
            _quiz(prs, page[1], page[2])
        else:
            _content(prs, page[0], page[1], page[2] if len(page) > 2 else None)
        last = prs.slides[len(prs.slides._sldIdLst) - 1]
        _footer(last, i, total, meta["no"])
    safe_title = meta["title"].split(":")[0].split("、")[0]
    out = OUT / f"第{meta['no']}章-{safe_title}.pptx"
    prs.save(out)
    print(f"生成: {out.name}({total} 页)")


def main() -> int:
    targets = sys.argv[1:] or [f"ch{i}" for i in range(1, 8)]
    sys.path.insert(0, str(Path(__file__).parent))
    OUT.mkdir(parents=True, exist_ok=True)
    for t in targets:
        build(t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
