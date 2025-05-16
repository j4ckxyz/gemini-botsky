#!/usr/bin/env python3
import os
import time
import logging
import requests
from dotenv import load_dotenv
from atproto import Client, models
from atproto.exceptions import AtProtocolError
from atproto_client.models.app.bsky.notification.list_notifications import (
    Params as ListNotificationsParams,
)
from atproto_client.models.app.bsky.feed.get_post_thread import (
    Params as GetPostThreadParams,
)

# Load environment
load_dotenv()
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
GPT_MODEL = "x-ai/grok-3-mini-beta"
MENTION_CHECK_INTERVAL_SECONDS = 30
NOTIFICATION_FETCH_LIMIT = 30

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def initialize_bluesky_client():
    if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
        logging.error("Bluesky credentials missing in environment.")
        return None
    try:
        client = Client()
        client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
        logging.info(f"Logged in as {BLUESKY_HANDLE}")
        return client
    except Exception as e:
        logging.error(f"Bluesky login failed: {e}")
        return None


def get_post_text(post):
    """Extract text from a post record."""
    if hasattr(post, "record") and hasattr(post.record, "text"):
        return post.record.text
    return ""


def fetch_thread_context(client, uri):
    """Fetch the thread context and return both thread history and most recent post."""
    try:
        params = GetPostThreadParams(uri=uri)
        thread_response = client.app.bsky.feed.get_post_thread(params=params)
        
        # Initialize empty lists for thread history
        thread_posts = []
        
        # Helper function to traverse the thread
        def traverse_thread(node):
            if hasattr(node, "parent") and node.parent:
                traverse_thread(node.parent)
            if hasattr(node, "post"):
                author = node.post.author.handle
                text = get_post_text(node.post)
                thread_posts.append(f"@{author}: {text}")
        
        # Start traversal from the current post
        traverse_thread(thread_response.thread)
        
        # Get the most recent post (last in thread)
        most_recent_post = thread_posts[-1] if thread_posts else ""
        
        # Join all posts into a single string for context
        thread_history = "\n".join(thread_posts)
        
        return thread_history, most_recent_post
    
    except Exception as e:
        logging.error(f"Error fetching thread: {e}")
        return "", ""


def get_openrouter_reply(thread_history, most_recent_post):
    prompt = f"""You are a useful Bluesky bot. Your task is to reply to the last message in the thread with a useful insight. Keep your response under 300 characters and type in the language of the thread. Do not include images, hashtags, or emojis.

Thread history:
{thread_history}

Most recent post to reply to:
{most_recent_post}"""

    headers = {
        ...
    }

    payload = {
        ...
    }

    try:
        ...
    except Exception as e:
        ...



def main():
    client = initialize_bluesky_client()
    if not client:
        return

    processed_uris = set()

    while True:
        try:
            params = ListNotificationsParams(limit=NOTIFICATION_FETCH_LIMIT)
            notifications = client.app.bsky.notification.list_notifications(
                params=params
            )

            for notif in notifications.notifications:
                if (
                    notif.uri in processed_uris
                    or notif.author.handle == BLUESKY_HANDLE
                    or notif.reason not in ["mention", "reply"]
                ):
                    continue

                thread_history, most_recent_post = fetch_thread_context(
                    client, notif.uri
                )

                if not most_recent_post:
                    continue

                reply_text = get_openrouter_reply(thread_history, most_recent_post)
                if not reply_text:
                    continue

                # Truncate if necessary
                reply_text = (
                    reply_text[:297] + "..."
                    if len(reply_text) > 300
                    else reply_text
                )

                # Create reply reference
                parent_ref = models.ComAtprotoRepoStrongRef.Main(
                    cid=notif.cid, uri=notif.uri
                )
                root_ref = parent_ref
                if hasattr(notif.record, "reply") and notif.record.reply:
                    root_ref = notif.record.reply.root

                # Send the reply
                client.send_post(
                    text=reply_text,
                    reply_to=models.AppBskyFeedPost.ReplyRef(
                        root=root_ref, parent=parent_ref
                    ),
                )

                processed_uris.add(notif.uri)
                logging.info(f"Replied to {notif.uri} with: {reply_text[:50]}...")

        except Exception as e:
            logging.error(f"Error in main loop: {e}")

        time.sleep(MENTION_CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
