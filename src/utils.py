import requests
from urllib.parse import urlparse

def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return all([parsed.scheme, parsed.netloc])
    except Exception:
        return False

def is_reachable(url: str, timeout: int = 5) -> bool:
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False
