"""Scrape doctrines, fittings, and categories from an external Alliance Auth instance.

Uses an authenticated ``sessionid`` cookie supplied by the user for a single
request; the cookie is never persisted or logged. Scraped records are written
with ``source=Source.REMOTE_AUTH`` and stay read-only in Doctrine Hub.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..models import Category, Doctrine, Fitting, Source
from .eft import EftParseError, parse_eft
from .fittings_sync import (
    SourceCategory,
    SourceDoctrine,
    SourceFitting,
    SourceItem,
    SourceSnapshot,
    SyncResult,
    apply_snapshot,
)

logger = logging.getLogger(__name__)

FIT_DETAIL_RE = re.compile(r"/fittings/fit/(\d+)/?$")
DOCTRINE_DETAIL_RE = re.compile(r"/fittings/doctrine/(\d+)/?$")
CAT_DETAIL_RE = re.compile(r"/fittings/cat/(\d+)/?$")
RGB_RE = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
EVETECH_TYPE_ICON_RE = re.compile(r"images\.evetech\.net/types/(\d+)/")


class RemoteScrapeError(RuntimeError):
    """Raised when scraping an external Alliance Auth instance fails."""


def normalize_base_url(base_url: str) -> str:
    """Validate and normalize the external Alliance Auth base URL."""
    cleaned = base_url.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RemoteScrapeError("Base URL must start with http:// or https:// and include a hostname.")
    return f"{parsed.scheme}://{parsed.netloc}"


def make_remote_session(base_url: str, sessionid: str) -> requests.Session:
    """Build a ``requests.Session`` authenticated with the given ``sessionid`` cookie."""
    normalized = normalize_base_url(base_url)
    cookie = sessionid.strip()
    if not cookie:
        raise RemoteScrapeError("A sessionid cookie value is required.")
    domain = urlparse(normalized).hostname or ""
    session = requests.Session()
    session.cookies.set("sessionid", cookie, domain=domain)
    session.headers.update({"User-Agent": "aa-doctrinehub-remote-scrape/1.0"})
    return session


def _get_html(session: requests.Session, url: str, *, timeout: int = 15) -> BeautifulSoup:
    try:
        resp = session.get(url, allow_redirects=True, timeout=timeout)
    except requests.RequestException as exc:
        raise RemoteScrapeError(f"Failed to reach {url}: {exc}") from exc
    if "/account/login" in resp.url or "sso.eveonline.com" in resp.url:
        raise RemoteScrapeError(
            "Session cookie is missing or expired (redirected to login). Grab a fresh sessionid cookie and try again."
        )
    if resp.status_code >= 400:
        raise RemoteScrapeError(f"Remote Auth returned HTTP {resp.status_code} for {url}.")
    return BeautifulSoup(resp.text, "html.parser")


def _extract_links(soup_or_tag: Any, href_re: re.Pattern[str]) -> dict[int, str]:
    """Map integer object ID -> longest link text seen for matching anchors."""
    best: dict[int, str] = {}
    for link in soup_or_tag.find_all("a", href=True):
        match = href_re.search(str(link["href"]))
        if not match:
            continue
        obj_id = int(match.group(1))
        text = link.get_text(strip=True)
        if len(text) > len(best.get(obj_id, "")):
            best[obj_id] = text
    return best


def _rgb_to_hex(style: str) -> str | None:
    match = RGB_RE.search(style or "")
    if not match:
        return None
    r, g, b = (int(x) for x in match.groups())
    return f"#{r:02x}{g:02x}{b:02x}"


def _extract_ship_type_id(soup: BeautifulSoup) -> int | None:
    for img in soup.select("img[src]"):
        src = str(img.get("src") or "")
        match = EVETECH_TYPE_ICON_RE.search(src)
        if match:
            return int(match.group(1))
    return None


def _extract_fit_notes(soup: BeautifulSoup) -> str:
    for card_title in soup.select(".card-title"):
        if card_title.get_text(strip=True) == "Fitting Notes":
            header = card_title.find_parent(class_="card-header")
            if header:
                body = header.find_next_sibling(class_="card-body")
                if body:
                    return "\n".join(p.get_text(strip=True) for p in body.find_all("p")).strip()
            break
    return ""


def _scrape_doctrine(
    session: requests.Session,
    base_url: str,
    doctrine_id: int,
    fallback_name: str,
    *,
    timeout: int,
) -> SourceDoctrine:
    soup = _get_html(session, urljoin(base_url, f"/fittings/doctrine/{doctrine_id}/"), timeout=timeout)

    name = fallback_name
    for selector in ("h1", ".card-title"):
        heading = soup.select_one(selector)
        if heading:
            text = heading.get_text(strip=True)
            if text and text.lower() not in {"fittings", "doctrine"}:
                name = text
                break

    description = ""
    for card_title in soup.select(".card-title"):
        if card_title.get_text(strip=True).lower() in {"description", "notes", "doctrine description"}:
            header = card_title.find_parent(class_="card-header")
            if header:
                body = header.find_next_sibling(class_="card-body")
                if body:
                    description = "\n".join(p.get_text(strip=True) for p in body.find_all("p")).strip()
            break

    icon_url = ""
    for img in soup.select('img[src*="images.evetech.net"]'):
        src = str(img.get("src") or "").strip()
        if src:
            icon_url = src
            break

    fit_links = _extract_links(soup, FIT_DETAIL_RE)
    return SourceDoctrine(
        external_id=doctrine_id,
        name=name or f"Doctrine {doctrine_id}",
        description=description,
        icon_url=icon_url,
        fitting_ids=list(fit_links.keys()),
    )


def _scrape_fitting(
    session: requests.Session,
    base_url: str,
    fit_id: int,
    fallback_name: str,
    *,
    timeout: int,
) -> SourceFitting | None:
    soup = _get_html(session, urljoin(base_url, f"/fittings/fit/{fit_id}/"), timeout=timeout)
    eft_textarea = soup.select_one("#eft-fitting")
    if not eft_textarea:
        return None

    eft_text = eft_textarea.get_text().strip()
    if not eft_text:
        return None

    try:
        parsed = parse_eft(eft_text)
        name = parsed.name or fallback_name or f"Fit {fit_id}"
        ship_type_name = parsed.ship_type_name
        items = [
            SourceItem(flag=item.flag, type_id=0, type_name=item.type_name, quantity=item.quantity)
            for item in parsed.items
        ]
    except EftParseError:
        logger.warning("Remote scrape: could not parse EFT for external fit %s", fit_id)
        return None

    return SourceFitting(
        external_id=fit_id,
        name=name,
        description=_extract_fit_notes(soup),
        ship_type_id=_extract_ship_type_id(soup) or 0,
        ship_type_name=ship_type_name,
        eft=eft_text,
        items=items,
    )


def _scrape_category(
    session: requests.Session,
    base_url: str,
    cat_id: int,
    name: str,
    *,
    timeout: int,
) -> SourceCategory:
    soup = _get_html(session, urljoin(base_url, f"/fittings/cat/{cat_id}/"), timeout=timeout)
    color = "#6c757d"
    for badge in soup.select(".badge"):
        if badge.get_text(strip=True) == name:
            hex_color = _rgb_to_hex(str(badge.get("style") or ""))
            if hex_color:
                color = hex_color
            break

    fittings_tab = soup.select_one("#tab-fittings") or soup
    fitting_ids = list(_extract_links(fittings_tab, FIT_DETAIL_RE).keys())
    doctrines_tab = soup.select_one("#tab-doctrines") or soup
    doctrine_ids = list(_extract_links(doctrines_tab, DOCTRINE_DETAIL_RE).keys())

    return SourceCategory(
        external_id=cat_id,
        name=name,
        color=color,
        group_ids=[],
        fitting_ids=fitting_ids,
        doctrine_ids=doctrine_ids,
    )


def scrape_remote_fittings_site(
    base_url: str,
    sessionid: str,
    *,
    include_standalone_fits: bool = True,
    include_categories: bool = True,
    timeout: int = 15,
    request_delay: float = 0.05,
) -> SourceSnapshot:
    """Scrape doctrines, fittings, and categories from an external Alliance Auth."""
    normalized = normalize_base_url(base_url)
    session = make_remote_session(normalized, sessionid)

    # Verify session and collect standalone fits if requested.
    fits_soup = _get_html(session, urljoin(normalized, "/fittings/fit/all/"), timeout=timeout)
    fit_links: dict[int, str] = _extract_links(fits_soup, FIT_DETAIL_RE) if include_standalone_fits else {}

    # Collect doctrine links from the Fittings index (and /fittings/doctrine/all/ if available).
    index_soup = _get_html(session, urljoin(normalized, "/fittings/"), timeout=timeout)
    doctrine_links = _extract_links(index_soup, DOCTRINE_DETAIL_RE)

    snapshot = SourceSnapshot()
    for doctrine_id, d_name in doctrine_links.items():
        if request_delay > 0:
            time.sleep(request_delay)
        doctrine = _scrape_doctrine(session, normalized, doctrine_id, d_name, timeout=timeout)
        snapshot.doctrines.append(doctrine)
        for fid in doctrine.fitting_ids:
            fit_links.setdefault(fid, f"Fit {fid}")

    for fit_id, f_name in fit_links.items():
        if request_delay > 0:
            time.sleep(request_delay)
        fitting = _scrape_fitting(session, normalized, fit_id, f_name, timeout=timeout)
        if fitting is not None:
            snapshot.fittings.append(fitting)

    if include_categories:
        cats_soup = _get_html(session, urljoin(normalized, "/fittings/cat/all/"), timeout=timeout)
        cat_links = _extract_links(cats_soup, CAT_DETAIL_RE)
        for cat_id, c_name in cat_links.items():
            if request_delay > 0:
                time.sleep(request_delay)
            snapshot.categories.append(
                _scrape_category(session, normalized, cat_id, c_name, timeout=timeout)
            )

    return snapshot


def preview_remote_scrape(snapshot: SourceSnapshot) -> dict[str, Any]:
    """Summarize what an import of ``snapshot`` would create or update without writing."""
    existing_doc_ids = set(
        Doctrine.objects.from_source(Source.REMOTE_AUTH).values_list("external_id", flat=True)
    )
    existing_fit_ids = set(
        Fitting.objects.from_source(Source.REMOTE_AUTH).values_list("external_id", flat=True)
    )
    existing_cat_ids = set(
        Category.objects.from_source(Source.REMOTE_AUTH).values_list("external_id", flat=True)
    )

    doctrines_new = sum(1 for d in snapshot.doctrines if d.external_id not in existing_doc_ids)
    fittings_new = sum(1 for f in snapshot.fittings if f.external_id not in existing_fit_ids)
    categories_new = sum(1 for c in snapshot.categories if c.external_id not in existing_cat_ids)

    return {
        "mode": "preview",
        "doctrines_count": len(snapshot.doctrines),
        "doctrines_new": doctrines_new,
        "doctrines_existing": len(snapshot.doctrines) - doctrines_new,
        "fittings_count": len(snapshot.fittings),
        "fittings_new": fittings_new,
        "fittings_existing": len(snapshot.fittings) - fittings_new,
        "categories_count": len(snapshot.categories),
        "categories_new": categories_new,
        "categories_existing": len(snapshot.categories) - categories_new,
        "doctrines": [
            {
                "external_id": d.external_id,
                "name": d.name,
                "fittings_count": len(d.fitting_ids),
                "is_new": d.external_id not in existing_doc_ids,
            }
            for d in snapshot.doctrines
        ],
    }


def import_remote_scrape(snapshot: SourceSnapshot) -> SyncResult:
    """Apply ``snapshot`` as read-only ``Source.REMOTE_AUTH`` records."""
    return apply_snapshot(
        snapshot,
        source=Source.REMOTE_AUTH,
        change_note="Synced from External Auth",
    )
