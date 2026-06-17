#!/usr/bin/env python3
"""
GitHub Profile SVG Generator
Generates dark and light editorial SVGs for a GitHub profile README.
Architecture: research notebook × systems laboratory × technical journal.
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Colors:
    bg: str
    text: str
    secondary: str
    border: str
    accent: str
    grid: str
    tag_bg: str
    tag_text: str


DARK = Colors(
    bg="#0A0A0A",
    text="#E8E8E8",
    secondary="#7A7A7A",
    border="#1E1E1E",
    accent="#FFFFFF",
    grid="rgba(255,255,255,0.025)",
    tag_bg="#141414",
    tag_text="#7A7A7A",
)

LIGHT = Colors(
    bg="#FAFAFA",
    text="#111111",
    secondary="#6B6B6B",
    border="#E2E2E2",
    accent="#000000",
    grid="rgba(0,0,0,0.04)",
    tag_bg="#F2F2F2",
    tag_text="#6B6B6B",
)

# Spacing scale (px)
SP = {4: 4, 8: 8, 12: 12, 16: 16, 24: 24, 32: 32, 48: 48, 64: 64, 80: 80}

# Typography scale
TYPE = {
    "hero":    {"size": 28, "weight": 300, "tracking": "-0.5px", "line": 36},
    "section": {"size": 10, "weight": 500, "tracking": "0.12em",  "line": 14},
    "title":   {"size": 14, "weight": 500, "tracking": "0px",     "line": 20},
    "body":    {"size": 12, "weight": 400, "tracking": "0px",     "line": 19},
    "small":   {"size": 10, "weight": 400, "tracking": "0px",     "line": 15},
    "mono":    {"size": 10, "weight": 400, "tracking": "0.01em",  "line": 16},
    "tag":     {"size": 9,  "weight": 400, "tracking": "0.04em",  "line": 13},
}

MARGIN_X = 48   # left/right page margin
CONTENT_W = 764  # 860 - 48*2


# ──────────────────────────────────────────────────────────────────────────────
# SVG Primitives
# ──────────────────────────────────────────────────────────────────────────────

def esc(s: str) -> str:
    """Escape XML special characters."""
    return (s
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def px(n: int | float) -> str:
    return str(int(round(n)))


def wrap_text(text: str, chars_per_line: int) -> list[str]:
    """Wrap text to a given character width, preserving paragraph breaks."""
    lines = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
        else:
            wrapped = textwrap.wrap(para, chars_per_line)
            lines.extend(wrapped if wrapped else [""])
    return lines


def svg_text(
    x: int | float,
    y: int | float,
    content: str,
    color: str,
    size: int,
    weight: int,
    tracking: str,
    font_family: str,
    opacity: float = 1.0,
    anchor: str = "start",
    extra: str = "",
) -> str:
    return (
        f'<text x="{px(x)}" y="{px(y)}" '
        f'fill="{color}" '
        f'font-size="{size}" '
        f'font-weight="{weight}" '
        f'font-family="{font_family}" '
        f'letter-spacing="{tracking}" '
        f'text-anchor="{anchor}" '
        f'opacity="{opacity}" '
        f'{extra}>'
        f'{esc(content)}</text>'
    )


def svg_line(
    x1: int | float,
    y1: int | float,
    x2: int | float,
    y2: int | float,
    color: str,
    opacity: float = 1.0,
    width: float = 0.5,
) -> str:
    return (
        f'<line x1="{px(x1)}" y1="{px(y1)}" x2="{px(x2)}" y2="{px(y2)}" '
        f'stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>'
    )


def svg_rect(
    x: int | float,
    y: int | float,
    w: int | float,
    h: int | float,
    fill: str,
    rx: int = 0,
    opacity: float = 1.0,
    stroke: str = "none",
    stroke_width: float = 0.5,
) -> str:
    return (
        f'<rect x="{px(x)}" y="{px(y)}" width="{px(w)}" height="{px(h)}" '
        f'fill="{fill}" rx="{rx}" opacity="{opacity}" '
        f'stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# GitHub Data Fetching
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RepoInfo:
    name: str
    description: str
    stars: int
    language: str | None
    url: str


def fetch_github_data(username: str) -> dict[str, Any]:
    """Fetch public GitHub data. Returns empty dict on failure."""
    token = os.environ.get("GITHUB_TOKEN", "")
    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data: dict[str, Any] = {
        "repos": [],
        "user": {},
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    try:
        # User profile
        r = requests.get(
            f"https://api.github.com/users/{username}",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            u = r.json()
            data["user"] = {
                "followers": u.get("followers", 0),
                "public_repos": u.get("public_repos", 0),
                "created_at": u.get("created_at", "")[:4],
            }

        # Repos — sorted by stars
        r = requests.get(
            f"https://api.github.com/users/{username}/repos",
            headers=headers,
            params={"per_page": 100, "sort": "updated"},
            timeout=10,
        )
        if r.status_code == 200:
            repos = r.json()
            parsed: list[RepoInfo] = []
            for repo in repos:
                if repo.get("fork"):
                    continue
                parsed.append(
                    RepoInfo(
                        name=repo["name"],
                        description=repo.get("description") or "",
                        stars=repo.get("stargazers_count", 0),
                        language=repo.get("language"),
                        url=repo["html_url"],
                    )
                )
            parsed.sort(key=lambda r: r.stars, reverse=True)
            data["repos"] = [
                {
                    "name": r.name,
                    "description": r.description,
                    "stars": r.stars,
                    "language": r.language,
                    "url": r.url,
                }
                for r in parsed[:6]
            ]
    except Exception as e:
        print(f"[warn] GitHub fetch failed: {e}")

    return data


# ──────────────────────────────────────────────────────────────────────────────
# Rendering Components
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RenderContext:
    cfg: dict[str, Any]
    gh: dict[str, Any]
    colors: Colors
    width: int
    font_mono: str
    font_sans: str
    margin: int = MARGIN_X
    content_w: int = CONTENT_W

    # Running cursor — mutated as sections are appended
    y: float = 0.0
    elements: list[str] = field(default_factory=list)

    def add(self, el: str) -> None:
        self.elements.append(el)

    def advance(self, n: float) -> None:
        self.y += n

    def section_label(self, text: str) -> None:
        """Render an uppercase monospace section label with a leading tick mark."""
        t = TYPE["section"]
        self.add(svg_text(
            self.margin, self.y,
            text.upper(),
            self.colors.secondary,
            t["size"], t["weight"], t["tracking"],
            self.font_mono,
        ))
        self.advance(SP[16])

    def divider(self, gap_before: int = 40, gap_after: int = 40) -> None:
        """Full-width hairline rule."""
        self.advance(gap_before)
        self.add(svg_line(
            self.margin, self.y,
            self.margin + self.content_w, self.y,
            self.colors.border, opacity=1.0, width=0.5,
        ))
        self.advance(gap_after)

    def body_text(
        self,
        text: str,
        chars: int = 88,
        color: str | None = None,
        indent: int = 0,
        small: bool = False,
    ) -> None:
        """Render auto-wrapped body or small text."""
        key = "small" if small else "body"
        t = TYPE[key]
        col = color or self.colors.text
        lines = wrap_text(text, chars)
        for line in lines:
            self.add(svg_text(
                self.margin + indent, self.y,
                line, col,
                t["size"], t["weight"], t["tracking"],
                self.font_sans,
            ))
            self.advance(t["line"] + 2)

    def coord_mark(self, x: float, y: float) -> None:
        """Tiny crosshair blueprint mark."""
        c = self.colors.grid
        size = 4
        self.add(svg_line(x - size, y, x + size, y, c, opacity=1.0, width=0.5))
        self.add(svg_line(x, y - size, x, y + size, c, opacity=1.0, width=0.5))


# ──────────────────────────────────────────────────────────────────────────────
# Section Renderers
# ──────────────────────────────────────────────────────────────────────────────

def render_grid_background(ctx: RenderContext, height: int) -> None:
    """
    Faint coordinate grid — the signature element.
    Blueprint-style: horizontal bands + sparse vertical guides.
    """
    w = ctx.width
    # Sparse vertical guides
    col_positions = [ctx.margin, ctx.margin + ctx.content_w // 3,
                     ctx.margin + (ctx.content_w * 2) // 3,
                     ctx.margin + ctx.content_w]
    for xp in col_positions:
        ctx.add(svg_line(xp, 0, xp, height, ctx.colors.grid, opacity=1.0, width=0.5))

    # Horizontal rule every 80px
    y = 80
    while y < height:
        ctx.add(svg_line(0, y, w, y, ctx.colors.grid, opacity=1.0, width=0.5))
        y += 80

    # Coord marks at intersections of outer columns × grid rows
    y = 80
    while y < height:
        for xp in [ctx.margin, ctx.margin + ctx.content_w]:
            ctx.coord_mark(xp, y)
        y += 80


def render_header(ctx: RenderContext) -> None:
    cfg = ctx.cfg
    c = ctx.colors

    ctx.advance(SP[48])

    # Overline: github handle
    ctx.add(svg_text(
        ctx.margin, ctx.y,
        f"github.com/{cfg['github_username']}",
        c.secondary,
        TYPE["mono"]["size"], TYPE["mono"]["weight"], TYPE["mono"]["tracking"],
        ctx.font_mono,
    ))
    ctx.advance(SP[24])

    # Name — hero weight
    t = TYPE["hero"]
    ctx.add(svg_text(
        ctx.margin, ctx.y,
        cfg["name"],
        c.text,
        t["size"], t["weight"], t["tracking"],
        ctx.font_sans,
        extra='font-style="normal"',
    ))
    ctx.advance(t["line"] + SP[8])

    # Title + subtitle on one line, separated by a thin em-dash
    ctx.add(svg_text(
        ctx.margin, ctx.y,
        cfg["title"],
        c.text,
        TYPE["title"]["size"], TYPE["title"]["weight"],
        TYPE["title"]["tracking"],
        ctx.font_sans,
    ))
    ctx.add(svg_text(
        ctx.margin + 140, ctx.y,
        "·",
        c.secondary,
        TYPE["title"]["size"], 300, "0px",
        ctx.font_sans,
    ))
    ctx.add(svg_text(
        ctx.margin + 154, ctx.y,
        cfg["subtitle"],
        c.secondary,
        TYPE["small"]["size"], TYPE["small"]["weight"],
        TYPE["small"]["tracking"],
        ctx.font_sans,
    ))
    ctx.advance(TYPE["title"]["line"] + SP[16])

    # Tagline
    ctx.add(svg_text(
        ctx.margin, ctx.y,
        cfg["tagline"],
        c.secondary,
        TYPE["body"]["size"], 400, "0px",
        ctx.font_sans,
        opacity=0.8,
    ))
    ctx.advance(TYPE["body"]["line"])


def render_status_block(ctx: RenderContext) -> None:
    """
    Terminal-style status readout — monospace, left-aligned columns.
    Contains a blinking cursor animation.
    """
    cfg = ctx.cfg
    c = ctx.colors
    status = cfg.get("status", {})

    ctx.divider(gap_before=SP[32], gap_after=SP[32])

    # Define key-value rows
    rows: list[tuple[str, str]] = [
        ("LOCATION", cfg.get("location", "—")),
        ("FOCUS",    status.get("focus", "—")),
        ("BUILDING", status.get("building", "—")),
    ]
    for item in status.get("learning", []):
        rows.append(("LEARNING" if item == status["learning"][0] else "", item))
    for item in status.get("reading", []):
        rows.append(("READING" if item == status["reading"][0] else "", item))

    t = TYPE["mono"]
    key_w = 80
    line_h = t["line"] + 4
    block_h = len(rows) * line_h + SP[8]
    bx = ctx.margin
    by = ctx.y

    # Background rectangle
    ctx.add(svg_rect(bx, by - SP[8], ctx.content_w, block_h + SP[8],
                     c.tag_bg, rx=0, opacity=1.0,
                     stroke=c.border, stroke_width=0.5))

    ctx.advance(SP[4])

    for key, val in rows:
        # Key column
        if key:
            ctx.add(svg_text(
                bx + SP[16], ctx.y,
                key,
                c.secondary,
                t["size"], 500, t["tracking"],
                ctx.font_mono,
            ))
        # Value column
        ctx.add(svg_text(
            bx + SP[16] + key_w, ctx.y,
            val,
            c.text,
            t["size"], t["weight"], t["tracking"],
            ctx.font_mono,
        ))
        ctx.advance(line_h)

    # Blinking cursor after last row
    cursor_x = bx + SP[16] + key_w
    cursor_y = ctx.y - line_h + 2
    ctx.add(
        f'<rect x="{px(cursor_x)}" y="{px(cursor_y - 9)}" '
        f'width="5" height="10" '
        f'fill="{c.secondary}" opacity="0.7">'
        f'<animate attributeName="opacity" values="0.7;0;0.7" '
        f'dur="1.4s" repeatCount="indefinite"/>'
        f'</rect>'
    )

    ctx.advance(SP[16])


def render_current_direction(ctx: RenderContext) -> None:
    cfg = ctx.cfg
    c = ctx.colors
    cd = cfg.get("current_direction", {})

    ctx.divider(gap_before=SP[32], gap_after=SP[32])
    ctx.section_label("Current Direction")

    ctx.body_text(cd.get("body", ""), chars=80, color=c.text)
    ctx.advance(SP[24])

    # Two-column interest list
    interests = cd.get("interests", [])
    left = interests[:len(interests) // 2 + len(interests) % 2]
    right = interests[len(interests) // 2 + len(interests) % 2:]
    col2_x = ctx.margin + ctx.content_w // 2

    t = TYPE["small"]
    start_y = ctx.y
    max_y = ctx.y

    for i, item in enumerate(left):
        y = start_y + i * (t["line"] + 4)
        ctx.add(svg_text(
            ctx.margin + SP[12], y,
            item,
            c.text, t["size"], t["weight"], t["tracking"], ctx.font_sans,
        ))
        ctx.add(svg_text(
            ctx.margin, y, "—",
            c.secondary, t["size"], 300, "0px", ctx.font_sans,
        ))
        max_y = y + t["line"] + 4

    for i, item in enumerate(right):
        y = start_y + i * (t["line"] + 4)
        ctx.add(svg_text(
            col2_x + SP[12], y,
            item,
            c.text, t["size"], t["weight"], t["tracking"], ctx.font_sans,
        ))
        ctx.add(svg_text(
            col2_x, y, "—",
            c.secondary, t["size"], 300, "0px", ctx.font_sans,
        ))
        max_y = max(max_y, y + t["line"] + 4)

    ctx.y = max_y


def render_selected_work(ctx: RenderContext) -> None:
    cfg = ctx.cfg
    c = ctx.colors
    projects = cfg.get("projects", [])

    ctx.divider(gap_before=SP[32], gap_after=SP[32])
    ctx.section_label("Selected Work")

    for proj in projects:
        proj_x = ctx.margin
        name_t = TYPE["title"]
        body_t = TYPE["body"]
        tag_t  = TYPE["tag"]

        # Project name
        ctx.add(svg_text(
            proj_x, ctx.y,
            proj.get("name", ""),
            c.text,
            name_t["size"], name_t["weight"], name_t["tracking"],
            ctx.font_sans,
        ))
        # Language label — right-aligned
        lang = proj.get("lang", "")
        if lang:
            ctx.add(svg_text(
                proj_x + ctx.content_w, ctx.y,
                lang,
                c.secondary,
                TYPE["mono"]["size"], 400, TYPE["mono"]["tracking"],
                ctx.font_mono,
                anchor="end",
            ))
        ctx.advance(name_t["line"] + SP[8])

        # Description — wrapped
        desc_lines = wrap_text(proj.get("description", ""), 82)
        for line in desc_lines:
            ctx.add(svg_text(
                proj_x, ctx.y,
                line,
                c.secondary,
                body_t["size"], body_t["weight"], body_t["tracking"],
                ctx.font_sans,
            ))
            ctx.advance(body_t["line"] + 1)
        ctx.advance(SP[8])

        # Tags — inline chips
        tags = proj.get("tags", [])
        tag_x = proj_x
        for tag in tags:
            char_w = 6.2
            tag_pw = SP[8]
            tw = int(len(tag) * char_w) + tag_pw * 2
            th = tag_t["line"] + 6
            ctx.add(svg_rect(tag_x, ctx.y - tag_t["line"] + 1,
                             tw, th, c.tag_bg, rx=0,
                             opacity=1.0, stroke=c.border, stroke_width=0.5))
            ctx.add(svg_text(
                tag_x + tag_pw, ctx.y + 3,
                tag,
                c.tag_text,
                tag_t["size"], tag_t["weight"], tag_t["tracking"],
                ctx.font_mono,
            ))
            tag_x += tw + SP[4]

        ctx.advance(SP[24])

        # Thin separator between projects (not after last)
        if proj != projects[-1]:
            ctx.add(svg_line(
                ctx.margin, ctx.y,
                ctx.margin + ctx.content_w, ctx.y,
                c.border, opacity=0.5, width=0.5,
            ))
            ctx.advance(SP[24])


def render_research_log(ctx: RenderContext) -> None:
    cfg = ctx.cfg
    c = ctx.colors
    rl = cfg.get("research_log", {})

    ctx.divider(gap_before=SP[32], gap_after=SP[32])
    ctx.section_label("Research Log")

    t = TYPE["small"]
    current = rl.get("current", [])
    horizon = rl.get("horizon", [])

    # Two columns: Current / Horizon
    col1_x = ctx.margin
    col2_x = ctx.margin + ctx.content_w // 2
    start_y = ctx.y

    # Column labels
    ctx.add(svg_text(col1_x, ctx.y, "Active",
                     c.secondary, t["size"], 500, "0.06em", ctx.font_mono))
    ctx.add(svg_text(col2_x, ctx.y, "Horizon",
                     c.secondary, t["size"], 500, "0.06em", ctx.font_mono))
    ctx.advance(t["line"] + SP[8])

    max_rows = max(len(current), len(horizon))
    row_h = t["line"] + 5

    for i in range(max_rows):
        y = ctx.y + i * row_h
        if i < len(current):
            ctx.add(svg_text(col1_x + SP[12], y, current[i],
                             c.text, t["size"], t["weight"], t["tracking"],
                             ctx.font_sans))
            ctx.add(svg_text(col1_x, y, "→",
                             c.secondary, t["size"], 300, "0px", ctx.font_mono))
        if i < len(horizon):
            ctx.add(svg_text(col2_x + SP[12], y, horizon[i],
                             c.text, t["size"], t["weight"], t["tracking"],
                             ctx.font_sans))
            ctx.add(svg_text(col2_x, y, "→",
                             c.secondary, t["size"], 300, "0px", ctx.font_mono))

    ctx.y += max_rows * row_h


def render_notes(ctx: RenderContext) -> None:
    cfg = ctx.cfg
    c = ctx.colors
    notes = cfg.get("notes", [])

    ctx.divider(gap_before=SP[32], gap_after=SP[32])
    ctx.section_label("Notes")

    t = TYPE["body"]
    for i, note in enumerate(notes):
        # Opening quote mark
        ctx.add(svg_text(
            ctx.margin, ctx.y,
            "\u201C",  # "
            c.border,
            20, 300, "0px",
            ctx.font_sans,
        ))
        ctx.add(svg_text(
            ctx.margin + SP[16], ctx.y,
            note,
            c.text,
            t["size"], 300, "0.01em",
            ctx.font_sans,
            opacity=0.85,
        ))
        ctx.advance(t["line"] + SP[4])

        if i < len(notes) - 1:
            ctx.advance(SP[12])


def render_network(ctx: RenderContext) -> None:
    cfg = ctx.cfg
    c = ctx.colors
    socials = cfg.get("socials", {})
    portfolio = cfg.get("portfolio", {})

    ctx.divider(gap_before=SP[32], gap_after=SP[32])
    ctx.section_label("Network")

    t = TYPE["small"]
    label_w = 80
    row_h = t["line"] + 6

    all_links: list[tuple[str, str]] = []
    for k, v in socials.items():
        all_links.append((k.upper(), v))
    for k, v in portfolio.items():
        all_links.append((k.upper(), v))

    for key, url in all_links:
        ctx.add(svg_text(
            ctx.margin, ctx.y,
            key,
            c.secondary,
            t["size"], 500, "0.06em",
            ctx.font_mono,
        ))
        ctx.add(svg_text(
            ctx.margin + label_w, ctx.y,
            url,
            c.text,
            t["size"], t["weight"], "0px",
            ctx.font_mono,
            opacity=0.6,
        ))
        ctx.advance(row_h)


def render_footer(ctx: RenderContext, generated_at: str) -> None:
    cfg = ctx.cfg
    c = ctx.colors

    ctx.divider(gap_before=SP[32], gap_after=SP[24])

    # Philosophy — right-aligned
    ctx.add(svg_text(
        ctx.margin + ctx.content_w, ctx.y,
        cfg.get("philosophy", ""),
        c.secondary,
        TYPE["small"]["size"], 400, "0.02em",
        ctx.font_sans,
        anchor="end",
        opacity=0.6,
    ))
    ctx.advance(TYPE["small"]["line"] + SP[8])

    # Generated timestamp — right-aligned mono
    ctx.add(svg_text(
        ctx.margin + ctx.content_w, ctx.y,
        f"generated {generated_at}",
        c.secondary,
        TYPE["mono"]["size"], 400, TYPE["mono"]["tracking"],
        ctx.font_mono,
        anchor="end",
        opacity=0.3,
    ))
    ctx.advance(SP[48])


# ──────────────────────────────────────────────────────────────────────────────
# SVG Document Assembly
# ──────────────────────────────────────────────────────────────────────────────

CURSOR_BLINK_CSS = """
  @keyframes blink {
    0%, 100% { opacity: 0.7; }
    50%       { opacity: 0.0; }
  }
"""


def build_svg(
    cfg: dict[str, Any],
    gh: dict[str, Any],
    colors: Colors,
    generated_at: str,
) -> str:
    svg_cfg = cfg.get("svg", {})
    width: int = svg_cfg.get("width", 860)
    font_mono: str = svg_cfg.get("font_mono", "monospace")
    font_sans: str = svg_cfg.get("font_sans", "sans-serif")

    ctx = RenderContext(
        cfg=cfg,
        gh=gh,
        colors=colors,
        width=width,
        font_mono=font_mono,
        font_sans=font_sans,
    )

    # Accumulate all section renders — height is computed afterward
    render_header(ctx)
    render_status_block(ctx)
    render_current_direction(ctx)
    render_selected_work(ctx)
    render_research_log(ctx)
    render_notes(ctx)
    render_network(ctx)
    render_footer(ctx, generated_at)

    height = int(ctx.y) + SP[16]

    # Build final SVG string
    content_elements = "\n  ".join(ctx.elements)

    # Grid background — rendered first (below content)
    grid_ctx = RenderContext(
        cfg=cfg, gh=gh, colors=colors, width=width,
        font_mono=font_mono, font_sans=font_sans,
    )
    render_grid_background(grid_ctx, height)
    grid_elements = "\n  ".join(grid_ctx.elements)

    svg = f"""<svg
  xmlns="http://www.w3.org/2000/svg"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  width="{width}"
  height="{height}"
  viewBox="0 0 {width} {height}"
  role="img"
  aria-label="GitHub profile of {esc(cfg.get('name', ''))}"
>
  <title>{esc(cfg.get('name', ''))} — {esc(cfg.get('title', ''))}</title>
  <defs>
    <style>
{CURSOR_BLINK_CSS}
    </style>
  </defs>

  <!-- Background -->
  <rect width="{width}" height="{height}" fill="{colors.bg}"/>

  <!-- Blueprint grid -->
  {grid_elements}

  <!-- Content -->
  {content_elements}
</svg>"""

    return svg


# ──────────────────────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    root = Path(__file__).parent.parent
    config_path = root / "config" / "profile.json"
    assets_path = root / "assets"
    assets_path.mkdir(parents=True, exist_ok=True)

    print("[info] Loading configuration...")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg: dict[str, Any] = json.load(f)

    username: str = cfg.get("github_username", "")
    print(f"[info] Fetching GitHub data for @{username}...")
    gh = fetch_github_data(username)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"[info] Generating SVGs ({generated_at})...")

    dark_svg  = build_svg(cfg, gh, DARK,  generated_at)
    light_svg = build_svg(cfg, gh, LIGHT, generated_at)

    dark_path  = assets_path / "profile-dark.svg"
    light_path = assets_path / "profile-light.svg"

    dark_path.write_text(dark_svg, encoding="utf-8")
    light_path.write_text(light_svg, encoding="utf-8")

    print(f"[done] Written → {dark_path}")
    print(f"[done] Written → {light_path}")


if __name__ == "__main__":
    main()
