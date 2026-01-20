import os
import re
import time

import openai
from dotenv import load_dotenv
from langdetect import detect

# Load environment variables
load_dotenv()

# Get OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = None
if OPENAI_API_KEY:
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
else:
    print("WARNING: OPENAI_API_KEY not found in environment variables")


def translate(text, target="en"):
    """
    Translates text to English using OpenAI's GPT-5 mini

    Args:
        text (str): Text to translate
        target (str): Target language code (default: "en" for English)

    Returns:
        str: Translated text or original text if translation fails
    """
    start_time = time.time()
    print(f"TRANSLATE: Starting translation of '{text[:30]}...'")

    # Check if text is empty
    if not text or not text.strip():
        print("DEBUG: Empty text, returning")
        return None

    # Skip translation only for English
    # First check if it's a link to avoid language detection errors
    if is_link_only(text):
        print("DEBUG: Text is a link, skipping language detection")
        return None

    # Check for common English words first (before langdetect)
    common_english_words = {
        "hello",
        "hi",
        "hey",
        "bye",
        "ok",
        "yes",
        "no",
        "thanks",
        "please",
        "lol",
        "lmao",
        "good",
        "bad",
        "nice",
        "cool",
        "awesome",
        "great",
        "wow",
        "omg",
        "wtf",
        "idk",
        "what",
        "when",
        "where",
        "why",
        "how",
        "who",
        "this",
        "that",
        "these",
        "those",
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "her",
        "was",
        "one",
        "our",
        "out",
        "day",
        "get",
        "has",
        "him",
        "his",
        "how",
        "its",
        "may",
        "new",
        "now",
        "old",
        "see",
        "two",
        "way",
        "who",
        "boy",
        "did",
        "didnt",
        "let",
        "put",
        "say",
        "she",
        "too",
        "use",
    }

    text_clean = text.lower().strip()
    words = text_clean.split()

    # Check if most words are common English words (for all message lengths)
    if words:
        english_word_ratio = sum(
            1 for word in words if word in common_english_words
        ) / len(words)
        if english_word_ratio > 0.6:
            print("DEBUG: Text with mostly common English words, returning None")
            return None

    # Use langdetect to determine if text needs translation (only if common words check didn't catch it)
    try:
        detected_lang = detect(text)
        if detected_lang in ["en"]:
            print(
                f"DEBUG: Text is detected as English ({detected_lang}), returning None"
            )
            return None
        else:
            print(
                f"DEBUG: Text is detected as {detected_lang}, proceeding with translation"
            )
    except Exception as e:
        print(f"DEBUG: Language detection error: {e}, proceeding with translation")
        # If language detection fails, proceed with translation

    print("DEBUG: Translating text (assumed to be Swiss German dialect)")

    if not OPENAI_API_KEY:
        print("DEBUG: OpenAI API key not available, returning original text")
        return text

    if target != "en":
        print(f"DEBUG: Unsupported target language: {target}, defaulting to English")
        target = "en"

    try:
        # Create a system prompt for translating Portuguese or Swiss German to English
        system_prompt = "Translate non-English text to English. For English/slang (jk, gg, lol, etc.), return unchanged. Only return translation or original text."
        print(f"DEBUG: System prompt: {system_prompt}")

        # Call OpenAI API
        if not client:
            print("DEBUG: OpenAI client not initialized")
            return text

        print("DEBUG: Calling OpenAI API...")
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            max_completion_tokens=1000,  # Adjust based on expected message length
        )

        # Extract and return the translated text
        if response and response.choices and response.choices[0].message.content:
            translated_text = response.choices[0].message.content.strip()
            elapsed_time = time.time() - start_time
            print(
                f"TRANSLATE: Completed in {elapsed_time:.2f}s - '{translated_text[:50]}...'"
            )
            return translated_text
        else:
            print("DEBUG: No choices in response")
            return text

    except Exception as e:
        print(f"DEBUG: Translation error: {e}")
        import traceback

        traceback.print_exc()
        return text  # Return original text if translation fails


def is_link_only(text):
    """
    Check if message contains only a link

    Args:
        text (str): The message text to check

    Returns:
        bool: True if message contains only a link
    """
    print(f"DEBUG: is_link_only() called with: '{text[:30]}...'")
    # Remove common whitespace
    text = text.strip()

    # Common URL patterns
    url_pattern = re.compile(
        r"^https?:\/\/[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$"
    )

    # Discord attachment pattern
    discord_attachment_pattern = re.compile(
        r"^https?:\/\/(?:cdn\.)?discord(?:app)?\.com\/attachments\/\d+\/\d+\/[^ ]+$"
    )

    result = bool(url_pattern.match(text) or discord_attachment_pattern.match(text))
    print(f"DEBUG: is_link_only() result: {result}")
    return result


def translate_message_with_links(text, target="en"):
    """
    Translate a message that may contain links

    If message contains only a link, returns None (message is skipped)
    If message contains text with links, translates only the text parts
    If message is in English, returns None (message is skipped)

    Args:
        text (str): Message text that may contain links
        target (str): Target language code (default: "en")

    Returns:
        str | None: Translated message with original links preserved, or None if no translation needed
    """
    print(f"DEBUG: translate_message_with_links() called with: '{text[:50]}...'")

    # If it's just a link, skip entirely
    if is_link_only(text):
        print("DEBUG: Message is link only, skipping")
        return None

    # Pattern to find URLs in the text
    url_pattern = re.compile(
        r"(https?:\/\/[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)|https?:\/\/(?:cdn\.)?discord(?:app)?\.com\/attachments\/\d+\/\d+\/[^ ]+)"
    )

    # Split the text into parts (links and non-links)
    parts = []
    last_end = 0

    for match in url_pattern.finditer(text):
        # Add the text before the link
        if last_end < match.start():
            parts.append(("text", text[last_end : match.start()]))

        # Add the link
        parts.append(("link", match.group(0)))
        last_end = match.end()

    # Add any remaining text after the last link
    if last_end < len(text):
        parts.append(("text", text[last_end:]))

    print(f"DEBUG: Found {len(parts)} parts in message")
    for i, (part_type, content) in enumerate(parts):
        print(f"DEBUG: Part {i}: type={part_type}, content='{content[:30]}...'")

    # If no links were found, just translate the whole message
    if not parts:
        print("DEBUG: No links found, translating entire message")
        return translate(
            text, target
        )  # translate already returns None for English text

    # Translate text parts and keep links as-is
    result_parts = []
    for part_type, content in parts:
        if part_type == "text":
            # Only translate if there's actual text content (not just whitespace)
            if content.strip():
                print(f"DEBUG: Translating text part: '{content[:30]}...'")
                translated = translate(content, target)
                # If translation returns None (English text), don't include this part
                if translated is not None:
                    result_parts.append(translated)
                # If no parts will be added (all English text), we'll return None at the end
            else:
                print("DEBUG: Skipping empty text part")
        else:  # link
            print("DEBUG: Keeping link part as-is")
            result_parts.append(content)

    # If we have no result parts (all text was English), return None
    if not result_parts:
        print("DEBUG: No translatable content, returning None")
        return None

    result = "".join(result_parts)
    print(f"DEBUG: Final result: '{result[:50]}...'")
    return result
