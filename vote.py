import asyncio
import json
import os
import random
import time
import logging
from dataclasses import asdict, is_dataclass, fields
from typing import Any, Dict, get_type_hints
from browserforge.fingerprints import Fingerprint, Screen
from camoufox.async_api import AsyncCamoufox
from geoip2 import database
from geoip2.errors import AddressNotFoundError
import pytz
import hashlib
from dataclasses import fields
from emunium import EmuniumPlaywright



logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler('reddit_stealth.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def dict_to_dataclass(cls: type, d: Dict[str, Any]) -> Any:
    if not is_dataclass(cls) or not isinstance(d, dict):
        return d

    type_hints = get_type_hints(cls)
    field_values = {}
    for field in fields(cls):
        if field.name in d:
            field_type = type_hints.get(field.name, Any)
            field_values[field.name] = dict_to_dataclass(field_type, d[field.name])
    return cls(**field_values)

class HumanBehavior:
    @staticmethod
    async def random_delay(min_ms: int, max_ms: int):
        logger.info(f"Sleeping randomly between {min_ms} and {max_ms} milliseconds")
        await asyncio.sleep(random.uniform(min_ms/1000, max_ms/1000))

    @staticmethod
    # async def human_scroll(page):
    #     logger.info("Starting human-like scrolling")

    #     # Estimate page height to avoid scrolling beyond content
    #     page_height = await page.evaluate("document.body.scrollHeight")
    #     viewport_height = await page.evaluate("window.innerHeight")
    #     max_scroll = page_height - viewport_height
    #     current_position = await page.evaluate("window.scrollY")
    #     logger.info(f"Page height: {page_height}, Viewport height: {viewport_height}, Max scroll: {max_scroll}")

    #     # Define scroll types: small (reading), medium (skimming), large (jumping)
    #     scroll_types = [
    #         {"distance": random.randint(100, 300), "speed": random.uniform(0.3, 0.6), "pause": (500, 1500)},  # Small, detailed reading
    #         {"distance": random.randint(400, 800), "speed": random.uniform(0.5, 1.0), "pause": (300, 1000)},  # Medium, skimming
    #         {"distance": random.randint(900, 1500), "speed": random.uniform(0.8, 1.5), "pause": (200, 800)},   # Large, jumping
    #     ]

    #     # Occasionally reverse scroll to mimic revisiting content
    #     reverse_chance = 0.2
    #     # Chance to pause longer at "interesting" elements
    #     content_pause_chance = 0.3

    #     # Perform 3-7 scroll actions to simulate natural browsing
    #     num_scrolls = random.randint(3, 7)
    #     for i in range(num_scrolls):
    #         # Prevent scrolling beyond page bounds
    #         if current_position >= max_scroll * 0.9:
    #             logger.info("Near page bottom, reversing or stopping")
    #             scroll_direction = -1
    #             scroll = random.choice(scroll_types[:2])  # Use smaller scrolls near bottom
    #         elif current_position <= 100:
    #             logger.info("Near page top, scrolling down")
    #             scroll_direction = 1
    #             scroll = random.choice(scroll_types)
    #         else:
    #             scroll_direction = -1 if random.random() < reverse_chance else 1
    #             scroll = random.choice(scroll_types)

    #         # Calculate scroll distance
    #         distance = scroll["distance"] * scroll_direction
    #         speed = scroll["speed"]
    #         pause_min, pause_max = scroll["pause"]

    #         # Smooth scrolling with multiple small steps
    #         steps = random.randint(3, 6)  # Break scroll into smaller steps for smoothness
    #         step_distance = distance / steps
    #         for _ in range(steps):
    #             await page.mouse.wheel(delta_x=0, delta_y=step_distance)
    #             await asyncio.sleep(speed / steps)  # Spread out the scroll duration

    #         current_position += distance
    #         current_position = max(0, min(current_position, max_scroll))  # Clamp to valid range
    #         logger.info(f"Scrolled {distance} pixels, new position: {current_position}")

    #         # Simulate pausing at interesting content (e.g., posts, images)
    #         if random.random() < content_pause_chance:
    #             logger.info("Pausing at potentially interesting content")
    #             # Query for elements like posts or images to simulate attention
    #             elements = await page.query_selector_all('article, img, h1, h2, h3')
    #             if elements:
    #                 element = random.choice(elements)
    #                 await page.evaluate("(element) => element.scrollIntoView({ behavior: 'smooth', block: 'center' })", element)
    #                 await HumanBehavior.random_delay(1000, 3000)  # Longer pause for "reading"
    #             else:
    #                 await HumanBehavior.random_delay(pause_min, pause_max)
    #         else:
    #             await HumanBehavior.random_delay(pause_min, pause_max)

    #     logger.info("Finished human-like scrolling")

    @staticmethod
    async def human_scroll(page):
        """Perform human-like scrolling using Lenis smooth scroll library."""
        logger.info("Starting human-like scrolling with Lenis")

        # Load Lenis from CDN
        await page.add_script_tag(url="https://cdn.jsdelivr.net/npm/lenis@1/dist/lenis.min.js")

        # Initialize Lenis with natural scrolling settings
        await page.evaluate("""
            const lenis = new Lenis({
                duration: 1.2,  // Duration in seconds for smooth scroll
                easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),  // Ease-out curve
                smooth: true,   // Enable smooth scrolling
                direction: 'vertical',
                infinite: false,
            });

            // Animation loop for Lenis
            function raf(time) {
                lenis.raf(time);
                requestAnimationFrame(raf);
            }
            requestAnimationFrame(raf);
        """)

        # Get page scroll dimensions
        page_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = await page.evaluate("window.innerHeight")
        max_scroll = page_height - viewport_height
        current_position = await page.evaluate("window.scrollY")
        logger.info(f"Page height: {page_height}, Viewport height: {viewport_height}, Max scroll: {max_scroll}")

        # Define scroll profiles for variety
        scroll_profiles = [
            {"name": "slow_read", "distance": (100, 300), "duration": (1.5, 2.5), "pause_chance": 0.6},
            {"name": "quick_skim", "distance": (400, 800), "duration": (0.8, 1.5), "pause_chance": 0.3},
        ]
        profile = random.choice(scroll_profiles)
        logger.info(f"Using scroll profile: {profile['name']}")

        # Perform random number of scrolls
        for _ in range(random.randint(3, 6)):
            # Decide scroll direction
            scroll_direction = 1 if current_position < max_scroll * 0.9 else -1
            distance = random.randint(*profile["distance"]) * scroll_direction
            duration = random.uniform(*profile["duration"])

            # Scroll with Lenis
            target_position = max(0, min(current_position + distance, max_scroll))
            await page.evaluate(f"""
                lenis.scrollTo({target_position}, {{
                    duration: {duration},
                    easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t))
                }});
            """)
            await asyncio.sleep(duration + 0.2)  # Wait for scroll to finish
            current_position = target_position
            logger.info(f"Scrolled to: {current_position}")

            # Pause at content with Lenis
            if random.random() < profile["pause_chance"]:
                elements = await page.query_selector_all('article, img, video, h1, h2')
                if elements:
                    element = random.choice(elements)
                    element_type = await element.evaluate("el => el.tagName.toLowerCase()")
                    logger.info(f"Pausing at: {element_type}")
                    await page.evaluate("""
                        const el = arguments[0];
                        lenis.scrollTo(el.getBoundingClientRect().top + window.scrollY, {
                            duration: 1.0
                        });
                    """, element)
                    pause_ms = 2000 if element_type in ["img", "video"] else 1000
                    await HumanBehavior.random_delay(pause_ms, pause_ms + 1000)
                else:
                    await HumanBehavior.random_delay(500, 1500)
            else:
                await HumanBehavior.random_delay(500, 1500)

        logger.info("Completed human-like scrolling")
        
    @staticmethod
    async def random_mouse_movement(emunium, page):
        # Select elements like links, buttons, or images from the page
        elements = await page.query_selector_all('a, button, img')  # You can adjust this selector
        if not elements:
            logger.warning("No elements found for mouse movement")
            return

        # Pick 2-3 random elements
        num_elements = 1 # Choose between 2 or 3 elements
        selected_elements = random.sample(elements, num_elements)

        # Move the mouse to each element randomly
        for element in selected_elements:
            logger.info(f"Moving mouse to element: {await element.evaluate('el => el.outerHTML')}")
            await emunium.scroll_to(element)
            await emunium.move_to(element)  # Move to the element with human-like movement
            await HumanBehavior.random_delay(500, 1000)  # Add a small random delay (assuming this method exists)

        logger.info("Finished random mouse movement")


    @staticmethod
    async def human_click(emunium, element):
        logger.info("Starting Human Like Click")
        await emunium.click_at(element)
        logger.info("Finished human-like click")


class StealthEnhancer:
    def __init__(self, account_id):
        self.account_id = account_id
        self.profiles_dir = "profiles"
        self.fingerprint = self.load_fingerprint()



    def load_fingerprint(self):
        # Construct the file path
        fingerprint_file = os.path.join(
            self.profiles_dir, str(self.account_id),
            f"fingerprint_{self.account_id}.json"
        )
        print(f"Loading fingerprint from {fingerprint_file}")
        
        # Load the JSON file
        with open(fingerprint_file, "r") as f:
            data = json.load(f)
        
        try:
            fingerprint = dict_to_dataclass(Fingerprint, data["fingerprint"])
            print("Successfully created Fingerprint instance")
            return fingerprint
        except TypeError as e:
            print(f"Error creating Fingerprint instance: {e}")
            raise

async def upvote_post(account_id: int, post_url: str, proxy_config: Dict[str, Any] = None):
    stealth = StealthEnhancer(account_id)
    profiles_dir = "profiles"
    
    cookies_file = os.path.join(profiles_dir, str(account_id), f"cookies_{account_id}.json")
    logger.info(f"Loading cookies from {cookies_file}")
    with open(cookies_file, "r") as f:
        cookies = json.load(f)
    logger.info("Cookies Loaded successfully!")
    print("Configuring")
    config = {
        "fingerprint": stealth.fingerprint,
        "os": "windows",
        "screen": Screen(max_width=1280, max_height=720),
        "geoip": True,
        "humanize": True,
        "i_know_what_im_doing": True
    }
    print("Configured")
    if proxy_config:
        config["proxy"] = proxy_config
        logger.info(f"Using proxy configuration: {proxy_config}")

    async with AsyncCamoufox(**config) as browser:
        try:
            page = await browser.new_page()
            emunium = EmuniumPlaywright(page)

            await page.context.add_cookies(cookies)
            logger.info(f"Added cookies for account {account_id}")

            await page.set_extra_http_headers({
                'Referer': random.choice([
                    'https://www.google.com/',
                    'https://x.com/',
                    'https://www.reddit.com/'
                ])
            })

            await HumanBehavior.random_delay(1000, 3000)
            logger.info(f"Navigating to Reddit homepage for account {account_id}")
            await page.goto('https://www.reddit.com/', wait_until='domcontentloaded')
            await HumanBehavior.human_scroll(page)
            await HumanBehavior.random_delay(2000, 5000)
            
            logger.info(f"Navigating to post URL: {post_url} for account {account_id}")
            await page.goto(post_url)
            await HumanBehavior.random_delay(4000,8000)
            # num_scrolls = random.randint(3, 6)
            # for _ in range(num_scrolls):
            #     await HumanBehavior.human_scroll(page)
            #     await HumanBehavior.random_delay(500, 3000)
            
            
            upvote_selector = 'button:has(svg[icon-name="upvote-outline"])'
            print(upvote_selector)
            
            #await HumanBehavior.random_mouse_movement(emunium,page)
            print("finding button")
            button = await page.wait_for_selector(upvote_selector, timeout=15000)
            
            if button is None:
                logger.error("Could not find upvote button")
                raise RuntimeError("Could not find upvote button")
            else:
                await emunium.scroll_to(button)
                #await emunium.move_to(button)
                logger.info("Found upvote button")
                print(button)

            aria_pressed = await button.get_attribute('aria-pressed')
  
            if aria_pressed == "false":
                print("Post is not upvoted. Upvoting now...")
                # await HumanBehavior.human_click(emunium, button)
                await button.click()
                await HumanBehavior.random_delay(2000, 5000)

                upvote_selector2 = 'button:has(svg[icon-name="upvote-fill"])'
                button2 = await page.wait_for_selector(upvote_selector2, timeout=15000)
                aria_pressed2 = await button2.get_attribute('aria-pressed')

                if aria_pressed2 == "true":
                    logger.info(f"Successfully upvoted post with account {account_id}")
                else:
                    logger.warning("Upvote validation failed")
            else:
                print("Post is already upvoted.")
            
            #await HumanBehavior.random_mouse_movement(emunium, page)
            await asyncio.sleep(random.uniform(2, 5))
            
            random_pages = [
                'https://www.reddit.com/',
                'https://www.reddit.com/r/popular/',
                'https://www.reddit.com/r/AskReddit/',
                'https://www.reddit.com/r/funny/',
                'https://www.reddit.com/r/science/'
            ]
            random_page = random.choice(random_pages)
            logger.info(f"Navigating to random page {random_page} after upvote")
            await page.goto(random_page)
            await HumanBehavior.random_delay(1000,5000)
        except Exception as e:
            logger.error(f"Error during upvote process: {str(e)}")
            raise
        finally:
            print("Closing")
            await page.close()

async def orchestrate_upvotes(post_url: str, account_ids: list, proxies: dict[str, Any] = None):
    proxies = proxies or {} 
    tasks = []
    for account_id in account_ids:
        task = asyncio.create_task(
            upvote_post(account_id, post_url),
            name=f"Account_{account_id}"
        )
        tasks.append(task)
        logger.info(f"Scheduled upvote task for account {account_id}")
        await asyncio.sleep(random.randint(300, 900))
    
    logger.info("Awaiting completion of all upvote tasks")
    await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    target_url = "https://www.reddit.com/r/AppearanceAdvice/comments/1ki1ooo/what_do_you_think_of_my_face/"
    account_ids = [1]
    # proxies = {
    #     1: 'http://proxy1.example.com:8080',
    #     2: 'http://proxy2.example.com:8080',
    #     3: 'http://proxy3.example.com:8080',
    #     4: 'http://proxy4.example.com:8080',
    #     5: 'http://proxy5.example.com:8080'
    # }
    
    try:
        asyncio.run(orchestrate_upvotes(target_url, account_ids))
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    finally:
        logger.info("Upvoting session completed")
