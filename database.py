"""
database.py — работа с SQLite базой данных
Три таблицы: users, raw_messages, symptoms
"""

import sqlite3
import json
from datetime import datetime


class Database:
    def __init__(self, db_path: str = "health.db"):
        self.db_path = db_path

    def _connect(self):
        """Открываем соединение с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # чтобы результаты были как dict
        return conn

    def create_tables(self):
        """Создаём все таблицы при первом запуске"""
        conn = self._connect()
        cursor = conn.cursor()

        # Пользователи
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        # Сырые сообщения — сохраняем всегда, ничего не теряем
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                raw_text    TEXT NOT NULL,
                timestamp   TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Структурированные симптомы, извлечённые AI
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS symptoms (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id  INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                name        TEXT NOT NULL,
                onset       TEXT,
                timing      TEXT,
                severity    TEXT,
                triggers    TEXT,
                notes       TEXT,
                timestamp   TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (message_id) REFERENCES raw_messages(id),
                FOREIGN KEY (user_id)    REFERENCES users(user_id)
            )
        """)

        conn.commit()
        conn.close()
        print("✅ Таблицы созданы (или уже существуют)")

    def ensure_user_exists(self, user_id: int):
        """Создаём пользователя если его нет"""
        conn = self._connect()
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,)
        )
        conn.commit()
        conn.close()

    def save_raw_message(self, user_id: int, raw_text: str) -> int:
        """
        Сохраняем сырое сообщение пользователя.
        Возвращаем ID записи (нужен чтобы потом привязать симптомы).
        """
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO raw_messages (user_id, raw_text) VALUES (?, ?)",
            (user_id, raw_text)
        )
        conn.commit()
        message_id = cursor.lastrowid
        conn.close()
        return message_id

    def save_symptoms(self, message_id: int, user_id: int, symptoms: list):
        """
        Сохраняем список симптомов из AI-ответа.
        symptoms — это список dict из JSON ответа Claude.
        """
        conn = self._connect()
        for symptom in symptoms:
            conn.execute("""
                INSERT INTO symptoms
                    (message_id, user_id, name, onset, timing, severity, triggers, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message_id,
                user_id,
                symptom.get("name", "unknown"),
                symptom.get("onset"),
                symptom.get("timing"),
                symptom.get("severity"),
                symptom.get("triggers"),
                symptom.get("notes"),
            ))
        conn.commit()
        conn.close()

    def get_symptoms_for_report(self, user_id: int, days: int = 7) -> list:
        """
        Достаём симптомы за последние N дней для отчёта.
        Возвращаем список dict.
        """
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM symptoms
            WHERE user_id = ?
              AND timestamp >= datetime('now', ? )
            ORDER BY timestamp ASC
        """, (user_id, f"-{days} days"))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_all_messages(self, user_id: int) -> list:
        """Достаём все сырые сообщения пользователя"""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM raw_messages
            WHERE user_id = ?
            ORDER BY timestamp ASC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_raw_messages_for_period(self, user_id: int, days: int = 7) -> list:
        """Достаём сырые сообщения за период"""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM raw_messages
            WHERE user_id = ?
              AND timestamp >= datetime('now', ?)
            ORDER BY timestamp ASC
        """, (user_id, f"-{days} days"))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def clear_user_data(self, user_id: int):
        """Удаляем все данные пользователя"""
        conn = self._connect()
        conn.execute("DELETE FROM symptoms WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM raw_messages WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
