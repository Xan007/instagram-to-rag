import datetime
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

WORKOUT_PLAN_SYSTEM = """You are an expert fitness coach. Your output must be concise, clean, and direct without conversational filler.
Build a structured workout plan based EXCLUSIVELY on the knowledge from the cited posts. Respond in the same language as the user's query.

Required Structure:
1. Target Goal and Suggested Level (1-2 concise lines).
2. Weekly Split Overview (concise list of days and muscle groups).
3. Detailed Workout Schedule organized by Training Day:
   For EACH training day, create a clear subheader (e.g. `### Día 1: Torso (Fuerza / Hipertrofia)`) followed by its dedicated Markdown table:
   | Ejercicio | Series | Repeticiones | Notas Clave |
   Do NOT create a 'Day' column that repeats the day on every row. Group exercises cleanly under their corresponding day subheader.
4. Cite original sources using [Source N] sparingly and naturally only when directly relevant.

Rule: Go straight to the plan. Zero long introductions, preambles, or filler conclusions.
"""


RECIPE_BOOK_SYSTEM = """You are an expert chef and nutritionist. Your output must be direct, clear, and free of conversational fluff.
Build the recipe step-by-step based on the knowledge from the cited posts. Respond in the same language as the user's query.

Required Structure:
1. Dish Name and Estimated Prep Time.
2. Markdown table of ingredients with columns: | Ingredient | Quantity | Notes / Substitution |
3. Step-by-step preparation instructions clearly and directly.
4. Nutritional or storage tips (maximum 2 brief bullet points).
5. Cite original sources using [Source N] cleanly and sparingly.

Rule: Zero introductory pleasantries. Go straight to the recipe.
"""

GROCERY_LIST_SYSTEM = """You are a practical and organized shopping assistant. Your output must be direct, clean, and structured.
Consolidate the ingredients into a categorized grocery list based on the cited posts. Respond in the same language as the user's query.

Required Structure:
- [ ] Proteins
- [ ] Vegetables and Fruits
- [ ] Carbs and Grains
- [ ] Healthy Fats and Condiments
- [ ] Others / Supplements

Rule: No greetings or sign-offs, output only the clean Markdown checklist ready for shopping.
"""


ARTIFACT_PROMPTS = {
    "workout_plan": WORKOUT_PLAN_SYSTEM,
    "recipe_book": RECIPE_BOOK_SYSTEM,
    "grocery_list": GROCERY_LIST_SYSTEM,
}




def get_artifact_system_prompt(artifact_type: Optional[str]) -> Optional[str]:
    if not artifact_type:
        return None
    key = artifact_type.strip().lower().replace("-", "_").replace(" ", "_")
    return ARTIFACT_PROMPTS.get(key)


def _replace_sources_in_bracket(match: re.Match, sources_map: Optional[Dict[int, str]] = None) -> str:
    inner = match.group(1)
    numbers = re.findall(r"\d+", inner)
    if not numbers:
        return match.group(0)
    links = []
    for n_str in numbers:
        n = int(n_str)
        target_url = sources_map.get(n) if sources_map else None
        if target_url:
            links.append(f'<a href="{target_url}"><u><b>Source {n}</b></u></a>')
        else:
            links.append(f'<a href="#source_{n}"><u><b>Source {n}</b></u></a>')
    return f"[{', '.join(links)}]"


def _md_to_reportlab_html(text: str, sources_map: Optional[Dict[int, str]] = None) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', escaped)
    # Support both single [Source 1] and grouped [Source 1, Source 2, Source 5] linking directly to video URL
    escaped = re.sub(
        r"\[(Source\s*\d+[^\]]*)\]",
        lambda m: _replace_sources_in_bracket(m, sources_map=sources_map),
        escaped,
        flags=re.IGNORECASE,
    )
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2"><u>\1</u></a>', escaped)
    return escaped




def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 2


def _is_table_separator(line: str) -> bool:
    s = line.strip().replace(" ", "")
    return s.startswith("|") and re.match(r"^\|(\:?\-{2,}\:?\|)+$", s) is not None


def _parse_table_block(table_lines: List[str]) -> Optional[Tuple[List[str], List[List[str]]]]:
    clean_lines = [l.strip() for l in table_lines if l.strip()]
    if not clean_lines:
        return None

    header = []
    rows = []

    for i, line in enumerate(clean_lines):
        if _is_table_separator(line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not header:
            header = cells
        else:
            if len(cells) < len(header):
                cells += [""] * (len(header) - len(cells))
            elif len(cells) > len(header):
                cells = cells[:len(header)]
            rows.append(cells)

    if not header:
        return None
    return header, rows


def _render_reportlab_table(
    header: List[str],
    rows: List[List[str]],
    max_width: float = 540.0,
    sources_map: Optional[Dict[int, str]] = None,
) -> Any:
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    col_count = len(header)
    if col_count == 0:
        return None

    col_max_lengths = [len(h) for h in header]
    for r in rows:
        for c_idx, cell in enumerate(r):
            if c_idx < col_count:
                col_max_lengths[c_idx] = max(col_max_lengths[c_idx], len(cell))

    total_len = max(sum(col_max_lengths), 1)
    col_widths = []
    for l in col_max_lengths:
        fraction = max(l / total_len, 0.12)
        col_widths.append(fraction)

    norm_sum = sum(col_widths)
    actual_widths = [(w / norm_sum) * max_width for w in col_widths]

    th_style = ParagraphStyle(
        "THStyle",
        fontSize=9,
        leading=12,
        textColor=colors.black,
        fontName="Helvetica-Bold",
        alignment=0,
    )
    td_style = ParagraphStyle(
        "TDStyle",
        fontSize=9,
        leading=12,
        textColor=colors.black,
        fontName="Helvetica",
        alignment=0,
    )

    table_data = []
    th_row = [Paragraph(_md_to_reportlab_html(h, sources_map=sources_map), th_style) for h in header]
    table_data.append(th_row)

    for r in rows:
        td_row = [Paragraph(_md_to_reportlab_html(c, sources_map=sources_map), td_style) for c in r]
        table_data.append(td_row)

    t = Table(table_data, colWidths=actual_widths, repeatRows=1)

    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ]

    t.setStyle(TableStyle(t_style))
    return t


def export_artifact(
    content: str,
    output_path: str,
    title: str = "InstaRAG Export",
    sources: Optional[List[Dict[str, Any]]] = None,
) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    sources_map = {i: s.get("url", "") for i, s in enumerate(sources or [], start=1)}

    if out.suffix.lower() == ".pdf":
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            HRFlowable,
            Table,
            TableStyle,
        )
        from reportlab.lib import colors

        doc = SimpleDocTemplate(
            str(out),
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()

        doc_title_style = ParagraphStyle(
            "CleanDocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.black,
            fontName="Helvetica-Bold",
            spaceAfter=8,
        )
        h1_style = ParagraphStyle(
            "CleanH1",
            parent=styles["Heading1"],
            fontSize=14,
            leading=18,
            textColor=colors.black,
            fontName="Helvetica-Bold",
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True,
        )
        h2_style = ParagraphStyle(
            "CleanH2",
            parent=styles["Heading2"],
            fontSize=11.5,
            leading=15,
            textColor=colors.black,
            fontName="Helvetica-Bold",
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        )
        body_style = ParagraphStyle(
            "CleanBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.black,
            fontName="Helvetica",
            spaceAfter=4,
        )
        bullet_style = ParagraphStyle(
            "CleanBullet",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.black,
            fontName="Helvetica",
            leftIndent=14,
            spaceAfter=3,
        )
        quote_style = ParagraphStyle(
            "CleanQuote",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13.5,
            textColor=colors.black,
            fontName="Helvetica-Oblique",
            leftIndent=16,
            spaceBefore=4,
            spaceAfter=6,
        )

        elements = []

        elements.append(Paragraph(f"<b>{title}</b>", doc_title_style))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=2, spaceAfter=12))

        raw_lines = content.split("\n")
        idx = 0
        while idx < len(raw_lines):
            line = raw_lines[idx].strip()
            if not line:
                elements.append(Spacer(1, 4))
                idx += 1
                continue

            if _is_table_row(line):
                table_lines = []
                while idx < len(raw_lines) and _is_table_row(raw_lines[idx]):
                    table_lines.append(raw_lines[idx])
                    idx += 1
                
                parsed_table = _parse_table_block(table_lines)
                if parsed_table:
                    hdr, data_rows = parsed_table
                    rendered_tbl = _render_reportlab_table(hdr, data_rows, max_width=532.0, sources_map=sources_map)
                    if rendered_tbl:
                        elements.append(Spacer(1, 4))
                        elements.append(rendered_tbl)
                        elements.append(Spacer(1, 6))
                continue

            if line.startswith("### "):
                elements.append(Paragraph(_md_to_reportlab_html(line[4:], sources_map=sources_map), h2_style))
            elif line.startswith("## "):
                elements.append(Paragraph(_md_to_reportlab_html(line[3:], sources_map=sources_map), h1_style))
            elif line.startswith("# "):
                elements.append(Paragraph(_md_to_reportlab_html(line[2:], sources_map=sources_map), h1_style))
            elif line.startswith(("- [ ]", "- [x]", "- [X]")):
                is_checked = line.startswith(("- [x]", "- [X]"))
                icon = "[X]" if is_checked else "[  ]"
                item_text = line[5:].strip()
                elements.append(Paragraph(f"<b>{icon}</b> {_md_to_reportlab_html(item_text, sources_map=sources_map)}", bullet_style))
            elif line.startswith(("- ", "* ", "• ")):
                bullet_text = line[2:].strip()
                elements.append(Paragraph(f"• {_md_to_reportlab_html(bullet_text, sources_map=sources_map)}", bullet_style))
            elif re.match(r"^\d+\.\s+", line):
                match = re.match(r"^(\d+)\.\s+(.*)", line)
                num, item_text = match.group(1), match.group(2)
                elements.append(Paragraph(f"<b>{num}.</b> {_md_to_reportlab_html(item_text, sources_map=sources_map)}", bullet_style))
            elif line.startswith(">"):
                quote_text = line.lstrip("> ").strip()
                elements.append(Paragraph(_md_to_reportlab_html(quote_text, sources_map=sources_map), quote_style))
            elif line.startswith("---"):
                elements.append(Spacer(1, 4))
                elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.black, spaceBefore=4, spaceAfter=8))
            else:
                elements.append(Paragraph(_md_to_reportlab_html(line, sources_map=sources_map), body_style))

            idx += 1


        if sources:
            elements.append(Spacer(1, 14))
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=6, spaceAfter=8))
            elements.append(Paragraph("<b>Fuentes Citadas (Reels / Posts)</b>", h1_style))

            for i, s in enumerate(sources, 1):
                if s.get("cited", True):
                    creator = s.get("creator", "creador")
                    url = s.get("url", "")
                    summary = s.get("summary", "")
                    summary_html = f"<br/><font size=\"8.5\" color=\"#444444\"><i>- {summary}</i></font>" if summary else ""
                    src_line = f'<a name="source_{i}"/><b>[Source {i}]</b> @{creator}: <a href="{url}"><u>{url}</u></a>{summary_html}'
                    elements.append(Paragraph(src_line, body_style))

                    elements.append(Spacer(1, 3))

        doc.build(elements)
    else:
        full_text = f"# {title}\n\n{content}"
        if sources:
            full_text += "\n\n---\n### Fuentes Citadas\n"
            for i, s in enumerate(sources, 1):
                if s.get("cited", True):
                    summary_str = f" — *{s.get('summary')}*" if s.get("summary") else ""
                    full_text += f"- **[Source {i}]** @{s.get('creator', '')}: {s.get('url', '')}{summary_str}\n"
        out.write_text(full_text, encoding="utf-8")

    return out.resolve()

