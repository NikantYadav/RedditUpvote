import asyncio
import json
import os
import random
import logging
from dataclasses import asdict, is_dataclass, fields
from typing import Any, Dict, get_type_hints
from browserforge.fingerprints import Fingerprint, Screen
from camoufox.async_api import AsyncCamoufox
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for detailed logging
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler('reddit_stealth.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Utility to convert dict to dataclass
def dict_to_dataclass(cls: type, d: Dict[str, Any]) -> Any:
    logger.debug(f"Converting dict to dataclass: {cls.__name__}")
    if not is_dataclass(cls) or not isinstance(d, dict):
        logger.warning(f"Invalid input for dataclass conversion: cls={cls}, dict={type(d)}")
        return d

    try:
        type_hints = get_type_hints(cls)
        field_values = {}
        for field in fields(cls):
            if field.name in d:
                field_type = type_hints.get(field.name, Any)
                field_values[field.name] = dict_to_dataclass(field_type, d[field.name])
        instance = cls(**field_values)
        logger.debug(f"Successfully created {cls.__name__} instance")
        return instance
    except Exception as e:
        logger.error(f"Failed to convert dict to {cls.__name__}: {str(e)}")
        raise


class HumanBehavior:
    @staticmethod
    async def random_delay(min_ms: int, max_ms: int):
        try:
            delay = random.uniform(min_ms/1000, max_ms/1000)
            logger.debug(f"Applying random delay of {delay:.2f} seconds")
            await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"Error in random_delay: {str(e)}")
            raise

    @staticmethod
    async def human_scroll(page):
        logger.info("Starting human-like scrolling")
        try:
            async def randomized_pause(base_duration):
                variance = random.choice([(1.0, 1.2), (0.8, 1.0), (0.5, 0.8), (1.5, 3.0)])
                pause = base_duration * random.uniform(*variance)
                logger.debug(f"Randomized pause for {pause:.2f} seconds")
                await asyncio.sleep(pause)

            page_height = await page.evaluate("document.body.scrollHeight")
            viewport_height = await page.evaluate("window.innerHeight")
            max_scroll = page_height - viewport_height
            current_position = await page.evaluate("window.scrollY")
            logger.debug(f"Page height: {page_height}, Viewport height: {viewport_height}, Max scroll: {max_scroll}")

            scroll_types = [
                {"distance_min": 20, "distance_max": 150, "speed_min": 0.1, "speed_max": 0.3, "pause_min": 300, "pause_max": 700, "horizontal_jitter": (0, 8), "reversal_chance": 0.25, "accuracy_deviation": 5, "step_variability": (3, 6), "tremor_factor": 2, "finger_slip_chance": 0.02},
                {"distance_min": 80, "distance_max": 350, "speed_min": 0.25, "speed_max": 0.65, "pause_min": 800, "pause_max": 3000, "horizontal_jitter": (0, 15), "reversal_chance": 0.15, "accuracy_deviation": 10, "step_variability": (2, 5), "curve_type": "ease-out", "finger_slip_chance": 0.05},
                {"distance_min": 300, "distance_max": 900, "speed_min": 0.4, "speed_max": 1.2, "pause_min": 400, "pause_max": 1500, "horizontal_jitter": (0, 25), "reversal_chance": 0.08, "accuracy_deviation": 25, "step_variability": (3, 8), "overshoot_factor": (1.1, 1.3), "finger_slip_chance": 0.1},
                {"distance_min": 800, "distance_max": 2200, "speed_min": 0.7, "speed_max": 2.0, "pause_min": 200, "pause_max": 800, "horizontal_jitter": (0, 30), "reversal_chance": 0.03, "accuracy_deviation": 50, "step_variability": (4, 10), "momentum_scroll": True, "swing_variance": (0.8, 1.2)}
            ]

            content_pause_chance = 0.4
            momentum_chance = 0.3
            max_scroll_attempts = random.randint(1, 4)

            for attempt in range(max_scroll_attempts):
                current_position = await page.evaluate("window.scrollY")
                if max_scroll <= 0:
                    logger.debug("Max scroll reached, stopping")
                    break

                position_ratio = current_position / max_scroll
                scroll_direction = 1 if position_ratio <= 0.1 else (-1 if position_ratio >= 0.9 else (-1 if random.random() < (0.15 + 0.25 * position_ratio) else 1))
                type_weights = [0.2 + (0.3 * (1 - position_ratio)), 0.3 + (0.4 * position_ratio), 0.25 - (0.1 * position_ratio), 0.1 * position_ratio]
                scroll_type = random.choices(scroll_types, weights=type_weights, k=1)[0]

                base_distance = random.randint(scroll_type["distance_min"], scroll_type["distance_max"])
                accuracy_dev = random.randint(-scroll_type["accuracy_deviation"], scroll_type["accuracy_deviation"])
                actual_distance = (base_distance + accuracy_dev) * scroll_direction

                if random.random() < scroll_type.get("finger_slip_chance", 0):
                    slip_factor = random.uniform(1.5, 3.0)
                    actual_distance *= slip_factor
                    logger.debug(f"Finger slip applied, distance multiplier: {slip_factor}")

                h_jitter = random.randint(*scroll_type["horizontal_jitter"]) * random.choice([-1, 1])
                steps = random.randint(*scroll_type["step_variability"])
                step_distance = actual_distance / steps
                h_step = h_jitter / steps

                for step in range(steps):
                    speed = random.uniform(scroll_type["speed_min"], scroll_type["speed_max"]) * random.uniform(*scroll_type.get("swing_variance", (1, 1)))
                    tremor_x = random.randint(-scroll_type.get("tremor_factor", 0), scroll_type.get("tremor_factor", 0))
                    tremor_y = random.randint(-scroll_type.get("tremor_factor", 0), scroll_type.get("tremor_factor", 0))
                    await page.mouse.wheel(delta_x=h_step + tremor_x, delta_y=step_distance + tremor_y)
                    await asyncio.sleep(speed / steps)

                if scroll_type.get("momentum_scroll") and random.random() < momentum_chance:
                    momentum_distance = actual_distance * 0.3 * random.uniform(0.5, 1.5)
                    await page.mouse.wheel(delta_x=0, delta_y=momentum_distance)
                    await asyncio.sleep(random.uniform(0.1, 0.3))

                if "overshoot_factor" in scroll_type:
                    correction = -int(actual_distance * random.uniform(*scroll_type["overshoot_factor"]))
                    await page.mouse.wheel(delta_x=0, delta_y=correction)
                    await asyncio.sleep(0.1)

                current_position = max(0, min(current_position + actual_distance, max_scroll))
                logger.debug(f"Scroll attempt {attempt + 1}, new position: {current_position}")

                base_pause = random.uniform(scroll_type["pause_min"], scroll_type["pause_max"]) / 1000
                await randomized_pause(base_pause)

                if random.random() < 0.15:
                    logger.debug("Random scroll pattern break")
                    break

            logger.info("Completed human-like scrolling")
        except Exception as e:
            logger.error(f"Error in human_scroll: {str(e)}")
            raise

class StealthEnhancer:
    def __init__(self, account_id):
        self.account_id = account_id
        self.profiles_dir = "profiles"
        logger.debug(f"Initializing StealthEnhancer for account {account_id}")
        self.fingerprint = self.load_fingerprint()

    def load_fingerprint(self):
        fingerprint_file = os.path.join(self.profiles_dir, str(self.account_id), f"fingerprint_{self.account_id}.json")
        logger.debug(f"Loading fingerprint from {fingerprint_file}")

        try:
            if not os.path.exists(fingerprint_file):
                logger.error(f"Fingerprint file not found: {fingerprint_file}")
                raise FileNotFoundError(f"Fingerprint file not found: {fingerprint_file}")

            with open(fingerprint_file, "r") as f:
                data = json.load(f)
            logger.debug(f"Fingerprint data loaded: {data}")

            fingerprint = dict_to_dataclass(Fingerprint, data["fingerprint"])
            logger.info(f"Successfully loaded fingerprint for account {self.account_id}")
            return fingerprint
        except Exception as e:
            logger.error(f"Failed to load fingerprint: {str(e)}")
            raise


async def upvote_post(account_id: int, post_url: str, proxy_config: Dict[str, Any] = None):
    logger.info(f"Starting upvote process for account {account_id} on post {post_url}")
    try:
        stealth = StealthEnhancer(account_id)
        cookies_file = os.path.join("profiles", str(account_id), f"cookies_{account_id}.json")
        logger.debug(f"Loading cookies from {cookies_file}")

        try:
            with open(cookies_file, "r") as f:
                cookies = json.load(f)
            logger.info(f"Cookies loaded successfully for account {account_id}")
        except Exception as e:
            logger.error(f"Failed to load cookies: {str(e)}")
            raise

        config = {
            "fingerprint": stealth.fingerprint,
            "os": "windows",
            "screen": Screen(max_width=1280, max_height=720),
            "geoip": True,
            "humanize": True,
            "i_know_what_im_doing": True
        }
        if proxy_config:
            config["proxy"] = proxy_config
            logger.debug(f"Using proxy configuration: {proxy_config}")

        logger.debug(f"Browser configuration: {config}")
        async with AsyncCamoufox(**config) as browser:
            try:
                page = await browser.new_page()
                logger.info(f"New browser page created for account {account_id}")

                await page.context.add_cookies(cookies)
                logger.debug(f"Cookies added to browser context")

                await page.set_extra_http_headers({
                    'Referer': random.choice(['https://www.google.com/', 'https://x.com/', 'https://www.reddit.com/'])
                })
                logger.debug("Extra HTTP headers set")

                await HumanBehavior.random_delay(1000, 3000)
                logger.info(f"Navigating to Reddit homepage")
                await page.goto('https://www.reddit.com/', wait_until='domcontentloaded')
                logger.debug("Reddit homepage loaded")
                await HumanBehavior.random_delay(500, 1000)
                await HumanBehavior.human_scroll(page)
                await HumanBehavior.random_delay(2000, 5000)

                logger.info(f"Navigating to post URL: {post_url}")
                await page.goto(post_url)
                logger.debug(f"Post page loaded: {post_url}")
                await HumanBehavior.random_delay(8000, 20000)

                upvote_selector = 'button:has(svg[icon-name="upvote-outline"])'
                voted_selector = 'button:has(svg[icon-name="upvote-fill"])'
                logger.debug(f"Querying for upvote button with selector: {upvote_selector}")

                button = await page.query_selector(upvote_selector)
                if button is None:
                    logger.warning("Upvote button not found, checking if already upvoted")
                    voted_button = await page.wait_for_selector(voted_selector, timeout=15000)
                    if voted_button:
                        logger.info(f"Post already upvoted: {post_url}")
                        await HumanBehavior.random_delay(2000, 3500)
                        return
                    else:
                        logger.error(f"Neither upvote nor voted button found for {post_url}")
                        raise Exception("Upvote button not found")

                logger.debug("Upvote button found")
                aria_pressed = await button.get_attribute('aria-pressed')
                logger.debug(f"Upvote button aria-pressed: {aria_pressed}")

                if aria_pressed == "false":
                    logger.info(f"Post not upvoted, performing upvote: {post_url}")
                    await button.click()
                    logger.debug("Upvote button clicked")
                    await HumanBehavior.random_delay(2000, 5000)

                    button2 = await page.wait_for_selector(voted_selector, timeout=15000)
                    if button2:
                        aria_pressed2 = await button2.get_attribute('aria-pressed')
                        if aria_pressed2 == "true":
                            logger.info(f"Successfully upvoted post: {post_url}")
                        else:
                            logger.error(f"Upvote validation failed, aria-pressed: {aria_pressed2}")
                            raise Exception("Upvote validation failed")
                    else:
                        logger.error("Failed to find upvoted button after click")
                        raise Exception("Upvoted button not found")
                else:
                    logger.info(f"Post already upvoted: {post_url}")

                await HumanBehavior.random_delay(2000, 5000)
                random_pages = [
                    'https://www.reddit.com/', 'https://www.reddit.com/r/popular/', 'https://www.reddit.com/r/all/',
                    'https://www.reddit.com/r/AskReddit/', 'https://www.reddit.com/r/funny/', 'https://www.reddit.com/r/science/',
                    'https://www.reddit.com/r/technology/', 'https://www.reddit.com/r/worldnews/', 'https://www.reddit.com/r/movies/',
                    'https://www.reddit.com/r/gaming/', 'https://www.reddit.com/r/todayilearned/', 'https://www.reddit.com/r/pics/',
                    'https://www.reddit.com/r/aww/', 'https://www.reddit.com/r/Showerthoughts/', 'https://www.reddit.com/r/interestingasfuck/',
                    'https://www.reddit.com/r/AskScience/', 'https://www.reddit.com/r/MadeMeSmile/', 'https://www.reddit.com/r/mildlyinteresting/',
                    'https://www.reddit.com/r/dataisbeautiful/', 'https://www.reddit.com/r/InternetIsBeautiful/', 'https://www.reddit.com/r/HistoryPorn/',
                    'https://www.reddit.com/r/wholesomememes/', 'https://www.reddit.com/r/NoStupidQuestions/', 'https://www.reddit.com/r/TrueOffMyChest/',
                    'https://www.reddit.com/r/lifeprotips/', 'https://www.reddit.com/r/explainlikeimfive/', 'https://www.reddit.com/r/nottheonion/',
                    'https://www.reddit.com/r/DIY/', 'https://www.reddit.com/r/EarthPorn/', 'https://www.reddit.com/r/space/'
                ]
                random_page = random.choice(random_pages)
                logger.info(f"Navigating to random page: {random_page}")
                await page.goto(random_page)
                await HumanBehavior.random_delay(1000, 5000)
            except Exception as e:
                logger.error(f"Error during browser operations for {post_url}: {str(e)}")
                raise
            finally:
                if 'page' in locals():
                    logger.debug("Closing page")
                    await page.close()
    except Exception as e:
        logger.error(f"Upvote process failed for {post_url}: {str(e)}")
        raise

async def orchestrate_upvotes(account_id: int, post_urls: list, proxy_config: Dict[str, Any] = None):
    logger.info(f"Starting upvote orchestration for account {account_id} on {len(post_urls)} posts")
    try:
        # Calculate time intervals for 24 hours (86400 seconds)
        total_time = 86400  # 24 hours in seconds
        min_gap = 1800  # 30 minutes in seconds
        max_posts = len(post_urls)
        
        # Generate random times ensuring minimum gap
        times = [0]
        last_time = 0
        for _ in range(max_posts):
            next_time = last_time + random.uniform(min_gap, total_time / max_posts)
            if next_time > total_time:
                break
            times.append(next_time)
            last_time = next_time
        times.sort()
        logger.debug(f"Scheduled upvote times: {[datetime.now() + timedelta(seconds=t) for t in times]}")

        for i, (post_url, delay) in enumerate(zip(post_urls, times)):
            
            if i == 0:
                logger.info(f"Immediately executing upvote 1/{max_posts} for {post_url}")
            else:
                wait_time = delay - times[i - 1]
                logger.info(f"Scheduling upvote {i + 1}/{max_posts} for {post_url} after {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)

            logger.debug(f"Executing upvote for {post_url}")
            
            try:
                await upvote_post(account_id, post_url)
                logger.info(f"Completed upvote {i + 1}/{max_posts} for {post_url}")
            except Exception as e:
                logger.error(f"Failed upvote {i + 1}/{max_posts} for {post_url}: {str(e)}")
                continue  # Continue with next post despite error
    except Exception as e:
        logger.error(f"Orchestration failed: {str(e)}")
        raise

if __name__ == "__main__":
    account_id = 1
    post_urls = [
        "https://www.reddit.com/r/AskReddit/comments/1ki36is/a_newly_elected_pope_can_technically_choose_any/",
        "https://www.reddit.com/r/indiafitchecks/comments/1kef91u/soft_boy_summer_starter_packdoes_this_work/",
        "https://www.reddit.com/r/SanjeedaSheikh/comments/1kf34w1/can_anyone_feed/",
        "https://www.reddit.com/r/AppearanceAdvice/comments/1khryvh/18_f_makeup_or_no_makeup/",
        "https://www.reddit.com/r/NameMyDog/comments/1khp56l/need_out_of_pocketfood_names/"
    ]
    
    try:
        logger.info("Starting upvoting session")
        asyncio.run(orchestrate_upvotes(account_id, post_urls))
        logger.info("Upvoting session completed successfully")
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Upvoting session failed: {str(e)}")
    finally:
        logger.info("Program execution ended")