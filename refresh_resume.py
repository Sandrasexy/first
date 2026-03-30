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
                # Пробуем оба варианта домена
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
        # Устанавливаем куки в браузерный cookie jar (не через заголовки)
        # Это позволяет JavaScript читать _xsrf для CSRF-защиты
        context.add_cookies(parse_cookies(hh_cookie))
        page = context.new_page()

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

        # ── Поднимаем резюме через прямой API-запрос ─────────────────────
        # Находим ID всех резюме со страницы
        resume_ids = page.evaluate("""
            () => {
                const ids = [];
                // Ищем ссылки вида /resume/XXXXX
                document.querySelectorAll('a[href*="/resume/"]').forEach(a => {
                    const m = a.href.match(/\\/resume\\/([a-z0-9]+)/i);
                    if (m && !ids.includes(m[1])) ids.push(m[1]);
                });
                return ids;
            }
        """)
        print(f"Найдены ID резюме: {resume_ids}")

        # Проверяем xsrf-токен
        xsrf = page.evaluate("() => document.cookie")
        print(f"Куки на странице: {xsrf[:200]}")
        local_storage = page.evaluate("() => JSON.stringify(Object.fromEntries(Object.entries(localStorage)))")
        print(f"localStorage: {local_storage[:300]}")

        raise_buttons = page.query_selector_all("[data-qa='resume-update-button']")
        if not raise_buttons:
            print("Кнопок «Поднять в поиске» не найдено.")
            page.screenshot(path="login_page.png")
            browser.close()
            return

        print(f"\nНайдено кнопок для поднятия: {len(raise_buttons)}")

        # Пробуем API-запросы с разными endpoint'ами
        success = 0
        for resume_id in resume_ids:
            endpoints = [
                "/applicant/resumes/touch?resume=" + resume_id,
                "/resume/" + resume_id + "/touch",
                "/applicant/resume/" + resume_id + "/publish",
            ]
            for ep in endpoints:
                js = """
                async (ep) => {
                    try {
                        // Читаем _xsrf из куки для CSRF-защиты
                        const xsrf = document.cookie.split(';')
                            .map(c => c.trim())
                            .find(c => c.startsWith('_xsrf='));
                        const xsrfVal = xsrf ? xsrf.split('=')[1] : '';

                        const r = await fetch(ep, {
                            method: 'POST',
                            credentials: 'include',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded',
                                'X-Requested-With': 'XMLHttpRequest',
                                'X-XSRFToken': xsrfVal
                            }
                        });
                        const text = await r.text();
                        return { status: r.status, xsrf: xsrfVal.slice(0,20), body: text.slice(0, 100) };
                    } catch(e) { return { error: e.message }; }
                }
                """
                result = page.evaluate(js, ep)
                print(f"  {ep} → {result}")
                if isinstance(result, dict) and result.get("status") in (200, 204):
                    print(f"  Поднято резюме {resume_id}!")
                    success += 1
                    break

        page.screenshot(path="login_page.png")
        print(f"\nОбработано: {success}")
        browser.close()


if __name__ == "__main__":
    main()
