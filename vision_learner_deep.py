import json
import logging
import time
from playwright.sync_api import sync_playwright
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DeepVisionLearner")

def scrape_deep_buyleads(base_url, start_page, end_page):
    leads = []
    with sync_playwright() as p:
        try:
            logger.info("Connecting to your open Chrome browser...")
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            default_context = browser.contexts[0]
            page = default_context.new_page()
            
            all_hrefs = set()
            
            # Phase 1: Collect URLs across all pages
            for pg in range(start_page, end_page + 1):
                page_url = base_url
                if "pg_buyers=" in page_url:
                    page_url = page_url.replace("pg_buyers=2", f"pg_buyers={pg}")
                else:
                    page_url = base_url + f"&pg_buyers={pg}"
                    
                logger.info(f"Scanning Page {pg}: {page_url}")
                page.goto(page_url, timeout=60000)
                time.sleep(2)
                
                links = page.locator("a").all()
                for link in links:
                    try:
                        text = link.inner_text().strip()
                        href = link.get_attribute("href")
                        if href and ("Wanted:" in text or "buylead/view" in href):
                            if not href.startswith("http"):
                                href = "https://www.go4worldbusiness.com" + href
                            all_hrefs.add(href)
                    except:
                        pass
                        
            hrefs = list(all_hrefs)
            logger.info(f"Found a total of {len(hrefs)} unique buy leads across pages {start_page}-{end_page}.")
            
            # Phase 2: Scrape details
            for i, href in enumerate(hrefs):
                logger.info(f"Scraping lead {i+1}/{len(hrefs)}: {href}")
                try:
                    page.goto(href, timeout=30000)
                    time.sleep(1) # Fast scrape
                    text = page.locator("body").inner_text()
                    leads.append(text)
                except Exception as e:
                    logger.error(f"Failed to scrape {href}: {e}")
                
            page.close()
            browser.close()
        except Exception as e:
            logger.error(f"Playwright error: {e}")
            
    return leads

def analyze_and_build_context(leads):
    if not leads:
        logger.warning("No leads scraped. Context not generated.")
        return
        
    logger.info("Sending massive lead dataset to Gemini for Deep Vision Learning...")
    client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
    
    combined_text = "\n\n--- NEXT LEAD ---\n\n".join(leads)
    
    prompt = f"""
    You are an expert B2B supply chain analyst and AI architect. 
    Below are HUNDREDS of raw 'Buy Leads' scraped from a B2B platform (go4worldbusiness).
    Analyze these leads to deeply understand the exact types of products, specifications, materials, and volumes the user's buyers are requesting.
    
    Your task:
    We already have an initial Vision Context. I want you to read all these new leads and CREATE AN UPDATED, MASSIVE "Business Vision Context v2.0" document.
    1. Expand the target niches if you find new ones, or reinforce existing ones.
    2. List ALL specific keywords, HS codes, materials, and component types discovered.
    3. Output the ultimate System Prompt block that covers EVERYTHING.
    
    RAW LEADS:
    {combined_text[:500000]}
    """
    
    try:
        from llm_fallback import generate_with_fallback
        response = generate_with_fallback(prompt, logger=logger)
        
        with open("vision_context_v2.md", "w", encoding="utf-8") as f:
            f.write(response.text)
            
        logger.info("Successfully created 'vision_context_v2.md'!")
    except Exception as e:
        logger.error(f"Failed to generate context: {e}")

if __name__ == "__main__":
    base_url = "https://www.go4worldbusiness.com/buyers/electrical-household-other-goods-components.html?region=worldwide&pg_buyers=2"
    leads = scrape_deep_buyleads(base_url, 2, 10)
    analyze_and_build_context(leads)
