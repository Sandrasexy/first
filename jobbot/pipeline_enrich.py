"""
Пайплайн обогащения: поиск вакансий + генерация сопроводительных писем.
Запускается автоматически 3 раза в день через GitHub Actions.
"""

import db
import hh_search
import generate_covers


def run():
    db.init_db()

    # ── 1. Поиск вакансий ──────────────────────────────────────────────────
    print("=" * 60)
    print("  Поиск вакансий на hh.ru")
    print("=" * 60)

    all_vacancies = hh_search.search_all_roles()
    print(f"\nВсего найдено вакансий: {len(all_vacancies)}")

    new_count = 0
    for v in all_vacancies:
        if not db.vacancy_exists(v["hh_id"]):
            db.save_vacancy(v)
            new_count += 1

    print(f"Новых вакансий добавлено: {new_count}")

    if new_count == 0:
        print("Новых вакансий нет — генерация писем не нужна.")
        return

    # ── 2. Генерация сопроводительных писем ───────────────────────────────
    print("\n" + "=" * 60)
    print("  Генерация сопроводительных писем")
    print("=" * 60)

    without_cover = db.get_vacancies_without_cover()
    print(f"Вакансий без письма: {len(without_cover)}")

    covers = generate_covers.generate_covers_for_vacancies(without_cover)

    for vacancy_id, text in covers.items():
        # Найдём role_alias из списка
        v = next((x for x in without_cover if x["id"] == vacancy_id), None)
        if v:
            db.save_cover(vacancy_id, v["role_alias"], text)

    print(f"\nПисем сгенерировано: {len(covers)}")
    print("\nПайплайн завершён.")


if __name__ == "__main__":
    run()
