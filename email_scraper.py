"""
Visits a business website's homepage (and, if needed, a contact/about page)
and extracts publicly-listed email addresses.

Deliberately conservative: it only reads static HTML (no JS execution), skips
pages robots.txt disallows, and filters out obvious junk like image filenames
that look like emails (e.g. "logo@2x.png") and placeholder addresses
(e.g. "email@example.com").
"""
from __future__ import annotations

import re
import time
from typing import Optional, Set
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# If any of these appear in a matched "email", it's almost certainly an image
# filename (e.g. "photo@2x.png") rather than a real address.
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".tiff")

# Placeholder / non-business domains and local-parts we don't want cluttering results.
BLOCKLIST_DOMAINS = {
    "example.com", "example.org", "example.net", "domain.com", "yourdomain.com",
    "email.com", "sentry.io", "wixpress.com", "godaddy.com", "gravatar.com",
    "cloudflare.com", "schema.org",
}
BLOCKLIST_LOCALPARTS = {
    "name", "email", "user", "test", "yourname", "youremail",
    "noreply", "no-reply", "donotreply",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 LeadGenBot/1.0"
    )
}

CONTACT_PATH_KEYWORDS = ("contact", "about", "get-in-touch", "reach-us")


def _is_valid_email(email: str) -> bool:
    """Filters out image-filename false positives and common dummy addresses."""
    email_lower = email.lower()

    if any(ext in email_lower for ext in IMAGE_EXTENSIONS):
        return False

    local_part, _, domain = email_lower.partition("@")
    if not domain:
        return False
    if domain in BLOCKLIST_DOMAINS or "example" in domain:
        return False
    if local_part in BLOCKLIST_LOCALPARTS:
        return False

    return True


def _extract_emails_from_html(html: str) -> Set[str]:
    soup = BeautifulSoup(html, "lxml")

    # Strip script/style content so JS/CSS/JSON-LD text never gets scanned.
    for tag in soup(["script", "style"]):
        tag.decompose()

    mailto_emails = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.lower().startswith("mailto:"):
            addr = href.split(":", 1)[1].split("?")[0].strip()
            if addr:
                mailto_emails.add(addr)

    visible_text = soup.get_text(" ")
    text_emails = set(EMAIL_REGEX.findall(visible_text))

    candidates = mailto_emails | text_emails
    return {e for e in candidates if _is_valid_email(e)}


def _find_contact_links(html: str, base_url: str) -> Set[str]:
    """Finds same-domain links whose path looks like a contact/about page."""
    soup = BeautifulSoup(html, "lxml")
    base_domain = urlparse(base_url).netloc
    links = set()

    for a in soup.find_all("a", href=True):
        full_url = urljoin(base_url, a["href"])
        parsed = urlparse(full_url)
        if parsed.netloc != base_domain:
            continue
        if any(keyword in parsed.path.lower() for keyword in CONTACT_PATH_KEYWORDS):
            links.add(full_url)

    return links


def _robots_allow(url: str) -> bool:
    """
    Best-effort robots.txt check so the scraper doesn't visit pages a site
    has explicitly disallowed. Fails OPEN (treats as allowed) if robots.txt
    is missing, unreadable, or slow to respond - a network hiccup shouldn't
    silently block a legitimate lookup.
    """
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        resp = requests.get(robots_url, headers=HEADERS, timeout=5)
        if resp.status_code >= 400:
            return True
        parser = RobotFileParser()
        parser.parse(resp.text.splitlines())
        return parser.can_fetch(HEADERS["User-Agent"], url)
    except Exception:
        return True


def scrape_emails_from_website(url: str, delay: float = 1.5, timeout: int = 10) -> Optional[str]:
    """
    Returns a comma-separated string of email addresses found on the site's
    homepage or a contact/about page, or None if none were found, the site
    couldn't be reached, or robots.txt disallows access.
    """
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not _robots_allow(url):
        return None

    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    found = _extract_emails_from_html(resp.text)

    if not found:
        try:
            contact_links = _find_contact_links(resp.text, url)
        except Exception:
            contact_links = set()

        for link in list(contact_links)[:2]:
            time.sleep(delay)
            if not _robots_allow(link):
                continue
            try:
                contact_resp = requests.get(link, headers=HEADERS, timeout=timeout)
                contact_resp.raise_for_status()
                found = _extract_emails_from_html(contact_resp.text)
            except requests.RequestException:
                continue
            if found:
                break

    return ", ".join(sorted(found)) if found else None
