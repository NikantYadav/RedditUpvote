import customtkinter as ctk
import asyncio
import os
import json
from threading import Thread
from account import dict_to_dataclass
from browserforge.fingerprints import FingerprintGenerator, Fingerprint, Screen
from camoufox.async_api import AsyncCamoufox
from dataclasses import asdict
from typing import Any, Dict

desired_folder = "profiles"
os.makedirs(desired_folder, exist_ok=True)

# GUI init
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")
app = ctk.CTk()
app.title("Reddit Proxy Runner")
app.geometry("500x600")

# Text logger widget
log_output = ctk.CTkTextbox(app, height=200, wrap="word")
log_output.pack(pady=10, padx=20)

def clear_fields_and_log():
    entry_account_id.delete(0, "end")
    entry_proxy_server.delete(0, "end")
    entry_proxy_username.delete(0, "end")
    entry_proxy_password.delete(0, "end")
    entry_reddit_username.delete(0, "end")
    log_output.delete("1.0", "end")

def log(message: str):
    log_output.insert("end", message + "\n")
    log_output.see("end")

manual_completion_event = None  # will be set later

def exit_and_save():
    if manual_completion_event:
        manual_completion_event.set()

async def run_async(account_id: int, reddit_username: str, proxy_config: Dict[str, Any]):
    global manual_completion_event
    fingerprint_file = os.path.join(desired_folder, str(account_id), f"fingerprint_{account_id}.json")

    # Load or create fingerprint
    if os.path.exists(fingerprint_file):
        with open(fingerprint_file, "r") as f:
            fingerprint_dict = json.load(f)
        fingerprint = dict_to_dataclass(Fingerprint, fingerprint_dict["fingerprint"])
        log(f"✅ Loaded fingerprint for account {account_id}")
    else:
        fg = FingerprintGenerator(browser='firefox')
        fingerprint = fg.generate()
        fingerprint_dict = asdict(fingerprint)
        if 'navigator' in fingerprint_dict:
            fingerprint_dict['navigator']['globalPrivacyControl'] = \
                fingerprint_dict['navigator']['extraProperties'].pop('globalPrivacyControl', False)
        fingerprint_data = {"id": account_id, "fingerprint": fingerprint_dict}
        os.makedirs(os.path.dirname(fingerprint_file), exist_ok=True)
        with open(fingerprint_file, "w") as f:
            json.dump(fingerprint_data, f, indent=2)
        log(f"✅ Saved new fingerprint for account {account_id}")

    # Setup camoufox config
    camoufox_config = {
        "fingerprint": fingerprint,
        "os": "windows",
        "screen": Screen(max_width=1280, max_height=720),
        "fonts": ["Arial", "Helvetica", "Times New Roman"],
        "geoip": True,
        "i_know_what_im_doing": True
    }
    if proxy_config:
        camoufox_config["proxy"] = proxy_config

    manual_completion_event = asyncio.Event()
    async with AsyncCamoufox(**camoufox_config) as browser:
        page = await browser.new_page()
        cookies_file = os.path.join(desired_folder, str(account_id), f"cookies_{account_id}.json")
        if os.path.exists(cookies_file):
            with open(cookies_file, "r") as f:
                cookies = json.load(f)
            await page.context.add_cookies(cookies)
            log(f"✅ Loaded cookies for account {account_id}")
        else:
            try:
                await page.goto("https://www.reddit.com", timeout=60000, wait_until="networkidle")
                log("✅ Loaded Reddit")
                log("========== INSTRUCTIONS ==========")
                log("1. Log in to Reddit in the opened browser")
                log("2. Return to this window and click 'Exit & Save'")
                log("===================================")
                await manual_completion_event.wait()

                # Save cookies
                cookies = await page.context.cookies()
                with open(cookies_file, "w") as f:
                    json.dump(cookies, f, indent=2)
                log(f"✅ Cookies saved to {cookies_file}")

                # Save account info
                accounts_file = os.path.join(desired_folder, "accounts.json")
                if os.path.exists(accounts_file):
                    with open(accounts_file, "r") as f:
                        accounts_data = json.load(f)
                else:
                    accounts_data = {}

                accounts_data[str(account_id)] = {
                    "account_id": account_id,
                    "reddit_username": reddit_username,
                    "proxy": proxy_config or {}
                }
                with open(accounts_file, "w") as f:
                    json.dump(accounts_data, f, indent=2)
                log(f"✅ Account info updated")
                log("✅ Task complete. Clearing fields...")
                app.after(500, clear_fields_and_log)
            except Exception as e:
                log(f"❌ Error: {e}")
            finally:
                await browser.close()

def on_run_click():
    account_id = entry_account_id.get().strip()
    proxy_server = entry_proxy_server.get().strip()
    proxy_username = entry_proxy_username.get().strip()
    proxy_password = entry_proxy_password.get().strip()
    reddit_username = entry_reddit_username.get().strip()

    if not (account_id and reddit_username):
        log("❌ Account ID and Reddit Username are required.")
        return

    proxy_config = {
        "server": proxy_server,
        "username": proxy_username,
        "password": proxy_password
    } if proxy_server else None

    def start_asyncio_loop():
        asyncio.run(run_async(int(account_id), reddit_username, proxy_config))

    Thread(target=start_asyncio_loop).start()

# Inputs
entry_account_id = ctk.CTkEntry(app, placeholder_text="Account ID")
entry_account_id.pack(pady=5, padx=20)

entry_proxy_server = ctk.CTkEntry(app, placeholder_text="Proxy Server (IP:Port)")
entry_proxy_server.pack(pady=5, padx=20)

entry_proxy_username = ctk.CTkEntry(app, placeholder_text="Proxy Username")
entry_proxy_username.pack(pady=5, padx=20)

entry_proxy_password = ctk.CTkEntry(app, placeholder_text="Proxy Password", show="*")
entry_proxy_password.pack(pady=5, padx=20)

entry_reddit_username = ctk.CTkEntry(app, placeholder_text="Reddit Username")
entry_reddit_username.pack(pady=5, padx=20)

# Buttons
run_button = ctk.CTkButton(app, text="Run", command=on_run_click)
run_button.pack(pady=10)

exit_button = ctk.CTkButton(app, text="Exit & Save", command=exit_and_save)
exit_button.pack(pady=5)

app.mainloop()
