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
        
    try:
        return p.chromium.launch(headless=True)
    except Exception as e:
        if logger:
            logger.warning(f"Standard Chromium launch failed: {e}. Attempting fallback to system Microsoft Edge...")
            
    try:
        return p.chromium.launch(headless=True, channel="msedge")
    except Exception as e:
        if logger:
            logger.warning(f"Edge launch failed: {e}. Attempting fallback to Google Chrome...")
            
    try:
        return p.chromium.launch(headless=True, channel="chrome")
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
