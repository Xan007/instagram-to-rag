import os
from pathlib import Path
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
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
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

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1A365D"),
            spaceAfter=12,
        )
        heading_style = ParagraphStyle(
            "Heading2",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=10,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "DocBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#2D3748"),
            spaceAfter=6,
        )

        elements = []
        elements.append(Paragraph(title, title_style))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceAfter=14))

        for line in content.split("\n"):
            clean_line = line.strip()
            if not clean_line:
                elements.append(Spacer(1, 6))
                continue
            if clean_line.startswith("#"):
                header_text = clean_line.lstrip("#").strip()
                elements.append(Paragraph(header_text, heading_style))
            else:
                formatted_line = clean_line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                elements.append(Paragraph(formatted_line, body_style))

        if sources:
            elements.append(Spacer(1, 14))
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceAfter=10))
            elements.append(Paragraph("Fuentes Citadas (Reels / Posts)", heading_style))
            for i, s in enumerate(sources, 1):
                if s.get("cited", True):
                    src_line = f"• [Source {i}] @{s.get('creator', '')}: {s.get('url', '')}"
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

