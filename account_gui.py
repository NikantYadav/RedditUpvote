import customtkinter as ctk
import asyncio
import os
import json
from threading import Thread, Lock
from account import dict_to_dataclass
from browserforge.fingerprints import FingerprintGenerator, Fingerprint, Screen
from camoufox.async_api import AsyncCamoufox
from dataclasses import asdict
from typing import Any, Dict

# Reddit-inspired color scheme
REDDIT_COLORS = {
    "primary": "#1A1A1B",       # Dark background
    "secondary": "#272729",     # Secondary background
    "accent": "#FF4500",        # Reddit orange
    "text": "#D7DADC",          # Light text
    "border": "#343536"         # Border color
}

desired_folder = "profiles"
os.makedirs(desired_folder, exist_ok=True)

# Configure appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")  # Use dark-blue as base theme

app = ctk.CTk()
app.title("Reddit Proxy Runner")
app.geometry("800x700")
app.configure(fg_color=REDDIT_COLORS["primary"])

# Font configuration
bold_font = ctk.CTkFont(family="Arial", size=14, weight="bold")
title_font = ctk.CTkFont(family="Arial", size=24, weight="bold")


# Global variables for cross-thread communication
current_loop = None
current_event = None
loop_lock = Lock()

# Main container
main_frame = ctk.CTkFrame(app, fg_color="transparent")
main_frame.pack(pady=20, padx=40, fill="both", expand=True)

# Header
ctk.CTkLabel(
    main_frame,
    text="REDDIT PROXY RUNNER",
    font=title_font,
    text_color=REDDIT_COLORS["accent"]
).pack(pady=(0, 20))

# Input Section
input_frame = ctk.CTkFrame(
    main_frame,
    fg_color=REDDIT_COLORS["secondary"],
    corner_radius=8,
    border_color=REDDIT_COLORS["border"],
    border_width=1
)
input_frame.pack(fill="x", pady=(0, 20))

# Form fields
form_elements = [
    ("Account ID", "account_id"),
    ("Proxy Server (http://IP:Port)", "proxy_server"),
    ("Proxy Username", "proxy_username"),
    ("Proxy Password", "proxy_password"),
    ("Reddit Username", "reddit_username")
]

entries = {}
for idx, (label, name) in enumerate(form_elements):
    ctk.CTkLabel(
        input_frame,
        text=label + ":",
        font=bold_font,
        text_color=REDDIT_COLORS["text"]
    ).grid(row=idx, column=0, padx=20, pady=10, sticky="w")
    
    entry = ctk.CTkEntry(
        input_frame,
        width=500,
        font=bold_font,
        corner_radius=6,
        border_color=REDDIT_COLORS["border"],
        fg_color=REDDIT_COLORS["primary"],
        text_color=REDDIT_COLORS["text"],
        show="*" if "password" in name else ""
    )
    entry.grid(row=idx, column=1, padx=20, pady=10)
    entries[name] = entry

# Button Section
button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
button_frame.pack(pady=20)

run_button = ctk.CTkButton(
    button_frame,
    text="🚀 RUN",
    command=lambda: on_run_click(),
    width=120,
    height=40,
    font=bold_font,
    corner_radius=8,
    fg_color=REDDIT_COLORS["accent"],
    hover_color="#FF5714",
    text_color=REDDIT_COLORS["text"]
)
run_button.pack(side="left", padx=10)

exit_button = ctk.CTkButton(
    button_frame,
    text="🔒 EXIT & SAVE",
    command=lambda: exit_and_save(),
    width=120,
    height=40,
    font=bold_font,
    corner_radius=8,
    fg_color="#4A4A4A",
    hover_color="#5A5A5A",
    text_color=REDDIT_COLORS["text"]
)
exit_button.pack(side="left", padx=10)

# Log Section
log_output = ctk.CTkTextbox(
    main_frame,
    wrap="word",
    fg_color=REDDIT_COLORS["secondary"],
    text_color=REDDIT_COLORS["text"],
    font=ctk.CTkFont(family="Consolas", size=12),
    corner_radius=8,
    height=200
)
log_output.pack(fill="both", expand=True, pady=(10, 0))

def clear_fields_and_log():
    for entry in entries.values():
        entry.delete(0, "end")
    log_output.delete("1.0", "end")

def log(message: str):
    log_output.insert("end", message + "\n")
    log_output.see("end")

manual_completion_event = None  # will be set later

def exit_and_save():
    log("Exit button clicked")
    global current_loop, current_event
    with loop_lock:
        if current_event and current_loop:
            current_loop.call_soon_threadsafe(current_event.set)
            log("✓ Exit signal sent to browser instance")
        else:
            log("❌ No active session to exit and save")


async def run_async(account_id: int, reddit_username: str, proxy_config: Dict[str, Any]):
    global current_loop, current_event
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

    #manual_completion_event = asyncio.Event()

    with loop_lock:
        current_event = asyncio.Event()
        current_loop = asyncio.get_running_loop()

    try:
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
                    await current_event.wait()

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
    except Exception as e:
        log(f"Critical Error : {str(e)}")
    finally:
        with loop_lock:
            current_loop = None
            current_event = None


def on_run_click():
    account_id = entries["account_id"].get().strip()
    proxy_server = entries["proxy_server"].get().strip()
    proxy_username = entries["proxy_username"].get().strip()
    proxy_password = entries["proxy_password"].get().strip()
    reddit_username = entries["reddit_username"].get().strip()

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

app.mainloop()

