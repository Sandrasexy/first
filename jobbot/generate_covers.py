"""
Генерация сопроводительных писем с помощью Claude (Anthropic API).
"""

import os
import sys
import anthropic
from config import ROLES, RESUME_SUMMARIES

MODEL = "claude-haiku-4-5-20251001"  # быстро и дёшево для писем


def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("Ошибка: переменная ANTHROPIC_API_KEY не задана.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


def generate_cover_letter(client: anthropic.Anthropic, vacancy: dict) -> str:
    """Генерирует сопроводительное письмо для конкретной вакансии."""
    role_alias = vacancy["role_alias"]
    role_title = ROLES[role_alias]["title"]
    resume_summary = RESUME_SUMMARIES.get(role_alias, "")

    salary_str = ""
    if vacancy.get("salary_from") or vacancy.get("salary_to"):
        parts = []
        if vacancy.get("salary_from"):
            parts.append(f"от {vacancy['salary_from']}")
        if vacancy.get("salary_to"):
            parts.append(f"до {vacancy['salary_to']}")
        cur = vacancy.get("salary_cur", "")
        salary_str = f"Зарплата: {' '.join(parts)} {cur}"

    prompt = f"""Напиши краткое сопроводительное письмо для отклика на вакансию.

Вакансия: {vacancy['title']}
Компания: {vacancy['employer']}
{salary_str}

Роль, на которую я претендую: {role_title}

Мой опыт (кратко):
{resume_summary}

Требования:
- Письмо на русском языке
- 3–5 предложений, без воды
- Конкретно и по делу: почему я подхожу именно для этой компании/вакансии
- Без шаблонных фраз «меня привлекает динамичная компания»
- Закончи предложением о готовности обсудить детали
- Не пиши «Уважаемые» и вступлений — сразу по делу

Напиши только текст письма, без заголовков и пояснений."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def generate_covers_for_vacancies(vacancies: list[dict]) -> dict[int, str]:
    """
    Принимает список вакансий (из db.get_vacancies_without_cover),
    возвращает словарь {vacancy_id: cover_text}.
    """
    if not vacancies:
        return {}

    client = get_client()
    covers = {}

    for v in vacancies:
        vid = v["id"]
        print(f"  Генерирую письмо для «{v['title']}» ({v['employer']})...")
        try:
            text = generate_cover_letter(client, v)
            covers[vid] = text
            print(f"    OK ({len(text)} симв.)")
        except Exception as e:
            print(f"    Ошибка: {e}")

    return covers
