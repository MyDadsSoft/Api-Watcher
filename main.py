from flask import Flask
from threading import Thread
import requests
import time
import os
from datetime import datetime

app = Flask('')

WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')
API_URL = "https://molerapi.moler.cloud/mods/"
CHECK_INTERVAL = 60  # seconds
START_DATE_STR = "2025-06-07"
START_DATE = datetime.strptime(START_DATE_STR, "%Y-%m-%d").date()
seen_mod_ids = set()  # In-memory cache only


@app.route('/')
def home():
    return "✅ I'm alive! Watching for new mods..."


def fetch_mods():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        mods = response.json()
        print(f"[FETCHED] {len(mods)} mods fetched from API.")
        return mods
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
    mod_id = mod.get("id", "unknown")

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

    data = {
        "username": "API Bot",
        "embeds": [embed]
    }

    if not WEBHOOK_URL:
        print("[ERROR] WEBHOOK_URL is not set!")
        return

    while True:
        try:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ModWatcherBot/1.0"
            }
            response = requests.post(WEBHOOK_URL, json=data, headers=headers)
            if response.status_code == 429:
                retry_after = response.json().get("retry_after", 1000) / 1000
                print(f"[RATE LIMITED] Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            print(f"[SENT] Webhook for: {title} (ID: {mod_id})")
            break
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Webhook failed: {e}")
            break


def check_for_new_mods():
    print("🔁 Mod watcher started...")

    while True:
        mods = fetch_mods()
        print(f"[INFO] Checking {len(mods)} mods for new entries since {START_DATE}")
        new_mods = []

        for mod in mods:
            mod_id = mod.get('id')
            if not mod_id:
                continue

            created_str = mod.get('created_at')
            if not created_str:
                continue

            try:
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                created_date = created_dt.date()
            except Exception as e:
                print(f"[ERROR] Date parsing error: {e}")
                continue

            print(f"[DEBUG] Mod: {mod.get('name')} | Created: {created_date} | ID: {mod_id}")

            if mod_id not in seen_mod_ids and created_date >= START_DATE:
                new_mods.append(mod)
                seen_mod_ids.add(mod_id)

        if new_mods:
            print(f"[FOUND] {len(new_mods)} new mod(s).")
            for mod in new_mods:
                send_discord_notification(mod)
                time.sleep(1.5)  # Rate-limit-safe delay
        else:
            print("✅ No new mods found.")

        time.sleep(CHECK_INTERVAL)


def run_background_tasks():
    t = Thread(target=check_for_new_mods)
    t.daemon = True
    t.start()


if __name__ == '__main__':
    print("[BOOT] App started fresh — in-memory cache cleared.")
    run_background_tasks()
    app.run(host='0.0.0.0', port=8080)
