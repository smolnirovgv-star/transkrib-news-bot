"""Генерация текста поста через Claude Sonnet 4 с anti-repeat."""

import os
import logging
from datetime import datetime
from typing import Optional, Tuple

from anthropic import Anthropic

from topics import WEEKLY_TOPICS
from deduplication import get_recent_titles

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1500


def generate_post(day_of_week: int) -> Tuple[str, str, str, str]:
    """
    Генерирует пост для указанного дня недели.
    
    Returns:
        (title, body, image_prompt, topic_category)
    """
    topic = WEEKLY_TOPICS[day_of_week]
    recent_titles = get_recent_titles(topic["category"], limit=10)
    
    # Anti-repeat блок в промте
    avoid_block = ""
    if recent_titles:
        avoid_block = f"\n\nИЗБЕГАЙ повторения этих недавних заголовков и тем:\n" + "\n".join(f"- {t}" for t in recent_titles)
    
    user_prompt = f"""Сгенерируй пост для Telegram-канала @video_transkrib (Transkrib — AI для видео).

ФОРМАТ ОТВЕТА (строго JSON, без обрамляющих тегов):
{{
  "title": "Заголовок (до 60 символов, можно с эмодзи)",
  "body": "Тело поста (200-350 слов, Telegram markdown allowed: *bold*, _italic_, `code`, [link](url))",
  "image_prompt": "EN-промт для генератора картинок, 1 предложение, abstract minimal style, no people, no logos, no text"
}}

Тема дня: {topic["title_hint"]}{avoid_block}

В конце body всегда добавляй небольшой CTA-блок:
"🤖 Попробовать: @transkrib_smartcut_bot"

Хэштеги в конце 3-5 штук, релевантные."""
    
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=topic["system_prompt"],
        messages=[{"role": "user", "content": user_prompt}]
    )
    
    text = response.content[0].text
    
    # Парсим JSON
    import json
    import re
    cleaned = text.strip()
    json_match = re.search(r"{.*}", cleaned, re.DOTALL)
    if not json_match:
        raise ValueError(f"Claude не вернул JSON. Ответ: {cleaned[:200]}")
    cleaned = json_match.group(0)
    data = json.loads(cleaned)

    topic_category = WEEKLY_TOPICS[day_of_week]["category"]
    return data["title"], data["body"], data["image_prompt"], topic_category
