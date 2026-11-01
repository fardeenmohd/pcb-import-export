from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup
import time
import logging

def launch_browser(p, logger=None):
    """
    Launches a browser with multi-tier resilience:
    1. Bundled or local Playwright Chromium
    2. System Microsoft Edge (pre-installed on Windows 10/11)
    3. System Google Chrome
    """
    import os
    from resource_util import resource_path
    
    bundled_browser_dir = resource_path("ms-playwright")
    if os.path.exists(bundled_browser_dir):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = bundled_browser_dir

    common_args = [
        "--disable-http2",
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage"
    ]
        
    try:
        return p.chromium.launch(headless=True, args=common_args)
    except Exception as e:
        if logger:
            logger.warning(f"Standard Chromium launch failed: {e}. Attempting fallback to system Microsoft Edge...")
            
    try:
        return p.chromium.launch(headless=True, channel="msedge", args=common_args)
    except Exception as e:
        if logger:
            logger.warning(f"Edge launch failed: {e}. Attempting fallback to Google Chrome...")
            
    try:
        return p.chromium.launch(headless=True, channel="chrome", args=common_args)
    except Exception as e:
        if logger:
            logger.error(f"All browser launch methods failed: {e}")
        raise

def scrape_url(url: str, logger: logging.Logger = None) -> str:
    """
    Scrapes the given URL using a stealth browser, returning clean plain text.
    """
    if logger is None:
        logger = logging.getLogger("ScraperAgent")
        
    logger.info(f"Starting to scrape URL: {url}")
    
    try:
        with sync_playwright() as p:
            browser = launch_browser(p, logger)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)
            
            logger.debug(f"Navigating to {url}")
            # wait_until="domcontentloaded" is usually faster, wait for networkidle if SPA
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # small delay to let dynamic content load if any
            time.sleep(3)
            
            html = page.content()
            browser.close()
            
            logger.debug(f"Extracting text from HTML for {url}")
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove unwanted tags to reduce LLM token usage (DO NOT remove header/footer/nav as they contain emails!)
            for element in soup(["script", "style", "noscript", "meta", "svg", "button", "iframe"]):
                element.decompose()
                
            # Get text and clean up whitespace
            text = soup.get_text(separator=' ')
            clean_text = ' '.join(text.split())
            
            logger.info(f"Successfully scraped {url}. Extracted {len(clean_text)} characters.")
            return clean_text
            
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return ""

def is_yellowpages_directory(url: str) -> bool:
    """
    Checks if a URL is a real estate / yellowpages directory search listing page
    rather than an individual property detail page.
    """
    if not url:
        return False
    u = url.lower()
    directory_domains = [
        "olx.in", "99acres.com", "magicbricks.com", "nobroker.in", 
        "housing.com", "quikr.com", "justdial.com", "indiamart.com"
    ]
    if not any(d in u for d in directory_domains):
        return False
    # If it is already an individual listing, return False
    individual_indicators = ["/item/", "-spid-", "propertydetail", "/iid-", "/ad/", "/proddetail/"]
    if any(ind in u for ind in individual_indicators):
        return False
    return True

def extract_subproperties_from_directory(url: str, logger: logging.Logger = None, max_properties: int = 10) -> list:
    """
    Given a yellowpages / classifieds directory search URL (e.g. OLX, 99acres, MagicBricks, NoBroker, JustDial, etc.),
    scrapes the page and extracts individual property/warehouse listing URLs.
    """
    if logger is None:
        logger = logging.getLogger("ScraperAgent")

    logger.info(f"Deep scraping directory for individual property opportunities: {url}")
    results = []
    try:
        with sync_playwright() as p:
            browser = launch_browser(p, logger)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            page.wait_for_timeout(2500)
            html = page.content()
            browser.close()

            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.find_all('a', href=True):
                h = a['href'].strip()
                if not h or h.startswith('#') or h.startswith('javascript:'):
                    continue

                # OLX individual property items
                if ('olx.in' in url or 'olx.in' in h) and ('/item/' in h or '/iid-' in h):
                    full = h if h.startswith('http') else 'https://www.olx.in' + h
                    if full not in results:
                        results.append(full)
                # 99acres individual property pages
                elif ('99acres.com' in url or '99acres.com' in h) and ('spid-' in h or '-spid-' in h or '-prpid-' in h):
                    full = h if h.startswith('http') else 'https://www.99acres.com' + h
                    if full not in results:
                        results.append(full)
                # MagicBricks individual property details
                elif ('magicbricks.com' in url or 'magicbricks.com' in h) and ('propertyDetail' in h or 'property-detail' in h or '-pd-' in h or 'psid-' in h):
                    full = h if h.startswith('http') else 'https://www.magicbricks.com' + h
                    if full not in results:
                        results.append(full)
                # NoBroker commercial properties
                elif ('nobroker.in' in url or 'nobroker.in' in h) and ('/property/' in h or '/commercial-property/' in h or 'commercial-space' in h):
                    full = h if h.startswith('http') else 'https://www.nobroker.in' + h
                    if full not in results:
                        results.append(full)
                # Housing.com
                elif ('housing.com' in url or 'housing.com' in h) and ('/commercial/' in h or '/rent/' in h) and ('-p' in h or '-pid' in h):
                    full = h if h.startswith('http') else 'https://housing.com' + h
                    if full not in results:
                        results.append(full)
                # JustDial specific company/property profiles
                elif ('justdial.com' in url or 'justdial.com' in h) and ('/detail/' in h or (h.count('/') >= 3 and not h.endswith('/nct-'))):
                    full = h if h.startswith('http') else 'https://www.justdial.com' + h
                    if full not in results and 'justdial.com' in full:
                        results.append(full)
                # Quikr individual ads
                elif ('quikr.com' in url or 'quikr.com' in h) and ('/ad/' in h or '/item/' in h or '/property-' in h):
                    full = h if h.startswith('http') else 'https://www.quikr.com' + h
                    if full not in results:
                        results.append(full)
                # IndiaMart product/company details
                elif ('indiamart.com' in url or 'indiamart.com' in h) and ('/proddetail/' in h or ('indiamart.com/' in h and h.count('/') >= 4)):
                    full = h if h.startswith('http') else 'https://www.indiamart.com' + h
                    if full not in results:
                        results.append(full)

                if len(results) >= max_properties:
                    break

        logger.info(f"Extracted {len(results)} individual property URLs from directory {url}")
    except Exception as e:
        logger.warning(f"Failed to extract subproperties from {url}: {e}")
    return results
