import json
import logging
import time
from playwright.sync_api import sync_playwright
import os
from dotenv import load_dotenv
load_dotenv()
from google import genai

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("VisionLearner")

def scrape_buyleads(start_url):
    leads = []
    with sync_playwright() as p:
        try:
            logger.info("Connecting to your open Chrome browser...")
            # Connect to the Chrome instance running with remote debugging
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            default_context = browser.contexts[0]
            page = default_context.new_page()
            
            logger.info(f"Navigating to {start_url}")
            page.goto(start_url, timeout=60000)
            time.sleep(3)
            
            # Find all links containing "Wanted:" or matching the buylead pattern
            links = page.locator("a").all()
            hrefs = []
            for link in links:
                try:
                    text = link.inner_text().strip()
                    href = link.get_attribute("href")
                    if href and ("Wanted:" in text or "buylead/view" in href):
                        if not href.startswith("http"):
                            href = "https://www.go4worldbusiness.com" + href
                        hrefs.append(href)
                except:
                    pass
                    
            # Deduplicate
            hrefs = list(set(hrefs))
            logger.info(f"Found {len(hrefs)} potential buy leads on the page.")
            
            # Scrape up to 20 leads to build a solid context
            for href in hrefs[:20]: 
                logger.info(f"Scraping lead: {href}")
                try:
                    page.goto(href, timeout=60000)
                    time.sleep(2)
                    text = page.locator("body").inner_text()
                    leads.append(text)
                except Exception as e:
                    logger.error(f"Failed to scrape {href}: {e}")
                
            page.close()
            browser.close()
        except Exception as e:
            logger.error(f"Playwright error: {e}")
            logger.error("Make sure you launched Chrome with --remote-debugging-port=9222")
            
    return leads

def analyze_and_build_context(leads):
    if not leads:
        logger.warning("No leads scraped. Context not generated.")
        return
        
    logger.info("Sending scraped leads to Gemini to learn your vision...")
    client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
    
    combined_text = "\n\n--- NEXT LEAD ---\n\n".join(leads)
    
    prompt = f"""
    You are an expert B2B supply chain analyst and AI architect. 
    Below are several raw 'Buy Leads' scraped from a B2B platform (go4worldbusiness).
    Analyze these leads to deeply understand the exact types of products, specifications, materials, and volumes the user's buyers are requesting.
    
    Your task:
    Create a comprehensive "Business Vision Context" document.
    1. Summarize the exact hardware, electronic, or mechanical niches we need to target based on these real leads.
    2. List the specific keywords, HS codes (if any), materials, and component types.
    3. Write an optimized 'System Prompt' block that we can inject into our Scraper Agent later so it permanently knows to look for these specific profiles.
    
    RAW LEADS:
    {combined_text[:80000]}
    """
    
    try:
        from llm_fallback import generate_with_fallback
        response = generate_with_fallback(prompt, logger=logger)
        
        with open("vision_context.md", "w", encoding="utf-8") as f:
            f.write(response.text)
            
        logger.info("Successfully created 'vision_context.md'!")
        logger.info("We will use this file to permanently upgrade our Scraper's intelligence.")
    except Exception as e:
        logger.error(f"Failed to generate context: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        start_url = sys.argv[1]
    else:
        start_url = input("Enter the URL of the page containing the 'Wanted:' leads: ")
        
    leads = scrape_buyleads(start_url)
    analyze_and_build_context(leads)
