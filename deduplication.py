"""Anti-repeat: проверка что мы не повторяем недавние темы."""

import os
import logging
from typing import List

from supabase import create_client, Client

logger = logging.getLogger(__name__)

_client: Client = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    return _client


def get_recent_titles(category: str, limit: int = 10) -> List[str]:
    """Возвращает последние N заголовков из этой категории для anti-repeat."""
    try:
        client = _get_client()
        result = client.table("news_posts") \
            .select("title") \
            .eq("topic_category", category) \
            .eq("status", "published") \
            .order("published_at", desc=True) \
            .limit(limit) \
            .execute()
        return [r["title"] for r in (result.data or [])]
    except Exception as e:
        logger.warning(f"[DEDUP] Failed to fetch recent titles: {e}")
        return []


def save_draft(day_of_week: int, category: str, title: str, body: str, image_url: str, image_prompt: str) -> int:
    """Сохраняет draft, возвращает ID."""
    client = _get_client()
    result = client.table("news_posts").insert({
        "day_of_week": day_of_week,
        "topic_category": category,
        "title": title,
        "body": body,
        "image_url": image_url,
        "image_prompt": image_prompt,
        "status": "draft",
    }).execute()
    return result.data[0]["id"]


def update_status(post_id: int, status: str, telegram_message_id: int = None, rejection_reason: str = None) -> None:
    """Обновляет статус поста."""
    client = _get_client()
    update_data = {
        "status": status,
        "admin_decision_at": "now()",
    }
    if telegram_message_id:
        update_data["telegram_message_id"] = telegram_message_id
        update_data["published_at"] = "now()"
    if rejection_reason:
        update_data["rejection_reason"] = rejection_reason
    
    client.table("news_posts").update(update_data).eq("id", post_id).execute()
