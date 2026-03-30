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

        # ── Поднимаем резюме через перехват AJAX-запроса ─────────────────
        raise_buttons = page.query_selector_all("[data-qa='resume-update-button']")

        if not raise_buttons:
            print("Кнопок «Поднять в поиске» не найдено — резюме уже подняты или недоступны.")
            page.screenshot(path="login_page.png")
            browser.close()
            return

        print(f"Найдено кнопок для поднятия: {len(raise_buttons)}")
        success = 0

        for i, btn in enumerate(raise_buttons, 1):
            print(f"  Кнопка {i}: кликаю и слушаю запросы...")
            captured = []

            def on_request(req):
                if req.method in ("POST", "PUT") and "hh.ru" in req.url:
                    captured.append({"method": req.method, "url": req.url})
                    print(f"    → {req.method} {req.url}")

            page.on("request", on_request)

            btn.scroll_into_view_if_needed()
            time.sleep(0.3)
            box = btn.bounding_box()
            if box:
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            else:
                btn.dispatch_event("click")
            time.sleep(3)

            page.remove_listener("request", on_request)

            if captured:
                print(f"    Перехвачено запросов: {len(captured)}")
            else:
                print("    Запросов после клика не было — пробуем прямой API вызов")
                # Пробуем поднять через API напрямую
                # Получаем resume_id из data-qa или ссылки на странице
                resume_id = btn.evaluate("""el => {
                    const card = el.closest('[data-qa*="resume"]') || el.closest('[class*="resume"]');
                    if (!card) return null;
                    const link = card.querySelector('a[href*="/resume/"]');
                    if (link) {
                        const m = link.href.match(/resume\\/([^?#]+)/);
                        return m ? m[1] : null;
                    }
                    return null;
                }""")
                print(f"    resume_id={resume_id}")

                if resume_id:
                    result = page.evaluate(f"""async () => {{
                        const r = await fetch('/applicant/resumes/touch', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                            body: 'resume={resume_id}'
                        }});
                        return {{ status: r.status, url: r.url }};
                    }}""")
                    print(f"    API ответ: {result}")

            success += 1

        page.screenshot(path="login_page.png")
        print(f"\nГотово! Обработано резюме: {success}")
        browser.close()


if __name__ == "__main__":
    main()
