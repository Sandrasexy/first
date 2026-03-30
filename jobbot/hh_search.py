"""
Поиск вакансий через публичный API hh.ru.
Авторизация не требуется.
"""

import json
import time
import requests
from config import ROLES, SEARCH_AREA, SEARCH_PAGES, ONLY_WITH_SALARY, MIN_SALARY

HH_API = "https://api.hh.ru/vacancies"
HEADERS = {"User-Agent": "jobbot/1.0 (personal project)"}


def _salary_info(vacancy: dict) -> tuple:
    sal = vacancy.get("salary") or {}
    return sal.get("from"), sal.get("to"), sal.get("currency")


def _build_vacancy_record(v: dict, role_alias: str) -> dict:
    sal_from, sal_to, sal_cur = _salary_info(v)
    return {
        "hh_id": v["id"],
        "role_alias": role_alias,
        "title": v.get("name", ""),
        "employer": (v.get("employer") or {}).get("name", ""),
        "url": v.get("alternate_url", ""),
        "salary_from": sal_from,
        "salary_to": sal_to,
        "salary_cur": sal_cur,
        "area": (v.get("area") or {}).get("name", ""),
        "published_at": v.get("published_at", ""),
        "raw_json": json.dumps(v, ensure_ascii=False),
    }


def search_vacancies_for_role(role_alias: str) -> list[dict]:
    """Возвращает список словарей вакансий для роли."""
    role = ROLES[role_alias]
    seen_ids: set[str] = set()
    results = []

    for query in role["queries"]:
        for page in range(SEARCH_PAGES):
            params = {
                "text": query,
                "area": SEARCH_AREA,
                "per_page": 20,
                "page": page,
                "only_with_salary": str(ONLY_WITH_SALARY).lower(),
            }
            try:
                resp = requests.get(HH_API, params=params, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"  Ошибка запроса ({query}, стр.{page}): {e}")
                break

            items = data.get("items", [])
            if not items:
                break

            for v in items:
                vid = v["id"]
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)

                # Фильтр по зарплате
                if MIN_SALARY > 0:
                    sal_from = (v.get("salary") or {}).get("from") or 0
                    if sal_from and sal_from < MIN_SALARY:
                        continue

                results.append(_build_vacancy_record(v, role_alias))

            time.sleep(0.3)  # не перегружаем API

    return results


def search_all_roles() -> list[dict]:
    """Поиск по всем ролям из config.ROLES."""
    all_vacancies = []
    for alias in ROLES:
        print(f"\nПоиск вакансий для роли «{ROLES[alias]['title']}»...")
        vacancies = search_vacancies_for_role(alias)
        print(f"  Найдено: {len(vacancies)}")
        all_vacancies.extend(vacancies)
    return all_vacancies
