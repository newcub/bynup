"""
RDAP (Registration Data Access Protocol) helper for domain availability checks.

RDAP is the modern, JSON-based successor to WHOIS. It is:
  - Free to query (no API key)
  - Run directly by registries
  - Standardized by ICANN

Endpoint bootstrap: https://data.iana.org/rdap/dns.json
This maps TLDs to their RDAP endpoint URLs.

For our v1, we support gTLDs only (no ccTLDs). The gTLD set covers
.com, .store, .org, .net, and other ICANN-managed generic TLDs.
"""

import logging
from typing import Optional, Dict, Any

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------

# IANA's RDAP bootstrap file (authoritative TLD → endpoint mapping)
RDAP_BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"

# Timeouts (in seconds)
RDAP_CONNECT_TIMEOUT = 5
RDAP_READ_TIMEOUT = 8

# Cache settings
# Cache the bootstrap file for a long time (it changes rarely)
RDAP_BOOTSTRAP_CACHE_KEY = "rdap_bootstrap_v1"
RDAP_BOOTSTRAP_CACHE_TTL = 60 * 60 * 24  # 24 hours

# Cache individual availability results for a short time
# (RDAP is free, so this is mostly a politeness to registries)
RDAP_AVAILABILITY_CACHE_TTL = 60 * 10  # 10 minutes

# User agent for polite registry identification
RDAP_USER_AGENT = getattr(
    settings,
    "RDAP_USER_AGENT",
    "bynUp-DomainChecker/1.0 (+https://bynup.store)"
)


# ---------------------------------------------------------------
# BOOTSTRAP LOADING
# ---------------------------------------------------------------

def _load_bootstrap() -> Dict[str, list]:
    """
    Fetch and cache the IANA RDAP bootstrap file.
    Returns a dict mapping TLD -> list of endpoint base URLs.
    """
    cached = cache.get(RDAP_BOOTSTRAP_CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(
            RDAP_BOOTSTRAP_URL,
            timeout=(RDAP_CONNECT_TIMEOUT, RDAP_READ_TIMEOUT),
            headers={"User-Agent": RDAP_USER_AGENT},
        )
        resp.raise_for_status()
        data = resp.json()

        # The bootstrap format looks like:
        # { "services": [ [["com","net"], ["https://rdap.verisign.com/com/v1/"]], ... ] }
        tld_map = {}
        for service_entry in data.get("services", []):
            if len(service_entry) < 2:
                continue
            tlds, endpoints = service_entry[0], service_entry[1]
            if not tlds or not endpoints:
                continue
            # Take the first HTTPS endpoint for each TLD
            endpoint = None
            for ep in endpoints:
                if ep.startswith("https://"):
                    endpoint = ep
                    break
            if not endpoint and endpoints:
                endpoint = endpoints[0]
            if endpoint:
                for tld in tlds:
                    tld_map[tld.lower()] = endpoint

        cache.set(RDAP_BOOTSTRAP_CACHE_KEY, tld_map, RDAP_BOOTSTRAP_CACHE_TTL)
        logger.info("RDAP bootstrap loaded: %d TLDs mapped", len(tld_map))
        return tld_map

    except Exception as exc:
        logger.exception("Failed to load RDAP bootstrap: %s", exc)
        return {}


def _get_endpoint_for_tld(tld: str) -> Optional[str]:
    """
    Return the RDAP endpoint base URL for a given TLD, or None if unsupported.
    """
    if not tld:
        return None
    tld = tld.lower().lstrip(".")
    bootstrap = _load_bootstrap()
    return bootstrap.get(tld)


# ---------------------------------------------------------------
# AVAILABILITY CHECKS
# ---------------------------------------------------------------

def _cache_key_for_domain(domain_name: str) -> str:
    return f"rdap_avail_v1:{domain_name.lower()}"


def _query_rdap(endpoint_base: str, domain_name: str) -> Dict[str, Any]:
    """
    Perform a single RDAP query and interpret the response.

    Returns a dict:
      {
        "available": bool,
        "status_code": int,
        "reason": str,       # short human-readable explanation
        "raw_http_status": int,
      }
    """
    url = endpoint_base.rstrip("/") + "/domain/" + domain_name

    try:
        resp = requests.get(
            url,
            timeout=(RDAP_CONNECT_TIMEOUT, RDAP_READ_TIMEOUT),
            headers={
                "User-Agent": RDAP_USER_AGENT,
                "Accept": "application/rdap+json, application/json",
            },
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        return {
            "available": None,
            "status_code": 0,
            "reason": "RDAP query timed out",
            "raw_http_status": 0,
        }
    except requests.exceptions.RequestException as exc:
        logger.warning("RDAP request failed for %s: %s", domain_name, exc)
        return {
            "available": None,
            "status_code": 0,
            "reason": "RDAP query failed",
            "raw_http_status": 0,
        }

    status = resp.status_code

    if status == 200:
        # Domain is registered
        return {
            "available": False,
            "status_code": 200,
            "reason": "Domain is registered",
            "raw_http_status": 200,
        }
    elif status == 404:
        # Domain is not found = available
        return {
            "available": True,
            "status_code": 404,
            "reason": "Domain is available",
            "raw_http_status": 404,
        }
    elif status == 429:
        return {
            "available": None,
            "status_code": 429,
            "reason": "Rate-limited by registry",
            "raw_http_status": 429,
        }
    elif 500 <= status < 600:
        return {
            "available": None,
            "status_code": status,
            "reason": "Registry server error",
            "raw_http_status": status,
        }
    else:
        return {
            "available": None,
            "status_code": status,
            "reason": f"Unexpected RDAP status: {status}",
            "raw_http_status": status,
        }


def check_domain_availability(domain_name: str) -> Dict[str, Any]:
    """
    Public entry point: check if a domain is available.

    Accepts a full domain name (e.g. "mystore.store").
    Returns a dict:
      {
        "domain_name": str,
        "tld": str,
        "available": True | False | None,
        "reason": str,
        "supported": bool,
        "cached": bool,
      }

    `available is None` means "could not determine" (network issue,
    unsupported TLD, rate-limited, etc.) — the caller should handle
    this gracefully.
    """
    if not domain_name or "." not in domain_name:
        return {
            "domain_name": domain_name or "",
            "tld": "",
            "available": None,
            "reason": "Invalid domain name",
            "supported": False,
            "cached": False,
        }

    domain_name = domain_name.strip().lower()
    tld = domain_name.rsplit(".", 1)[-1]

    # Check cache
    cache_key = _cache_key_for_domain(domain_name)
    cached = cache.get(cache_key)
    if cached is not None:
        result = dict(cached)
        result["cached"] = True
        return result

    # Resolve endpoint
    endpoint = _get_endpoint_for_tld(tld)
    if not endpoint:
        result = {
            "domain_name": domain_name,
            "tld": tld,
            "available": None,
            "reason": f"No RDAP endpoint known for .{tld}",
            "supported": False,
            "cached": False,
        }
        # Cache negative-support results briefly too
        cache.set(cache_key, result, RDAP_AVAILABILITY_CACHE_TTL)
        return result

    # Query
    query_result = _query_rdap(endpoint, domain_name)

    result = {
        "domain_name": domain_name,
        "tld": tld,
        "available": query_result["available"],
        "reason": query_result["reason"],
        "supported": True,
        "cached": False,
        "raw_http_status": query_result["raw_http_status"],
    }

    # Only cache positive/negative confirmations, not transient failures
    if query_result["available"] is not None:
        cache.set(cache_key, result, RDAP_AVAILABILITY_CACHE_TTL)

    return result


def check_multiple_domains(names: list, tlds: list) -> Dict[str, Dict[str, Any]]:
    """
    Check a single name across multiple TLDs.
    Example: check_multiple_domains(['mystore'], ['store', 'com', 'org'])

    Returns a dict keyed by full domain name:
      { "mystore.store": {...}, "mystore.com": {...}, ... }
    """
    results = {}
    for name in names:
        name = (name or "").strip().lower().replace(" ", "-")
        if not name:
            continue
        for tld in tlds:
            tld = (tld or "").strip().lower().lstrip(".")
            if not tld:
                continue
            full = f"{name}.{tld}"
            results[full] = check_domain_availability(full)
    return results


def is_tld_supported(tld: str) -> bool:
    """
    Quick check: is this TLD supported by RDAP?
    Used by the frontend to decide which TLDs to show in search.
    """
    return _get_endpoint_for_tld(tld) is not None


# ---------------------------------------------------------------
# SUPPORTED TLDS FOR OUR UI
# ---------------------------------------------------------------

# The TLDs our search UI will expose.
# Keep this small in v1 to keep the UX focused.
SUPPORTED_TLDS = [
    {"tld": "store", "label": ".store", "is_gtld": True},
    {"tld": "com",   "label": ".com",   "is_gtld": True},
    {"tld": "org",   "label": ".org",   "is_gtld": True},
    {"tld": "net",   "label": ".net",   "is_gtld": True},
    {"tld": "shop",  "label": ".shop",  "is_gtld": True},
    {"tld": "online","label": ".online","is_gtld": True},
    {"tld": "site",  "label": ".site",  "is_gtld": True},
    {"tld": "co",    "label": ".co",    "is_gtld": True},
]


def get_supported_tlds() -> list:
    """Return the list of TLDs we support in the search UI."""
    return list(SUPPORTED_TLDS)