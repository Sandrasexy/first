"""
Скрипт автоматически поднимает все резюме на hh.ru через браузер.
Запускается через GitHub Actions каждые 4 часа.
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
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 3000},  # высокий viewport — всё видно
            extra_http_headers={"Cookie": hh_cookie},
        )

        # Открываем страницу резюме
        print("Открываю hh.ru...")
        page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded")
        time.sleep(3)

        # Проверяем авторизацию
        page_text = page.inner_text("body")
        if "Войдите на сайт" in page_text or "Мои резюме" not in page_text:
            print("Ошибка: сессия истекла. Обнови HH_COOKIE в GitHub Secrets.")
            page.screenshot(path="login_page.png")
            browser.close()
            sys.exit(1)

        print(f"Сессия активна! URL: {page.url}")

        # Закрываем попап через JS
        closed = page.evaluate("""
            () => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const ok = buttons.find(b =>
                    b.textContent.trim() === 'Понятно' ||
                    b.textContent.trim() === 'Закрыть' ||
                    b.textContent.trim() === 'OK'
                );
                if (ok) { ok.click(); return true; }
                return false;
            }
        """)
        if closed:
            print("  Попап закрыт")
            time.sleep(1)

        # ── Собираем статус каждого резюме ───────────────────────────────
        print("\n─── Статус резюме ───")
        resume_data = page.evaluate("""
            () => {
                const results = [];
                // Каждая карточка резюме
                const cards = document.querySelectorAll('[data-qa="resume-block"]');
                cards.forEach(card => {
                    // Название резюме
                    const titleEl = card.querySelector('[data-qa="resume-title"]') ||
                                    card.querySelector('h2') ||
                                    card.querySelector('a[href*="/resume/"]');
                    const title = titleEl ? titleEl.textContent.trim() : '(без названия)';

                    // Статус (текст под названием)
                    const raiseBtn  = card.querySelector('a:not([href])') ||
                                      card.querySelector('[data-qa*="raise"]');
                    const statusEl  = card.querySelector('[data-qa*="raise-time"]') ||
                                      card.querySelector('[class*="raise"]') ||
                                      card.querySelector('[class*="status"]');

                    // Весь текст карточки для поиска статуса
                    const text = card.innerText;
                    let status = 'неизвестно';
                    if (text.includes('Поднять в поиске')) status = '✅ Можно поднять';
                    else if (text.match(/Поднять в \\d+:\\d+/)) {
                        const m = text.match(/Поднять в (\\d+:\\d+)/);
                        status = `⏳ Можно поднять в ${m[1]}`;
                    }
                    else if (text.includes('Заблокировано')) status = '🚫 Заблокировано';
                    else if (text.includes('Сделать видимым')) status = '👁 Скрыто';
                    else if (text.includes('Не ищу работу')) status = '⏸ Не ищу работу';

                    results.push({ title, status });
                });
                return results;
            }
        """)

        if resume_data:
            for r in resume_data:
                print(f"  «{r['title']}» — {r['status']}")
        else:
            # Запасной вариант — просто текст
            lines = [l.strip() for l in page_text.split('\n') if l.strip()]
            for i, line in enumerate(lines):
                if 'Поднять' in line or 'Заблокировано' in line or 'Сделать видимым' in line:
                    title = lines[i-1] if i > 0 else '?'
                    print(f"  «{title}» — {line}")

        print()

        # ── Поднимаем резюме ──────────────────────────────────────────────
        # Ищем ссылку «Поднять в поиске» через JS по тексту
        raised = page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a, button'));
                const targets = links.filter(el =>
                    el.textContent.trim() === 'Поднять в поиске'
                );
                if (targets.length === 0) return { count: 0, found: [] };

                const found = [];
                targets.forEach(el => {
                    // Получаем координаты центра элемента
                    const rect = el.getBoundingClientRect();
                    // Скроллим к элементу
                    el.scrollIntoView({ block: 'center' });
                    const rect2 = el.getBoundingClientRect();
                    found.push({
                        x: rect2.left + rect2.width / 2,
                        y: rect2.top + rect2.height / 2,
                        text: el.textContent.trim()
                    });
                });
                return { count: targets.length, found };
            }
        """)

        if raised["count"] == 0:
            print("Кнопок «Поднять в поиске» не найдено — резюме уже подняты или недоступны.")
            page.screenshot(path="login_page.png")
            browser.close()
            return

        print(f"Найдено кнопок для поднятия: {raised['count']}")
        success = 0
        for item in raised["found"]:
            print(f"  Кликаю по «{item['text']}» в координатах ({item['x']:.0f}, {item['y']:.0f})")
            # Реальный клик мышью по координатам
            page.mouse.click(item["x"], item["y"])
            time.sleep(3)
            print(f"  URL после клика: {page.url}")
            if "/applicant/resumes" not in page.url:
                page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded")
                time.sleep(2)
            success += 1

        page.screenshot(path="login_page.png")
        print(f"\nГотово! Поднято резюме: {success}")
        browser.close()


if __name__ == "__main__":
    main()
