import re
import unicodedata
from bs4 import BeautifulSoup

def clean_text(text):
    if not text:
        return ""
    # Remove HTML tags
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text(separator='\n')
    # Remove encoded text
    text = re.sub(r'\\u[0-9a-fA-F]{4}', '', text)
    text = text.replace(r'\/', '/')
    # Remove HTML close tag
    text = re.sub(r"</[a-z]+>", "", text)

    # Remove anti-spam marker
    cleaned_text = re.sub(r'Please mention the word .*? human\.', '', text, flags=re.DOTALL | re.IGNORECASE)

    return cleaned_text.strip()