"""
Пайплайн откликов: отправка откликов на вакансии с готовыми письмами.
Запускается вручную через GitHub Actions (workflow_dispatch).
"""

from datetime import datetime
import db
import hh_apply


def run():
    db.init_db()

    print("=" * 60)
    print("  Отклики на вакансии")
    print("=" * 60)

    pending = db.get_pending_applications()
    print(f"Вакансий с готовым письмом, ожидающих отклика: {len(pending)}")

    if not pending:
        print("Нечего делать.")
        return

    results = hh_apply.apply_batch(pending)

    # Сохраняем результаты в БД
    for v in pending:
        vid = v["id"]
        result = results.get(vid, "skipped")
        status = "applied" if result == "success" else (
            "already_applied" if result == "already_applied" else "error"
        )
        applied_at = datetime.utcnow().isoformat() if status in ("applied", "already_applied") else None
        error_msg = result if status == "error" else None

        import os
        resume_id = os.environ.get(
            f"HH_{v['role_alias'].upper()}_RESUME_ID", ""
        ).strip()

        db.save_application(
            vacancy_id=vid,
            role_alias=v["role_alias"],
            resume_id=resume_id,
            cover_id=v.get("cover_id"),
            status=status,
            applied_at=applied_at,
            error_msg=error_msg,
        )

    applied = sum(1 for r in results.values() if r == "success")
    already = sum(1 for r in results.values() if r == "already_applied")
    errors = sum(1 for r in results.values() if r.startswith("error"))

    print(f"\nИтог:")
    print(f"  Успешно: {applied}")
    print(f"  Уже откликались: {already}")
    print(f"  Ошибки: {errors}")
    print("\nПайплайн завершён.")


if __name__ == "__main__":
    run()
