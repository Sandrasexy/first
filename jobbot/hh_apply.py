"""
Отклик на вакансии hh.ru через браузер Playwright.
Использует cookies из переменной окружения HH_COOKIE.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def get_cookie() -> str:
    value = os.environ.get("HH_COOKIE", "").strip()
    if not value:
        print("Ошибка: переменная HH_COOKIE не задана.")
        sys.exit(1)
    return value


def parse_cookies(cookie_string: str) -> list:
    cookies = []
    for pair in cookie_string.split(";"):
        pair = pair.strip()
        if "=" in pair:
            name, _, value = pair.partition("=")
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


def _close_popup(page):
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


def apply_to_vacancy(page, vacancy_url: str, resume_id: str,
                     cover_letter: str) -> str:
    """
    Откликается на вакансию.
    Возвращает: 'success' | 'already_applied' | 'no_button' | 'error:<msg>'
    """
    try:
        page.goto(vacancy_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        _close_popup(page)

        # Уже откликались?
        already = page.query_selector(
            "[data-qa='vacancy-response-completed'], "
            "[data-qa='response-letter-finished']"
        )
        if already:
            return "already_applied"

        # Находим кнопку «Откликнуться»
        btn = (
            page.query_selector("[data-qa='vacancy-response-link-top']")
            or page.query_selector("[data-qa='vacancy-response-link']")
            or page.query_selector("[data-qa='vacancy-response-link-bottom']")
            or page.query_selector("a[data-qa*='response-link']")
            or page.query_selector("button[data-qa*='response-link']")
        )

        # Запасной вариант: ищем по тексту кнопки через JS
        if not btn:
            try:
                handle = page.evaluate_handle("""() => {
                    const els = document.querySelectorAll('a, button, [role="button"]');
                    for (const el of els) {
                        const t = (el.innerText || el.textContent || '').trim();
                        if (t === 'Откликнуться' || t.startsWith('Откликнуться ')) {
                            return el;
                        }
                    }
                    return null;
                }""")
                element = handle.as_element()
                if element and element.is_visible():
                    btn = element
            except Exception:
                pass

        if not btn:
            # Скриншот для отладки
            try:
                vac_id = vacancy_url.rstrip("/").split("/")[-1]
                page.screenshot(path=f"no_button_{vac_id}.png", full_page=True)
            except Exception:
                pass
            return "no_button"

        btn.click()
        time.sleep(2)

        # ── Выбор резюме ────────────────────────────────────────────────────
        # Ищем элемент с нашим resume_id в href и кликаем/выбираем его
        resume_selected = page.evaluate(
            """(resumeId) => {
                // Вариант 1: радиокнопки с data-qa="resume-block"
                const radios = document.querySelectorAll(
                    'input[type="radio"][name="resume"]'
                );
                for (const r of radios) {
                    if (r.value === resumeId || (r.closest('a') || {}).href?.includes(resumeId)) {
                        r.click();
                        return true;
                    }
                }
                // Вариант 2: ссылки на резюме
                const links = document.querySelectorAll('a[href*="/resume/"]');
                for (const a of links) {
                    if (a.href.includes(resumeId)) {
                        a.click();
                        return true;
                    }
                }
                return false;
            }""",
            resume_id,
        )

        if not resume_selected:
            # Если резюме одно — оно уже выбрано, продолжаем
            count = page.evaluate(
                "() => document.querySelectorAll('input[type=\"radio\"][name=\"resume\"]').length"
            )
            if count > 1:
                return "error:resume_not_found"

        time.sleep(0.5)

        # ── Сопроводительное письмо ─────────────────────────────────────────
        if cover_letter:
            textarea = (
                page.query_selector(
                    "[data-qa='vacancy-response-popup-form-letter-input']"
                )
                or page.query_selector("textarea[name='letter']")
                or page.query_selector("textarea")
            )
            if textarea:
                textarea.fill(cover_letter)
                time.sleep(0.3)

        # ── Отправка ────────────────────────────────────────────────────────
        submit = (
            page.query_selector("[data-qa='vacancy-response-submit-popup']")
            or page.query_selector("[data-qa='vacancy-response-submit']")
            or page.query_selector("button[type='submit']")
        )
        if not submit:
            return "error:no_submit_button"

        submit.click()
        time.sleep(2)

        # Проверяем успех
        success_el = page.query_selector(
            "[data-qa='vacancy-response-completed'], "
            "[data-qa='response-letter-finished']"
        )
        if success_el:
            return "success"

        # Запасная проверка — ищем текст подтверждения
        body_text = page.inner_text("body")
        if "Отклик отправлен" in body_text or "Резюме отправлено" in body_text:
            return "success"

        return "error:no_confirmation"

    except PlaywrightTimeout as e:
        return f"error:timeout {e}"
    except Exception as e:
        return f"error:{e}"


def apply_batch(vacancies: list[dict]) -> dict[int, str]:
    """
    Принимает список словарей из db.get_pending_applications().
    Возвращает {vacancy_id: result_string}.
    """
    if not vacancies:
        return {}

    hh_cookie = get_cookie()
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        context.add_cookies(parse_cookies(hh_cookie))
        page = context.new_page()

        # Прогрев — открываем hh.ru для установки сессии
        page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded")
        time.sleep(2)

        body = page.inner_text("body")
        if "Войдите на сайт" in body or "Мои резюме" not in body:
            print("Ошибка: сессия истекла. Обнови HH_COOKIE в GitHub Secrets.")
            browser.close()
            sys.exit(1)

        print("Сессия активна.")

        for v in vacancies:
            vid = v["id"]
            resume_id = os.environ.get(
                f"HH_{v['role_alias'].upper()}_RESUME_ID", ""
            ).strip()

            if not resume_id:
                print(
                    f"  Пропускаю «{v['title']}»: "
                    f"не задан HH_{v['role_alias'].upper()}_RESUME_ID"
                )
                results[vid] = "skipped:no_resume_id"
                continue

            print(f"  Откликаюсь на «{v['title']}» ({v['employer']})...")
            result = apply_to_vacancy(
                page, v["url"], resume_id, v.get("cover_text", "")
            )
            results[vid] = result
            print(f"    → {result}")

            time.sleep(3)  # пауза между откликами

        browser.close()

    return results
