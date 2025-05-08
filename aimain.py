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
from pyvirtualdisplay import Display
from curl_cffi import Curl
from nodriver import start
from geoip2 import database
from geoip2.errors import AddressNotFoundError
import pytz
from typing import Tuple, Dict, Any
import hashlib
from nodriver.cdp import network, page

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
        self.geo_reader = None  # Placeholder for geoip2 database.Reader
        self.locale_map = {
            'US': 'en_US',
            'DE': 'de_DE',
            'FR': 'fr_FR',
            'JP': 'ja_JP',
            # Add all target countries
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
            'base_download': 150,  # Mbps
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
        """Extract country from proxy IP"""
        try:
            ip = proxy_url.split('@')[-1].split(':')[0]
            # response = self.geo_reader.country(ip)  # Uncomment if using geoip2
            # return response.country.iso_code
            return 'US'  # Mock return for testing
        except (Exception, IndexError):
            return 'US'  # Fallback


class StealthUtils:
    @staticmethod
    async def human_mouse(page, element):
        """Realistic mouse movement using Bézier curves"""
        target = await element.bounding_box()
        start_x = random.randint(0, 400)
        start_y = random.randint(0, 400)
        
        
        # Generate intermediate points using Bézier curve
        points = StealthUtils.generate_bezier_path(
            (start_x, start_y),
            (target['x'] + target['width']/2, target['y'] + target['height']/2),
            spread=random.uniform(0.8, 1.2)
        )
        
        for x, y in points:
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.01, 0.05))
            
        await page.mouse.click(target['x'] + target['width']/2, 
                             target['y'] + target['height']/2,
                             delay=random.randint(80, 150))

    @staticmethod
    def generate_bezier_path(start, end, spread=1.0, num_points=20):
        """Generate smooth mouse path using Bézier curve"""
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
        """Calculate Bézier curve point"""
        x = (1-t)**3 * p0[0] + 3*(1-t)**2*t*p1[0] + 3*(1-t)*t**2*p2[0] + t**3*p3[0]
        y = (1-t)**3 * p0[1] + 3*(1-t)**2*t*p1[1] + 3*(1-t)*t**2*p2[1] + t**3*p3[1]
        return (x, y)

    @staticmethod
    async def spoof_canvas(page):
        """Canvas fingerprint spoofing using CDP"""
        await page.send(
            page.addScriptToEvaluateOnNewDocument(
            source="""
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function(...args) {
                const result = originalGetImageData.apply(this, args);
                for(let i = 0; i < result.data.length; i += Math.floor(Math.random() * 10) + 1) {
                    result.data[i] += Math.random() * 10 - 5;
                }
                return result;
            };
            
            HTMLCanvasElement.prototype.getContext = function(orig) {
                return function(type, ...args) {
                    const ctx = orig.apply(this, [type, ...args]);
                    if(type === 'webgl' || type === '2d') {
                        const ext = ctx.getExtension('WEBGL_debug_renderer_info');
                        if(ext) {
                            const original = ctx.getParameter;
                            ctx.getParameter = function(param) {
                                if(param === ext.UNMASKED_RENDERER_WEBGL) {
                                    return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0)';
                                }
                                return original.apply(this, [param]);
                            };
                        }
                    }
                    return ctx;
                };
            }(HTMLCanvasElement.prototype.getContext);
            """
        )
    )

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
            # Reset daily uses if new day
            last_used_date = datetime.fromtimestamp(acc['last_used']).date()
            today = datetime.today().date()
            if last_used_date < today:
                acc['daily_uses'] = 0
                acc['last_used'] = 0  # Reset to allow immediate use
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
        self.display = None
        self.browser = None
        self.page = None
        self.fingerprint = None
        self.session_start = time.time()
        self.logger.info(f"New session initialized for account {account['id']}")

    def generate_regional_referrer(self, country):
        """Generate realistic referrer URLs for Reddit posts (no subreddits)."""
        reddit_home = 'https://www.reddit.com/'
        google_map = {
            'US': 'https://www.google.com/',
            'DE': 'https://www.google.de/',
            'JP': 'https://www.google.co.jp/',
            'FR': 'https://www.google.fr/',
            'IN': 'https://www.google.co.in/',
        }
        # Optionally, a sample direct Reddit post link
        reddit_post = 'https://www.reddit.com/comments/example_post_id/'

        referrer_map = {
            'US': [reddit_home, google_map['US'], reddit_post],
            'DE': [reddit_home, google_map['DE'], reddit_post],
            'JP': [reddit_home, google_map['JP'], reddit_post],
            'FR': [reddit_home, google_map['FR'], reddit_post],
            'IN': [reddit_home, google_map['IN'], reddit_post],
        }
        # Default fallback: reddit homepage and google.com
        default_referrers = [reddit_home, google_map['US'], reddit_post]
        return random.choice(referrer_map.get(country, default_referrers))

    async def generate_persistent_fingerprint(self):
        """Generate geo-consistent browser fingerprint aligned with proxy location"""
        try:
            self.logger.info("Generating geo-aligned persistent fingerprint")
            
            # =====================
            # GeoIP Configuration
            # =====================
            geo_util = GeoUtils()
            proxy_country = geo_util.get_proxy_country(self.account['proxy'])
            locale_config = geo_util.get_locale_settings(proxy_country)
            
            # Initialize Faker with regional settings
            self.fake = Faker(locale_config['faker_locale'])
            self.fake.seed_instance(hash(self.account['id']))
            
            # =====================
            # Core Fingerprint Components
            # =====================
            fingerprint = {
                # Geo-dependent settings
                'timezone': locale_config['timezone'],
                'locale': locale_config['http_accept_language'],
                'screen_resolution': self.account.get('screen_resolution') or locale_config['common_resolution'],
                
                # Device characteristics
                'device_model': self.account.get('device_model') or self.generate_regional_device_model(proxy_country),
                'fonts': self.account.get('fonts') or self.generate_regional_font_stack(proxy_country),
                
                # Hardware specs
                'webgl_hash': self.account.get('webgl_hash') or self.generate_webgl_hash(proxy_country),
                'device_memory': self.account.get('device_memory') or random.choice(locale_config['memory_options']),
                
                # Network characteristics
                'network_conditions': self.account.get('network_conditions') or {
                    'latency': random.normalvariate(*locale_config['latency_range']),
                    'download': locale_config['base_download'] * random.uniform(0.9, 1.1),
                    'upload': locale_config['base_upload'] * random.uniform(0.9, 1.1)
                },
                
                # Behavioral markers
                'referrer': self.generate_regional_referrer(proxy_country),
                'tz_offset': self.calculate_timezone_offset(locale_config['timezone'])
            }

            # =====================
            # User Agent Generation
            # =====================

            if not self.account.get('user_agent'):
                is_mobile = random.random() < locale_config['mobile_probability']
                if is_mobile:
                    # Determine target mobile OS based on country
                    target_os = 'ios' if proxy_country in ['US', 'JP'] else 'android'
                    
                    # Generate mobile user agents until matching OS pattern
                    max_retries = 5
                    for _ in range(max_retries):
                        ua = self.fake.user_agent()
                        if target_os == 'android' and 'Android' in ua:
                            fingerprint['user_agent'] = ua
                            break
                        elif target_os == 'ios' and ('iPhone' in ua or 'iPad' in ua):
                            fingerprint['user_agent'] = ua
                            break
                    else:  # Fallback to any mobile UA
                        fingerprint['user_agent'] = self.fake.user_agent()
                else:
                    # Generate desktop user agent
                    fingerprint['user_agent'] = self.fake.user_agent()
            
            # =====================
            # Pixel Ratio Calculation
            # =====================
            if not self.account.get('pixel_ratio'):
                base_density = 1.0 if 'Desktop' in fingerprint['device_model'] else 2.0
                fingerprint['pixel_ratio'] = round(base_density * random.uniform(0.95, 1.05), 2)

            # =====================
            # Headers Configuration
            # =====================
            fingerprint['headers'] = {
                'Accept-Language': fingerprint['locale'],
                'X-Client-Timezone-Offset': str(fingerprint['tz_offset']),
                'Sec-CH-UA-Platform': locale_config['platform_header'],
                'Referer': fingerprint['referrer'],
                'X-Client-Geo': proxy_country
            }

            # =====================
            # Persistence & Return
            # =====================
            self.account.update(fingerprint)
            self.logger.debug(f"Final fingerprint: {json.dumps(fingerprint, indent=2)}")
            return fingerprint

        except Exception as e:
            self.logger.critical(f"Geo fingerprint generation failed: {str(e)}", exc_info=True)
            raise

    # Helper methods
    def generate_regional_device_model(self, country):
        regional_models = {
            'US': ['iPhone15,2', 'Pixel 7 Pro', 'Dell XPS 15'],
            'DE': ['Samsung Galaxy S23', 'Fairphone 4', 'Lenovo ThinkPad'],
            'JP': ['Xperia 1 V', 'AQUOS sense7', 'VAIO SX14'],
            'KR': ['Galaxy S24 Ultra', 'LG gram Style'],
            'IN': ['Redmi Note 13 Pro', 'Realme 11 Pro']
        }
        return random.choice(regional_models.get(country, ['Pixel 7 Pro']))

    def generate_regional_font_stack(self, country):
        font_map = {
            'US': ['Arial', 'Segoe UI', 'Tahoma'],
            'DE': ['Helvetica', 'Frühling Gothic'],
            'JP': ['Meiryo', 'Yu Gothic', 'Noto Sans JP'],
            'KR': ['Malgun Gothic', 'Apple SD Gothic Neo'],
            'CN': ['Microsoft YaHei', 'SimSun']
        }
        base_fonts = font_map.get(country, ['Arial', 'Helvetica'])
        return ', '.join(base_fonts + random.sample([
            'Georgia', 'Verdana', 'DejaVu Sans', 
            'Liberation Sans', 'Courier New'
        ], 3))

    def generate_webgl_hash(self, country):
        regional_gpus = {
            'US': ['NVIDIA', 'AMD'],
            'DE': ['AMD', 'Intel'],
            'JP': ['NVIDIA', 'Intel'],
            'KR': ['NVIDIA', 'AMD'],
            'CN': ['AMD', 'NVIDIA']
        }
        vendor = random.choice(regional_gpus.get(country, ['NVIDIA']))
        model = random.choice(['RTX 4090', 'Radeon 7900 XTX', 'Arc A770']) if vendor != 'Apple' else 'M2 Max'
        return hashlib.sha3_256(f"{vendor}{model}{self.fake.pystr(12)}".encode()).hexdigest()[:32]

    def calculate_timezone_offset(self, timezone):
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        return int(now.utcoffset().total_seconds() / 3600 * 100)


    def apply_natural_variations(self):
        """Add realistic session-to-session variations"""
        self.logger.debug("Applying natural device variations")
        variations = {
            'connection_type': random.choice(['wifi', 'cellular']),
            'battery_level': random.randint(20, 95),
            'clock_skew': random.randint(-300, 300),
            'network_conditions': {
                'latency': random.normalvariate(28, 5),
                'download': 4*1024*1024*random.uniform(0.8, 1.2),
                'upload': 2*1024*1024*random.uniform(0.8, 1.2)
            },
            'headers': {
                **self.fingerprint['headers'],
                'Cache-Control': random.choice(['max-age=0', 'no-cache']),
                'Pragma': random.choice(['no-cache', '']),
                'Accept-Encoding': random.choice(['gzip, deflate', 'gzip'])
            }
        }
        self.logger.debug(f"Applied natural variations: {json.dumps(variations, indent=2)}")
        return {**self.fingerprint, **variations}

    async def init_environment(self):
        """Initialize browser with persistent fingerprint"""
        self.logger.info("Initializing browser environment")
        try:
            if not self.fingerprint:
                self.fingerprint = await self.generate_persistent_fingerprint()
            
            device = self.apply_natural_variations()

            # Start virtual display
            self.logger.debug(f"Starting virtual display: {self.fingerprint['screen_resolution']}")
            self.display = Display(
                visible=0, 
                size=tuple(map(int, self.fingerprint['screen_resolution'].split('x')))
            )
            self.display.start()

            self.logger.info("Launching browser instance with fingerprint parameters")

            # Prepare browser args
            browser_args = [
                f'--proxy-server={self.account["proxy"]}',
                '--disable-blink-features=AutomationControlled',
                f'--user-agent={self.fingerprint["user_agent"]}',
                '--force-device-scale-factor=1',
                '--headless=new',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-hang-monitor',
                '--disable-component-extensions-with-background-pages',
                '--disable-sync',
                '--metrics-recording-only',
                '--disable-default-apps',
                '--mute-audio',
                f'--user-data-dir=./profiles/{self.account["id"]}'
            ]

            # Prepare mobile emulation options
            mobile_emulation = {
                'deviceMetrics': {
                    'width': int(self.fingerprint['screen_resolution'].split('x')[0]),
                    'height': int(self.fingerprint['screen_resolution'].split('x')[1]),
                    'pixelRatio': self.fingerprint['pixel_ratio'],
                    'touch': True
                }
            }

            # Launch browser
            self.browser = await start(
                browser_executable_path="/home/nikant/Desktop/RedditUpvote/chrome/linux-136.0.7103.92/chrome-linux64/chrome",
                headless=False,
                browser_args=browser_args,
                headers={
                    'Accept-Language': self.fingerprint['locale'],
                    'Referer': self.fingerprint['referrer']
                },
                experimental_options={
                    'mobileEmulation': mobile_emulation
                }
            )

            self.page = await self.browser.get('about:blank')
            await self.apply_stealth_measures(device)
            self.logger.info("Browser environment ready with stealth measures")

        except Exception as e:
            self.logger.critical(f"Browser initialization failed: {str(e)}", exc_info=True)
            raise

    async def initialize_profile(self):
        """First-time manual login with full fingerprint setup"""
        if os.path.exists(f"profiles/{self.account['id']}/Cookies"):
            return  # Already initialized

        self.logger.info("Performing first-time manual login")
        
        try:
            # Initialize browser with full fingerprint
            await self.init_environment()
            
            # Navigate to login page
            await self.page.goto(
                "https://www.reddit.com/login",
                wait_until="networkidle",
                timeout=120000
            )
            
            # User manual login
            self.logger.info("""
            =============================================
            PLEASE PERFORM MANUAL LOGIN IN THE BROWSER!
            1. Complete login with credentials
            2. Handle 2FA if required
            3. Wait for Reddit home page to load
            4. Close the browser when done
            =============================================
            """)
            
            # Keep browser open until user closes it
            while True:
                await asyncio.sleep(1)
                if not await self.page.evaluate("document.visibilityState === 'visible'"):
                    break

            self.logger.info("Login completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Initial login failed: {str(e)}")
            return False
        finally:
            await self.cleanup()

    async def apply_stealth_measures(self, device):
        """Implement anti-detection measures"""
        self.logger.info("Applying advanced stealth measures")

        try:
            # Network characteristics
            self.logger.debug(f"Emulating network conditions: {device['network_conditions']}")
            await self.page.send(
                network.emulateNetworkConditions(
                    offline=False,
                    latency=device['network_conditions']['latency'],
                    downloadThroughput=device['network_conditions']['download'],
                    uploadThroughput=device['network_conditions']['upload'],
                    connectionType=device.get('connection_type', 'wifi')
                )
            )
            
            # Headers and TLS fingerprint
            self.logger.debug("Configuring browser headers and TLS fingerprint")
            curl = Curl(impersonate="chrome120")
            await self.page.send(
                network.setExtraHTTPHeaders(
                    headers={**curl.headers, **device['headers']}
                )
            )
            
            # Persistent API spoofing
            self.logger.debug("Injecting hardware spoofing scripts")
            await self.page.send(
                page.addScriptToEvaluateOnNewDocument(
                    source=f"""
                    Object.defineProperty(navigator, 'deviceMemory', {{
                        get: () => {self.fingerprint['device_memory']}
                    }});
                    Object.defineProperty(navigator, 'hardwareConcurrency', {{
                        value: {random.randint(4, 8)}
                    }});
                    window.chrome = {{ app: {{ isInstalled: true }} }};
                    """
                )
            )
            
            # Canvas/WebGL fingerprint consistency
            self.logger.debug("Modifying canvas fingerprints")
            await StealthUtils.spoof_canvas(self.page)
            
            self.logger.info("Stealth measures applied successfully")
        except Exception as e:
            self.logger.error(f"Failed to apply stealth measures: {str(e)}", exc_info=True)
            raise

    async def organic_behavior(self):
        """Simulate natural browsing patterns"""
        self.logger.info("Simulating organic user behavior")
        try:
            # Random reading time
            if random.random() > 0.3:
                delay = random.normalvariate(7, 2)
                self.logger.debug(f"Simulating reading time: {delay:.2f}s")
                await asyncio.sleep(delay)
                scroll_amount = random.randint(400, 800)
                self.logger.debug(f"Scrolling {scroll_amount}px")
                await self.page.mouse.wheel(delta_y=scroll_amount)
            
            # Random exploration
            exploration_steps = random.randint(2, 4)
            self.logger.debug(f"Starting {exploration_steps} exploration movements")
            for step in range(exploration_steps):
                x = random.randint(0, 412)
                y = random.randint(0, 915)
                move_steps = random.randint(15, 30)
                self.logger.trace(f"Exploration {step+1} - Target: ({x}, {y}) Steps: {move_steps}")
                await self.page.mouse.move(x, y, steps=move_steps)
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
            await self.init_environment()
            await self.load_authenticated_session()
            
            referrer = random.choice(['https://www.google.com/', 'https://reddit.com/', 'https://t.co/'])
            self.logger.info(f"Navigating to target post via {referrer}")
            await self.page.goto(post_url, wait_until='networkidle2', referer=referrer)
            
            await self.organic_behavior()
            
            self.logger.debug("Locating upvote button with multiple selectors")
            upvote_btn = await self.page.wait_for_selector(
                '[data-click-id="upvote"], [aria-label="Upvote"], [upvote]',
                state="attached",
                timeout=20000
            )
            self.logger.info("Upvote button located successfully")
            
            self.logger.debug("Generating human interaction sequence")
            await StealthUtils.human_mouse(self.page, upvote_btn)
            
            if await self.validate_vote():
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
            await self.cleanup()

    async def validate_vote(self):
        """Multi-layer vote verification"""
        self.logger.info("Validating vote registration")
        try:
            # DOM check
            upvote_state = await self.page.evaluate('''() => {
                const btn = document.querySelector('[data-click-id="upvote"]');
                return btn ? btn.getAttribute('aria-pressed') : 'missing';
            }''')
            self.logger.debug(f"DOM validation state: {upvote_state}")
            
            # Network check
            validation = asyncio.Future()
            async def check_response(response):
                if "vote" in response.url and response.status == 200:
                    self.logger.debug("Received successful vote API response")
                    validation.set_result(True)
            
            self.page.on('response', check_response)
            
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

    async def load_authenticated_session(self):
        """Load persistent browser profile"""
        self.logger.debug("Loading authenticated session")
        try:
            if os.path.exists(f"profiles/{self.account['id']}/Cookies"):
                self.logger.info("Found existing browser profile - resuming session")
                await self.page.goto('https://reddit.com/')
                await asyncio.sleep(2)
                self.logger.debug("Session restoration complete")
            else:
                self.logger.warning("No existing profile found - new session")
        except Exception as e:
            self.logger.error(f"Session load failed: {str(e)}", exc_info=True)
            raise

    async def cleanup(self):
        """Proper resource cleanup"""
        self.logger.info("Cleaning up system resources")
        try:
            if self.browser:
                self.logger.debug("Closing browser instance")
                self.browser.stop()
            if self.display:
                self.logger.debug("Stopping virtual display")
                self.display.stop()
            self.logger.info("Cleanup completed successfully")
        except Exception as e:
            self.logger.error(f"Cleanup failed: {str(e)}", exc_info=True)

async def orchestrate_voting(post_url, total_upvotes):
    logger = logging.getLogger('Orchestrator')
    manager = AccountManager()
    completed = 0

    while completed < total_upvotes:
        available = manager.get_available_accounts()
        if not available:
            # Find the earliest time an account becomes available
            next_available = min(
                (acc['last_used'] + 1800 for acc in manager.accounts if acc['daily_uses'] < 5),
                default=None
            )
            if next_available:
                wait_time = max(next_available - time.time(), 0)
                logger.info(f"⏳ Next available in {humanfriendly.format_timespan(wait_time)}")
                await asyncio.sleep(wait_time + 1)  # Small buffer
                continue
            else:
                logger.error("All accounts at daily limit")
                break

        # Process one account per batch
        account = available[0]
        system = RedditStealthSystem(account)
        success = await system.execute_stealth_vote(post_url)
        if success:
            completed += 1
            manager.save_accounts()
            logger.info(f"✅ Success: {completed}/{total_upvotes}")

        # Wait at least 30 minutes before next vote
        await asyncio.sleep(1800)  # 30 minutes cooldown

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