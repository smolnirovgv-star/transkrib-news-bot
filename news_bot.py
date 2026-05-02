"""Главный модуль: scheduler + approval flow в @TranskribAdmin_Bot."""

import os
import logging
from datetime import datetime, time, timezone, timedelta

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from content_generator import generate_post
from image_generator import generate_image_url
from publisher import publish_to_channel
from deduplication import save_draft, update_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger(__name__)

ADMIN_ID = int(os.getenv("ADMIN_ID", "5052641158"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # отдельный bot token для news-бота

# Время постинга: 11:00 МСК = 08:00 UTC
POST_TIME_UTC = time(hour=8, minute=0)
# Время генерации draft: 10:30 МСК = 07:30 UTC (за 30 мин до постинга)
GENERATE_TIME_UTC = time(hour=7, minute=30)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "👋 News-bot запущен.\n\n"
        "Каждый день в 10:30 МСК буду генерить draft и присылать тебе на approval.\n"
        "В 11:00 МСК публикуется approved пост.\n\n"
        "/generate — сгенерить draft вручную сейчас\n"
        "/status — текущий статус"
    )


async def cmd_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ручная генерация draft."""
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("⏳ Генерирую...")
    await generate_and_send_draft(context)


async def generate_and_send_draft(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Генерирует draft и отправляет его ADMIN_ID на approval."""
    try:
        day_of_week = datetime.now(timezone.utc).weekday()
        title, body, image_prompt, category = generate_post(day_of_week)
        image_url = generate_image_url(image_prompt)
        post_id = save_draft(day_of_week, category, title, body, image_url, image_prompt)
        
        preview = f"*{title}*\n\n{body}\n\n_Image prompt: {image_prompt}_"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Publish", callback_data=f"approve:{post_id}"),
                InlineKeyboardButton("🔄 Regenerate", callback_data=f"regenerate:{post_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject:{post_id}"),
            ]
        ])
        
        # Отправляем картинку + caption
        if len(preview) <= 1024:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=image_url,
                caption=preview,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        else:
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=image_url)
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=preview,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        
        logger.info(f"[DRAFT] Sent draft {post_id} to admin")
    except Exception as e:
        logger.error(f"[DRAFT] Generation failed: {e}", exc_info=True)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ Ошибка генерации: {e}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка кнопок approve/reject/regenerate."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        return
    
    await query.answer()
    action, post_id_str = query.data.split(":")
    post_id = int(post_id_str)
    
    if action == "approve":
        # Публикуем
        from supabase import create_client
        client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        post = client.table("news_posts").select("*").eq("id", post_id).single().execute().data
        msg_id = await publish_to_channel(context.bot, post["title"], post["body"], post["image_url"])
        update_status(post_id, "published", telegram_message_id=msg_id)
        await query.edit_message_caption(caption=f"✅ Опубликовано (msg_id={msg_id})")
    
    elif action == "regenerate":
        update_status(post_id, "rejected", rejection_reason="regenerate_requested")
        try:
            await query.edit_message_caption(caption="🔄 Перегенерирую...")
        except Exception:
            await query.edit_message_text(text="🔄 Перегенерирую...")
        await generate_and_send_draft(context)
    
    elif action == "reject":
        update_status(post_id, "rejected", rejection_reason="admin_rejected")
        try:
            await query.edit_message_caption(caption="❌ Отклонено.")
        except Exception:
            await query.edit_message_text(text="❌ Отклонено.")


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("generate", cmd_generate))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # Daily generation 10:30 МСК (07:30 UTC)
    app.job_queue.run_daily(
        generate_and_send_draft,
        time=GENERATE_TIME_UTC,
        name="daily_draft_generation",
    )
    
    logger.info("[NEWS BOT] Started. Daily draft at 10:30 МСК.")
    app.run_polling()


if __name__ == "__main__":
    main()
