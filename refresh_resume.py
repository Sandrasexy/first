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


def try_fill(page, selectors: list, value: str, label: str):
    """Пробует заполнить поле по списку селекторов."""
    for selector in selectors:
        try:
            page.wait_for_selector(selector, timeout=5000)
            page.fill(selector, value)
            print(f"  Поле «{label}» заполнено (селектор: {selector})")
            return True
        except PlaywrightTimeout:
            continue
    return False


def try_click(page, selectors: list, label: str):
    """Пробует нажать кнопку по списку селекторов."""
    for selector in selectors:
        try:
            page.wait_for_selector(selector, timeout=5000)
            page.click(selector)
            print(f"  Нажата кнопка «{label}» (селектор: {selector})")
            return True
        except PlaywrightTimeout:
            continue
    return False


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
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # --- Авторизация ---
        print("Открываю страницу входа...")
        page.goto("https://hh.ru/account/login", wait_until="domcontentloaded")
        time.sleep(3)

        # Скриншот для отладки
        page.screenshot(path="login_page.png")
        print(f"Скриншот сохранён: login_page.png (URL: {page.url})")

        # Закрываем попап/куки если есть
        try_click(page, [
            "button[data-qa='cookie-agreement-button']",
            "[data-qa='noauth-popup-close']",
            "button.bloko-modal-close",
        ], "закрыть попап")

        # Переключаемся на вход по паролю (если есть такая кнопка)
        try_click(page, [
            "button[data-qa='expand-login-by-password']",
            "a[data-qa='login-by-password']",
            "[data-hh-tab='byPassword']",
        ], "войти по паролю")
        time.sleep(1)

        # Заполняем логин
        login_filled = try_fill(page, [
            "input[data-qa='login-input-username']",
            "input[name='login']",
            "input[type='email']",
            "input[autocomplete='username']",
            "input[placeholder*='айл']",   # «email» или «мобильный»
        ], email, "логин")

        if not login_filled:
            page.screenshot(path="login_page.png")
            print("Не удалось найти поле логина. Смотри скриншот login_page.png")
            browser.close()
            sys.exit(1)

        # Заполняем пароль
        password_filled = try_fill(page, [
            "input[data-qa='login-input-password']",
            "input[name='password']",
            "input[type='password']",
            "input[autocomplete='current-password']",
        ], password, "пароль")

        if not password_filled:
            # Возможно, пароль на следующем шаге — нажимаем «Продолжить»
            try_click(page, [
                "button[data-qa='account-login-submit']",
                "button[type='submit']",
                "input[type='submit']",
            ], "продолжить")
            time.sleep(2)
            page.screenshot(path="login_page.png")

            password_filled = try_fill(page, [
                "input[data-qa='login-input-password']",
                "input[name='password']",
                "input[type='password']",
            ], password, "пароль (шаг 2)")

        if not password_filled:
            print("Не удалось найти поле пароля. Смотри скриншот login_page.png")
            browser.close()
            sys.exit(1)

        # Нажимаем войти
        submitted = try_click(page, [
            "button[data-qa='account-login-submit']",
            "button[type='submit']",
            "input[type='submit']",
        ], "войти")

        if not submitted:
            print("Не удалось найти кнопку входа.")
            browser.close()
            sys.exit(1)

        time.sleep(4)
        page.screenshot(path="login_page.png")
        print(f"После входа URL: {page.url}")

        if "login" in page.url or "account" in page.url:
            print("Ошибка: не удалось войти. Проверьте HH_EMAIL и HH_PASSWORD.")
            browser.close()
            sys.exit(1)

        print("Вошёл успешно!")

        # --- Переходим к резюме ---
        print("\nОткрываю страницу резюме...")
        page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded")
        time.sleep(3)

        raise_buttons = page.query_selector_all(
            "button[data-qa='resume-raise-button'], "
            "button[data-qa='resume-update-button'], "
            "[data-qa*='raise'], "
            "[data-qa*='update-date']"
        )

        if not raise_buttons:
            print("Кнопки поднятия не найдены — резюме уже подняты недавно или ещё не опубликованы.")
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
                print(f"  Поднято успешно")
            except Exception as e:
                print(f"  Ошибка: {e}")

        print("\nГотово! Все резюме подняты.")
        browser.close()


if __name__ == "__main__":
    main()
