import asyncio
import random
import json
import time
import logging
import os
import hashlib
from datetime import datetime
from faker import Faker
from pyvirtualdisplay import Display
from nodriver import start

# Logging Configuration
class BotLogger:
    def __init__(self):
        self.logger = logging.getLogger('RedditBot')
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # File Handler with Rotation
        file_handler = logging.handlers.RotatingFileHandler(
            'bot_operations.log',
            maxBytes=5*1024*1024,
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)

        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info("Logger initialized successfully")

logger = BotLogger().logger

# Core Components
class FingerprintGenerator:
    def __init__(self):
        self.faker = Faker()
        self.device_profiles = [
            {
                'name': 'Desktop_Windows',
                'type': 'desktop',
                'os': 'Windows 10',
                'resolutions': ['1920x1080', '2560x1440'],
                'user_agent_templates': [
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36'
                ],
                'fonts': ['Arial', 'Times New Roman', 'Verdana']
            },
            {
                'name': 'Mobile_Android',
                'type': 'mobile',
                'os': 'Android 13',
                'resolutions': ['1080x2340', '1440x3200'],
                'user_agent_templates': [
                    'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Mobile Safari/537.36'
                ],
                'fonts': ['Roboto', 'Noto Sans', 'Droid Sans']
            }
        ]

    def generate_fingerprint(self, proxy):
        profile = random.choice(self.device_profiles)
        chrome_version = f"{random.randint(115,125)}.0.{random.randint(1000,9999)}"
        
        return {
            'user_agent': random.choice(profile['user_agent_templates']).format(version=chrome_version),
            'resolution': random.choice(profile['resolutions']),
            'platform': profile['os'],
            'fonts': profile['fonts'],
            'device_type': profile['type'],
            'proxy': proxy,
            'chrome_version': chrome_version,
            'webgl_hash': hashlib.sha256(str(time.time()).encode()).hexdigest()[:16],
            'generated_at': datetime.utcnow().isoformat()
        }

class AccountManager:
    def __init__(self):
        self.accounts_file = 'accounts.json'
        self.accounts = self.load_or_create_accounts()

    def load_or_create_accounts(self):
        if not os.path.exists(self.accounts_file):
            logger.warning("Accounts file not found, creating default")
            default_accounts = [
                {
                    "id": f"acc_{x}",
                    "proxy": f"user:pass@192.168.1.{x}:8080",
                    "usage_count": 0,
                    "last_used": 0,
                    "status": "active"
                } for x in range(1, 6)
            ]
            self.save_accounts(default_accounts)
            return default_accounts
        
        with open(self.accounts_file, 'r') as f:
            return json.load(f)

    def get_available_account(self):
        now = time.time()
        valid = [acc for acc in self.accounts 
                if acc['usage_count'] < 5 
                and (now - acc['last_used']) > 1800
                and acc['status'] == 'active']
        return random.choice(valid) if valid else None

    def save_accounts(self, accounts=None):
        with open(self.accounts_file, 'w') as f:
            json.dump(accounts or self.accounts, f, indent=2)

class StealthUtils:
    @staticmethod
    async def human_interaction(page, element):
        try:
            start_x = random.randint(0, 300)
            start_y = random.randint(0, 300)
            target = await element.rect
            
            logger.info(f"Moving from ({start_x}, {start_y}) to ({target['x']}, {target['y']})")

            # Generate intermediate points
            steps = random.randint(15, 25)
            x_step = (target['x'] - start_x) / steps
            y_step = (target['y'] - start_y) / steps
            
            for i in range(steps):
                x = start_x + x_step * i + random.uniform(-5, 5)
                y = start_y + y_step * i + random.uniform(-5, 5)
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.05, 0.2))
            
            await page.mouse.click(target['x'], target['y'], delay=random.randint(100, 250))
            logger.debug("Click completed successfully")
            
        except Exception as e:
            logger.error(f"Interaction failed: {str(e)}")
            raise

    @staticmethod
    async def spoof_environment(page, fingerprint):
        try:
            logger.info("Applying environment spoofing")
            
            # Set user agent
            await page.cdp.send(
                "Network.setUserAgentOverride",
                userAgent=fingerprint['user_agent']
            )
            
            # Spoof WebGL
            await page.cdp.send(
                "Page.addScriptToEvaluateOnNewDocument",
                source=f"""
                HTMLCanvasElement.prototype.getContext = function(orig) {{
                    return function(type) {{
                        const ctx = orig.apply(this, [type]);
                        if(type === 'webgl') {{
                            const ext = ctx.getExtension('WEBGL_debug_renderer_info');
                            ctx.getParameter = function(param) {{
                                return param === ext.UNMASKED_RENDERER_WEBGL 
                                    ? '{fingerprint['webgl_hash']}' 
                                    : ctx.__proto__.getParameter(param);
                            }};
                        }}
                        return ctx;
                    }};
                }}(HTMLCanvasElement.prototype.getContext);
                """
            )
            
            # Remove automation flags
            await page.cdp.send(
                "Page.addScriptToEvaluateOnNewDocument",
                source="delete navigator.__proto__.webdriver;"
            )
            
            logger.debug("Environment spoofing completed")
            
        except Exception as e:
            logger.error(f"Spoofing failed: {str(e)}")
            raise

class RedditVoter:
    def __init__(self, account):
        self.account = account
        self.fingerprint = FingerprintGenerator().generate_fingerprint(account['proxy'])
        self.browser = None
        self.page = None

    async def initialize(self):
        try:
            logger.info(f"Initializing browser for account {self.account['id']}")
            
            # Start virtual display
            Display(visible=0, size=tuple(map(int, self.fingerprint['resolution'].split('x')))).start()
            
            # Launch browser
            self.browser = await start(
                browser_args=[
                    f'--proxy-server={self.account["proxy"]}',
                    '--disable-blink-features=AutomationControlled',
                    '--headless=new',
                    f'--user-agent={self.fingerprint["user_agent"]}'
                ]
            )
            
            self.page = await self.browser.new_page()
            await StealthUtils.spoof_environment(self.page, self.fingerprint)
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}")
            return False

    async def perform_vote(self, post_url):
        try:
            logger.info(f"Starting voting process on {post_url}")
            
            # Navigate to post
            await self.page.goto(post_url, wait_until='networkidle2')
            
            # Simulate human behavior
            await self._simulate_activity()
            
            # Find and click upvote
            upvote_button = await self.page.wait_for_selector('[data-click-id="upvote"]', timeout=15000)
            await StealthUtils.human_interaction(self.page, upvote_button)
            
            # Validate success
            await asyncio.sleep(2)
            is_voted = await self.page.evaluate('''() => {
                const btn = document.querySelector('[data-click-id="upvote"]');
                return btn && btn.getAttribute('aria-pressed') === 'true';
            }''')
            
            if is_voted:
                self.account['usage_count'] += 1
                self.account['last_used'] = time.time()
                logger.info("Vote successfully registered")
                return True
            
            logger.warning("Vote verification failed")
            return False
            
        except Exception as e:
            logger.error(f"Voting process failed: {str(e)}")
            return False
            
        finally:
            if self.browser:
                await self.browser.close()
            logger.info("Browser instance closed")

    async def _simulate_activity(self):
        """Simulate human-like browsing patterns"""
        actions = [
            self._random_scroll,
            self._random_mouse_movement,
            self._random_delay
        ]
        
        for _ in range(random.randint(3, 5)):
            await random.choice(actions)()

    async def _random_scroll(self):
        scroll_amount = random.randint(300, 800)
        await self.page.mouse.wheel(delta_y=scroll_amount)
        logger.debug(f"Scrolled {scroll_amount}px")
        await asyncio.sleep(random.uniform(0.5, 1.5))

    async def _random_mouse_movement(self):
        x = random.randint(0, 1920)
        y = random.randint(0, 1080)
        await self.page.mouse.move(x, y, steps=random.randint(15, 30))
        logger.debug(f"Moved mouse to ({x}, {y})")

    async def _random_delay(self):
        delay = random.normalvariate(3, 0.5)
        logger.debug(f"Delaying for {delay:.2f}s")
        await asyncio.sleep(delay)

class VotingOrchestrator:
    def __init__(self):
        self.account_manager = AccountManager()
        self.target_url = "https://www.reddit.com/r/test/comments/abc123"
        self.target_votes = 100

    async def run(self):
        logger.info(f"Starting voting campaign for {self.target_votes} votes")
        success_count = 0
        
        while success_count < self.target_votes:
            account = self.account_manager.get_available_account()
            if not account:
                logger.warning("No available accounts, waiting...")
                await asyncio.sleep(300)
                continue
            
            logger.info(f"Using account {account['id']}")
            voter = RedditVoter(account)
            
            if await voter.initialize():
                if await voter.perform_vote(self.target_url):
                    success_count += 1
                    logger.info(f"Progress: {success_count}/{self.target_votes}")
                    self.account_manager.save_accounts()
                
                await asyncio.sleep(random.randint(60, 120))
            else:
                account['status'] = 'error'
                self.account_manager.save_accounts()
        
        logger.info("Voting campaign completed successfully")

if __name__ == "__main__":
    try:
        logger.info("Reddit Voting System Starting")
        orchestrator = VotingOrchestrator()
        asyncio.run(orchestrator.run())
        logger.info("Reddit Voting System Shutting Down")
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}", exc_info=True)