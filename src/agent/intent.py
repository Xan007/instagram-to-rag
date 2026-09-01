from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class ArtifactIntent:
    should_generate: bool
    artifact_type: Optional[str] = None
    output_format: str = "pdf"
    suggested_filename: str = "documento.pdf"
    title: str = "InstaRAG Document"


class ArtifactIntentDetector:
    WORKOUT_KEYWORDS = ["rutina", "entrenamiento", "ejercicio", "workout", "hipertrofia", "fuerza", "torso", "pierna"]
    RECIPE_KEYWORDS = ["receta", "cocina", "plato", "comida", "postre", "ingredientes", "preparacion"]
    GROCERY_KEYWORDS = ["mercado", "supermercado", "compras", "lista de compra", "grocery", "ingredientes para comprar"]
    EXPORT_KEYWORDS = ["pdf", "descargar", "exportar", "documento", "archivo", "imprimir", "guarda", "mandamelo en"]

    @classmethod
    def detect(cls, query: str, explicit_artifact: Optional[str] = None, explicit_export: Optional[str] = None) -> ArtifactIntent:
        q_lower = query.lower().strip()

        # Check format
        is_md = bool(re.search(r"\b(markdown|\.md|notion|obsidian)\b", q_lower)) or (explicit_export and explicit_export.endswith(".md"))
        output_format = "md" if is_md else "pdf"

        # Explicit override
        if explicit_export or explicit_artifact:
            art_type = explicit_artifact or cls._classify_type(q_lower)
            ext = ".md" if output_format == "md" else ".pdf"
            filename = explicit_export or f"{art_type or 'document'}{ext}"
            title = (art_type or "InstaRAG Document").replace("_", " ").title()
            return ArtifactIntent(
                should_generate=True,
                artifact_type=art_type,
                output_format=output_format,
                suggested_filename=filename,
                title=title,
            )

        # Automatic detection from query text
        wants_export = any(k in q_lower for k in cls.EXPORT_KEYWORDS)
        classified_type = cls._classify_type(q_lower)

        if wants_export or (classified_type and any(k in q_lower for k in ["crea", "arma", "hazme", "dame", "genera", "plan"])):
            ext = ".md" if output_format == "md" else ".pdf"
            art_type = classified_type or "workout_plan"
            filename = f"{art_type}{ext}"
            title = art_type.replace("_", " ").title()
            return ArtifactIntent(
                should_generate=wants_export or bool(classified_type),
                artifact_type=art_type,
                output_format=output_format,
                suggested_filename=filename,
                title=title,
            )

        return ArtifactIntent(should_generate=False)

    @classmethod
    def _classify_type(cls, text: str) -> Optional[str]:
        if any(k in text for k in cls.GROCERY_KEYWORDS):
            return "grocery_list"
        if any(k in text for k in cls.RECIPE_KEYWORDS):
            return "recipe_book"
        if any(k in text for k in cls.WORKOUT_KEYWORDS):
            return "workout_plan"
        return None
