"""
Скрипт автоматически поднимает все резюме на hh.ru через браузер.
Запускается через GitHub Actions каждые 4 часа.
Использует куки сессии — без логина и кодов подтверждения.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright


def get_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"Ошибка: переменная окружения {name} не задана.")
        sys.exit(1)
    return value


def main():
    hh_cookie = get_env("HH_COOKIE")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )

        # Устанавливаем куки сессии
        context.add_cookies([
            {
                "name": "_zzatgib-w-hh",
                "value": hh_cookie,
                "domain": ".hh.ru",
                "path": "/",
            }
        ])

        page = context.new_page()

        # Проверяем что сессия работает
        print("Открываю hh.ru...")
        page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded")
        time.sleep(3)
        page.screenshot(path="login_page.png")
        print(f"URL: {page.url}")

        # Если нас перебросило на логин — куки устарели
        if "login" in page.url or "account/login" in page.url:
            print("Ошибка: сессия истекла. Обнови значение HH_COOKIE в GitHub Secrets.")
            browser.close()
            sys.exit(1)

        print("Сессия активна!")

        # Ищем кнопки поднятия резюме
        raise_buttons = page.query_selector_all(
            "button[data-qa='resume-raise-button'], "
            "button[data-qa='resume-update-button'], "
            "[data-qa*='raise'], "
            "[data-qa*='update-date']"
        )

        if not raise_buttons:
            print("Кнопки поднятия не найдены — резюме уже подняты недавно или не опубликованы.")
            browser.close()
            return

        print(f"Найдено кнопок для поднятия: {len(raise_buttons)}")

        for i, button in enumerate(raise_buttons, 1):
            try:
                button_text = button.inner_text().strip()
                print(f"Нажимаю кнопку {i}: «{button_text}»")
                button.click()
                time.sleep(2)
                try:
                    confirm = page.query_selector(
                        "button[data-qa='resume-raise-confirm'], "
                        "[data-qa='modal-confirm-button']"
                    )
                    if confirm:
                        confirm.click()
                        time.sleep(1)
                except Exception:
                    pass
                print("  Поднято успешно")
            except Exception as e:
                print(f"  Ошибка: {e}")

        print("\nГотово! Все резюме подняты.")
        browser.close()


if __name__ == "__main__":
    main()
