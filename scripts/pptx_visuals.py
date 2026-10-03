#!/usr/bin/env python3
"""PPT 视觉库:代码化绘制架构图/流程图/状态机/时序图/数据图表/看板/终端/金字塔/时间线。

设计规范(大厂风):Design Tokens 与平台同源;白底内容页+深空蓝章节页;
图表一律用平台真实实测数据。全部原生 pptx 形状 + matplotlib 渲染,零外部素材。
"""

from __future__ import annotations

import math
from pathlib import Path

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE as SHP
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt

INK = RGBColor(0x0B, 0x1D, 0x3A)
PANEL = RGBColor(0x14, 0x2A, 0x4C)
BLUE = RGBColor(0x25, 0x63, 0xEB)
AMBER = RGBColor(0xF5, 0x9E, 0x0B)
TEAL = RGBColor(0x14, 0xB8, 0xA6)
GREEN = RGBColor(0x34, 0xD3, 0x99)
RED = RGBColor(0xF8, 0x71, 0x71)
PURPLE = RGBColor(0x8B, 0x5C, 0xF6)
GREY = RGBColor(0x47, 0x55, 0x69)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SILVER = RGBColor(0xCB, 0xD5, 0xE1)
FAINT = RGBColor(0x94, 0xA3, 0xB8)
LIGHT = RGBColor(0xF1, 0xF5, 0xF9)
BORDER = RGBColor(0xDD, 0xE5, 0xEE)
FONT = "PingFang SC"
ACCENTS = (BLUE, TEAL, PURPLE, AMBER, GREEN, RED)

W, H = Emu(12192000), Emu(6858000)


def _px(v: float) -> Emu:
    return Emu(int(v * 9525))  # px → EMU


def box(slide, x, y, w, h, fill=None, line=None, radius=True, shadow=False):
    shp = slide.shapes.add_shape(SHP.ROUNDED_RECTANGLE if radius else SHP.RECTANGLE, x, y, w, h)
    if radius:
        try:
            shp.adjustments[0] = 0.08
        except Exception:
            pass
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1)
    shp.shadow.inherit = False
    return shp


def label(
    slide,
    x,
    y,
    w,
    h,
    text,
    size=12,
    color=GREY,
    bold=False,
    align=PP_ALIGN.CENTER,
    font=FONT,
    anchor=MSO_ANCHOR.MIDDLE,
    spacing=1.0,
):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    first = True
    for line in text.split("\n"):
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.line_spacing = spacing
        r = p.add_run()
        r.text = line
        r.font.name = font
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
    return tb


def header(slide, title: str, tag: str = "", dark: bool = False):
    bar = box(slide, 0, 0, W, _px(74), fill=INK if not dark else PANEL, radius=False)
    box(slide, 0, 0, _px(8), _px(74), fill=AMBER, radius=False)
    label(slide, _px(28), 0, W - _px(200), _px(74), title, 20, WHITE, True, align=PP_ALIGN.LEFT)
    if tag:
        label(slide, W - _px(300), 0, _px(280), _px(74), tag, 11, FAINT, align=PP_ALIGN.RIGHT)


def footer(slide, idx, total, chapter):
    label(
        slide,
        W - _px(200),
        H - _px(34),
        _px(170),
        _px(28),
        f"第{chapter}章 · {idx}/{total}",
        9,
        FAINT,
        align=PP_ALIGN.RIGHT,
    )


def arrow(slide, x1, y1, x2, y2, color=FAINT, width=1.5, dashed=False):
    conn = slide.shapes.add_connector(1, x1, y1, x2, y2)  # straight
    conn.line.color.rgb = color
    conn.line.width = Pt(width)
    if dashed:
        from pptx.enum.dml import MSO_LINE_DASH_STYLE

        conn.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    # 箭头:终点小三角
    dx, dy = x2 - x1, y2 - y1
    ang = math.atan2(int(dy), int(dx))
    L, spread = _px(9), _px(0.32)
    import pptx.util as U

    cx = int(x2) - int(L / 2 * math.cos(ang))
    cy = int(y2) - int(L / 2 * math.sin(ang))
    tri = slide.shapes.add_shape(
        SHP.ISOSCELES_TRIANGLE, U.Emu(cx - int(L / 2)), U.Emu(cy - int(L / 2)), L, L
    )
    tri.rotation = math.degrees(ang) + 90
    tri.fill.solid()
    tri.fill.fore_color.rgb = color
    tri.line.fill.background()
    tri.shadow.inherit = False
    return conn


# ── 1) 分层架构图 ----------------------------------------------------------


def arch_diagram(slide, title: str, layers: list[list[str]], tag: str = "", flows: str = ""):
    """layers: 每层若干组件;flows: 层间标注。空层渲染提示页。"""
    header(slide, title, tag)
    layers = [l for l in layers if l]
    if not layers:
        label(slide, _px(120), H // 2 - _px(40), W - _px(240), _px(80), "(图数据缺失)", 16, FAINT)
        return
    n = len(layers)
    top, lh = _px(100), _px(min(430 / n, 120))
    gap = _px(min(26, 380 / n))
    width = W - _px(360)
    x0 = _px(200)
    for i, comps in enumerate(layers):
        y = top + i * (lh + gap)
        band = box(
            slide, x0 - _px(6), y - _px(4), width + _px(12), lh + _px(8), fill=LIGHT, radius=True
        )
        cw = (width - _px(16) * (len(comps) - 1)) // max(1, len(comps))
        for j, c in enumerate(comps):
            cx = x0 + j * (cw + _px(16))
            color = ACCENTS[i % len(ACCENTS)]
            b = box(slide, cx, y, cw, lh, fill=WHITE, line=color)
            box(slide, cx, y, _px(5), lh, fill=color, radius=False)
            label(slide, cx + _px(14), y, cw - _px(24), lh, c, 12, GREY, True, align=PP_ALIGN.LEFT)
        if i < n - 1:
            arrow(slide, W // 2, y + lh + _px(6), W // 2, y + lh + gap - _px(4), FAINT, 1.2)
            if flows:
                marks = flows.split(",")
                if i < len(marks):
                    label(
                        slide,
                        W // 2 + _px(16),
                        y + lh,
                        _px(220),
                        gap,
                        marks[i],
                        10,
                        FAINT,
                        align=PP_ALIGN.LEFT,
                    )


# ── 2) 横向流程图 ----------------------------------------------------------


def flow_diagram(
    slide, title: str, steps: list[str], tag: str = "", loop_to: int | None = None, note: str = ""
):
    header(slide, title, tag)
    n = len(steps)
    margin = _px(90)
    total_w = W - margin * 2
    gapw = _px(64 if n <= 5 else 34)
    cw = (total_w - gapw * (n - 1)) // n
    ch = _px(120)
    y = H // 2 - ch // 2 - _px(20)
    centers = []
    for i, s in enumerate(steps):
        x = margin + i * (cw + gapw)
        color = ACCENTS[i % len(ACCENTS)]
        b = box(slide, x, y, cw, ch, fill=WHITE, line=color)
        box(slide, x, y, cw, _px(6), fill=color, radius=False)
        # 序号徽章
        badge = box(slide, x + cw // 2 - _px(15), y - _px(15), _px(30), _px(30), fill=color)
        label(
            slide, x + cw // 2 - _px(15), y - _px(16), _px(30), _px(30), str(i + 1), 13, WHITE, True
        )
        label(slide, x + _px(8), y + _px(14), cw - _px(16), ch - _px(20), s, 12, GREY, True)
        centers.append((x, x + cw))
        if i:
            px = centers[i - 1][1]
            arrow(slide, px + _px(6), y + ch // 2, x - _px(8), y + ch // 2, GREY, 1.6)
    if loop_to is not None and loop_to < n:
        lx1 = centers[n - 1][0] + cw // 2
        lx2 = centers[loop_to][0] + cw // 2
        yb = y + ch + _px(30)
        arrow(slide, lx1, y + ch + _px(6), lx1, yb, AMBER, 1.6, dashed=True)
        arrow(slide, lx1, yb, lx2, yb, AMBER, 1.6, dashed=True)
        arrow(slide, lx2, yb, lx2, y + ch + _px(6), AMBER, 1.6, dashed=True)
        label(slide, lx2, yb - _px(26), lx1 - lx2 + cw, _px(22), "循环(loop)", 10, AMBER, True)
    if note:
        box(slide, margin, H - _px(120), W - margin * 2, _px(44), fill=LIGHT)
        label(
            slide,
            margin + _px(16),
            H - _px(120),
            W - margin * 2 - _px(32),
            _px(44),
            "▶ " + note,
            12,
            BLUE,
            align=PP_ALIGN.LEFT,
        )


# ── 3) 状态机图 ------------------------------------------------------------


def state_diagram(slide, title: str, spec: str, tag: str = ""):
    """spec: 'A,B,C,D;A->B:启动;B->C:完成;C->A:回退'  网格自动布局。"""
    header(slide, title, tag)
    node_part, _, edge_part = spec.partition(";")
    nodes = [n.strip() for n in node_part.split(",") if n.strip()]
    edges = []
    for e in edge_part.split(";"):
        e = e.strip()
        if not e:
            continue
        l, _, lbl = e.partition(":")
        a, _, b = l.partition("->")
        edges.append((a.strip(), b.strip(), lbl.strip()))
    n = len(nodes)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    gw, gh = _px(250), _px(110)
    x0 = (W - cols * gw) // 2
    y0 = _px(130)
    vgap = _px(60)
    y0 = max(y0, (H - rows * (gh + vgap)) // 2 + _px(10))
    pos = {}
    for i, node in enumerate(nodes):
        r, c = divmod(i, cols)
        x, y = x0 + c * gw, y0 + r * (gh + vgap)
        terminal = node in ("completed", "failed", "cancelled")
        start = node == "created"
        fill = GREEN if terminal else (AMBER if start else WHITE)
        fg = INK if (terminal or start) else GREY
        b = box(
            slide, x, y, gw - _px(16), gh, fill=fill, line=None if (terminal or start) else BLUE
        )
        label(slide, x, y, gw - _px(16), gh, node, 13, fg, True)
        pos[node] = (x + (gw - _px(16)) // 2, y, y + gh, x, x + gw - _px(16))
    for a, b, lbl in edges:
        if a not in pos or b not in pos:
            continue
        ax, atop, abot, _, aright = pos[a]
        bx, btop, bbot, bleft, bright = pos[b]
        if abs(bx - ax) < 10 and bbot < atop:  # 下→上(回退)
            arrow(slide, ax + _px(30), atop, bx + _px(30), bbot, RED, 1.4, dashed=True)
        elif abs(bx - ax) < 10 and btop > abot:  # 上→下
            arrow(slide, ax, abot, bx, btop, GREY, 1.4)
        elif bx > ax:  # 右向
            arrow(slide, aright, (atop + abot) // 2, bleft, (btop + bbot) // 2, GREY, 1.4)
        else:
            arrow(slide, ax - _px(0) + 0, (atop + abot) // 2, bright, (btop + bbot) // 2, GREY, 1.4)
        if lbl:
            mx = (aright + bleft) // 2 if bx > ax else (bright + ax - _px(16)) // 2
            label(
                slide, mx - _px(90), (atop + abot) // 2 - _px(34), _px(180), _px(24), lbl, 9, FAINT
            )


# ── 4) 时序图 --------------------------------------------------------------


def seq_diagram(slide, title: str, actors: list[str], messages: list[tuple]):
    """messages: (from_idx,to_idx,'label') 索引相同=自调用。"""
    header(slide, title)
    n = len(actors)
    margin = _px(140)
    xs = [margin + i * (W - margin * 2) // (n - 1) for i in range(n)]
    top, bot = _px(150), H - _px(110)
    for i, a in enumerate(actors):
        box(slide, xs[i] - _px(100), top - _px(46), _px(200), _px(42), fill=PANEL)
        label(slide, xs[i] - _px(100), top - _px(46), _px(200), _px(42), a, 12, WHITE, True)
        from pptx.enum.dml import MSO_LINE_DASH_STYLE

        ln = slide.shapes.add_connector(1, xs[i], top, xs[i], bot)
        ln.line.color.rgb = BORDER
        ln.line.width = Pt(1)
        ln.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    step_h = (bot - top - _px(30)) // max(1, len(messages))
    for k, (fi, ti, msg) in enumerate(messages):
        y = top + _px(40) + k * step_h
        if fi == ti:  # 自调用
            arrow(slide, xs[fi], y, xs[fi] + _px(60), y, TEAL, 1.4)
            arrow(slide, xs[fi] + _px(60), y, xs[fi] + _px(60), y + _px(22), TEAL, 1.4)
            arrow(slide, xs[fi] + _px(60), y + _px(22), xs[fi], y + _px(22), TEAL, 1.4)
            label(
                slide,
                xs[fi] + _px(10),
                y - _px(28),
                _px(260),
                _px(24),
                msg,
                10,
                TEAL,
                align=PP_ALIGN.LEFT,
            )
        else:
            color = BLUE if ti > fi else AMBER  # 请求蓝 / 响应琥珀
            arrow(slide, xs[fi], y, xs[ti], y, color, 1.6)
            mid = min(xs[fi], xs[ti]) + (abs(xs[ti] - xs[fi]) // 2)
            label(
                slide, mid - _px(160), y - _px(30), _px(320), _px(24), f"{k + 1}. {msg}", 10, color
            )


# ── 5) 数据图表(matplotlib → PNG)------------------------------------------


def chart_png(spec: str, out: Path) -> str:
    """spec: 'bar|标题|a=1,b=2' / 'hbar|…' / 'line|标题|k1=v1,k2=v2' / 'donut|…'"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm

    fp = fm.FontProperties(fname="/System/Library/Fonts/Hiragino Sans GB.ttc")
    plt.rcParams["axes.unicode_minus"] = False
    kind, _, rest = spec.partition("|")
    title, _, data_part = rest.partition("|")
    pairs = []
    for kv in data_part.split(","):
        k, _, v = kv.partition("=")
        pairs.append((k.strip(), float(v)))
    labels = [p[0] for p in pairs]
    values = [p[1] for p in pairs]
    colors = ["#2563EB", "#14B8A6", "#8B5CF6", "#F59E0B", "#34D399", "#F87171"]
    fig, ax = plt.subplots(figsize=(11.2, 4.6), dpi=160)
    fig.patch.set_facecolor("white")
    if kind in ("bar", "hbar"):
        (
            ax.barh(labels, values, color=colors[: len(values)])
            if kind == "hbar"
            else ax.bar(labels, values, color=colors[: len(values)], width=0.55)
        )
        for i, v in enumerate(values):
            (
                ax.text(
                    v,
                    i,
                    f"{v:g}",
                    va="center",
                    fontsize=11,
                    fontproperties=fp,
                    color="#0B1D3A",
                    fontweight="bold",
                )
                if kind == "hbar"
                else ax.text(
                    i,
                    v,
                    f"{v:g}",
                    ha="center",
                    va="bottom",
                    fontsize=11,
                    fontproperties=fp,
                    color="#0B1D3A",
                    fontweight="bold",
                )
            )
    elif kind == "line":
        ax.plot(labels, values, "-o", color="#2563EB", lw=2.5, ms=8, mfc="#F59E0B")
        for i, v in enumerate(values):
            ax.annotate(
                f"{v:g}",
                (i, v),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=11,
                fontproperties=fp,
                color="#0B1D3A",
                fontweight="bold",
            )
        ax.set_ylim(min(values) * 0.9 if min(values) > 0 else 0, max(values) * 1.15)
    elif kind == "donut":
        wedges, _, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors[: len(values)],
            autopct="%1.1f%%",
            startangle=90,
            pctdistance=0.78,
            wedgeprops=dict(width=0.42, edgecolor="white"),
            textprops=dict(fontproperties=fp, fontsize=11, color="#0B1D3A"),
        )
        for at in autotexts:
            at.set_color("white")
            at.set_fontweight("bold")
    elif kind == "groupbar":  # data_part: label:a1/a2,b1/b2 (两组)
        groups = [kv.split("=") for kv in data_part.split(",")]
        gl = [g[0] for g in groups]
        import numpy as np

        v1 = [float(g[1].split("/")[0]) for g in groups]
        v2 = [float(g[1].split("/")[1]) for g in groups]
        x = np.arange(len(gl))
        ax.bar(x - 0.18, v1, 0.34, label="仅精确键", color="#94A3B8")
        ax.bar(x + 0.18, v2, 0.34, label="+L3 语义层", color="#2563EB")
        for xi, (a, b) in enumerate(zip(v1, v2)):
            ax.text(
                xi - 0.18,
                a,
                f"{a:g}",
                ha="center",
                va="bottom",
                fontsize=10,
                fontproperties=fp,
                color="#475569",
            )
            ax.text(
                xi + 0.18,
                b,
                f"{b:g}",
                ha="center",
                va="bottom",
                fontsize=10,
                fontproperties=fp,
                color="#0B1D3A",
                fontweight="bold",
            )
        ax.set_xticks(x)
        ax.set_xticklabels(gl, fontproperties=fp)
        ax.legend(prop=fp, frameon=False)
        labels, values = gl, v1  # 供标题使用
    if kind != "donut":
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color("#DDE5EE")
        ax.tick_params(colors="#475569")
        if kind not in ("groupbar",):
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, fontproperties=fp, fontsize=11)
        if kind == "hbar":
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, fontproperties=fp, fontsize=11)
    ax.set_title(title, fontproperties=fp, fontsize=15, color="#0B1D3A", fontweight="bold", pad=14)
    fig.tight_layout()
    out = out.with_suffix(".png")
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return str(out)


def chart_slide(prs, slide, title: str, png_path: str, tag: str = "", insight: str = ""):
    header(slide, title, tag)
    slide.shapes.add_picture(
        png_path, _px(150), _px(96), W - _px(300), int((H - _px(96) - _px(120)) * 0.92)
    )
    if insight:
        y = H - _px(104)
        box(slide, _px(150), y, W - _px(300), _px(64), fill=LIGHT)
        label(
            slide,
            _px(170),
            y,
            W - _px(340),
            _px(64),
            "💡 " + insight,
            12,
            BLUE,
            align=PP_ALIGN.LEFT,
        )


# ── 6) 指标看板 ------------------------------------------------------------


def metric_cards(slide, title: str, cards: list[tuple[str, str, str]], tag=""):
    """cards: (数值, 单位/后缀, 标签) 3~4 张大数字卡。"""
    header(slide, title, tag)
    n = len(cards)
    margin = _px(110)
    gap = _px(30)
    cw = (W - margin * 2 - gap * (n - 1)) // n
    ch = _px(300)
    y = H // 2 - ch // 2 - _px(10)
    for i, (value, suffix, lab) in enumerate(cards):
        x = margin + i * (cw + gap)
        color = ACCENTS[i % len(ACCENTS)]
        box(slide, x, y, cw, ch, fill=WHITE, line=BORDER)
        box(slide, x, y, cw, _px(8), fill=color, radius=False)
        label(slide, x, y + _px(40), cw, _px(110), value, 40, color, True)
        if suffix:
            label(slide, x, y + _px(150), cw, _px(34), suffix, 13, FAINT)
        label(slide, x + _px(16), y + ch - _px(74), cw - _px(32), _px(60), lab, 13, GREY, True)


# ── 7) 终端模拟 ------------------------------------------------------------


def terminal(slide, title: str, lines: list[str], tag: str = ""):
    header(slide, title, tag)
    x, y = _px(140), _px(100)
    w, h = W - _px(280), H - _px(190)
    box(slide, x, y, w, h, fill=RGBColor(0x0D, 0x11, 0x17), radius=True)
    box(slide, x, y, w, _px(40), fill=RGBColor(0x1F, 0x29, 0x37), radius=False)
    for i, c in enumerate((RED, AMBER, GREEN)):
        box(slide, x + _px(18) + i * _px(26), y + _px(14), _px(13), _px(13), fill=c)
    label(
        slide,
        x + _px(110),
        y,
        w - _px(130),
        _px(40),
        "terminal — 平台实测",
        11,
        FAINT,
        align=PP_ALIGN.LEFT,
    )
    tb = slide.shapes.add_textbox(x + _px(24), y + _px(56), w - _px(48), h - _px(70))
    tf = tb.text_frame
    tf.word_wrap = True
    mono = "Menlo"
    first = True
    for ln in lines[:18]:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.line_spacing = 1.15
        r = p.add_run()
        r.text = ln
        r.font.name = mono
        r.font.size = Pt(13)
        if ln.startswith("$"):
            r.font.color.rgb = GREEN
            r.font.bold = True
        elif "429" in ln or "400" in ln or "✗" in ln or "FAILED" in ln:
            r.font.color.rgb = RED
        elif "200" in ln or "✓" in ln or "PASSED" in ln:
            r.font.color.rgb = GREEN
        elif ln.startswith("#"):
            r.font.color.rgb = FAINT
        else:
            r.font.color.rgb = SILVER


# ── 8) 三层金字塔 ----------------------------------------------------------


def pyramid(slide, title: str, levels: list[tuple[str, str]], tag=""):
    """levels: [(名称, 说明)] 自顶向下。"""
    header(slide, title, tag)
    n = len(levels)
    top_y, layer_h, gap = _px(140), _px(112), _px(22)
    max_w = W - _px(700)
    for i, (name, desc) in enumerate(levels):
        w = max_w * (0.42 + 0.29 * i)
        x = (W - w) // 2
        y = top_y + i * (layer_h + gap)
        color = ACCENTS[(n - 1 - i) % len(ACCENTS)]
        box(slide, x, y, w, layer_h, fill=WHITE, line=color)
        box(slide, x, y, _px(6), layer_h, fill=color, radius=False)
        label(slide, x + _px(20), y, w * 0.38, layer_h, name, 16, color, True, align=PP_ALIGN.LEFT)
        label(slide, x + w * 0.40, y, w * 0.58, layer_h, desc, 12, GREY, align=PP_ALIGN.LEFT)
        if i < n - 1:
            arrow(
                slide, W // 2, y + layer_h + _px(2), W // 2, y + layer_h + gap - _px(2), FAINT, 1.2
            )


# ── 9) 时间线 --------------------------------------------------------------


def timeline(slide, title: str, items: list[tuple[str, str]], tag=""):
    header(slide, title, tag)
    n = len(items)
    y = H // 2 - _px(10)
    margin = _px(170)
    span = W - margin * 2
    box(slide, margin, y - _px(2), span, _px(4), fill=BORDER, radius=False)
    step = span // max(1, n - 1) if n > 1 else 0
    for i, (head, desc) in enumerate(items):
        cx = margin + i * step
        color = ACCENTS[i % len(ACCENTS)]
        box(slide, cx - _px(11), y - _px(11), _px(22), _px(22), fill=color)
        up = i % 2 == 0
        ty = y - _px(150) if up else y + _px(30)
        box(slide, cx - _px(150), ty, _px(300), _px(118), fill=LIGHT)
        box(slide, cx - _px(150), ty if up else ty, _px(300), _px(4), fill=color, radius=False)
        label(slide, cx - _px(140), ty + _px(10), _px(280), _px(30), head, 14, color, True)
        label(
            slide,
            cx - _px(140),
            ty + _px(42),
            _px(280),
            _px(70),
            desc,
            10.5,
            GREY,
            align=PP_ALIGN.LEFT,
            spacing=1.05,
        )


# ── 10) 对比表(美化) -----------------------------------------------------


def styled_table(slide, title: str, rows: list[list[str]], tag="", highlight_col: int = -1):
    header(slide, title, tag)
    n_cols = max(len(r) for r in rows)
    total_w = W - _px(240)
    x0 = _px(120)
    row_h = _px(min(64, 460 // len(rows)))
    y0 = _px(110)
    for ri, row in enumerate(rows):
        y = y0 + ri * row_h
        is_head = ri == 0
        box(
            slide,
            x0,
            y,
            total_w,
            row_h - _px(5),
            fill=INK if is_head else (LIGHT if ri % 2 else WHITE),
            line=None if is_head else BORDER,
        )
        cw = total_w // n_cols
        for ci, cell in enumerate(row):
            color = WHITE if is_head else (BLUE if ci == highlight_col else GREY)
            bold = is_head or ci == 0 or ci == highlight_col
            label(
                slide,
                x0 + ci * cw + _px(12),
                y,
                cw - _px(22),
                row_h - _px(5),
                cell,
                12.5 if not is_head else 13,
                color,
                bold,
                align=PP_ALIGN.LEFT,
            )


# ── 11) 卡片网格(概念/角色/清单) ------------------------------------------


def card_grid(slide, title: str, cards: list[tuple[str, str]], tag="", cols: int = 3):
    """cards: (标题, 描述)。"""
    header(slide, title, tag)
    n = len(cards)
    rows = math.ceil(n / cols)
    margin = _px(110)
    gap = _px(26)
    cw = (W - margin * 2 - gap * (cols - 1)) // cols
    ch = _px(min(160, (H - _px(240) - gap * (rows - 1)) // rows))
    y0 = H // 2 - (rows * ch + (rows - 1) * gap) // 2 - _px(6)
    for i, (head, desc) in enumerate(cards):
        r, c = divmod(i, cols)
        x = margin + c * (cw + gap)
        y = y0 + r * (ch + gap)
        color = ACCENTS[i % len(ACCENTS)]
        box(slide, x, y, cw, ch, fill=WHITE, line=BORDER)
        box(slide, x, y, cw, _px(6), fill=color, radius=False)
        box(slide, x + _px(16), y + _px(20), _px(34), _px(34), fill=color)
        label(slide, x + _px(16), y + _px(20), _px(34), _px(34), f"{i + 1:02d}", 12, WHITE, True)
        label(
            slide,
            x + _px(62),
            y + _px(22),
            cw - _px(78),
            _px(30),
            head,
            14,
            INK,
            True,
            align=PP_ALIGN.LEFT,
        )
        label(
            slide,
            x + _px(16),
            y + _px(64),
            cw - _px(32),
            ch - _px(78),
            desc,
            11.5,
            GREY,
            align=PP_ALIGN.LEFT,
            spacing=1.1,
        )
