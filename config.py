"""
config.py — токены и настройки
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    print("❌ Ошибка: переменная TELEGRAM_TOKEN не задана")
    sys.exit(1)

if not OPENAI_API_KEY:
    print("❌ Ошибка: переменная OPENAI_API_KEY не задана")
    sys.exit(1)
