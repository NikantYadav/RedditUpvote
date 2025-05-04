import praw
import time
import logging
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class UpvoteBot:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent="ResearchBot/1.0 (by YOUR_TEAM_NAME)",
            username=os.getenv("REDDIT_USERNAME"),
            password=os.getenv("REDDIT_PASSWORD")
        )
        self.subreddit_name = "test"  # Target subreddit for testing
        self.post_limit = 10  # Number of posts to process per run
        self.dry_run = True  # Set to False to enable upvoting

    def _validate_permissions(self):
        """Ensure the bot account has necessary permissions."""
        try:
            # Check if authenticated user can upvote
            user = self.reddit.user.me()
            logging.info(f"Authenticated as: {user}")
        except Exception as e:
            logging.error(f"Authentication failed: {e}")
            raise

    def _process_post(self, post):
        """Upvote a post if criteria are met."""
        try:
            # Skip self-upvotes to avoid vote manipulation
            if post.author == self.reddit.user.me():
                return

            # Add custom logic here (e.g., keyword matching)
            if not self.dry_run:
                post.upvote()
                logging.info(f"Upvoted: {post.title}")
            else:
                logging.info(f"[Dry Run] Would upvote: {post.title}")
        except praw.exceptions.APIException as e:
            logging.error(f"API Error: {e}")

    def run(self):
        """Main execution loop."""
        self._validate_permissions()
        subreddit = self.reddit.subreddit(self.subreddit_name)

        while True:
            try:
                # Process new/hot posts (modify as needed)
                for post in subreddit.hot(limit=self.post_limit):
                    self._process_post(post)

                # Respect rate limits (600 requests per 10 minutes)
                time.sleep(60)  # Adjust based on post_limit

            except Exception as e:
                logging.error(f"Critical error: {e}")
                time.sleep(300)  # Backoff on critical failure

if __name__ == "__main__":
    bot = UpvoteBot()
    bot.run()
