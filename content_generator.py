"""Генерация текста поста через Claude Sonnet 4 с anti-repeat."""
import os
import json
import logging
import time
from pathlib import Path
from typing import Tuple
import anthropic
import httpx
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
        user_prompt = f'Сгенерируй пост для Telegram-канала @video_transkrib (Transkrib — AI для видео).\n\nФОРМАТ ОТВЕТА (строго JSON, без обрамляющих тегов):\n{{"title": "Заголовок (до 60 символов, можно с эмодзи)", "body": "Тело поста (длину и стиль смотри в инструкциях, plain text без HTML/markdown тегов)", "image_prompt": "EN-prompt for image generator, 1-2 sentences. Create a SPECIFIC visual scene directly related to the post topic. Examples: transcription topic → screen with subtitles/waveform; phone video → smartphone recording; video editing → timeline with clips; AI → neural network visualization with relevant context. Be concrete and thematic. No text overlays, no logos."}}\n\nТема дня: {topic["title_hint"]}{avoid_block}\n\nВ конце body всегда добавляй небольшой CTA-блок:\n"🤖 Попробовать: @transkrib_plus_bot"\n\nХэштеги в конце 3-5 штук, релевантные.\n\nВАЖНО: поле image_prompt — служебное, для генератора картинок. НЕ упоминай его в body, не пиши "Image prompt:" или похожее в тексте поста. Body — это только то, что увидит читатель в канале.\n\nФОРМАТИРОВАНИЕ: body пиши РОВНЫМ ТЕКСТОМ без markdown-разметки. НЕ используй звёздочки *, подчёркивания _ или backticks для выделения — они будут видны как литералы. Заголовки разделов оформляй как обычный текст с двоеточием и новой строкой, например: "Что фиксим:\\n...". Ссылки и юзернеймы пиши как есть, без обрамляющих символов.\n\nВАЖНО: верни строго JSON с тремя полями — title, body, image_prompt. Все три поля ОБЯЗАТЕЛЬНЫЕ, не пропускай ни одно. Не оборачивай в markdown ```json — только чистый JSON-объект.'
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        system = (
            f"{KNOWLEDGE_CONTEXT}\n\n---\n\n{topic['system_prompt']}"
            if KNOWLEDGE_CONTEXT
            else topic["system_prompt"]
        )
        REQUIRED_FIELDS = ['title', 'body', 'image_prompt']
        last_error: Exception = ValueError("No attempts made")
        for attempt in range(3):
            try:
                response = client.messages.create(model=CLAUDE_MODEL, max_tokens=MAX_TOKENS, system=system, messages=[{"role": "user", "content": user_prompt}])
                text = response.content[0].text
                raw = text.strip()
                decoder = json.JSONDecoder()
                data = None
                search_from = 0

                logger.info(f"[CONTENT_GEN] Claude raw response length={len(raw)} preview={raw[:200]!r}")

                for scan in range(3):
                    start = raw.find('{', search_from)
                    if start == -1:
                        break
                    end_pos = start + 1  # fallback if raw_decode raises
                    try:
                        candidate, end_pos = decoder.raw_decode(raw, start)
                    except json.JSONDecodeError as e:
                        if scan == 0:
                            # Claude sometimes returns literal newlines in JSON strings (RFC 8259 violation)
                            normalized_tail = raw[start:].replace('\r\n', '\n').replace('\n', '\\n')
                            try:
                                candidate, _ = decoder.raw_decode(normalized_tail)
                                logger.info("[CONTENT_GEN] Newline normalization succeeded.")
                            except json.JSONDecodeError as e2:
                                logger.warning(f"[CONTENT_GEN] Scan {scan+1} failed after normalization: {e2}")
                                search_from = start + 1
                                continue
                        else:
                            logger.warning(f"[CONTENT_GEN] Scan {scan+1} raw_decode failed: {e}")
                            search_from = start + 1
                            continue

                    if isinstance(candidate, dict) and all(f in candidate for f in REQUIRED_FIELDS):
                        data = candidate
                        logger.info(f"[CONTENT_GEN] Valid JSON found on scan {scan+1}")
                        break
                    else:
                        logger.warning(
                            f"[CONTENT_GEN] Scan {scan+1} missing required fields. "
                            f"Got: {list(candidate.keys()) if isinstance(candidate, dict) else type(candidate)}"
                        )
                        search_from = end_pos

                if data is None:
                    raise ValueError(f"Could not find valid post JSON with fields {REQUIRED_FIELDS}. Raw: " + raw[:200])

                if attempt > 0:
                    logger.info(f"[CONTENT_GEN] Succeeded on attempt {attempt+1}/3. Sonnet skipped field on earlier tries.")
                return data["title"], data["body"], data["image_prompt"], topic["category"]

            except (ValueError, json.JSONDecodeError, anthropic.APIError, httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(f"[CONTENT_GEN] Attempt {attempt+1}/3 failed: {e}. Retrying...")
                if attempt < 2:
                    time.sleep(2)

        logger.error(f"[CONTENT_GEN] All 3 attempts failed for day {day_of_week}. Last error: {last_error}")
        raise last_error
    
