"""
Скрипт автоматически поднимает все резюме на hh.ru.
Запускается через GitHub Actions каждые 4 часа.
"""

import os
import sys
import json
import base64
import requests
from nacl import encoding, public


HH_API = "https://api.hh.ru"
HH_TOKEN_URL = "https://hh.ru/oauth/token"


def get_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"Ошибка: переменная окружения {name} не задана.")
        sys.exit(1)
    return value


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    """Обновляет access_token используя refresh_token."""
    print("Обновляю access_token...")
    response = requests.post(
        HH_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    if response.status_code != 200:
        print(f"Не удалось обновить токен: {response.status_code} {response.text}")
        sys.exit(1)
    data = response.json()
    print("Токен успешно обновлён.")
    return data


def update_github_secret(repo: str, token: str, secret_name: str, secret_value: str):
    """Обновляет секрет в GitHub репозитории."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Получаем публичный ключ репозитория для шифрования секрета
    key_response = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
    )
    if key_response.status_code != 200:
        print(f"Не удалось получить ключ GitHub: {key_response.text}")
        return

    key_data = key_response.json()
    public_key = public.PublicKey(key_data["key"].encode(), encoding.Base64Encoder)
    sealed_box = public.SealedBox(public_key)
    encrypted = base64.b64encode(sealed_box.encrypt(secret_value.encode())).decode()

    put_response = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted, "key_id": key_data["key_id"]},
    )

    if put_response.status_code in (201, 204):
        print(f"Секрет {secret_name} обновлён в GitHub.")
    else:
        print(f"Не удалось обновить секрет {secret_name}: {put_response.text}")


def get_resumes(access_token: str) -> list:
    """Получает список резюме пользователя."""
    response = requests.get(
        f"{HH_API}/resumes/mine",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if response.status_code == 403:
        return None  # Токен устарел
    response.raise_for_status()
    return response.json().get("items", [])


def publish_resume(access_token: str, resume_id: str) -> bool:
    """Поднимает одно резюме. Возвращает False если токен устарел."""
    response = requests.post(
        f"{HH_API}/resumes/{resume_id}/publish",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if response.status_code == 403:
        return False  # Токен устарел
    if response.status_code == 429:
        print(f"  Резюме {resume_id}: слишком частое поднятие, пропускаем.")
        return True
    if response.status_code not in (200, 204):
        print(f"  Резюме {resume_id}: ошибка {response.status_code} {response.text}")
        return True
    return True


def main():
    client_id = get_env("HH_CLIENT_ID")
    client_secret = get_env("HH_CLIENT_SECRET")
    access_token = get_env("HH_ACCESS_TOKEN")
    refresh_token = get_env("HH_REFRESH_TOKEN")
    github_repo = os.environ.get("GITHUB_REPOSITORY", "")
    github_token = os.environ.get("GH_PAT", "")

    print("Получаю список резюме...")
    resumes = get_resumes(access_token)

    # Если токен устарел — обновляем
    if resumes is None:
        new_tokens = refresh_access_token(client_id, client_secret, refresh_token)
        access_token = new_tokens["access_token"]
        refresh_token = new_tokens["refresh_token"]

        # Сохраняем новые токены в GitHub Secrets
        if github_repo and github_token:
            update_github_secret(github_repo, github_token, "HH_ACCESS_TOKEN", access_token)
            update_github_secret(github_repo, github_token, "HH_REFRESH_TOKEN", refresh_token)
        else:
            print("Предупреждение: GH_PAT не задан, новые токены не сохранены в GitHub.")
            print("Добавьте GH_PAT в секреты GitHub для автоматического обновления токенов.")

        resumes = get_resumes(access_token)

    if not resumes:
        print("Резюме не найдены.")
        return

    print(f"Найдено резюме: {len(resumes)}")
    print()

    for resume in resumes:
        resume_id = resume["id"]
        title = resume.get("title", "Без названия")
        print(f"Поднимаю: «{title}» (id: {resume_id})")
        success = publish_resume(access_token, resume_id)
        if not success:
            print("Токен снова устарел. Проверьте настройки.")
            sys.exit(1)
        print(f"  ✓ Поднято успешно")

    print()
    print("Готово! Все резюме подняты.")


if __name__ == "__main__":
    main()
