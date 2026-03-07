import logging
from typing import Optional

from openai import AsyncOpenAI
from openai import APIError, APIConnectionError, APITimeoutError, RateLimitError

from config.settings import settings

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, chat_model: Optional[AsyncOpenAI] = None):
        if not settings.OPENAI_API_KEY:
            raise ValueError("❌ OPENAI_API_KEY nincs beállítva (config / .env).")
        self.client = chat_model or AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def chat(self, question: str) -> str:
        """Chat üzenet küldése OpenAI API-nak."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Te egy segítőkész asszisztens vagy az AIPLAZA rendszerben."},
                    {"role": "user", "content": question},
                ],
            )
            if not response.choices or not response.choices[0].message.content:
                logger.warning("Üres válasz érkezett az OpenAI API-tól")
                return "⚠️ Nem sikerült választ kapni a modellből."
            return response.choices[0].message.content
        except RateLimitError as e:
            logger.error(f"OpenAI rate limit hiba: {e}", exc_info=True)
            return "⚠️ Túl sok kérés. Kérlek, próbáld újra később."
        except APITimeoutError as e:
            logger.error(f"OpenAI timeout hiba: {e}", exc_info=True)
            return "⚠️ A válasz túl sokáig tartott. Kérlek, próbáld újra."
        except APIConnectionError as e:
            logger.error(f"OpenAI kapcsolati hiba: {e}", exc_info=True)
            return "⚠️ Kapcsolati probléma történt. Kérlek, próbáld újra."
        except APIError as e:
            logger.error(f"OpenAI API hiba: {e}", exc_info=True)
            return "⚠️ Nem sikerült választ kapni a modellből."
        except Exception as e:
            logger.error(f"Váratlan hiba a chat szolgáltatásban: {e}", exc_info=True)
            return "⚠️ Nem sikerült választ kapni a modellből."
