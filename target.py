import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from vote import upvote_post  # Ensure this is your actual upvote function
import os
# File to store the account state
STATE_FILE = 'account_state.json'

logging.basicConfig(
    level=logging.DEBUG,  
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler('reddit_stealth.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_state():
    """Load account state from file."""
    try:
        with open(STATE_FILE, 'r') as file:
            content = file.read().strip()
            if not content:
                logger.warning(f"{STATE_FILE} is empty. Initializing with empty state.")
                save_state({})
                return {}
            return json.loads(content)
    except FileNotFoundError:
        logger.info(f"{STATE_FILE} not found, creating a new one.")
        save_state({})
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {STATE_FILE}: {e}")
        save_state({})
        return {}


def save_state(state):
    """Save account state to file."""
    with open(STATE_FILE, 'w') as file:
        json.dump(state, file, default=str, indent=4)

def load_accounts(file_path='profiles/accounts.json'):
    try:
        logger.info(f"Loading accounts from: {os.path.abspath(file_path)}")
        
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {os.path.abspath(file_path)}")
            return {}

        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            if not raw_content.strip():
                logger.error("File is empty!")
                return {}
                
            return json.loads(raw_content)
            
    except Exception as e:
        logger.error(f"Critical error: {str(e)}", exc_info=True)
        return {}
  


async def orchestrate_batches(
    post_url: str,
    account_ids: list,
    votes_per_min: int,
    total_votes: int,
    account_data: dict,
    max_daily_per_account: int = 5,
    min_gap_minutes: int = 30
):
    """
    Orchestrate upvotes in batches with enhanced account-wise logging.
    Keeps account state persistent across requests.
    """
    
    state = load_state()
    last_upvote = {acc: datetime.fromisoformat(state.get(str(acc), {}).get('last_upvote', '1970-01-01T00:00:00')) for acc in account_ids}
    daily_count = {acc: state.get(str(acc), {}).get('daily_count', 0) for acc in account_ids}
    votes_done = 0
    min_gap = timedelta(minutes=min_gap_minutes)

    # Log initial account states
    logger.debug("Initial account states:")
    for acc in account_ids:
        last = last_upvote[acc].strftime('%Y-%m-%d %H:%M') if last_upvote[acc] != datetime.min else "Never"
        logger.debug(f"Account {acc:2}: Last upvote: {last}, Daily uses: {daily_count[acc]}/{max_daily_per_account}")

    logger.info(f"Starting orchestrated batches: {total_votes} votes at {votes_per_min}/min")
    
    while votes_done < total_votes:
        batch_size = min(votes_per_min, total_votes - votes_done)
        now = datetime.now()
        
        # Find eligible accounts
        eligible = [
            acc for acc in account_ids
            if (now - last_upvote[acc] >= min_gap) 
            and (daily_count[acc] < max_daily_per_account)
        ]
        
        # Log eligibility check
        logger.debug(f"Eligibility check at {now.strftime('%H:%M:%S')}:")
        for acc in account_ids:
            gap_ok = now - last_upvote[acc] >= min_gap
            daily_ok = daily_count[acc] < max_daily_per_account
            status = "ELIGIBLE" if gap_ok and daily_ok else "INELIGIBLE"
            last = last_upvote[acc].strftime('%H:%M') if last_upvote[acc] != datetime.min else "Never"
            logger.debug(f"Account {acc:2}: {status} (Last: {last}, Uses: {daily_count[acc]}/{max_daily_per_account}, Gap OK: {gap_ok})")

        if not eligible:
            logger.warning("No eligible accounts available, waiting...")
            await asyncio.sleep(60)
            continue
            
        # Select batch
        batch = random.sample(eligible, min(batch_size, len(eligible)))
        logger.info(f"Selected batch of {len(batch)} accounts: {batch}")
        
        # Log batch details
        logger.debug("Batch account details:")
        for acc in batch:
            last = last_upvote[acc].strftime('%H:%M') if last_upvote[acc] != datetime.min else "Never"
            logger.debug(f"Account {acc:2}: Last upvote: {last}, Daily uses: {daily_count[acc]}/{max_daily_per_account}")

        # Process batch
        logger.info(f"Starting upvote batch processing")
        tasks = []
        for acc in batch:
            try:
                account = account_data[str(acc)]
                print(account)
                proxy_config = account.get('proxy', {})
                logger.debug(proxy_config)
                tasks.append(
                    upvote_post(
                        acc,
                        post_url,
                        proxy_config=proxy_config
                    )
                )
            except KeyError:
                logger.error(f"Account {acc} not found in account data")

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results with detailed logging
        success_count = 0
        for acc, result in zip(batch, results):
            current_time = datetime.now()
            if isinstance(result, Exception):
                logger.error(f"Account {acc:2} | ERROR: {str(result)}")
            else:
                success_count += 1
                last_upvote[acc] = current_time
                daily_count[acc] += 1
                votes_done += 1
                next_available = (current_time + min_gap).strftime('%H:%M')
                logger.info(
                    f"Account {acc:2} | SUCCESS | "
                    f"Daily uses: {daily_count[acc]}/{max_daily_per_account} | "
                    f"Next available: {next_available}"
                )

        logger.info(f"Batch completed: {success_count} successes, {len(batch)-success_count} failures")
        logger.info(f"Total progress: {votes_done}/{total_votes} ({votes_done/total_votes:.1%})")

        # Save the updated state to the file after each batch
        state = {
            str(acc): {
                'last_upvote': last_upvote[acc].isoformat(),
                'daily_count': daily_count[acc]
            } for acc in account_ids
        }
        save_state(state)

        # Wait for next batch
        elapsed = (datetime.now() - now).total_seconds()
        if elapsed < 60:
            wait_time = 60 - elapsed
            logger.debug(f"Sleeping {wait_time:.1f}s until next batch")
            await asyncio.sleep(wait_time)

    logger.info("All batches completed successfully")


if __name__ == "__main__":
    
    post_url = "https://www.reddit.com/r/AppearanceAdvice/comments/1kpcn8p/got_called_fat_and_unattractive_what_can_i_do_to/"
    votes_per_min = 2
    total_votes = 4

    account_ids = range(1, 7)
    account_data = load_accounts('profiles/accounts.json')
    try:
        logger.info("Starting batch upvoting session")
        asyncio.run(
            orchestrate_batches(
                post_url=post_url,
                account_ids=account_ids,
                votes_per_min=votes_per_min,
                total_votes=total_votes,
                account_data=account_data
            )
        )

        logger.info("Batch upvoting session completed successfully")
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Batch upvoting session failed: {str(e)}")
    finally:
        logger.info("Program execution ended")
