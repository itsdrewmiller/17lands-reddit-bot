import os
import re
import time
import json
import praw
import requests
from difflib import get_close_matches

# List of expansions supported by 17Lands
SUPPORTED_EXPANSIONS = ['SNC'] # ['WOE', 'LTR', 'MOM', 'ONE', 'BRO', 'DMU', 'HBG', 'SNC', 'NEO', 'VOW', 'MID', 'AFR']

# Cache for card data and mapping
card_data_cache = {}
card_data_last_fetched = {}
card_expansion_mapping = {}
card_expansion_last_fetched = 0

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

    # Build initial card-expansion mapping
    build_card_expansion_mapping()
    global card_expansion_last_fetched
    card_expansion_last_fetched = time.time()

    # Regex pattern to find [[Card Name]] syntax, handling escaped characters
    pattern = re.compile(r'\[\[([^\[\]]+)\]\]')

    for comment in subreddit.stream.comments(skip_existing=False):
        try:
            # Skip own comments
            if comment.author == reddit.user.me():
                continue

            # Refresh card-expansion mapping every 24 hours
            if time.time() - card_expansion_last_fetched > 86400:
                build_card_expansion_mapping()
                card_expansion_last_fetched = time.time()

            # Remove backslashes from the comment body to handle escaped characters
            comment_body = comment.body.replace('\\', '')

            matches = pattern.findall(comment_body)
            if matches:
                reply_text = ''
                for card_name in matches:
                    expansions = get_card_expansions(card_name)
                    if expansions:
                        card_found = False
                        for expansion in expansions:
                            if expansion in SUPPORTED_EXPANSIONS:
                                # Fetch or get cached card data for the expansion
                                card_data = get_card_data(expansion)
                                if card_data:
                                    print(card_data)
                                    card_info = get_card_info(card_name, card_data)
                                    if card_info:
                                        alsa = card_info['avg_seen']
                                        gih_wr = card_info['ever_drawn_win_rate'] * 100
                                        reply_text += f"**{card_info['name']}** ({expansion})\n"
                                        reply_text += f"- ALSA: {alsa:.2f}\n"
                                        reply_text += f"- GIH WR: {gih_wr:.2f}%\n\n"
                                        card_found = True
                                        break  # Use the first matching expansion
                        if not card_found:
                            reply_text += f"Could not find data for card: {card_name}\n\n"
                    else:
                        reply_text += f"Could not find expansions for card: {card_name}\n\n"

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
                            time.sleep(10*60)
                        except Exception as e:
                            print(f"Failed to reply to comment {comment.id}: {e}")
            else:
                print(f"No matches found in comment {comment.id}")
        except Exception as e:
            print(f"Error processing comment {comment.id}: {e}")
            continue

def build_card_expansion_mapping():
    global card_expansion_mapping
    card_expansion_mapping = {}
    try:
        for expansion in SUPPORTED_EXPANSIONS:
            print(f"Fetching card names for expansion {expansion} from Scryfall...")
            url = f'https://api.scryfall.com/cards/search?order=set&q=e%3A{expansion.lower()}&unique=cards'
            has_more = True
            page = 1
            while has_more:
                response = requests.get(url)
                if response.status_code != 200:
                    print(f"Error fetching cards for expansion {expansion}: {response.status_code}")
                    break
                data = response.json()
                for card in data['data']:
                    card_name = card['name'].lower()
                    if card_name not in card_expansion_mapping:
                        card_expansion_mapping[card_name] = set()
                    card_expansion_mapping[card_name].add(expansion)
                has_more = data.get('has_more', False)
                url = data.get('next_page', '')
                page += 1
        print("Built card-expansion mapping.")
    except Exception as e:
        print(f"Error building card-expansion mapping: {e}")

def get_card_expansions(card_name):
    card_name_lower = card_name.lower()
    if card_name_lower in card_expansion_mapping:
        return card_expansion_mapping[card_name_lower]
    else:
        # Fuzzy matching if exact match not found
        matches = get_close_matches(card_name_lower, card_expansion_mapping.keys(), n=1, cutoff=0.8)
        if matches:
            return card_expansion_mapping[matches[0]]
        else:
            return None

def get_card_data(expansion):
    current_time = time.time()
    # Refresh card data every 12 hours
    if expansion in card_data_cache and (current_time - card_data_last_fetched[expansion] < 43200):
        return card_data_cache[expansion]
    else:
        data = fetch_card_data(expansion)
        if data:
            card_data_cache[expansion] = data
            card_data_last_fetched[expansion] = current_time
        return data

def fetch_card_data(expansion, format='PremierDraft'):
    url = 'https://www.17lands.com/card_ratings/data'
    params = {
        'expansion': expansion,
        'format': format
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        card_data = {card['name'].lower(): card for card in data}
        print(f"Fetched latest card data for expansion {expansion} from 17Lands.")
        return card_data
    except Exception as e:
        print(f"Error fetching card data for expansion {expansion}: {e}")
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
