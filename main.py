from flask import Flask
from threading import Thread
import requests
import time
import os
from datetime import datetime
import json

app = Flask('')

WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')
API_URL = "https://molerapi.moler.cloud/mods/"
CHECK_INTERVAL = 60  # seconds
START_DATE_STR = "2025-06-07"
START_DATE = datetime.strptime(START_DATE_STR, "%Y-%m-%d").date()

seen_mod_ids = set()  # In-memory cache only

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

@app.route('/')
def home():
    return "✅ I'm alive! Watching for new mods..."

def fetch_mods():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log(f"[ERROR] Failed to fetch mods: {e}")
        return []

def send_discord_notification(mod):
    title = mod.get("name") or "Unknown Title"
    category = mod.get("category") or "Unknown"
    version = mod.get("version") or "Unknown"
    access = mod.get("access") or "Unknown"
    created_at = mod.get("created_at") or ""
    image_url = mod.get("image_url") or ""
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
        "color": 0x9b59b6  # Purple
    }

    if image_url.startswith("http"):
        embed["image"] = {"url": image_url}

    data = {
        "content": "<@&1374389568513769503>",
        "embeds": [embed],
        "allowed_mentions": {
            "parse": ["roles"],
            "roles": ["1374389568513769503"]
        }
    }

    while True:
        try:
            response = requests.post(WEBHOOK_URL, json=data)
            if response.status_code == 429:
                retry_after = response.json().get("retry_after", 1000) / 1000
                log(f"[RATE LIMITED] Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            log(f"[SENT] Webhook for: {title}")
            break
        except requests.exceptions.RequestException as e:
            log(f"[ERROR] Webhook failed: {e}")
            log(f"[WEBHOOK PAYLOAD] {json.dumps(data, indent=2)}")
            time.sleep(5)

def check_for_new_mods():
    log("🔁 Mod watcher started...")

    while True:
        mods = fetch_mods()
        log(f"[INFO] Checking {len(mods)} mods for new entries since {START_DATE}")
        new_mods = []

        for mod in mods:
            mod_id = mod.get("id")
            created_str = mod.get("created_at")

            if not mod_id or not created_str:
                continue

            try:
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                created_date = created_dt.date()
            except Exception as e:
                log(f"[ERROR] Date parsing error: {e}")
                continue

            log(f"[DEBUG] Mod: {mod.get('name')} | Created: {created_date} | ID: {mod_id}")

            if mod_id not in seen_mod_ids and created_date >= START_DATE:
                new_mods.append(mod)
                seen_mod_ids.add(mod_id)

        if new_mods:
            log(f"[FOUND] {len(new_mods)} new mod(s).")
            for mod in new_mods:
                send_discord_notification(mod)
        else:
            log("✅ No new mods found.")

        time.sleep(CHECK_INTERVAL)

def run_background_tasks():
    Thread(target=check_for_new_mods, daemon=True).start()

if __name__ == '__main__':
    log("[BOOT] App started fresh — in-memory cache only.")
    run_background_tasks()
    app.run(host='0.0.0.0', port=8080)
