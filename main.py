from flask import Flask
from threading import Thread
import requests
import time
import json
import os
from datetime import datetime

app = Flask('')

WEBHOOK_URL = os.environ['WEBHOOK_URL']
API_URL = "https://molerapi.moler.cloud/mods/"
CHECK_INTERVAL = 60  # seconds
CACHE_FILE = "mod_cache.json"

START_DATE_STR = "2025-06-07"
START_DATE = datetime.strptime(START_DATE_STR, "%Y-%m-%d").date()

@app.route('/')
def home():
    return "✅ I'm alive! Watching for new mods..."

def load_cached_mods():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return []

def save_cached_mods(mods):
    with open(CACHE_FILE, "w") as f:
        json.dump(mods, f)

def fetch_mods():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch mods: {e}")
        return []

def send_discord_notification(mod):
    title = mod.get("name", "Untitled Mod")  
    category = mod.get("category", "Unknown")
    version = mod.get("version", "Unknown")
    access = mod.get("access_type", "Unknown")
    created_at = mod.get("created_at", "")
    image_url = mod.get("image_url", "")

    created_date_str = created_at.split("T")[0] if "T" in created_at else created_at

    description = (
        f"**Category:** {category}\n"
        f"**Version:** {version}\n"
        f"**Access:** {access}\n"
        f"**Uploaded:** {created_date_str}"
    )

    embed = {
        "title": f"🆕 New Mod: {title}",
        "description": description,
        "color": 3066993
    }

    if image_url:
        embed["image"] = {"url": image_url}

    data = {"username": "API Bot", "embeds": [embed]}

    try:
        response = requests.post(WEBHOOK_URL, json=data)
        response.raise_for_status()
        print(f"[SENT] Webhook for: {title}")
    except Exception as e:
        print(f"[ERROR] Webhook failed: {e}")

def check_for_new_mods():
    print("🔁 Mod watcher started...")
    cached_mods = load_cached_mods()
    cached_ids = {mod['id'] for mod in cached_mods if 'id' in mod}

    while True:
        mods = fetch_mods()
        new_mods = []

        for mod in mods:
            mod_id = mod.get('id')
            if not mod_id:
                continue

            created_str = mod.get('created_at')
            if not created_str:
                continue

            try:
                created_dt = datetime.fromisoformat(
                    created_str.replace("Z", "+00:00"))
                created_date = created_dt.date()
            except Exception:
                continue

            if mod_id not in cached_ids and created_date >= START_DATE:
                new_mods.append(mod)

        if new_mods:
            print(f"[FOUND] {len(new_mods)} new mod(s).")
            for mod in new_mods:
                send_discord_notification(mod)
                cached_ids.add(mod['id'])
                cached_mods.append(mod)
            save_cached_mods(cached_mods)
        else:
            print("✅ No new mods found.")

        time.sleep(CHECK_INTERVAL)

def run_background_tasks():
    t = Thread(target=check_for_new_mods)
    t.daemon = True
    t.start()

def run():
    run_background_tasks()
    app.run(host='0.0.0.0', port=8080)

run()
