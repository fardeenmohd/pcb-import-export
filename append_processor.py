import os

code = """
from extractor import extract_buyer_info

def process_single_buyer_url(url: str, logger: logging.Logger) -> Dict:
    logger.info(f"Processing Buyer {url}...")
    text = scrape_url(url, logger)
    if not text:
        return {"url": url, "error": "Failed to scrape"}
        
    extracted_data = extract_buyer_info(text, logger)
    if not extracted_data:
        return {"url": url, "error": "Failed to extract data"}
        
    flat_data = {
        "url": url,
        "company_name": extracted_data.company_name,
        "industry": extracted_data.industry,
        "target_products": ", ".join(extracted_data.target_products),
        "contact_emails": ", ".join(extracted_data.contact_emails),
        "phone_numbers": ", ".join(extracted_data.phone_numbers),
        "locations": ", ".join(extracted_data.locations),
        "estimated_company_size": extracted_data.estimated_company_size,
        "is_hardware_oem": extracted_data.is_hardware_oem
    }
    
    logger.info(f"Finished processing buyer {url}")
    return flat_data

def run_buyer_pipeline(urls: List[str], logger: logging.Logger, output_file: str = "Buyers_Matrix.xlsx", max_workers: int = 3):
    logger.info(f"Starting buyer pipeline for {len(urls)} URLs with {max_workers} workers.")
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(process_single_buyer_url, url, logger): url for url in urls}
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                results.append(data)
            except Exception as exc:
                logger.error(f"{url} generated an exception: {exc}")
                results.append({"url": url, "error": str(exc)})
                
    logger.info("All buyer URLs processed. Saving to Excel.")
    
    try:
        df_new = pd.DataFrame(results)
        if os.path.exists(output_file):
            df_existing = pd.read_excel(output_file)
            df = pd.concat([df_existing, df_new], ignore_index=True)
            logger.info(f"Appending new results to existing {output_file}")
        else:
            df = df_new
            logger.info(f"Creating new file {output_file}")
            
        df.to_excel(output_file, index=False)
        logger.info(f"Successfully saved buyer results to {output_file}")
    except Exception as e:
        logger.error(f"Failed to save buyer Excel file: {e}")
"""

with open('processor.py', 'a', encoding='utf-8') as f:
    f.write(code)
