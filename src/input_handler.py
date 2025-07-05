import os
from typing import List

from utils import is_valid_url, is_reachable

def read_urls_from_file(filepath: str) -> List[str]:
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"No such file: {filepath}")

    with open(filepath, "r") as f:
        urls = [line.strip() for line in f if line.strip()]

    # Validate
    valid_urls = []
    for url in urls:
        if is_valid_url(url) and is_reachable(url):
            valid_urls.append(url)
        else:
            print(f"Invalid or unreachable URL skipped: {url}")

    return valid_urls
