"""
Этот скрипт запускается ОДИН РАЗ для получения токенов hh.ru.
Полученные токены нужно сохранить как секреты в GitHub.

Запуск:
    pip install requests
    python get_token.py
"""

import webbrowser
import requests

print("=" * 60)
print("  Получение токенов hh.ru (запускается один раз)")
print("=" * 60)
print()

client_id = input("Введите Client ID вашего приложения hh.ru: ").strip()
client_secret = input("Введите Client Secret вашего приложения hh.ru: ").strip()

auth_url = (
    f"https://hh.ru/oauth/authorize"
    f"?response_type=code"
    f"&client_id={client_id}"
)

print()
print("Открываю браузер для авторизации...")
print(f"Если браузер не открылся, перейдите по ссылке вручную:")
print(f"\n  {auth_url}\n")
webbrowser.open(auth_url)

print("После авторизации вас перенаправит на страницу с ошибкой — это нормально.")
print("Скопируйте значение параметра 'code' из адресной строки браузера.")
print("Пример: https://ваш-сайт.ru/?code=ABCDEF123  <- вот это нужно скопировать")
print()

code = input("Вставьте код из адресной строки: ").strip()

print()
print("Обмениваю код на токены...")

response = requests.post(
    "https://hh.ru/oauth/token",
    data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
    },
)

if response.status_code != 200:
    print(f"Ошибка: {response.status_code}")
    print(response.text)
    exit(1)

data = response.json()
access_token = data["access_token"]
refresh_token = data["refresh_token"]

print()
print("=" * 60)
print("  Токены получены! Сохраните их как секреты GitHub:")
print("=" * 60)
print()
print(f"HH_CLIENT_ID      = {client_id}")
print(f"HH_CLIENT_SECRET  = {client_secret}")
print(f"HH_ACCESS_TOKEN   = {access_token}")
print(f"HH_REFRESH_TOKEN  = {refresh_token}")
print()
print("Инструкция по добавлению секретов:")
print("  1. Откройте ваш репозиторий на GitHub")
print("  2. Settings → Secrets and variables → Actions")
print("  3. Нажмите 'New repository secret' и добавьте каждый из четырёх секретов выше")
