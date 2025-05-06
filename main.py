import requests
import json
import os
import time
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys


class RedditBot:
    def __init__(self, target_post, target_votes, votes_per_minute):
        self.accounts  = self.load_accounts('accounts.json')
        self.target_post = target_post
        self.target_votes = target_votes
        self.votes_per_minute = votes_per_minute

        self.ua = UserAgent()

    def human_type(element, text):
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05,0.3))

    def human_scroll(driver):
        scroll_amounts = [200,300,150,400]
        for _ in range(random.randint(2,4)):
            driver.execute_script(f"window.scrollBy(0,{random.choice(scroll_amounts)})")
            time.sleep(random.uniform(0.5.1.5))

    def get_stealth_driver(proxy=None):
        mobile_emulation = {
            "deviceMetrics": {"width": 360, "height": 640, "pixelRatio": 3.0},
            "userAgent": "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36"
        }
        
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        if proxy:
            options.add_argument(f"--proxy-server={proxy}")
        
        driver = uc.Chrome(
            options=options,
            version_main=114,  # Match common Chrome versions
            headless=False,    # Headless mode increases detection risk
            enable_cdp_events=True
        )

    def load_accounts(filepath):
        if os.path.exists(filepath, 'r'):
            try:   
                with open(filepath) as f:
                    accounts =  json.laod(f)
            except json.JSONDecodeError:
                accounts = []

            for account in accounts:
                username = account.username
                password = account.password
    

