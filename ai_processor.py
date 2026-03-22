"""
ai_processor.py — отправляем текст в OpenAI API и получаем структурированные данные
"""

import json
from openai import OpenAI
from config import OPENAI_API_KEY

SYSTEM_PROMPT = """
Ты медицинский ассистент. Извлекай симптомы из сообщения пациента.

Верни ТОЛЬКО валидный JSON — без пояснений, без markdown, без лишнего текста.

Формат:
{
  "symptoms": [
    {
      "name": "название симптома на русском (например: головная боль, головокружение, тошнота)",
      "onset": "когда началось на русском (например: 'сегодня', '3 дня назад', 'утром')",
      "timing": "когда происходит на русском (например: 'по утрам', 'после еды', 'постоянно')",
      "severity": "mild | moderate | severe",
      "triggers": "что вызывает или усиливает — строка на русском или null",
      "notes": "другие важные детали на русском — строка или null"
    }
  ]
}

Правила:
- Если в сообщении нет симптомов — верни {"symptoms": []}
- Лекарства и измерения (давление, температура) добавляй в notes
- Один симптом = один объект в массиве
- Всегда возвращай валидный JSON
- Все текстовые поля ТОЛЬКО на русском языке
"""


class AIProcessor:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def process_message(self, raw_text: str) -> dict | None:
        """
        Отправляем сообщение пациента в OpenAI.
        Возвращаем dict с ключом "symptoms" или None если что-то пошло не так.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # дешевле чем gpt-4o, но достаточно мощный
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Patient message:\n{raw_text}"}
                ],
                response_format={"type": "json_object"},  # гарантирует JSON-ответ
                max_tokens=1024,
                temperature=0,  # стабильность важнее креативности
            )

            response_text = response.choices[0].message.content.strip()
            result = json.loads(response_text)
            return result

        except json.JSONDecodeError as e:
            print(f"❌ JSON parse error: {e}")
            print(f"   OpenAI responded: {response_text[:200]}")
            return None

        except Exception as e:
            print(f"❌ OpenAI API error: {e}")
            return None
