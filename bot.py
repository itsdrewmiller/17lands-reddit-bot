import os
import re
import time
import json
import threading
import praw
import requests
from difflib import get_close_matches

# List of expansions supported by 17Lands
SUPPORTED_EXPANSIONS = ['TRK','FRA','HOB','MSH','SOS','TMT','ECL','TLA','OM1','SPM','EOE','FIN','TDM','DFT','PIO','FDN','DSK','KTK','XLN','RIX','DOM','GRN','RNA','WAR','ELD','THB','IKO','ZNR','KHM','STX','AFR','MID','VOW','NEO','SNC','DMU','BRO','ONE','MOM','MAT','WOE','LCI','MKM','OTJ','BLB','LTR','MH3','HBG','M21','M20','M19']

# Cache for card data and mapping
card_data_cache = {}
card_data_last_fetched = {}
card_expansion_mapping = {}

# Scryfall rate limiting (Scryfall asks for 50
# and a descriptive User-Agent; without them it returns 429s / blocks)
SCRYFALL_MIN_INTERVAL = 0.15

_scryfall_session = requests.Session()
_scryfall_session.headers.update({
    'User-Agent': 'lrcast-17lands-bot/1.0 (conom)',
    'Accept': 'application/json',
})
_scryfall_last_request = 0.0
_scryfall_lock = threading.Lock()

def main():
    # Set up Reddit instance using environment variables
    reddit = praw.Reddit(
        client_id=os.environ['REDDIT_CLIENT_ID'],
        client_secret=os.environ['REDDIT_CLIENT'],
        user_agent=os.environ['REDDIT_USER_AGENT'],
        username=os.environ['REDDIT_USERNAME'],
        password=os.environ['REDDIT_PASSWORD']
    )

    subreddit = reddit.subreddit('lrcast')

    # Build initial card-expansion mapping
    build_card_expansion_mapping()

    # Refresh the mapping daily on a dedicated thread so the
    # rebuild never blocks the comment/submiss
    refresher_thread = threading.Thread(target=mapping_refresher, daemon=True)
    refresher_thread.start()

    # Start threads for both comments and subm
    comment_thread = threading.Thread(target=stream_comments, args=(reddit, subreddit), daemon=True)
    submission_thread = threading.Thread(targe=(reddit, subreddit), daemon=True)

    comment_thread.start()
    submission_thread.start()

    # Keep main thread alive
    while True:
        time.sleep(60)

def stream_comments(reddit, subreddit):
    """Monitor comment stream for card referen
    pattern = re.compile(r'\[\[([^\[\]]+)\]\]')

    for comment in subreddit.stream.comments(skip_existing=True):
        try:
            # Skip own comments
            if comment.author == reddit.user.m
                continue

            # Remove backslashes to handle escaped characters
            text = comment.body.replace('\\',
            print(f"Comment: {text}")

            reply_text = process_text_for_cards(text, pattern)
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
                        comment.reply(reply_te
                        print(f"Replied to comment {comment.id}")
                        time.sleep(10*60)
                    except Exception as e:
                        print(f"Failed to repl {e}")
        except Exception as e:
            print(f"Error processing comment {
            continue

def stream_submissions(reddit, subreddit):
    """Monitor submission stream for card refe
    pattern = re.compile(r'\[\[([^\[\]]+)\]\]')

    for submission in subreddit.stream.submissions(skip_existing=True):
        try:
            # Skip own submissions
            if submission.author == reddit.use
                continue

            # Check both title and selftext, remove backslashes
            text = (submission.title + " " + ().replace('\\', '')
            print(f"Submission: {text}")

            reply_text = process_text_for_cards(text, pattern)
            if reply_text:
                # Check if we have already replied
                replied = False
                submission.comments.replace_more(limit=0)
                for comment in submission.comm
                    if comment.author == reddit.user.me():
                        replied = True
                        break
                if not replied:
                    try:
                        submission.reply(reply
                        print(f"Replied to submission {submission.id}")
                        time.sleep(10*60)
                    except Exception as e:
                        print(f"Failed to repln.id}: {e}")
        except Exception as e:
            print(f"Error processing submissio
            continue

def mapping_refresher():
    """Rebuild the card-expansion mapping ever
    while True:
        time.sleep(86400)
        build_card_expansion_mapping()

def process_text_for_cards(text, pattern):
    """Process text and return reply with card""
    matches = pattern.findall(text)
    if not matches:
        return None

    print(f"Found card names: {matches}")
    reply_text = ''

    for card_name in matches:
        expansions = get_card_expansions(card_name)
        if expansions:
            card_found = False
            for expansion in expansions:
                if expansion in SUPPORTED_EXPANSIONS:
                    card_data = get_card_data(
                    if card_data:
                        card_info = get_card_i
                        if card_info:
                            print(f"Found dataexpansion: {expansion}")
                            alsa = card_info['avg_seen']
                            gih_wr = card_info100
                            color = card_info['color'] or 'C'
                            rarity = card_info
                            card_id = card_info['mtga_id']
                            lands_link =f"https://www.17lands.com/card_data/details?card_id={card_id}&expansion={expansion}"
                            reply_text += f"[{_link}) {color}-{rarity} ({expansion}); "
                            reply_text += f"ALSA: {alsa:.2f}; GIH WR: {gih_wr:.2f}%  \n"
                            card_found = True
                            break
                        else:
                            print(f"Could not find data for card: {card_name} in expansion: {expansion}")
                    else:
                        print(f"Could not find card data for expansion: {expansion}")
                else:
                    print(f"Expansion {expansion} not supported by 17Lands.")
            if not card_found:
                print(f"Could not find data for card: {card_name}\n\n")
        else:
            print(f"Could not find expansions for card: {card_name}\n\n")

    if reply_text:
        reply_text += f"(data sourced from 17l\n\n"

    return reply_text if reply_text else None

def scryfall_get(url, max_retries=3):
    """GET from Scryfall, enforcing a minimum interval between requests
    and retrying on 429 responses."""
    global _scryfall_last_request
    response = None
    for attempt in range(max_retries + 1):
        with _scryfall_lock:
            wait = SCRYFALL_MIN_INTERVAL - (time.time() - _scryfall_last_request)
            if wait > 0:
                time.sleep(wait)
            _scryfall_last_request = time.time
        response = _scryfall_session.get(url, timeout=30)
        if response.status_code == 429:
            retry_after = float(response.headers.get('Retry-After', 2 ** attempt))
            print(f"Scryfall rate limited, sle
            time.sleep(retry_after)
            continue
        return response
    return response

def build_card_expansion_mapping():
    global card_expansion_mapping
    new_mapping = {}
    for expansion in SUPPORTED_EXPANSIONS:
        # Per-expansion try so one bad set can
        try:
            print(f"Fetching card names for excryfall...")
            url = f'https://api.scryfall.com/cards/search?order=set&q=e%3A{expansion.lower()}&unique=cards'
            while url:
                response = scryfall_get(url)
                if response.status_code != 200
                    print(f"Error fetching cards for expansion {expansion}: {response.status_code}")
                    break
                data = response.json()
                for card in data['data']:
                    card_name = card['name'].lower()
                    sets = new_mapping.setdefa
                    if expansion not in sets:
                        sets.append(expansion)
                url = data.get('next_page') if data.get('has_more') else None
        except Exception as e:
            print(f"Error fetching expansion {expansion}: {e}")
    if new_mapping:
        # Atomic swap: streams keep reading the old mapping until the
        # new one is fully built, and a failed
        card_expansion_mapping = new_mapping
        print(f"Built card-expansion mapping (")
    else:
        print("Card-expansion mapping build pristing mapping.")

def get_card_expansions(card_name):
    # Local reference so the daily refresh can't swap the dict out mid-lookup
    mapping = card_expansion_mapping
    card_name_lower = card_name.lower()
    result = mapping.get(card_name_lower)
    if result:
        return result
    # Fuzzy matching if exact match not found
    matches = get_close_matches(card_name_lowetoff=0.8)
    if matches:
        return mapping[matches[0]]
    return None

def get_card_data(expansion):
    current_time = time.time()
    # Refresh card data every 12 hours
    if expansion in card_data_cache and (curreetched[expansion] < 43200):
        return card_data_cache[expansion]
    else:
        data = fetch_card_data(expansion)
        if data:
            card_data_cache[expansion] = data
            card_data_last_fetched[expansion]
        return data

def fetch_card_data(expansion, format='PremierDraft'):
    url = 'https://www.17lands.com/card_rating
    params = {
        'expansion': expansion,
        'format': format,
        'start_date': '2000-01-01'
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        card_data = {card['name'].lower(): card for card in data}
        print(f"Fetched latest card data for e17Lands.")
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
        matches = get_close_matches(card_name_=1, cutoff=0.8)
        if matches:
            return card_data[matches[0]]
        else:
            return None

if __name__ == '__main__':
    main()
