import os
import logging
import pandas as pd
import concurrent.futures
from typing import List, Dict
from scraper import scrape_url
from extractor import extract_supplier_info

def process_single_url(url: str, logger: logging.Logger) -> Dict:
    """
    Worker function to scrape and extract data for a single URL.
    Returns a dictionary of the flattened data.
    """
    logger.info(f"Processing {url}...")
    text = scrape_url(url, logger)
    if not text:
        return {"url": url, "error": "Failed to scrape"}
        
    extracted_data = extract_supplier_info(text, logger)
    if not extracted_data:
        return {"url": url, "error": "Failed to extract data"}
        
    # Flatten the Pydantic model for CSV/Excel
    flat_data = {
        "url": url,
        "company_name": extracted_data.company_name,
        "contact_emails": ", ".join(extracted_data.contact_emails),
        "phone_numbers": ", ".join(extracted_data.phone_numbers),
        "locations": ", ".join(extracted_data.locations),
        "bare_pcb_manufacturing": extracted_data.services.bare_pcb_manufacturing,
        "pcb_assembly_smt_dip": extracted_data.services.pcb_assembly_smt_dip,
        "max_layer_count": extracted_data.max_layer_count,
        "materials": ", ".join(extracted_data.materials),
        "surface_finishes": ", ".join(extracted_data.surface_finishes),
        "certifications": ", ".join(extracted_data.certifications),
        "minimum_order_quantity": extracted_data.minimum_order_quantity,
        "lead_time_days": extracted_data.lead_time_days,
        "hdi": extracted_data.advanced_capabilities.hdi,
        "blind_buried_vias": extracted_data.advanced_capabilities.blind_buried_vias,
        "bga_assembly": extracted_data.advanced_capabilities.bga_assembly,
    }
    
    logger.info(f"Finished processing {url}")
    return flat_data

def run_pipeline(urls: List[str], logger: logging.Logger, output_file: str = "Suppliers_Matrix.xlsx", max_workers: int = 3):
    """
    Orchestrates the scraping and extraction pipeline using ThreadPoolExecutor.
    """
    logger.info(f"Starting pipeline for {len(urls)} URLs with {max_workers} workers.")
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks to the executor
        future_to_url = {executor.submit(process_single_url, url, logger): url for url in urls}
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                results.append(data)
            except Exception as exc:
                logger.error(f"{url} generated an exception: {exc}")
                results.append({"url": url, "error": str(exc)})
                
    logger.info("All URLs processed. Saving to Excel.")
    
    # Save to Excel
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
        logger.info(f"Successfully saved results to {output_file}")
    except Exception as e:
        logger.error(f"Failed to save Excel file: {e}")
