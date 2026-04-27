"""Генерация текста поста через Claude Sonnet 4 с anti-repeat."""
import os
import json
import logging
from typing import Tuple
from anthropic import Anthropic
from topics import WEEKLY_TOPICS
from deduplication import get_recent_titles

logger = logging.getLogger(__name__)
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1500


def generate_post(day_of_week: int) -> Tuple[str, str, str, str]:
        """Генерирует пост; возвращает (title, body, image_prompt, topic_category)."""
        topic = WEEKLY_TOPICS[day_of_week]
        recent_titles = get_recent_titles(topic["category"], limit=10)
        avoid_block = ("\n\nИЗБЕГАЙ повторения этих недавних заголовков и тем:\n" + "\n".join(f"- {t}" for t in recent_titles)) if recent_titles else ""
        user_prompt = f'Сгенерируй пост для Telegram-канала @video_transkrib (Transkrib — AI для видео).\n\nФОРМАТ ОТВЕТА (строго JSON, без обрамляющих тегов):\n{{"title": "Заголовок (до 60 символов, можно с эмодзи)", "body": "Тело поста (200-350 слов, Telegram markdown allowed: *bold*, _italic_, `code`, [link](url))", "image_prompt": "EN-промт для генератора картинок, 1 предложение, abstract minimal style, no people, no logos, no text"}}\n\nТема дня: {topic["title_hint"]}{avoid_block}\n\nВ конце body всегда добавляй небольшой CTA-блок:\n"🤖 Попробовать: @transkrib_smartcut_bot"\n\nХэштеги в конце 3-5 штук, релевантные.'
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(model=CLAUDE_MODEL, max_tokens=MAX_TOKENS, system=topic["system_prompt"], messages=[{"role": "user", "content": user_prompt}])
        text = response.content[0].text
        cleaned = text.strip()
        cleaned = cleaned[cleaned.find("\n")+1:] if cleaned.startswith("```") and "\n" in cleaned else cleaned
        cleaned = cleaned.rstrip()[:-3].rstrip() if cleaned.rstrip().endswith("```") else cleaned
        data = json.loads(cleaned)
        return data["title"], data["body"], data["image_prompt"], topic["category"]
    
