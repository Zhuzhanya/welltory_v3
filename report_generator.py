"""
report_generator.py — PDF-отчёт на русском языке через reportlab
"""

import os
import urllib.request
from datetime import datetime
from database import Database

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ── Шрифт с кириллицей ────────────────────────────────────────────────────
# ReportLab встроенные шрифты не поддерживают кириллицу.
# Используем DejaVuSans — скачивается автоматически при первом запуске.

FONT_PATH      = "DejaVuSans.ttf"
FONT_BOLD_PATH = "DejaVuSans-Bold.ttf"
FONT_URL       = "https://github.com/dejavu-fonts/dejavu-fonts/raw/main/ttf/DejaVuSans.ttf"
FONT_BOLD_URL  = "https://github.com/dejavu-fonts/dejavu-fonts/raw/main/ttf/DejaVuSans-Bold.ttf"


def _download_font(url, path):
    """Скачиваем файл с обходом SSL-проверки (нужно на macOS)."""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(url, context=ctx) as response:
        with open(path, 'wb') as f:
            f.write(response.read())


def ensure_fonts():
    """Скачиваем шрифты если их ещё нет, регистрируем в ReportLab."""
    if not os.path.exists(FONT_PATH):
        print("⏳ Скачиваю шрифт DejaVuSans.ttf (один раз)...")
        _download_font(FONT_URL, FONT_PATH)
        print("✅ Шрифт скачан")

    if not os.path.exists(FONT_BOLD_PATH):
        print("⏳ Скачиваю DejaVuSans-Bold.ttf (один раз)...")
        _download_font(FONT_BOLD_URL, FONT_BOLD_PATH)
        print("✅ Жирный шрифт скачан")

    pdfmetrics.registerFont(TTFont("DejaVu",     FONT_PATH))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_BOLD_PATH))


# ── Цвета ─────────────────────────────────────────────────────────────────
COLOR_PRIMARY  = colors.HexColor("#1a73e8")
COLOR_LIGHT_BG = colors.HexColor("#f0f4ff")
COLOR_BORDER   = colors.HexColor("#d0d9f0")
COLOR_MILD     = colors.HexColor("#f9a825")
COLOR_MODERATE = colors.HexColor("#ef6c00")
COLOR_SEVERE   = colors.HexColor("#c62828")
COLOR_TEXT     = colors.HexColor("#212121")
COLOR_SUBTLE   = colors.HexColor("#757575")


def build_styles():
    base = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=base["Normal"],
        fontName="DejaVu-Bold",
        fontSize=22,
        textColor=COLOR_PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=base["Normal"],
        fontName="DejaVu",
        fontSize=10,
        textColor=COLOR_SUBTLE,
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=base["Normal"],
        fontName="DejaVu-Bold",
        fontSize=13,
        textColor=COLOR_PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=base["Normal"],
        fontName="DejaVu",
        fontSize=10,
        textColor=COLOR_TEXT,
        leading=15,
    )
    body_bold_style = ParagraphStyle(
        "BodyBold",
        parent=base["Normal"],
        fontName="DejaVu-Bold",
        fontSize=10,
        textColor=COLOR_TEXT,
        leading=15,
    )
    quote_style = ParagraphStyle(
        "Quote",
        parent=base["Normal"],
        fontName="DejaVu",
        fontSize=9,
        textColor=COLOR_TEXT,
        leftIndent=10,
        leading=14,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=base["Normal"],
        fontName="DejaVu",
        fontSize=9,
        textColor=COLOR_SUBTLE,
    )

    return {
        "title":     title_style,
        "subtitle":  subtitle_style,
        "section":   section_style,
        "body":      body_style,
        "body_bold": body_bold_style,
        "quote":     quote_style,
        "label":     label_style,
    }


class ReportGenerator:
    def __init__(self, db: Database):
        self.db = db

    def generate_pdf_report(self, user_id: int, days: int = 7) -> str | None:
        symptoms     = self.db.get_symptoms_for_report(user_id, days)
        raw_messages = self.db.get_raw_messages_for_period(user_id, days)

        if not symptoms and not raw_messages:
            return None

        # Загружаем шрифты (скачает автоматически если нет)
        ensure_fonts()

        pdf_path = f"report_{user_id}.pdf"
        styles   = build_styles()
        story    = []

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            leftMargin=20*mm, rightMargin=20*mm,
            topMargin=18*mm,  bottomMargin=18*mm,
        )

        today = datetime.now().strftime("%d.%m.%Y")

        # ── Шапка ─────────────────────────────────────────────────────
        story.append(Paragraph("Медицинский отчёт пациента", styles["title"]))
        story.append(Paragraph(
            f"Период: последние {days} дней   |   Дата формирования: {today}",
            styles["subtitle"]
        ))
        story.append(Spacer(1, 4*mm))
        story.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_PRIMARY))
        story.append(Spacer(1, 4*mm))

        # ── Сводная таблица симптомов ──────────────────────────────────
        if symptoms:
            story.append(Paragraph("Сводка симптомов", styles["section"]))

            unique: dict[str, list] = {}
            for s in symptoms:
                unique.setdefault(s["name"], []).append(s)

            table_data = [[
                Paragraph("Симптом",         styles["body_bold"]),
                Paragraph("Кол-во",          styles["body_bold"]),
                Paragraph("Выраженность",    styles["body_bold"]),
                Paragraph("Время проявления",styles["body_bold"]),
            ]]

            SEV_RU = {"mild": "слабая", "moderate": "умеренная", "severe": "сильная"}

            for name, entries in sorted(unique.items()):
                severities = [e.get("severity", "") for e in entries if e.get("severity")]
                sev_en     = max(set(severities), key=severities.count) if severities else ""
                sev_ru     = SEV_RU.get(sev_en, "—")
                timings    = [e.get("timing", "") for e in entries if e.get("timing")]
                tim_text   = timings[0] if timings else "—"

                sev_color = {"mild": COLOR_MILD, "moderate": COLOR_MODERATE, "severe": COLOR_SEVERE}.get(sev_en, COLOR_SUBTLE)

                table_data.append([
                    Paragraph(name,          styles["body"]),
                    Paragraph(str(len(entries)), styles["body"]),
                    Paragraph(f'<font color="#{sev_color.hexval()[2:]}">{sev_ru}</font>', styles["body"]),
                    Paragraph(tim_text,      styles["body"]),
                ])

            tbl = Table(table_data, colWidths=[65*mm, 20*mm, 35*mm, 50*mm], repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND",     (0, 0), (-1, 0),  COLOR_LIGHT_BG),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
                ("GRID",           (0, 0), (-1, -1),  0.4, COLOR_BORDER),
                ("TOPPADDING",     (0, 0), (-1, -1),  5),
                ("BOTTOMPADDING",  (0, 0), (-1, -1),  5),
                ("LEFTPADDING",    (0, 0), (-1, -1),  6),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 4*mm))

        # ── Временная шкала ────────────────────────────────────────────
        if symptoms:
            story.append(Paragraph("Хронология симптомов", styles["section"]))

            by_date: dict[str, list] = {}
            for s in symptoms:
                by_date.setdefault(s["timestamp"][:10], []).append(s)

            MONTHS_RU = {
                "Jan":"янв", "Feb":"фев", "Mar":"мар", "Apr":"апр",
                "May":"май", "Jun":"июн", "Jul":"июл", "Aug":"авг",
                "Sep":"сен", "Oct":"окт", "Nov":"ноя", "Dec":"дек",
            }

            for date_str, day_symptoms in sorted(by_date.items()):
                dt       = datetime.strptime(date_str, "%Y-%m-%d")
                date_en  = dt.strftime("%d %b %Y")
                for en, ru in MONTHS_RU.items():
                    date_en = date_en.replace(en, ru)

                tl_data = [[
                    Paragraph(date_en,        styles["body_bold"]),
                    Paragraph("Подробности",  styles["body_bold"]),
                ]]

                SEV_RU = {"mild": "слабая", "moderate": "умеренная", "severe": "сильная"}

                for s in day_symptoms:
                    parts = []
                    if s.get("onset"):    parts.append(f"Начало: {s['onset']}")
                    if s.get("timing"):   parts.append(f"Когда: {s['timing']}")
                    if s.get("triggers"): parts.append(f"Триггер: {s['triggers']}")
                    if s.get("notes"):    parts.append(f"Заметки: {s['notes']}")
                    detail = "   |   ".join(parts) if parts else "—"

                    sev_en    = s.get("severity", "")
                    sev_ru    = SEV_RU.get(sev_en, "")
                    sev_color = {"mild": COLOR_MILD, "moderate": COLOR_MODERATE, "severe": COLOR_SEVERE}.get(sev_en, COLOR_SUBTLE)
                    sev_hex   = sev_color.hexval()[2:]

                    name_text = s["name"]
                    if sev_ru:
                        name_text += f'  <font color="#{sev_hex}">[{sev_ru}]</font>'

                    tl_data.append([
                        Paragraph(name_text, styles["body"]),
                        Paragraph(detail,    styles["label"]),
                    ])

                tl_tbl = Table(tl_data, colWidths=[55*mm, 115*mm])
                tl_tbl.setStyle(TableStyle([
                    ("BACKGROUND",    (0, 0), (-1, 0),  COLOR_LIGHT_BG),
                    ("SPAN",          (0, 0), (-1, 0)),
                    ("GRID",          (0, 0), (-1, -1),  0.3, COLOR_BORDER),
                    ("TOPPADDING",    (0, 0), (-1, -1),  4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1),  4),
                    ("LEFTPADDING",   (0, 0), (-1, -1),  6),
                ]))
                story.append(tl_tbl)
                story.append(Spacer(1, 2*mm))

        # ── Слова пациента ─────────────────────────────────────────────
        if raw_messages:
            story.append(Paragraph("Слова пациента (дословно)", styles["section"]))

            for msg in raw_messages[-10:]:
                date_str = msg["timestamp"][:10]
                dt       = datetime.strptime(date_str, "%Y-%m-%d")
                date_fmt = dt.strftime("%d.%m")
                story.append(Paragraph(
                    f'<font color="#757575">{date_fmt}</font>   {msg["raw_text"]}',
                    styles["quote"]
                ))
                story.append(Spacer(1, 1.5*mm))

        # ── Футер ─────────────────────────────────────────────────────
        story.append(Spacer(1, 6*mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            "Отчёт сформирован автоматически. Не является заменой консультации врача.",
            styles["label"]
        ))

        doc.build(story)
        return pdf_path

    # Текстовая версия (запасная)
    def generate_report(self, user_id: int, days: int = 7) -> str | None:
        symptoms     = self.db.get_symptoms_for_report(user_id, days)
        raw_messages = self.db.get_raw_messages_for_period(user_id, days)
        if not symptoms and not raw_messages:
            return None
        today  = datetime.now().strftime("%d.%m.%Y")
        report = f"🏥 *ОТЧЁТ ДЛЯ ВРАЧА*\nПериод: {days} дней | {today}\n\n"
        if symptoms:
            unique = list(set(s["name"] for s in symptoms))
            report += "📋 *Симптомы:* " + ", ".join(sorted(unique)) + "\n"
        return report
