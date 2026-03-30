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


def screenshot(page, label: str):
    page.screenshot(path="login_page.png")
    print(f"[скриншот] {label} | URL: {page.url}")


def main():
    email = get_env("HH_EMAIL")
    password = get_env("HH_PASSWORD")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 390, "height": 844},  # мобильный viewport как у скриншота
        )

        # ── Шаг 1: открываем страницу входа ──────────────────────────────
        print("Открываю страницу входа...")
        page.goto("https://hh.ru/account/login", wait_until="domcontentloaded")
        time.sleep(3)
        screenshot(page, "начало")

        # ── Шаг 2: выбираем «Я ищу работу» ──────────────────────────────
        try:
            page.wait_for_selector("text=Я ищу работу", timeout=5000)
            page.click("text=Я ищу работу")
            print("  Выбрано: Я ищу работу")
            time.sleep(1)
        except PlaywrightTimeout:
            print("  Экран выбора типа не найден, продолжаем...")

        # ── Шаг 3: нажимаем «Войти» ──────────────────────────────────────
        try:
            page.wait_for_selector("button:has-text('Войти')", timeout=5000)
            page.click("button:has-text('Войти')")
            print("  Нажато: Войти")
            time.sleep(2)
            screenshot(page, "после Войти")
        except PlaywrightTimeout:
            print("  Кнопка Войти не найдена, продолжаем...")

        # ── Шаг 4: переключаемся на вкладку «Почта» ──────────────────────
        try:
            page.wait_for_selector("text=Почта", timeout=5000)
            page.click("text=Почта")
            print("  Выбрана вкладка: Почта")
            time.sleep(1)
            screenshot(page, "после выбора Почта")
        except PlaywrightTimeout:
            print("  Вкладка Почта не найдена, продолжаем...")

        # ── Шаг 5: вводим email ───────────────────────────────────────────
        email_selectors = [
            "input[type='email']",
            "input[name='login']",
            "input[autocomplete='email']",
            "input[autocomplete='username']",
            "input[data-qa='login-input-username']",
            "input[type='text']",
            "input:not([type='hidden']):not([type='password']):not([type='submit'])",
        ]
        email_filled = False
        for sel in email_selectors:
            try:
                page.wait_for_selector(sel, timeout=4000)
                page.fill(sel, email)
                print(f"  Email введён (селектор: {sel})")
                email_filled = True
                break
            except PlaywrightTimeout:
                continue

        if not email_filled:
            screenshot(page, "email не найден")
            print("Не удалось найти поле email. Смотри скриншот.")
            browser.close()
            sys.exit(1)

        # ── Шаг 6: нажимаем «Дальше» ─────────────────────────────────────
        try:
            page.wait_for_selector("button:has-text('Дальше')", timeout=5000)
            page.click("button:has-text('Дальше')")
            print("  Нажато: Дальше")
            time.sleep(2)
            screenshot(page, "после Дальше")
        except PlaywrightTimeout:
            print("  Кнопка Дальше не найдена, пробуем сразу искать пароль...")

        # ── Шаг 7: вводим пароль ─────────────────────────────────────────
        password_selectors = [
            "input[type='password']",
            "input[name='password']",
            "input[autocomplete='current-password']",
            "input[data-qa='login-input-password']",
        ]
        password_filled = False
        for sel in password_selectors:
            try:
                page.wait_for_selector(sel, timeout=6000)
                page.fill(sel, password)
                print(f"  Пароль введён (селектор: {sel})")
                password_filled = True
                break
            except PlaywrightTimeout:
                continue

        if not password_filled:
            screenshot(page, "пароль не найден")
            print("Не удалось найти поле пароля. Смотри скриншот.")
            browser.close()
            sys.exit(1)

        # ── Шаг 8: нажимаем «Войти» (финальная кнопка) ───────────────────
        submit_selectors = [
            "button:has-text('Войти')",
            "button[type='submit']",
            "input[type='submit']",
            "button[data-qa='account-login-submit']",
        ]
        for sel in submit_selectors:
            try:
                page.wait_for_selector(sel, timeout=4000)
                page.click(sel)
                print(f"  Нажата кнопка входа (селектор: {sel})")
                break
            except PlaywrightTimeout:
                continue

        time.sleep(4)
        screenshot(page, "после входа")

        if "login" in page.url or "/account" in page.url:
            print("Ошибка: не удалось войти. Проверьте HH_EMAIL и HH_PASSWORD.")
            browser.close()
            sys.exit(1)

        print("Вошёл успешно!")

        # ── Поднимаем резюме ──────────────────────────────────────────────
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
