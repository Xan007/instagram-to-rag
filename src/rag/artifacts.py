import datetime
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

WORKOUT_PLAN_SYSTEM = """Eres un coach de entrenamiento experto, claro y empático.
Tu tarea es armar un plan de entrenamiento estructurado y práctico basado EXCLUSIVAMENTE en el conocimiento de los posts citados.

Estructura requerida:
1. Objetivo y Nivel sugerido.
2. División Semanal / Días de entrenamiento.
3. Tabla o lista de ejercicios por día con series, repeticiones recomendadas y notas técnicas clave.
4. Cita a las fuentes originales usando [Source N] en cada ejercicio relevante.
"""

RECIPE_BOOK_SYSTEM = """Eres un chef y nutricionista experto y cercano.
Tu tarea es armar una receta o recetario paso a paso basado en el conocimiento de los posts citados.

Estructura requerida:
1. Nombre del plato y tiempo estimado.
2. Ingredientes con cantidades aproximadas.
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
    escaped = re.sub(r"`(.+?)`", r'<font face="Courier" color="#4A5568">\1</font>', escaped)
    escaped = re.sub(r"\[Source\s+(\d+)\]", r'<font color="#4C51BF"><b>[Source \1]</b></font>', escaped)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" color="#3182CE"><u>\1</u></a>', escaped)
    return escaped


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

        PRIMARY = colors.HexColor("#1E1E2F")
        ACCENT = colors.HexColor("#6366F1")
        TEXT_DARK = colors.HexColor("#2D3748")
        MUTED = colors.HexColor("#718096")
        BG_LIGHT = colors.HexColor("#F7FAFC")
        BORDER_LIGHT = colors.HexColor("#E2E8F0")

        doc = SimpleDocTemplate(
            str(out),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        h1_style = ParagraphStyle(
            "CustomH1",
            parent=styles["Heading1"],
            fontSize=15,
            leading=19,
            textColor=PRIMARY,
            spaceBefore=14,
            spaceAfter=6,
            keepWithNext=True,
        )
        h2_style = ParagraphStyle(
            "CustomH2",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            textColor=ACCENT,
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        )
        body_style = ParagraphStyle(
            "CustomBody",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=14,
            textColor=TEXT_DARK,
            spaceAfter=4,
        )
        bullet_style = ParagraphStyle(
            "CustomBullet",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=14,
            textColor=TEXT_DARK,
            leftIndent=14,
            spaceAfter=3,
        )
        callout_style = ParagraphStyle(
            "CalloutText",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#2C5282"),
        )

        elements = []

        now_str = datetime.datetime.now().strftime("%d/%m/%Y • %H:%M")
        badge_html = f'<font size="8" color="#6366F1"><b>INSTARAG INTELLIGENCE</b></font><br/><font size="16" color="#1E1E2F"><b>{title}</b></font>'
        meta_html = f'<font size="8" color="#718096">Generado el {now_str}<br/>Documento Oficial InstaRAG</font>'

        header_table = Table(
            [[Paragraph(badge_html, body_style), Paragraph(meta_html, ParagraphStyle("RightMeta", parent=body_style, alignment=2))]],
            colWidths=[360, 180],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(header_table)
        elements.append(HRFlowable(width="100%", thickness=2, color=ACCENT, spaceBefore=4, spaceAfter=14))

        for raw_line in content.split("\n"):
            line = raw_line.strip()
            if not line:
                elements.append(Spacer(1, 4))
                continue

            if line.startswith("### "):
                elements.append(Paragraph(_md_to_reportlab_html(line[4:]), h2_style))
            elif line.startswith("## "):
                elements.append(Paragraph(_md_to_reportlab_html(line[3:]), h1_style))
            elif line.startswith("# "):
                elements.append(Paragraph(_md_to_reportlab_html(line[2:]), h1_style))
            elif line.startswith("- [ ]") or line.startswith("- [x]") or line.startswith("- [X]"):
                is_checked = line.startswith("- [x]") or line.startswith("- [X]")
                icon = "[X]" if is_checked else "[  ]"
                item_text = line[5:].strip()
                elements.append(Paragraph(f'<font color="#6366F1"><b>{icon}</b></font> {_md_to_reportlab_html(item_text)}', bullet_style))
            elif line.startswith(("- ", "* ", "• ")):
                bullet_text = line[2:].strip()
                elements.append(Paragraph(f'<font color="#6366F1">•</font> {_md_to_reportlab_html(bullet_text)}', bullet_style))
            elif re.match(r"^\d+\.\s+", line):
                match = re.match(r"^(\d+)\.\s+(.*)", line)
                num, item_text = match.group(1), match.group(2)
                elements.append(Paragraph(f'<font color="#6366F1"><b>{num}.</b></font> {_md_to_reportlab_html(item_text)}', bullet_style))
            elif line.startswith(">"):
                quote_text = line.lstrip("> ").strip()
                callout_table = Table([[Paragraph(_md_to_reportlab_html(quote_text), callout_style)]], colWidths=[540])
                callout_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EBF8FF")),
                    ("LINELEFT", (0, 0), (0, 0), 3, ACCENT),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]))
                elements.append(callout_table)
                elements.append(Spacer(1, 4))
            elif line.startswith("---"):
                elements.append(Spacer(1, 4))
                elements.append(HRFlowable(width="100%", thickness=0.8, color=BORDER_LIGHT, spaceBefore=4, spaceAfter=8))
            else:
                elements.append(Paragraph(_md_to_reportlab_html(line), body_style))

        if sources:
            elements.append(Spacer(1, 12))
            elements.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceBefore=6, spaceAfter=8))
            elements.append(Paragraph("Fuentes Citadas (Reels / Posts de Creadores)", h2_style))

            source_rows = []
            for i, s in enumerate(sources, 1):
                if s.get("cited", True):
                    creator = s.get("creator", "creador")
                    url = s.get("url", "")
                    src_p = Paragraph(
                        f'<b>[Source {i}]</b> <font color="#4C51BF">@{creator}</font>: <a href="{url}" color="#3182CE"><u>{url}</u></a>',
                        body_style,
                    )
                    source_rows.append([src_p])

            if source_rows:
                sources_table = Table(source_rows, colWidths=[540])
                sources_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), BG_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]))
                elements.append(sources_table)

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
