"""Публикация поста в @video_transkrib."""

import os
import logging

from telegram import Bot

logger = logging.getLogger(__name__)

CHANNEL_ID = os.getenv("CHANNEL_ID")  # @video_transkrib или -100xxxxxxx


async def publish_to_channel(bot: Bot, title: str, body: str, image_url: str = None) -> int:
    """Публикует пост в канал. Возвращает message_id."""
    full_text = f"<b>{title}</b>\n\n{body}"    
    # Telegram limit для caption — 1024 chars, для message — 4096
    if image_url and len(full_text) <= 1024:
        msg = await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=full_text,
            parse_mode="HTML",
        )
    else:
        # Если caption слишком длинный — отправляем отдельно картинку и текст
        if image_url:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url)
        msg = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=full_text,
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
    
    logger.info(f"[PUB] Published to {CHANNEL_ID}, message_id={msg.message_id}")
    return msg.message_id
