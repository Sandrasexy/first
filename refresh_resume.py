"""
Скрипт автоматически поднимает все резюме на hh.ru через браузер.
Запускается через GitHub Actions каждые 4 часа.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def get_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"Ошибка: переменная окружения {name} не задана.")
        sys.exit(1)
    return value


def main():
    email = get_env("HH_EMAIL")
    password = get_env("HH_PASSWORD")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        # --- Авторизация ---
        print("Открываю страницу входа...")
        page.goto("https://hh.ru/account/login?backurl=%2F", wait_until="networkidle")
        time.sleep(2)

        # Выбираем вход по паролю (не через соцсети)
        try:
            page.click("button[data-qa='expand-login-by-password']", timeout=5000)
            time.sleep(1)
        except PlaywrightTimeout:
            pass  # Кнопка могла уже быть активна

        print("Вввожу логин и пароль...")
        page.fill("input[data-qa='login-input-username']", email)
        page.fill("input[data-qa='login-input-password']", password)
        page.click("button[data-qa='account-login-submit']")

        # Ждём загрузки главной страницы
        try:
            page.wait_for_url("https://hh.ru/", timeout=15000)
        except PlaywrightTimeout:
            # Проверяем не появилась ли капча или ошибка
            if "login" in page.url:
                print("Ошибка: не удалось войти. Проверьте HH_EMAIL и HH_PASSWORD.")
                print(f"Текущий URL: {page.url}")
                browser.close()
                sys.exit(1)

        print(f"Вошёл успешно. Текущая страница: {page.url}")

        # --- Переходим к резюме ---
        print("\nОткрываю страницу резюме...")
        page.goto("https://hh.ru/applicant/resumes", wait_until="networkidle")
        time.sleep(2)

        # Ищем все кнопки "Поднять в поиске" / "Обновить дату"
        raise_buttons = page.query_selector_all(
            "button[data-qa='resume-raise-button'], "
            "button[data-qa='resume-update-button']"
        )

        if not raise_buttons:
            # Пробуем альтернативный селектор
            raise_buttons = page.query_selector_all(
                "[data-qa*='raise'], [data-qa*='update-date']"
            )

        if not raise_buttons:
            print("Кнопки поднятия не найдены.")
            print("Возможно, резюме уже были подняты недавно или изменился интерфейс hh.ru.")
            browser.close()
            return

        print(f"Найдено кнопок для поднятия: {len(raise_buttons)}")

        for i, button in enumerate(raise_buttons, 1):
            try:
                button_text = button.inner_text().strip()
                print(f"Нажимаю кнопку {i}: «{button_text}»")
                button.click()
                time.sleep(2)

                # Закрываем модальное окно подтверждения если появилось
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

                print(f"  Поднято успешно")
            except Exception as e:
                print(f"  Ошибка при нажатии кнопки {i}: {e}")

        print("\nГотово! Все резюме подняты.")
        browser.close()


if __name__ == "__main__":
    main()
