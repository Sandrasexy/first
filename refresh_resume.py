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


def _close_modal(page):
    """Закрывает модальное окно если оно открыто."""
    try:
        # Ждём немного чтобы модалка успела появиться
        time.sleep(0.5)
        overlay = page.query_selector("[data-qa='modal-overlay']")
        if not overlay:
            return

        print("  Обнаружена модалка — закрываю...")

        # Вариант 1: кнопка закрытия внутри модалки
        closed = page.evaluate("""() => {
            const modal = document.querySelector('[data-qa="modal-overlay"]');
            if (!modal) return false;
            // Ищем кнопку закрытия
            const closeBtn = modal.querySelector(
                'button[data-qa*="close"], button[aria-label*="\u0437\u0430\u043a\u0440\u044b\u0442\u044c"], ' +
                'button[aria-label*="Close"], [data-qa*="modal-close"]'
            );
            if (closeBtn) { closeBtn.click(); return true; }
            // Ищем любую кнопку с текстом "Понятно", "Закрыть", "OK"
            const btns = Array.from(modal.querySelectorAll('button'));
            const ok = btns.find(b =>
                ['Понятно', 'Закрыть', 'OK', 'Хорошо', 'Продолжить'].includes(b.textContent.trim())
            );
            if (ok) { ok.click(); return true; }
            return false;
        }""")

        if not closed:
            # Вариант 2: Escape
            page.keyboard.press("Escape")

        time.sleep(1)

        # Проверяем что модалка закрылась
        if page.query_selector("[data-qa='modal-overlay']"):
            # Вариант 3: клик вне модалки (в угол страницы)
            page.mouse.click(10, 10)
            time.sleep(0.5)

    except Exception as e:
        print(f"  Не удалось закрыть модалку: {e}")


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
        page.goto("https://hh.ru/applicant/resumes", wait_until="networkidle")
        time.sleep(2)

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

        # Отладка: выводим все data-qa атрибуты на странице
        all_data_qa = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('[data-qa]'))
                .map(el => el.getAttribute('data-qa'))
                .filter(qa => qa && (qa.includes('raise') || qa.includes('resume') || qa.includes('update')));
        }""")
        print(f"data-qa атрибуты на странице: {all_data_qa}")

        # Отладка: выводим тексты ссылок и кнопок связанных с поднятием
        raise_texts = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a, button'))
                .map(el => (el.innerText || el.textContent || '').trim())
                .filter(t => t.includes('Поднять') || t.includes('Обновить'));
        }""")
        print(f"Тексты кнопок/ссылок с 'Поднять'/'Обновить': {raise_texts}")

        # Ищем кнопки поднятия — без уточнения тега (могут быть <a> или <button>)
        raise_buttons = page.query_selector_all(
            "[data-qa='resume-raise-button'], "
            "[data-qa='resume-update-button']"
        )

        if not raise_buttons:
            raise_buttons = page.query_selector_all(
                "[data-qa*='raise'], [data-qa*='update-date']"
            )

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

                # Закрываем модальное окно если появилось
                _close_modal(page)

                print(f"  Поднято успешно")
            except Exception as e:
                print(f"  Ошибка при нажатии кнопки {i}: {e}")
                # Пробуем закрыть модалку и продолжить
                _close_modal(page)

        print("\nГотово! Все резюме подняты.")
        page.screenshot(path="debug_success.png", full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
