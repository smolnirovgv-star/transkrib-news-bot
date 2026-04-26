"""Бесплатный генератор картинок через Pollinations.ai (no auth required)."""

import logging
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


def generate_image_url(prompt: str, width: int = 1024, height: int = 768, seed: int = None) -> str:
    """
    Генерирует URL картинки через Pollinations.
    
    Args:
        prompt: EN-промт от Claude (уже adapted для image generation)
        width, height: размеры
        seed: для воспроизводимости (если None — random каждый раз)
    
    Returns:
        Прямой URL картинки. Telegram примет его как photo.
    """
    # Добавляем стилевую обёртку чтобы убрать AI-ширпотреб
    enhanced = f"{prompt}, minimalist abstract style, soft gradients, professional, high quality, 4k"
    
    encoded = quote_plus(enhanced)
    url = f"{POLLINATIONS_BASE}/{encoded}?width={width}&height={height}&nologo=true&enhance=true"
    
    if seed:
        url += f"&seed={seed}"
    
    logger.info(f"[IMG] Generated image URL: {url[:100]}...")
    return url
