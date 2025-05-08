import asyncio
import random
import json
import os
import time
import logging
from datetime import datetime
import humanfriendly
from faker import Faker
from geoip2 import database
from geoip2.errors import AddressNotFoundError
import pytz
import hashlib
from camoufox.async_api import AsyncCamoufox
from browserforge.fingerprints import FingerprintGenerator

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
            'latency_range': (28, 8),
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
            'latency_range': (32, 6),
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
            'latency_range': (45, 12),
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
            return 'US'
        except Exception:
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
        try:
            if os.path.exists("accounts/accounts.json"):
                with open("accounts/accounts.json") as f:
                    self.accounts = json.load(f)
                self.logger.info(f"Loaded {len(self.accounts)} accounts")
            else:
                self.logger.warning("No accounts file found")
        except Exception as e:
            self.logger.error(f"Error loading accounts: {str(e)}")
            self.accounts = []
                
    def get_available_accounts(self):
        valid_accounts = []
        for acc in self.accounts:
            last_used_date = datetime.fromtimestamp(acc['last_used']).date()
            today = datetime.today().date()
            if last_used_date < today:
                acc['daily_uses'] = 0
                acc['last_used'] = 0

            time_since_last = time.time() - acc['last_used']
            if acc['daily_uses'] < 5 and time_since_last > 1800:
                valid_accounts.append(acc)
        return valid_accounts

    def save_accounts(self):
        try:
            os.makedirs("accounts", exist_ok=True)
            with open("accounts/accounts.json", "w") as f:
                json.dump(self.accounts, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving accounts: {str(e)}")

class RedditStealthSystem:
    def __init__(self, account):
        self.account = account
        self.logger = logging.getLogger(f'StealthSystem:{account["id"]}')
        self.browser = None
        self.page = None
        self.fingerprint = None

    async def __aenter__(self):
        await self.init_environment()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def generate_fingerprint(self):
        geo_util = GeoUtils()
        proxy_country = geo_util.get_proxy_country(self.account['proxy'])
        locale_config = geo_util.get_locale_settings(proxy_country)

        generator = FingerprintGenerator()
        fingerprint = generator.generate(
            os='win' if 'Windows' in locale_config['platform_header'] else 'mac',
            browser="firefox",
            device="desktop" if locale_config['mobile_probability'] < 0.5 else "mobile",
            locale=locale_config['http_accept_language'],
            resolution=tuple(map(int, locale_config['common_resolution'].split('x'))),
            browser_version="latest"
        )

        fingerprint.update({
            'timezone': locale_config['timezone'],
            'referrer': self.generate_regional_referrer(proxy_country),
            'network_conditions': {
                'latency': random.normalvariate(*locale_config['latency_range']),
                'download': locale_config['base_download'] * 1024 * 1024,
                'upload': locale_config['base_upload'] * 1024 * 1024
            }
        })
        return fingerprint

    def generate_regional_referrer(self, country):
        referrer_map = {
            'US': ['https://www.google.com/', 'https://reddit.com/'],
            'DE': ['https://www.google.de/', 'https://reddit.com/'],
            'JP': ['https://www.google.co.jp/', 'https://reddit.com/'],
        }
        return random.choice(referrer_map.get(country, ['https://www.google.com/']))

    async def init_environment(self):
        try:
            self.fingerprint = await self.generate_fingerprint()
            
            self.browser = await AsyncCamoufox(
                proxy=self.account['proxy'],
                geoip=True,
                headless="virtual",
                humanize=1.5,
                fingerprint=self.fingerprint,
                user_data_dir=f"./profiles/{self.account['id']}"
            ).start()

            self.page = await self.browser.new_page()
            
            await self.page.context.set_network_conditions(
                offline=False,
                download_throughput=self.fingerprint['network_conditions']['download'],
                upload_throughput=self.fingerprint['network_conditions']['upload'],
                latency=self.fingerprint['network_conditions']['latency']
            )

            await self.page.set_extra_http_headers({
                'Accept-Language': self.fingerprint['headers']['accept-language'],
                'Referer': self.fingerprint['referrer']
            })

            self.logger.info("Browser environment ready")
            return self

        except Exception as e:
            self.logger.error(f"Initialization failed: {str(e)}")
            raise

    async def execute_stealth_vote(self, post_url):
        try:
            if not os.path.exists(f"profiles/{self.account['id']}/session.json"):
                if not await self.initialize_profile():
                    return False

            await self.page.goto(post_url, wait_until='networkidle')
            await self.organic_behavior()

            upvote_btn = await self.page.wait_for_selector(
                '[data-click-id="upvote"], [aria-label="Upvote"]',
                timeout=20000
            )
            
            await StealthUtils.human_mouse(self.page, upvote_btn)
            
            if await self.validate_vote():
                self.account['daily_uses'] += 1
                self.account['last_used'] = time.time()
                return True
            return False

        except Exception as e:
            self.logger.error(f"Voting failed: {str(e)}")
            return False

    async def organic_behavior(self):
        if random.random() > 0.3:
            await asyncio.sleep(random.uniform(2, 5))
            await self.page.mouse.wheel(delta_y=random.randint(300, 700))
        
        for _ in range(random.randint(2, 4)):
            x = random.randint(0, 400)
            y = random.randint(0, 800)
            await self.page.mouse.move(x, y, steps=random.randint(10, 20))
            await asyncio.sleep(random.uniform(0.2, 1.0))

    async def initialize_profile(self):
        try:
            await self.page.goto("https://www.reddit.com", wait_until='networkidle')
            self.logger.info("Please complete manual login in the browser...")
            
            while "reddit.com/login" in self.page.url:
                await asyncio.sleep(1)
            
            self.logger.info("Login successful")
            return True
        except Exception as e:
            self.logger.error(f"Login failed: {str(e)}")
            return False

    async def validate_vote(self):
        try:
            upvote_state = await self.page.evaluate('''() => {
                const btn = document.querySelector('[data-click-id="upvote"]');
                return btn?.ariaPressed || 'missing';
            }''')

            validation = asyncio.Future()
            async def check_response(response):
                if "/api/vote" in response.url and response.status == 200:
                    validation.set_result(True)
            
            self.page.on("response", check_response)
            
            try:
                await asyncio.wait_for(validation, timeout=10)
                return upvote_state == "true"
            except asyncio.TimeoutError:
                return upvote_state == "true"
                
        except Exception as e:
            self.logger.error(f"Validation error: {str(e)}")
            return False

    async def cleanup(self):
        if self.browser:
            await self.browser.close()
        self.logger.info("Cleanup completed")

async def orchestrate_voting(post_url, total_upvotes):
    manager = AccountManager()
    completed = 0

    while completed < total_upvotes:
        available = manager.get_available_accounts()
        if not available:
            next_available = min(
                (acc['last_used'] + 1800 for acc in manager.accounts),
                default=None
            )
            if next_available:
                wait_time = max(next_available - time.time(), 0)
                logger.info(f"Waiting {humanfriendly.format_timespan(wait_time)}")
                await asyncio.sleep(wait_time + 1)
                continue
            else:
                logger.error("All accounts exhausted")
                break

        account = available[0]
        async with RedditStealthSystem(account) as system:
            success = await system.execute_stealth_vote(post_url)
            if success:
                completed += 1
                manager.save_accounts()
                logger.info(f"Success: {completed}/{total_upvotes}")

        await asyncio.sleep(1800)

    logger.info(f"Completed {completed} upvotes")

if __name__ == "__main__":
    logger.info("Starting Reddit Stealth Voting System")
    
    post_url = "https://www.reddit.com/r/archlinux/comments/ki9hmm/how_to_properly_removeuninstall_packagesapps_with/"
    total_upvotes = 5
    
    try:
        asyncio.run(orchestrate_voting(post_url, total_upvotes))
    except KeyboardInterrupt:
        logger.info("Shutdown by user")
    except Exception as e:
        logger.critical(f"Critical error: {str(e)}")
    finally:
        logger.info("System shutdown")