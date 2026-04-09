"""
Скрипт автоматически поднимает все резюме на hh.ru через браузер.
Запускается через GitHub Actions каждые 4 часа.
Авторизация — через cookie (переменная HH_COOKIE).
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


def parse_cookies(cookie_string: str) -> list:
    """Парсит строку Cookie-заголовка в список для context.add_cookies()."""
    cookies = []
    for pair in cookie_string.split(";"):
        pair = pair.strip()
        if "=" in pair:
            name, value = pair.split("=", 1)
            name = name.strip()
            value = value.strip()
            if name:
                for domain in [".hh.ru", "hh.ru"]:
                    cookies.append({
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": "/",
                    })
    return cookies


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
            viewport={"width": 1280, "height": 3000},
        )
        context.add_cookies(parse_cookies(hh_cookie))
        page = context.new_page()

        # Открываем страницу резюме
        print("Открываю страницу резюме...")
        page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded")
        time.sleep(3)

        # Проверяем авторизацию
        page_text = page.inner_text("body")
        if "Войдите на сайт" in page_text or "Мои резюме" not in page_text:
            print("Ошибка: сессия истекла. Обнови HH_COOKIE в GitHub Secrets.")
            page.screenshot(path="debug_login_failed.png")
            browser.close()
            sys.exit(1)

        print(f"Сессия активна. URL: {page.url}")

        # Закрываем попап если есть
        try:
            page.evaluate("""() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const ok = buttons.find(b =>
                    ['Понятно', 'Закрыть', 'OK', 'Хорошо'].includes(b.textContent.trim())
                );
                if (ok) ok.click();
            }""")
            time.sleep(0.5)
        except Exception:
            pass

        # Ищем кнопки поднятия по нескольким селекторам
        raise_buttons = page.query_selector_all(
            "button[data-qa='resume-raise-button'], "
            "button[data-qa='resume-update-button']"
        )

        if not raise_buttons:
            raise_buttons = page.query_selector_all(
                "[data-qa*='raise'], [data-qa*='update-date']"
            )

        if not raise_buttons:
            # Ищем по тексту через JS (ищем <a> и <button>)
            handles = page.evaluate_handle("""() => {
                return Array.from(document.querySelectorAll('button, a'))
                    .filter(el => {
                        const t = (el.innerText || el.textContent || '').trim();
                        return t === 'Поднять в поиске' || t === 'Обновить дату';
                    });
            }""")
            try:
                items = handles.get_properties()
                raise_buttons = [
                    v.as_element() for v in items.values()
                    if v.as_element() is not None
                ]
            except Exception:
                raise_buttons = []

        if not raise_buttons:
            print("Кнопки поднятия не найдены.")
            print("Возможно, резюме уже были подняты недавно или изменился интерфейс hh.ru.")
            page.screenshot(path="debug_no_buttons.png", full_page=True)
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
        page.screenshot(path="debug_success.png", full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
