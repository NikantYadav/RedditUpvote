import asyncio
import random
import json
import os
import time
import logging
from datetime import datetime
import humanfriendly
from faker import Faker
from faker.providers import BaseProvider
from curl_cffi import Curl
from camoufox.async_api import AsyncCamoufox
from browserforge.fingerprints import Screen
from geoip2 import database
from geoip2.errors import AddressNotFoundError
import pytz
from typing import Tuple, Dict, Any
import hashlib
from playwright.async_api import async_playwright
from urllib.parse import urlparse

# Configure logging system
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler('reddit_stealth.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_proxy(proxy_str):
    parsed = urlparse(proxy_str)
    return {
        "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
        "username": parsed.username,
        "password": parsed.password
    }

class GeoUtils:
    def __init__(self):
        self.geo_reader = None
        self.locale_map = {
            'US': 'en_US',
            'DE': 'de_DE',
            'FR': 'fr_FR',
            'JP': 'ja_JP',
        }

    COUNTRY_CONFIG = {
        'US': {
            'faker_locale': 'en_US',
            'timezone': 'America/New_York',
            'http_accept_language': 'en-US,en;q=0.9',
            'common_resolution': '1920x1080',
            'mobile_probability': 0.4,
            'platform_header': '"Windows"',
            'latency_range': (8, 28),
            'base_download': 150,
            'base_upload': 50,
            'memory_options': [8, 16, 32]
        },
        'DE': {
            'faker_locale': 'de_DE',
            'timezone': 'Europe/Berlin',
            'http_accept_language': 'de-DE,de;q=0.9,en;q=0.8',
            'common_resolution': '1920x1080',
            'mobile_probability': 0.5,
            'platform_header': '"Android"',
            'latency_range': (6, 32),
            'base_download': 120,
            'base_upload': 40,
            'memory_options': [4, 8, 16]
        },
        'JP': {
            'faker_locale': 'ja_JP',
            'timezone': 'Asia/Tokyo',
            'http_accept_language': 'ja-JP,ja;q=0.9',
            'common_resolution': '1440x2560',
            'mobile_probability': 0.7,
            'platform_header': '"iPhone"',
            'latency_range': (12, 45),
            'base_download': 100,
            'base_upload': 30,
            'memory_options': [6, 8, 12]
        }
    }
        
    def get_locale_settings(self, country_code):
        return self.COUNTRY_CONFIG.get(country_code, self.COUNTRY_CONFIG['US'])

    def get_proxy_country(self, proxy_url):
        try:
            ip = proxy_url.split('@')[-1].split(':')[0]
            return 'US'  # Mock return for testing
        except (Exception, IndexError):
            return 'US'

class StealthUtils:
    @staticmethod
    async def human_mouse(page, element):
        target = await element.bounding_box()
        start_x = random.randint(0, 400)
        start_y = random.randint(0, 400)
        points = StealthUtils.generate_bezier_path(
            (start_x, start_y),
            (target['x'] + target['width']/2, target['y'] + target['height']/2),
            spread=random.uniform(0.8, 1.2)
        )
        for x, y in points:
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.01, 0.05))
        await page.mouse.click(
            target['x'] + target['width']/2, 
            target['y'] + target['height']/2,
            delay=random.randint(80, 150)
        )

    @staticmethod
    def generate_bezier_path(start, end, spread=1.0, num_points=20):
        cp1 = (
            start[0] + (end[0] - start[0]) * 0.25 + random.randint(-50, 50),
            start[1] + (end[1] - start[1]) * 0.25 + random.randint(-50, 50)
        )
        cp2 = (
            start[0] + (end[0] - start[0]) * 0.75 + random.randint(-50, 50),
            start[1] + (end[1] - start[1]) * 0.75 + random.randint(-50, 50)
        )
        t_values = [i/(num_points-1) for i in range(num_points)]
        return [StealthUtils.bezier_point(start, cp1, cp2, end, t) for t in t_values]

    @staticmethod
    def bezier_point(p0, p1, p2, p3, t):
        x = (1-t)**3 * p0[0] + 3*(1-t)**2*t*p1[0] + 3*(1-t)*t**2*p2[0] + t**3*p3[0]
        y = (1-t)**3 * p0[1] + 3*(1-t)**2*t*p1[1] + 3*(1-t)*t**2*p2[1] + t**3*p3[1]
        return (x, y)

class AccountManager:
    def __init__(self):
        self.logger = logging.getLogger('AccountManager')
        self.accounts = []
        self.load_accounts()
        
    def load_accounts(self):
        self.logger.info("Initializing account storage system")
        try:
            if os.path.exists("accounts/accounts.json"):
                with open("accounts/accounts.json") as f:
                    self.accounts = json.load(f)
                self.logger.debug(f"Successfully loaded {len(self.accounts)} accounts from storage")
            else:
                self.logger.warning("No accounts file found at accounts/accounts.json")
        except Exception as e:
            self.logger.error(f"Critical failure loading accounts: {str(e)}", exc_info=True)
            self.accounts = []
                
    def get_available_accounts(self):
        self.logger.debug("Evaluating account availability")
        valid_accounts = []
        for acc in self.accounts:
            last_used_date = datetime.fromtimestamp(acc['last_used']).date()
            today = datetime.today().date()
            if last_used_date < today:
                acc['daily_uses'] = 0
                acc['last_used'] = 0
                self.logger.info(f"Reset daily uses for account {acc['id']} (new day detected)")
            time_since_last = time.time() - acc['last_used']
            if acc['daily_uses'] < 5 and time_since_last > 1800:
                valid_accounts.append(acc)
        return valid_accounts

    def save_accounts(self):
        self.logger.debug("Initiating account storage sequence")
        try:
            os.makedirs("accounts", exist_ok=True)
            with open("accounts/accounts.json", "w") as f:
                json.dump(self.accounts, f, indent=2)
            self.logger.info(f"Successfully persisted {len(self.accounts)} accounts to storage")
        except Exception as e:
            self.logger.critical(f"Account storage failure: {str(e)}", exc_info=True)

class RedditStealthSystem:
    def __init__(self, account):
        self.account = account
        self.logger = logging.getLogger(f'StealthSystem:{account["id"]}')
        self.fake = Faker()
        self.fingerprint = None
        self.session_start = time.time()
        self.logger.info(f"New session initialized for account {account['id']}")

    def generate_regional_referrer(self, country):
        reddit_home = 'https://www.reddit.com/'
        google_map = {
            'US': 'https://www.google.com/',
            'DE': 'https://www.google.de/',
            'JP': 'https://www.google.co.jp/',
            'FR': 'https://www.google.fr/',
            'IN': 'https://www.google.co.in/'
        }
        reddit_post = 'https://www.reddit.com/r/all/'
        referrer_map = {
            'US': [reddit_home, google_map['US'], reddit_post],
            'DE': [reddit_home, google_map['DE'], reddit_post],
            'JP': [reddit_home, google_map['JP'], reddit_post],
            'FR': [reddit_home, google_map['FR'], reddit_post],
            'IN': [reddit_home, google_map['IN'], reddit_post],
        }
        default_referrers = [reddit_home, google_map['US'], reddit_post]
        return random.choice(referrer_map.get(country, default_referrers))

    def get_os_from_ua(self, ua):
        if 'Windows' in ua:
            return 'windows'
        elif 'Mac OS' in ua or 'macOS' in ua:
            return 'macos'
        elif 'Linux' in ua or 'Android' in ua:
            return 'linux'
        else:
            return 'windows'

    async def generate_persistent_fingerprint(self):
        self.logger.info("Generating geo-aligned persistent fingerprint")
        try:
            geo_util = GeoUtils()
            proxy_country = geo_util.get_proxy_country(self.account['proxy'])
            locale_config = geo_util.get_locale_settings(proxy_country)
            
            self.fake = Faker(locale_config['faker_locale'])
            self.fake.seed_instance(hash(self.account['id']))
            
            fingerprint = {
                'timezone': locale_config['timezone'],
                'locale': locale_config['http_accept_language'],
                'screen_resolution': self.account.get('screen_resolution') or locale_config['common_resolution'],
                'referrer': self.generate_regional_referrer(proxy_country),
                'tz_offset': self.calculate_timezone_offset(locale_config['timezone']),
                'latency_range': locale_config['latency_range'],
                'base_download': locale_config['base_download'],
                'base_upload': locale_config['base_upload']
            }

            is_mobile = random.random() < locale_config['mobile_probability']
            if not self.account.get('user_agent'):
                if is_mobile:
                    target_os = 'ios' if proxy_country in ['US', 'JP'] else 'android'
                    max_retries = 5
                    for _ in range(max_retries):
                        ua = self.fake.user_agent()
                        if target_os == 'android' and 'Android' in ua:
                            fingerprint['user_agent'] = ua
                            break
                        elif target_os == 'ios' and ('iPhone' in ua or 'iPad' in ua):
                            fingerprint['user_agent'] = ua
                            break
                    else:
                        fingerprint['user_agent'] = self.fake.user_agent()
                else:
                    fingerprint['user_agent'] = self.fake.user_agent()
            
            fingerprint['os'] = self.get_os_from_ua(fingerprint['user_agent'])
            fingerprint['is_mobile'] = is_mobile

            if not self.account.get('pixel_ratio'):
                base_density = 1.0 if not is_mobile else 2.0
                fingerprint['pixel_ratio'] = round(base_density * random.uniform(0.95, 1.05), 2)

            self.account.update(fingerprint)
            self.logger.debug(f"Final fingerprint: {json.dumps(fingerprint, indent=2)}")
            return fingerprint

        except Exception as e:
            self.logger.critical(f"Geo fingerprint generation failed: {str(e)}", exc_info=True)
            raise

    def calculate_timezone_offset(self, timezone):
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        return int(now.utcoffset().total_seconds() / 3600 * 100)

    def apply_natural_variations(self):
        self.logger.debug("Applying natural device variations")
        variations = {
            'connection_type': random.choice(['wifi', 'cellular']),
            'battery_level': random.randint(20, 95),
            'clock_skew': random.randint(-300, 300),
            'headers': {
                'Cache-Control': random.choice(['max-age=0', 'no-cache']),
                'Pragma': random.choice(['no-cache', '']),
                'Accept-Encoding': random.choice(['gzip, deflate', 'gzip'])
            }
        }
        self.logger.debug(f"Applied natural variations: {json.dumps(variations, indent=2)}")
        return {**self.fingerprint, **variations}

    async def initialize_profile(self):
        if os.path.exists(f"profiles/{self.account['id']}/cookies.sqlite"):
            return True
        self.logger.info("Performing first-time manual login")
        try:
            async with async_playwright() as p:
                print(self.account['proxy'])
                proxy_config = parse_proxy(self.account['proxy'])
                print(proxy_config)
                context = await p.firefox.launch_persistent_context(
                    user_data_dir=f"./profiles/{self.account['id']}",
                    headless=False,
                    #executable_path=AsyncCamoufox.get_executable_path(),
                    proxy=proxy_config,
                    locale=self.fingerprint['locale'] if self.fingerprint else 'en-US',
                )
                page = await context.new_page()
                await page.goto("https://www.reddit.com", wait_until="networkidle")
                self.logger.info("""
                =============================================
                PLEASE PERFORM MANUAL LOGIN IN THE BROWSER!
                1. Complete login with credentials
                2. Handle 2FA if required
                3. Wait for Reddit home page to load
                4. Close the browser when done
                =============================================
                """)
                # Wait for browser to close
                while True:
                    try:
                        await asyncio.sleep(1)
                        await page.title()  # Check if page is still accessible
                    except Exception:
                        break
                await context.close()
                self.logger.info("Login completed successfully")
                return True
        except Exception as e:
            self.logger.error(f"Initial login failed: {str(e)}")
            return False

    async def organic_behavior(self, page):
        self.logger.info("Simulating organic user behavior")
        try:
            if random.random() > 0.3:
                delay = random.normalvariate(7, 2)
                self.logger.debug(f"Simulating reading time: {delay:.2f}s")
                await asyncio.sleep(delay)
                scroll_amount = random.randint(400, 800)
                self.logger.debug(f"Scrolling {scroll_amount}px")
                await page.mouse.wheel(0, scroll_amount)
            
            exploration_steps = random.randint(2, 4)
            self.logger.debug(f"Starting {exploration_steps} exploration movements")
            for step in range(exploration_steps):
                x = random.randint(0, 412)
                y = random.randint(0, 915)
                move_steps = random.randint(15, 30)
                self.logger.trace(f"Exploration {step+1} - Target: ({x}, {y}) Steps: {move_steps}")
                await page.mouse.move(x, y, steps=move_steps)
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
        except Exception as e:
            self.logger.error(f"Behavior simulation failed: {str(e)}", exc_info=True)
            raise

    async def execute_stealth_vote(self, post_url):
        self.logger.info("Starting stealth vote operation")
        if not os.path.exists(f"profiles/{self.account['id']}/Cookies"):
            success = await self.initialize_profile()
            if not success:
                return False
        try:
            if not self.fingerprint:
                self.fingerprint = await self.generate_persistent_fingerprint()
            
            w, h = map(int, self.fingerprint['screen_resolution'].split('x'))
            screen = Screen(min_width=w, max_width=w, min_height=h, max_height=h)

            async with async_playwright() as p:
                context = await p.firefox.launch_persistent_context(
                    user_data_dir=f"./profiles/{self.account['id']}",
                    headless=False,
                    #executable_path=AsyncCamoufox.get_executable_path(),
                    proxy={'server': self.account['proxy']},
                    user_agent=self.fingerprint['user_agent'],
                    locale=self.fingerprint['locale'],
                )
                page = await context.new_page()
                await page.set_viewport_size({'width': w, 'height': h})
                await page.set_extra_http_headers({
                    'Accept-Language': self.fingerprint['locale'],
                    'Referer': self.fingerprint['referrer'],
                })
                # Set network conditions
                latency = random.randint(*self.fingerprint['latency_range'])
                download_throughput = self.fingerprint['base_download'] * 1024 * 1024 / 8 * random.uniform(0.8, 1.2)
                upload_throughput = self.fingerprint['base_upload'] * 1024 * 1024 / 8 * random.uniform(0.8, 1.2)
                await page.context.route('**/*', lambda route: route.continue_(
                    headers={
                        **route.request.headers,
                        'Accept-Language': self.fingerprint['locale'],
                        'Referer': self.fingerprint['referrer'],
                    }
                ))
                await page.context.emulate_network_conditions(
                    offline=False,
                    download_throughput=download_throughput,
                    upload_throughput=upload_throughput,
                    latency=latency
                )
                await self.load_authenticated_session(page)
                referrer = random.choice(['https://www.reddit.com/', 'https://www.google.com/', 'https://www.reddit.com/r/all/'])
                self.logger.info(f"Navigating to target post via {referrer}")
                await page.goto(post_url, wait_until='networkidle', referer=referrer)
                await self.organic_behavior(page)
                self.logger.debug("Locating upvote button with multiple selectors")
                upvote_btn = await page.wait_for_selector(
                    '[data-click-id="upvote"], [aria-label="Upvote"], [upvote]',
                    timeout=20000
                )
                self.logger.info("Upvote button located successfully")
                self.logger.debug("Generating human interaction sequence")
                await StealthUtils.human_mouse(page, upvote_btn)
                if await self.validate_vote(page):
                    self.account['daily_uses'] += 1
                    self.account['last_used'] = time.time()
                    self.logger.info("Vote successfully registered!")
                    return True
                self.logger.warning("Vote validation checks failed")
                return False
        except Exception as e:
            self.logger.error(f"Vote operation failed: {str(e)}", exc_info=True)
            return False
        finally:
            if 'context' in locals():
                await context.close()

    async def validate_vote(self, page):
        self.logger.info("Validating vote registration")
        try:
            upvote_state = await page.evaluate('''() => {
                const btn = document.querySelector('[data-click-id="upvote"]');
                return btn ? btn.getAttribute('aria-pressed') : 'missing';
            }''')
            self.logger.debug(f"DOM validation state: {upvote_state}")
            validation = asyncio.Future()
            async def check_response(response):
                if "vote" in response.url() and response.status() == 200:
                    self.logger.debug("Received successful vote API response")
                    validation.set_result(True)
            page.on('response', check_response)
            try:
                result = await asyncio.wait_for(validation, timeout=10)
                self.logger.debug("Network validation succeeded")
                return result or upvote_state == "true"
            except asyncio.TimeoutError:
                self.logger.warning("Network validation timeout - relying on DOM check")
                return upvote_state == "true"
        except Exception as e:
            self.logger.error(f"Validation error: {str(e)}", exc_info=True)
            return False

    async def load_authenticated_session(self, page):
        self.logger.debug("Loading authenticated session")
        try:
            if os.path.exists(f"profiles/{self.account['id']}/Cookies"):
                self.logger.info("Found existing browser profile - resuming session")
                await page.goto('https://www.reddit.com/', wait_until='domcontentloaded')
                await asyncio.sleep(2)
                self.logger.debug("Session restoration complete")
            else:
                self.logger.warning("No existing profile found - new session")
        except Exception as e:
            self.logger.error(f"Session load failed: {str(e)}", exc_info=True)
            raise

async def orchestrate_voting(post_url, total_upvotes):
    logger = logging.getLogger('Orchestrator')
    manager = AccountManager()
    completed = 0
    while completed < total_upvotes:
        available = manager.get_available_accounts()
        if not available:
            next_available = min(
                (acc['last_used'] + 1800 for acc in manager.accounts if acc['daily_uses'] < 5),
                default=None
            )
            if next_available:
                wait_time = max(next_available - time.time(), 0)
                logger.info(f"⏳ Next available in {humanfriendly.format_timespan(wait_time)}")
                await asyncio.sleep(wait_time + 1)
                continue
            else:
                logger.error("All accounts at daily limit")
                break
        account = available[0]
        system = RedditStealthSystem(account)
        success = await system.execute_stealth_vote(post_url)
        if success:
            completed += 1
            manager.save_accounts()
            logger.info(f"✅ Success: {completed}/{total_upvotes}")
        await asyncio.sleep(1800)
    logger.info(f"🎉 Total upvotes achieved: {completed}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Starting Reddit Stealth Voting System")
    post_url = "https://www.reddit.com/r/archlinux/comments/ki9hmm/how_to_properly_removeuninstall_packagesapps_with/"
    total_upvotes = 5
    try:
        asyncio.run(orchestrate_voting(post_url, total_upvotes))
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.critical(f"Catastrophic failure: {str(e)}", exc_info=True)
    finally:
        logger.info("System shutdown complete")