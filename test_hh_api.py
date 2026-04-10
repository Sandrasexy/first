"""
Тест: работает ли hh.ru REST API с cookie-авторизацией?
"""
import os
import sys
import requests

cookie = os.environ.get("HH_COOKIE", "").strip()
if not cookie:
    print("HH_COOKIE не задан")
    sys.exit(1)

headers = {
    "Cookie": cookie,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# 1. Проверяем /me
print("=== GET /me ===")
r = requests.get("https://api.hh.ru/me", headers=headers)
print(f"Status: {r.status_code}")
print(r.text[:500])
print()

# 2. Проверяем /resumes/mine
print("=== GET /resumes/mine ===")
r = requests.get("https://api.hh.ru/resumes/mine", headers=headers)
print(f"Status: {r.status_code}")
print(r.text[:500])
print()

# 3. Проверяем /negotiations (GET — список откликов)
print("=== GET /negotiations ===")
r = requests.get("https://api.hh.ru/negotiations", headers=headers)
print(f"Status: {r.status_code}")
print(r.text[:500])
