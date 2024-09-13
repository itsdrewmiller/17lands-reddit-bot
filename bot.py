import os
import re
import time
import praw
import requests
from difflib import get_close_matches

def main():
    # Set up Reddit instance using environment variables
    reddit = praw.Reddit(
        client_id=os.environ['REDDIT_CLIENT_ID'],
        client_secret=os.environ['REDDIT_CLIENT_SECRET'],
        user_agent=os.environ['REDDIT_USER_AGENT'],
        username=os.environ['REDDIT_USERNAME'],
        password=os.environ['REDDIT_PASSWORD']
    )

    subreddit = reddit.subreddit('17lands')

    # Fetch initial card data
    card_data = fetch_card_data()
    card_data_last_fetched = time.time()

    # Regex pattern to find [[Card Name]] syntax
    pattern = r'\\\[\\\[([^\[\]]+)\\\]\\\]'

    for comment in subreddit.stream.comments(skip_existing=False):
        print(comment.body)
        try:
            # Skip own comments
            if comment.author == reddit.user.me():
                continue

            # Refresh card data every 10 minutes
            if time.time() - card_data_last_fetched > 600:
                card_data = fetch_card_data()
                card_data_last_fetched = time.time()

            matches = re.findall(pattern, comment.body)
            if matches:
                reply_text = ''
                for card_name in matches:
                    card_info = get_card_info(card_name, card_data)
                    if card_info:
                        alsa = card_info['avg_seen']
                        gih_wr = card_info['ever_drawn_win_rate'] * 100
                        reply_text += f"**{card_info['name']}**\n"
                        reply_text += f"- ALSA: {alsa:.2f}\n"
                        reply_text += f"- GIH WR: {gih_wr:.2f}%\n\n"
                    else:
                        reply_text += f"Could not find data for card: {card_name}\n\n"

                if reply_text:
                    # Check if we have already replied
                    replied = False
                    comment.refresh()
                    for reply in comment.replies:
                        if reply.author == reddit.user.me():
                            replied = True
                            break
                    if not replied:
                        try:
                            comment.reply(reply_text)
                            print(f"Replied to comment {comment.id}")
                            # Sleep to respect rate limits
                            time.sleep(10)
                        except Exception as e:
                            print(f"Failed to reply to comment {comment.id}: {e}")
        except Exception as e:
            print(f"Error processing comment {comment.id}: {e}")
            continue

def fetch_card_data():
    url = 'https://www.17lands.com/card_ratings/data'
    try:
        response = requests.get(url)
        data = response.json()
        card_data = {card['name'].lower(): card for card in data}
        print("Fetched latest card data from 17Lands.")
        return card_data
    except Exception as e:
        print(f"Error fetching card data: {e}")
        return {}

def get_card_info(card_name, card_data):
    card_name_lower = card_name.lower()
    if card_name_lower in card_data:
        return card_data[card_name_lower]
    else:
        # Fuzzy matching if exact match not found
        matches = get_close_matches(card_name_lower, card_data.keys(), n=1, cutoff=0.8)
        if matches:
            return card_data[matches[0]]
        else:
            return None

if __name__ == '__main__':
    main()
