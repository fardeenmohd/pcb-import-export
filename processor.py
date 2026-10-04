import os
import logging
import pandas as pd
import concurrent.futures
from typing import List, Dict
from scraper import scrape_url
from extractor import extract_supplier_info, extract_buyer_info, extract_logistics_info

def process_single_url(url: str, logger: logging.Logger) -> List[Dict]:
    logger.info(f"Processing {url}...")
    text = scrape_url(url, logger)
    if not text:
        return [{"url": url, "error": "Failed to scrape"}]
        
    extracted_data_list = extract_supplier_info(text, logger)
    if not extracted_data_list:
        return [{"url": url, "error": "Failed to extract data"}]
        
    flat_data_list = []
    for extracted_data in extracted_data_list:
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
            "bga_assembly": extracted_data.advanced_capabilities.bga_assembly
        }
        flat_data_list.append(flat_data)
        
    logger.info(f"Finished processing {url} - Found {len(flat_data_list)} suppliers")
    return flat_data_list

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
                results.extend(data)
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

def clean_matrix(output_file: str, logger: logging.Logger):
    if not os.path.exists(output_file):
        logger.warning('No matrix to clean.')
        return
    try:
        df = pd.read_excel(output_file)
        initial_count = len(df)
        
        removed_rows = []
        keep_indices = []
        
        for idx, row in df.iterrows():
            remove = False
            reason = ''
            
            if 'error' in row and pd.notna(row['error']):
                remove = True
                reason = f"Scraping error: {row['error']}"
            elif ('company_name' not in row) or (pd.isna(row['company_name'])) or (str(row['company_name']).strip().lower() == 'unknown'):
                if ('contact_emails' not in row or pd.isna(row['contact_emails']) or not str(row['contact_emails']).strip()) and ('phone_numbers' not in row or pd.isna(row['phone_numbers']) or not str(row['phone_numbers']).strip()):
                    remove = True
                    reason = 'No company name and no contact info'
                    
            if remove:
                url = row['url'] if 'url' in row else 'Unknown'
                removed_rows.append(f'Removed URL: {url} - Reason: {reason}')
            else:
                keep_indices.append(idx)
                
        if len(removed_rows) > 0:
            df_cleaned = df.loc[keep_indices]
            df_cleaned.to_excel(output_file, index=False)
            
            logger.info(f'Cleaned matrix. Removed {len(removed_rows)} out of {initial_count} rows.')
            for msg in removed_rows:
                logger.info(msg)
        else:
            logger.info('Matrix is already clean. No rows removed.')
    except Exception as e:
        logger.error(f'Failed to clean matrix: {e}')


from extractor import extract_buyer_info

def process_single_buyer_url(url: str, logger: logging.Logger) -> List[Dict]:
    logger.info(f"Processing Buyer {url}...")
    text = scrape_url(url, logger)
    if not text:
        return [{"url": url, "error": "Failed to scrape"}]
        
    extracted_data_list = extract_buyer_info(text, logger)
    if not extracted_data_list:
        return [{"url": url, "error": "Failed to extract data"}]
        
    flat_data_list = []
    for extracted_data in extracted_data_list:
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
        flat_data_list.append(flat_data)
        
    if not flat_data_list:
        return [{"url": url, "error": "No companies extracted"}]
        
    logger.info(f"Finished processing buyer {url} - Found {len(flat_data_list)} OEMs")
    return flat_data_list

def run_buyer_pipeline(urls: List[str], logger: logging.Logger, output_file: str = "Buyers_Matrix.xlsx", max_workers: int = 3):
    logger.info(f"Starting buyer pipeline for {len(urls)} URLs with {max_workers} workers.")
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(process_single_buyer_url, url, logger): url for url in urls}
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                results.extend(data)
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


def process_single_logistics_url(url: str, logger: logging.Logger) -> List[Dict]:
    logger.info(f"Processing Logistics {url}...")
    text = scrape_url(url, logger)
    if not text:
        return [{"url": url, "error": "Failed to scrape"}]
        
    extracted_data_list = extract_logistics_info(text, logger)
    if not extracted_data_list:
        return [{"url": url, "error": "Failed to extract data or no logistics company found"}]
        
    flat_data_list = []
    for extracted_data in extracted_data_list:
        flat_data = {
            "url": url,
            "company_name": extracted_data.company_name,
            "contact_emails": ", ".join(extracted_data.contact_emails),
            "phone_numbers": ", ".join(extracted_data.phone_numbers),
            "locations_hq": ", ".join(extracted_data.locations_hq),
            "shipping_routes": ", ".join(extracted_data.shipping_routes),
            "services_offered": ", ".join(extracted_data.services_offered),
            "container_types": ", ".join(extracted_data.container_types)
        }
        flat_data_list.append(flat_data)
        
    return flat_data_list

def process_logistics_urls(urls: List[str], output_excel: str, logger: logging.Logger):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_single_logistics_url, url, logger): url for url in urls}
        for future in concurrent.futures.as_completed(futures):
            try:
                data_list = future.result()
                results.extend(data_list)
            except Exception as e:
                logger.error(f"Failed to process {futures[future]}: {e}")
                results.append({"url": futures[future], "error": str(e)})
                
    if results:
        df = pd.DataFrame(results)
        
        # Define preferred column order
        cols = ["company_name", "url", "contact_emails", "phone_numbers", 
                "locations_hq", "shipping_routes", "services_offered", "container_types", "error"]
                
        existing_cols = [c for c in cols if c in df.columns]
        other_cols = [c for c in df.columns if c not in cols]
        df = df[existing_cols + other_cols]
        
        # Append if exists
        if os.path.exists(output_excel):
            try:
                existing_df = pd.read_excel(output_excel)
                df = pd.concat([existing_df, df], ignore_index=True)
            except Exception as e:
                logger.error(f"Error appending to {output_excel}: {e}")
        
        df.to_excel(output_excel, index=False)
        logger.info(f"Logistics data saved to {output_excel}")
