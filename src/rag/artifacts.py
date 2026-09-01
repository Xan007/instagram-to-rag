import datetime
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

WORKOUT_PLAN_SYSTEM = """Eres un coach de entrenamiento experto, claro y empático.
Tu tarea es armar un plan de entrenamiento estructurado y práctico basado EXCLUSIVAMENTE en el conocimiento de los posts citados.

Estructura requerida:
1. Objetivo y Nivel sugerido.
2. División Semanal / Días de entrenamiento.
3. Tabla Markdown completa de ejercicios por día con columnas: | Día | Ejercicio | Series | Repeticiones | Notas Clave & Cita |
4. Cita a las fuentes originales usando [Source N] en cada ejercicio relevante.
"""

RECIPE_BOOK_SYSTEM = """Eres un chef y nutricionista experto y cercano.
Tu tarea es armar una receta o recetario paso a paso basado en el conocimiento de los posts citados.

Estructura requerida:
1. Nombre del plato y tiempo estimado.
2. Tabla Markdown de ingredientes con columnas: | Ingrediente | Cantidad | Notas / Sustituto |
3. Preparación paso a paso de forma clara y amena.
4. Tips nutricionales o de conservación.
5. Cita a las fuentes originales usando [Source N].
"""

GROCERY_LIST_SYSTEM = """Eres un asistente de compras de supermercado práctico y organizado.
Tu tarea es consolidar todos los ingredientes o alimentos mencionados en los posts citados en una lista de compras categorizada.

Estructura requerida:
- [ ] 🥩 Proteínas
- [ ] 🥦 Verduras y Frutas
- [ ] 🍚 Carbohidratos y Granos
- [ ] 🫒 Grasas saludables y Condimentos
- [ ] 📦 Otros / Suplementos

Usa casillas de verificación Markdown (- [ ]) para que sea fácil marcar al hacer la compra.
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


def _md_to_reportlab_html(text: str) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', escaped)
    # Convert [Source N] to clickable internal anchor jump to the bottom
    escaped = re.sub(r"\[Source\s+(\d+)\]", r'<a href="#source_\1"><u><b>[Source \1]</b></u></a>', escaped)
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


def _render_reportlab_table(header: List[str], rows: List[List[str]], max_width: float = 540.0) -> Any:
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
    th_row = [Paragraph(_md_to_reportlab_html(h), th_style) for h in header]
    table_data.append(th_row)

    for r in rows:
        td_row = [Paragraph(_md_to_reportlab_html(c), td_style) for c in r]
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
                    rendered_tbl = _render_reportlab_table(hdr, data_rows, max_width=532.0)
                    if rendered_tbl:
                        elements.append(Spacer(1, 4))
                        elements.append(rendered_tbl)
                        elements.append(Spacer(1, 6))
                continue

            if line.startswith("### "):
                elements.append(Paragraph(_md_to_reportlab_html(line[4:]), h2_style))
            elif line.startswith("## "):
                elements.append(Paragraph(_md_to_reportlab_html(line[3:]), h1_style))
            elif line.startswith("# "):
                elements.append(Paragraph(_md_to_reportlab_html(line[2:]), h1_style))
            elif line.startswith(("- [ ]", "- [x]", "- [X]")):
                is_checked = line.startswith(("- [x]", "- [X]"))
                icon = "[X]" if is_checked else "[  ]"
                item_text = line[5:].strip()
                elements.append(Paragraph(f"<b>{icon}</b> {_md_to_reportlab_html(item_text)}", bullet_style))
            elif line.startswith(("- ", "* ", "• ")):
                bullet_text = line[2:].strip()
                elements.append(Paragraph(f"• {_md_to_reportlab_html(bullet_text)}", bullet_style))
            elif re.match(r"^\d+\.\s+", line):
                match = re.match(r"^(\d+)\.\s+(.*)", line)
                num, item_text = match.group(1), match.group(2)
                elements.append(Paragraph(f"<b>{num}.</b> {_md_to_reportlab_html(item_text)}", bullet_style))
            elif line.startswith(">"):
                quote_text = line.lstrip("> ").strip()
                elements.append(Paragraph(_md_to_reportlab_html(quote_text), quote_style))
            elif line.startswith("---"):
                elements.append(Spacer(1, 4))
                elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.black, spaceBefore=4, spaceAfter=8))
            else:
                elements.append(Paragraph(_md_to_reportlab_html(line), body_style))

            idx += 1

        if sources:
            elements.append(Spacer(1, 14))
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=6, spaceAfter=8))
            elements.append(Paragraph("<b>Fuentes Citadas (Reels / Posts)</b>", h1_style))

            for i, s in enumerate(sources, 1):
                if s.get("cited", True):
                    creator = s.get("creator", "creador")
                    url = s.get("url", "")
                    src_line = f'<a name="source_{i}"/><b>[Source {i}]</b> @{creator}: <a href="{url}"><u>{url}</u></a>'
                    elements.append(Paragraph(src_line, body_style))


        doc.build(elements)
    else:
        full_text = f"# {title}\n\n{content}"
        if sources:
            full_text += "\n\n---\n### Fuentes Citadas\n"
            for i, s in enumerate(sources, 1):
                if s.get("cited", True):
                    full_text += f"- **[Source {i}]** @{s.get('creator', '')}: {s.get('url', '')}\n"
        out.write_text(full_text, encoding="utf-8")

    return out.resolve()
