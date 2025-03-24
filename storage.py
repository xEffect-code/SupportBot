import random
import json
import os

FILENAME = "aliases.json"
user_map = {}
reverse_map = {}

def load_aliases():
    global user_map, reverse_map
    if os.path.exists(FILENAME):
        try:
            with open(FILENAME, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:  # если файл не пустой
                    data = json.loads(content)
                    user_map = data.get("user_map", {})
                    reverse_map = data.get("reverse_map", {})
        except Exception as e:
            print(f"⚠️ Ошибка при чтении {FILENAME}: {e}")
            user_map = {}
            reverse_map = {}

def save_aliases():
    with open(FILENAME, "w", encoding="utf-8") as f:
        json.dump({"user_map": user_map, "reverse_map": reverse_map}, f, ensure_ascii=False, indent=2)

def get_or_create_alias(user_id):
    load_aliases()
    user_id = str(user_id)
    if user_id not in user_map:
        alias = f"Пользователь #{random.randint(1000, 9999)}"
        while alias in reverse_map:
            alias = f"Пользователь #{random.randint(1000, 9999)}"
        user_map[user_id] = alias
        reverse_map[alias] = user_id
        save_aliases()
    return user_map[user_id]

def get_user_by_alias(alias):
    load_aliases()
    return reverse_map.get(alias)
