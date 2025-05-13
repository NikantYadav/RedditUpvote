import asyncio
import json
import os
import time
from datetime import datetime
from dataclasses import asdict, is_dataclass, fields
from typing import Any, Dict

from browserforge.fingerprints import FingerprintGenerator, Fingerprint, Screen
from camoufox.async_api import AsyncCamoufox
from typing import get_type_hints


user_data_dir = "camoufox_profile"
desired_folder = "profiles"

os.makedirs(user_data_dir, exist_ok=True)
os.makedirs(desired_folder, exist_ok=True)

# Helper function to recursively convert a dictionary to a dataclass

from dataclasses import is_dataclass, fields
from typing import get_type_hints, Any, Dict, Type

def dict_to_dataclass(cls: Type, d: Dict[str, Any]) -> Any:
    if not is_dataclass(cls) or not isinstance(d, dict):
        return d

    type_hints = get_type_hints(cls)
    field_values = {}
    for field in fields(cls):
        if field.name in d:
            value = d[field.name]
            field_type = type_hints.get(field.name, Any)
            if field_type == bool:
                # Handle string representations of booleans
                if isinstance(value, str):
                    if value.lower() in ('true', '1', 'yes'):
                        field_values[field.name] = True
                    elif value.lower() in ('false', '0', 'no'):
                        field_values[field.name] = False
                    else:
                        raise ValueError(f"Invalid boolean value for {field.name}: {value}")
                # Handle null (None) values
                elif value is None:
                    field_values[field.name] = False  # Default to False for null
                # If already a boolean, use it as is
                elif isinstance(value, bool):
                    field_values[field.name] = value
                else:
                    raise ValueError(f"Unexpected value for boolean field {field.name}: {value}")
            else:
                # Recursively handle other types
                field_values[field.name] = dict_to_dataclass(field_type, value)
    return cls(**field_values)

async def save_all_cookies(context, profile_num,filename=None):
    try:
        cookies = await context.cookies()
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cookies_{timestamp}.json"
        save_path = os.path.join(desired_folder,str(profile_num) ,filename)
        with open(save_path, 'w') as f:
            json.dump(cookies, f, indent=2)
        print(f"✅ Saved {len(cookies)} cookies to {save_path}")
        domains = sorted(set(cookie.get('domain', '') for cookie in cookies))
        domain_summary = os.path.join(desired_folder, str(profile_num) ,"cookie_domains.txt")
        with open(domain_summary, 'w') as f:
            for domain in domains:
                f.write(f"{domain}\n")
        print(f"✅ Saved {len(domains)} cookie domains to {domain_summary}")
        return save_path
    except Exception as e:
        print(f"❌ Error saving cookies: {e}")
        return None

async def run(account_id: int, proxy_config: Dict[str, Any] = None):
    # Step 1: Check if fingerprint exists for the account
    fingerprint_file = os.path.join(desired_folder, str(account_id),f"fingerprint_{account_id}.json")
    print(os.path.exists(fingerprint_file))
    if os.path.exists(fingerprint_file):
        # Load existing fingerprint
        with open(fingerprint_file, "r") as f:
            fingerprint_dict = json.load(f)
        
        
        
        fingerprint = dict_to_dataclass(Fingerprint, fingerprint_dict["fingerprint"])
        print(f"✅ Loaded fingerprint for account {account_id} from {fingerprint_file}")

    else:
        # Generate new fingerprint
        fg = FingerprintGenerator(browser='firefox')
        fingerprint = fg.generate()
        # Save fingerprint with account ID
        fingerprint_dict = asdict(fingerprint)
        if 'navigator' in fingerprint_dict:
            # Restructure the navigator data
            fingerprint_dict['navigator']['globalPrivacyControl'] = \
                fingerprint_dict['navigator']['extraProperties'].pop('globalPrivacyControl', False)

        fingerprint_data = {"id": account_id, "fingerprint": fingerprint_dict}
        print(fingerprint_data)

        fingerprint_dir = os.path.dirname(fingerprint_file)
        os.makedirs(fingerprint_dir, exist_ok=True)
        with open(fingerprint_file, "w") as f:
            json.dump(fingerprint_data, f, indent=2)
        print(f"✅ Saved new fingerprint for account {account_id} to {fingerprint_file}")

    # Step 2: Initialize Camoufox with fingerprint and proxy (if provided)
    camoufox_config = {
        "fingerprint": fingerprint,
        "os": "windows",
        "screen": Screen(max_width=1280, max_height=720),
        "fonts": ["Arial", "Helvetica", "Times New Roman"],
        "geoip": True,
        "i_know_what_im_doing":True
    }
    if proxy_config:
        camoufox_config["proxy"] = proxy_config

    manual_completion_event = asyncio.Event()
    async with AsyncCamoufox(**camoufox_config) as browser:
        page = await browser.new_page()
        # Load cookies if they exist
        cookies_file = os.path.join(desired_folder,str(account_id), f"cookies_{account_id}.json")
        if os.path.exists(cookies_file):
            with open(cookies_file, "r") as f:
                cookies = json.load(f)
            await page.context.add_cookies(cookies)
            print(f"✅ Loaded cookies for account {account_id} from {cookies_file}")
            print("Cookies already present!!")
        else:
            try:
                print("Navigating to Reddit...")
                await page.goto("https://www.reddit.com", timeout=60000, wait_until="networkidle")
                print("Successfully loaded Reddit")
                print("\n========== INSTRUCTIONS ==========")
                print("Browser is open. Please:")
                print("1. Log in or perform any actions needed")
                print("2. Type 'exit' and press Enter to save cookies and close the browser")
                print("===================================")
                async def wait_for_input():
                    while True:
                        inp = await asyncio.get_event_loop().run_in_executor(
                            None, input, "Enter 'exit' to save cookies and close the browser: "
                        )
                        if inp.strip().lower() == 'exit':
                            print("\nSaving cookies and closing browser...")


                            reddit_username = await asyncio.get_event_loop().run_in_executor(
                                None, input, "Enter your Reddit username: "
                            )

                            accounts_file = os.path.join(desired_folder, "accounts.json")

                            if os.path.exists(accounts_file):
                                with open(accounts_file, "r") as f:
                                    accounts_data = json.load(f)
                            else:
                                accounts_data = {}
                            
                            proxy_info = proxy_config if proxy_config else {}

                            accounts_data[str(account_id)] = {
                                "account_id": account_id,
                                "reddit_username": reddit_username,
                                "proxy": proxy_info
                            }

                            with open(accounts_file, "w") as f:
                                json.dump(accounts_data, f, indent=2)

                            print(f"✅ Updated accounts.json for account {account_id}")

                            manual_completion_event.set()
                            break
                asyncio.create_task(wait_for_input())
                await manual_completion_event.wait()
                # Step 3: Save cookies
                await save_all_cookies(page.context,account_id ,filename=f"cookies_{account_id}.json")
            except Exception as e:
                print(f"Error occurred: {e}")
                await save_all_cookies(page.context,account_id ,filename=f"cookies_{account_id}.json")
            finally:
                await browser.close()


def main():
    account_id = 8 # Example account ID
    proxy_config = {
        "server": "http://82.23.62.96:7849",  # Replace with actual proxy server
        "username": "pstvdsop",                   # Replace with actual username
        "password": "vic5dg5kklfd"                    # Replace with actual password
    }  
    asyncio.run(run(account_id, proxy_config))

if __name__ == "__main__":
    main()