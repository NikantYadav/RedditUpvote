import asyncio
import random
import json
import os
from faker import Faker
from pyvirtualdisplay import Display
from curl_cffi import Curl
from nodriver import start
from ghost_cursor import generate_moves
from bablosoft import PerfectCanvas


def human_type(element, text):
    """Simulates human typing with variable speed"""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.3))

def human_scroll(driver):
    """Generates human-like scroll patterns"""
    scroll_amounts = [random.randint(100, 500) for _ in range(4)]
    for _ in range(random.randint(2,4)):
        driver.execute_script(f"window.scrollBy(0, {random.choice(scroll_amounts)})")
        time.sleep(random.uniform(0.5,1.5))
