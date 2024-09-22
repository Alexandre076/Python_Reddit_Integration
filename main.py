import requests
import os
import time
import sys
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, select, Column, Integer, String, Float, inspect
from logger_setup import setup_logging, log_and_print

# Set up logging
setup_logging()

# Check if the database exists
db_path = os.path.join('db', 'reddit_tracker.db')

log_and_print(f"Checking if database '{db_path}' exists...")
db_exists = os.path.exists(db_path)

# Database setup
engine = create_engine(f'sqlite:///{db_path}')
metadata = MetaData()

# Define the table schema (even if it exists, this doesn't create it yet)
posts_table = Table(
    'posts_tracker', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('subreddit', String, nullable=False),
    Column('title', String, nullable=False),
    Column('author', String, nullable=False),
    Column('created_utc', Float, nullable=False),
    Column('created_date', String, nullable=False)  # Readable date format
)

# If the database exists, check if the table already exists
try:
    if db_exists:
        inspector = inspect(engine)
        table_exists = inspector.has_table('posts_tracker')
    else:
        table_exists = False

    # If the table doesn't exist, create it
    if not table_exists:
        metadata.create_all(engine)  # This will create the table if it doesn't exist
        log_and_print("Table 'posts_tracker' created.")
    else:
        log_and_print("Table 'posts_tracker' already exists.")
except Exception as e:
    log_and_print(f"Error checking/creating table: {e}",'error')

# Function to get subreddit posts paginated

def get_subreddit_posts_paginated(subreddit, last_timestamp):
    """
    Retrieves paginated posts from a specified subreddit.

    Args:
        subreddit (str): The name of the subreddit.
        last_timestamp (float): The timestamp of the last processed post.

    Returns:
        List[Dict[str, Union[str, float]]]: A list of dictionaries representing the new posts.
            Each dictionary contains the following keys:
                - 'title' (str): The title of the post.
                - 'author' (str): The author of the post.
                - 'created_utc' (float): The creation timestamp of the post.

    Raises:
        requests.exceptions.RequestException: If there is a network-related error.
        Exception: If there is an unexpected error.

    """
    url = f"https://www.reddit.com/r/{subreddit}.json"
    headers = {'User-agent': 'Mozilla/5.0'}
    
    after = None
    new_posts = []
    retry_count = 0  # For exponential backoff

    while True:
        try:
            params = {'after': after} if after else {}
            response = requests.get(url, headers=headers, params=params)

            # Check for rate limiting
            if response.status_code == 429:
                # Get the wait time from headers, if available
                reset_time = int(response.headers.get('X-Ratelimit-Reset', 60))  # Default to 60 seconds
                log_and_print(f"Rate limit exceeded. Waiting for {reset_time} seconds...")
                time.sleep(reset_time)
                continue  # Retry after waiting

            # Check for throttling or server overload (HTTP 5xx errors)
            if response.status_code >= 500:
                retry_count += 1
                wait_time = min(2 ** retry_count, 60)  # Exponential backoff, max 60 seconds
                log_and_print(f"Server error, retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue  # Retry the request

            # Reset retry count if a request succeeds
            retry_count = 0
            response.raise_for_status()  # Raise any other HTTP errors

            # Parse the response data
            data = response.json()['data']
            posts = data['children']
            after = data['after']  # Get the next page's after value

            for post in posts:
                created_utc = post['data']['created_utc']
                if created_utc > last_timestamp:
                    new_posts.append({
                        'title': post['data']['title'],
                        'author': post['data']['author'],
                        'created_utc': created_utc
                    })
                else:
                    # Stop if posts are older than the last processed timestamp
                    return new_posts
            
            #Monitor Rate Limit Headers (Proactive Approach)
            remaining_requests = int(response.headers.get('X-Ratelimit-Remaining', 1))
            log_and_print(f"Remaining requests: {remaining_requests}")

            if remaining_requests <= 0:
                reset_time = int(response.headers.get('X-Ratelimit-Reset', 60))
                print(f"Rate limit exceeded. Waiting for {reset_time} seconds...")
                time.sleep(reset_time)

            # Stop if there are no more pages
            if not after:
                break

        except requests.exceptions.RequestException as e:
            # Handle network-related errors (e.g., connection errors, timeouts)
            log_and_print(f"Request error: {e}",'error')
            retry_count += 1
            wait_time = min(2 ** retry_count, 60)  # Exponential backoff
            log_and_print(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            continue  # Retry the request after the wait time

        except Exception as e:
            # Handle any other unforeseen errors
            log_and_print(f"An unexpected error occurred: {e}",'error')
            break

        finally:
            # This block will run whether or not an exception occurs
            # Can be used to perform cleanup if needed
            log_and_print(f"Finished handling page after: {after}")

    return new_posts

# Function to get the last processed timestamp from the database
def get_last_timestamp(subreddit):
    """
    Retrieves the most recent created_utc value for a specified subreddit from the database.

    Args:
        subreddit (str): The name of the subreddit.

    Returns:
        float: The most recent created_utc value for the specified subreddit. Returns 0 if there are no records.

    Raises:
        Exception: If there is an error retrieving the last timestamp.
    """
    try:
        with engine.connect() as conn:
            # Select the most recent created_utc for the specified subreddit
            query = (
                select(posts_table.c.created_utc)
                .where(posts_table.c.subreddit == subreddit)
                .order_by(posts_table.c.created_utc.desc())
                .limit(1)
            )
            result = conn.execute(query).fetchone()
            readable_time = datetime.utcfromtimestamp(result[0]).strftime('%Y-%m-%d %H:%M:%S')
            

            log_and_print(f"Last processed timestamp: {result[0]}, {readable_time}",'info')
            return result[0] if result else 0
    except Exception as e:
        log_and_print(f"Error getting last timestamp for subreddit {subreddit}: {e}. This happens while running the code for the first time as there's no data in the database.",'error')
        return 0

# Function to save new posts into the database
def save_new_posts(new_posts, subreddit):
    """
    Saves new posts to the database.

    Args:
        new_posts (List[Dict[str, Any]]): A list of dictionaries representing the new posts.
        subreddit (str): The subreddit to which the posts belong.

    Returns:
        None

    Raises:
        Exception: If there is an error saving the new posts.

    """
    try:
        with engine.connect() as conn:
            for post in new_posts:
                # Convert Unix timestamp to human-readable format
                readable_time = datetime.utcfromtimestamp(post['created_utc']).strftime('%Y-%m-%d %H:%M:%S')
            

                insert_query = posts_table.insert().values(
                    subreddit=subreddit,
                    title=post['title'],
                    author=post['author'],
                    created_utc=post['created_utc'],
                    created_date=readable_time
                )
                conn.execute(insert_query)
            conn.commit()  # Ensure transaction is committed
            log_and_print(f"Inserted {len(new_posts)} posts into the database")  # Debug print
    except Exception as e:
        log_and_print(f"Error saving new posts for subreddit {subreddit}: {e}")

# Main function
def main(subreddits):
    """
    Runs the main function that processes and saves new posts from multiple subreddits.

    This function iterates over a list of subreddits, retrieves the last processed timestamp
    for each subreddit using the `get_last_timestamp` function, and then retrieves new posts
    from the subreddit using the `get_subreddit_posts_paginated` function. If new posts are
    found, they are processed and saved to the database using the `save_new_posts` function.
    The last processed timestamp is also updated with the latest post time.

    Parameters:
    - None

    Returns:
    - None

    Raises:
    - Exception: If there is an error processing a subreddit.
    """
    #subreddits = ['computerscience', 'pics', 'brazil']

    for subreddit in subreddits:
        try:
            log_and_print(f"Processing subreddit: {subreddit}")
            
            last_timestamp = get_last_timestamp(subreddit)
            #log_and_print(f"Last processed timestamp: {last_timestamp}")

            new_posts = get_subreddit_posts_paginated(subreddit, last_timestamp)
            log_and_print(f"Found {len(new_posts)} new posts in {subreddit}")
            
            # Process and save new posts
            if new_posts:
                log_and_print(f"saving new posts for subreddit: {subreddit}")
                save_new_posts(new_posts, subreddit)
                
            else:
                log_and_print(f"No new posts in {subreddit}")
                
        except Exception as e:
            log_and_print(f"Error processing subreddit {subreddit}: {e}")

    log_and_print("Finished processing all subreddits")
            
if __name__ == "__main__":
    # Get subreddit list from command-line arguments
    subreddits = sys.argv[1].split(',') if len(sys.argv) > 1 else ['computerscience', 'pics', 'brazil']
    main(subreddits)
