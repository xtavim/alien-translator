import re
import json
import openai
import os
from dotenv import load_dotenv

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

    # Check if text is empty
    if not text or not text.strip():
        print("DEBUG: Empty text, returning")
        return text

    # Skip translation for English, Portuguese, or Spanish
    if detect(text) in ["en", "pt", "es"]:
        print(f"DEBUG: Text is in supported language, returning as-is")
        return text

    print("DEBUG: Translating text (assumed to be Swiss German dialect)")

    if not OPENAI_API_KEY:
        print("DEBUG: OpenAI API key not available, returning original text")
        return text

    if target != "en":
        print(f"DEBUG: Unsupported target language: {target}, defaulting to English")
        target = "en"

    try:
        # Create a more specific system prompt for Swiss German translation
        system_prompt = "Translate Swiss German/German to English. Preserve meaning and tone. Only return translation."
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
                {"role": "user", "content": text}
            ],
            max_completion_tokens=1000  # Adjust based on expected message length
        )

        # Extract and return the translated text
        if response and response.choices:
            translated_text = response.choices[0].message.content.strip()
            print(f"DEBUG: Translation result: '{translated_text[:50]}...'")
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
        r'^https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$'
    )

    # Discord attachment pattern
    discord_attachment_pattern = re.compile(
        r'^https?:\/\/(?:cdn\.)?discord(?:app)?\.com\/attachments\/\d+\/\d+\/[^ ]+$'
    )

    result = bool(url_pattern.match(text) or discord_attachment_pattern.match(text))
    print(f"DEBUG: is_link_only() result: {result}")
    return result

def translate_message_with_links(text, target="en"):
    """
    Translate a message that may contain links

    If message contains only a link, returns original link
    If message contains text with links, translates only the text parts

    Args:
        text (str): Message text that may contain links
        target (str): Target language code (default: "en")

    Returns:
        str: Translated message with original links preserved
    """
    print(f"DEBUG: translate_message_with_links() called with: '{text[:50]}...'")

    # If it's just a link, return as-is
    if is_link_only(text):
        print("DEBUG: Message is link only, returning as-is")
        return text

    # Pattern to find URLs in the text
    url_pattern = re.compile(
        r'(https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)|https?:\/\/(?:cdn\.)?discord(?:app)?\.com\/attachments\/\d+\/\d+\/[^ ]+)'
    )

    # Split the text into parts (links and non-links)
    parts = []
    last_end = 0

    for match in url_pattern.finditer(text):
        # Add the text before the link
        if last_end < match.start():
            parts.append(("text", text[last_end:match.start()]))

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
        return translate(text, target)

    # Translate text parts and keep links as-is
    result_parts = []
    for part_type, content in parts:
        if part_type == "text":
            # Only translate if there's actual text content (not just whitespace)
            if content.strip():
                print(f"DEBUG: Translating text part: '{content[:30]}...'")
                translated = translate(content, target)
                result_parts.append(translated)
            else:
                print("DEBUG: Skipping empty text part")
                result_parts.append(content)
        else:  # link
            print("DEBUG: Keeping link part as-is")
            result_parts.append(content)

    result = "".join(result_parts)
    print(f"DEBUG: Final result: '{result[:50]}...'")
    return result
