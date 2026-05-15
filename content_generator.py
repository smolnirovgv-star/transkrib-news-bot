"""Генерация текста поста через Claude Sonnet 4 с anti-repeat."""
import os
import json
import logging
from pathlib import Path
from typing import Tuple
from anthropic import Anthropic
from topics import WEEKLY_TOPICS
from deduplication import get_recent_titles

logger = logging.getLogger(__name__)
_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def _load_knowledge() -> str:
    """Читает все .md из knowledge/ один раз при импорте, сортирует по имени."""
    if not _KNOWLEDGE_DIR.exists():
        logger.warning(f"[KNOWLEDGE] Directory not found: {_KNOWLEDGE_DIR}")
        return ""
    parts = []
    for md_file in sorted(_KNOWLEDGE_DIR.glob("*.md")):
        parts.append(f"=== {md_file.name} ===\n{md_file.read_text(encoding='utf-8')}")
    result = "\n\n".join(parts)
    logger.info(f"[KNOWLEDGE] Loaded {len(parts)} files, {len(result)} chars")
    return result


KNOWLEDGE_CONTEXT = _load_knowledge()
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1500


def generate_post(day_of_week: int) -> Tuple[str, str, str, str]:
        """Генерирует пост; возвращает (title, body, image_prompt, topic_category)."""
        topic = WEEKLY_TOPICS[day_of_week]
        recent_titles = get_recent_titles(topic["category"], limit=10)
        avoid_block = ("\n\nИЗБЕГАЙ повторения этих недавних заголовков и тем:\n" + "\n".join(f"- {t}" for t in recent_titles)) if recent_titles else ""
        user_prompt = f'Сгенерируй пост для Telegram-канала @video_transkrib (Transkrib — AI для видео).\n\nФОРМАТ ОТВЕТА (строго JSON, без обрамляющих тегов):\n{{"title": "Заголовок (до 60 символов, можно с эмодзи)", "body": "Тело поста (длину и стиль смотри в инструкциях, plain text без HTML/markdown тегов)", "image_prompt": "EN-prompt for image generator, 1-2 sentences. Create a SPECIFIC visual scene directly related to the post topic. Examples: transcription topic → screen with subtitles/waveform; phone video → smartphone recording; video editing → timeline with clips; AI → neural network visualization with relevant context. Be concrete and thematic. No text overlays, no logos."}}\n\nТема дня: {topic["title_hint"]}{avoid_block}\n\nВ конце body всегда добавляй небольшой CTA-блок:\n"🤖 Попробовать: @transkrib_smartcut_bot"\n\nХэштеги в конце 3-5 штук, релевантные.\n\nВАЖНО: поле image_prompt — служебное, для генератора картинок. НЕ упоминай его в body, не пиши "Image prompt:" или похожее в тексте поста. Body — это только то, что увидит читатель в канале.\n\nФОРМАТИРОВАНИЕ: body пиши РОВНЫМ ТЕКСТОМ без markdown-разметки. НЕ используй звёздочки *, подчёркивания _ или backticks для выделения — они будут видны как литералы. Заголовки разделов оформляй как обычный текст с двоеточием и новой строкой, например: "Что фиксим:\\n...". Ссылки и юзернеймы пиши как есть, без обрамляющих символов.'
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        system = (
            f"{KNOWLEDGE_CONTEXT}\n\n---\n\n{topic['system_prompt']}"
            if KNOWLEDGE_CONTEXT
            else topic["system_prompt"]
        )
        response = client.messages.create(model=CLAUDE_MODEL, max_tokens=MAX_TOKENS, system=system, messages=[{"role": "user", "content": user_prompt}])
        text = response.content[0].text
        import re
        cleaned = text.strip()
        json_match = re.search(r'{.*}', cleaned, re.DOTALL)
        if not json_match:
            raise ValueError("Claude не вернул JSON. Ответ: " + cleaned[:200])
        cleaned = json_match.group(0)

        # Logging for future diagnostics
        logger.info(f"[CONTENT_GEN] Claude raw response length={len(cleaned)} preview={cleaned[:200]!r}")

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"[CONTENT_GEN] First JSON parse failed: {e}. Attempting newline normalization.")
            # Claude-sonnet-4-20250514 sometimes returns literal newlines inside JSON string values.
            # RFC 8259 forbids this -- normalize to escape sequences.
            cleaned_normalized = cleaned.replace('\r\n', '\n').replace('\n', '\\n')
            data = json.loads(cleaned_normalized)
            logger.info("[CONTENT_GEN] Newline normalization succeeded.")
        return data["title"], data["body"], data["image_prompt"], topic["category"]
    
