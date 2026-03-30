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
    # Полная строка Cookie-заголовка из браузера (Network → Request Headers → cookie)
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
            # Передаём весь Cookie-заголовок как есть
            extra_http_headers={"Cookie": hh_cookie},
        )

        page = context.new_page()

        # Открываем страницу резюме
        print("Открываю hh.ru...")
        page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded")
        time.sleep(3)
        page.screenshot(path="login_page.png")
        print(f"URL: {page.url}")

        # Проверяем авторизацию по наличию раздела «Мои резюме»
        page_text = page.inner_text("body")
        if "Мои резюме" not in page_text and "резюме" not in page_text.lower():
            print("Ошибка: сессия не активна. Обнови HH_COOKIE и HH_XSRF в GitHub Secrets.")
            browser.close()
            sys.exit(1)

        if "Войдите на сайт" in page_text or "Войдите" in page_text[:500]:
            print("Ошибка: сессия истекла. Обнови HH_COOKIE и HH_XSRF в GitHub Secrets.")
            browser.close()
            sys.exit(1)

        print("Сессия активна!")

        # Ищем ссылки/кнопки поднятия резюме по тексту и data-qa
        raise_buttons = page.query_selector_all(
            "a:has-text('Поднять в поиске'), "
            "button:has-text('Поднять в поиске'), "
            "a:has-text('Поднять резюме'), "
            "button:has-text('Поднять резюме'), "
            "[data-qa='resume-raise-button'], "
            "[data-qa='resume-update-button']"
        )

        if not raise_buttons:
            print("Кнопки поднятия не найдены — резюме уже подняты недавно или не опубликованы.")
            browser.close()
            return

        print(f"Найдено кнопок для поднятия: {len(raise_buttons)}")

        success_count = 0
        for i, button in enumerate(raise_buttons, 1):
            try:
                button_text = button.inner_text().strip()
                print(f"Нажимаю кнопку {i}: «{button_text}»")
                # JavaScript-клик обходит ограничения viewport
                button.evaluate("el => el.click()")
                time.sleep(2)
                # Закрываем модальное окно подтверждения если появилось
                try:
                    confirm = page.query_selector(
                        "button[data-qa='resume-raise-confirm'], "
                        "button:has-text('Поднять'), "
                        "[data-qa='modal-confirm-button']"
                    )
                    if confirm and confirm.is_visible():
                        confirm.evaluate("el => el.click()")
                        time.sleep(1)
                except Exception:
                    pass
                print("  Поднято успешно")
                success_count += 1
            except Exception as e:
                print(f"  Ошибка: {e}")

        if success_count > 0:
            print(f"\nГотово! Поднято резюме: {success_count}")
        else:
            print("\nНи одно резюме не удалось поднять.")
            sys.exit(1)
        browser.close()


if __name__ == "__main__":
    main()
