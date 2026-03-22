"""
config.py — токены и настройки
Локально: читает из .env файла
Railway: читает из Variables (переменные окружения)
"""

import os
import sys

# Пробуем загрузить .env если он есть (локально)
# На Railway .env нет — берётся из Variables автоматически
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    print("❌ Ошибка: переменная TELEGRAM_TOKEN не задана")
    sys.exit(1)

if not OPENAI_API_KEY:
    print("❌ Ошибка: переменная OPENAI_API_KEY не задана")
    sys.exit(1)
