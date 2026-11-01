import os
import logging
import pandas as pd
import concurrent.futures
from typing import List, Dict
from scraper import scrape_url
from extractor import extract_supplier_info, extract_buyer_info, extract_logistics_info, extract_warehouse_info

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
            "is_manufacturer": extracted_data.is_manufacturer,
            "product_categories": ", ".join(extracted_data.product_categories),
            "specific_products": ", ".join(extracted_data.specific_products),
            "materials": ", ".join(extracted_data.materials),
            "certifications": ", ".join(extracted_data.certifications),
            "production_capacity": extracted_data.production_capacity,
            "minimum_order_quantity": extracted_data.minimum_order_quantity,
            "export_markets": ", ".join(extracted_data.export_markets),
            "oem_odm_service": "Yes" if extracted_data.oem_odm_service else "No",
            "contact_emails": ", ".join(extracted_data.contact_emails),
            "phone_numbers": ", ".join(extracted_data.phone_numbers),
            "locations": ", ".join(extracted_data.locations)
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
    """
    Cleans the matrix Excel file by removing scraping errors, incomplete rows,
    and deduplicating identical URLs or duplicate entity leads.
    Returns a dictionary with cleaning statistics.
    """
    if not os.path.exists(output_file):
        logger.warning(f"No matrix found to clean at {output_file}.")
        return {"removed_count": 0, "initial_count": 0, "remaining_count": 0}
    try:
        import re
        df = pd.read_excel(output_file)
        initial_count = len(df)
        
        removed_rows = []
        keep_indices = []
        seen_urls = set()
        seen_entities = set()

        def normalize_url(u):
            if not u or pd.isna(u):
                return ""
            s = str(u).strip().lower()
            s = re.sub(r'^https?://', '', s)
            s = re.sub(r'^www\.', '', s)
            s = s.rstrip('/')
            s = s.split('#')[0]
            s = re.sub(r'[?&](?:utm_[^&]+|ref=[^&]+|fbclid=[^&]+|gclid=[^&]+)', '', s)
            return s.rstrip('?')

        for idx, row in df.iterrows():
            remove = False
            reason = ''
            
            # 1. Scraping error check
            if 'error' in row and pd.notna(row['error']):
                remove = True
                reason = f"Scraping error: {row['error']}"
            
            # 2. Minimum completeness check
            elif 'property_title' in row:
                title = str(row.get('property_title', '')).strip().lower()
                no_title = pd.isna(row.get('property_title')) or not title or title in ['unknown', 'none', 'nan']
                phone = str(row.get('contact_phone', '')).strip()
                no_phone = pd.isna(row.get('contact_phone')) or not phone or phone in ['unknown', 'none', 'nan']
                area = str(row.get('location_area', '')).strip()
                no_area = pd.isna(row.get('location_area')) or not area or area in ['unknown', 'none', 'nan']
                if no_title and no_phone and no_area:
                    remove = True
                    reason = 'No property title, contact phone, or location area'
            elif ('company_name' not in row) or (pd.isna(row['company_name'])) or (str(row['company_name']).strip().lower() in ['unknown', 'none', 'nan']):
                has_email = ('contact_emails' in row and pd.notna(row['contact_emails']) and str(row['contact_emails']).strip() and str(row['contact_emails']).strip().lower() not in ['[]', 'none', 'nan'])
                has_phone = ('phone_numbers' in row and pd.notna(row['phone_numbers']) and str(row['phone_numbers']).strip() and str(row['phone_numbers']).strip().lower() not in ['[]', 'none', 'nan'])
                if not has_email and not has_phone:
                    remove = True
                    reason = 'No company name and no contact info'
            
            # 3. Deduplication checks
            if not remove:
                raw_url = row.get('url', '')
                norm_u = normalize_url(raw_url)
                if norm_u:
                    if norm_u in seen_urls:
                        remove = True
                        reason = f"Duplicate URL ({raw_url})"
                    else:
                        seen_urls.add(norm_u)
                
                # Check entity duplicates
                if not remove:
                    if 'property_title' in row:
                        t = str(row.get('property_title', '')).strip().lower()
                        p = str(row.get('contact_phone', '')).strip().lower()
                        phone_digits = re.sub(r'\D', '', p)
                        if t and phone_digits and len(phone_digits) >= 8 and t not in ['unknown', 'none', 'nan']:
                            ent_key = ('warehouse', t, phone_digits)
                            if ent_key in seen_entities:
                                remove = True
                                reason = f"Duplicate warehouse listing ('{row.get('property_title')}' - {row.get('contact_phone')})"
                            else:
                                seen_entities.add(ent_key)
                    elif 'company_name' in row:
                        c = str(row.get('company_name', '')).strip().lower()
                        if c and c not in ['unknown', 'none', 'nan']:
                            contact_sig = str(row.get('contact_emails', '')).strip().lower() + str(row.get('phone_numbers', '')).strip().lower()
                            if contact_sig and contact_sig not in ['[]', 'none']:
                                ent_key = ('company', c, contact_sig)
                                if ent_key in seen_entities:
                                    remove = True
                                    reason = f"Duplicate company lead ('{row.get('company_name')}')"
                                else:
                                    seen_entities.add(ent_key)

            if remove:
                url = row['url'] if ('url' in row and pd.notna(row['url'])) else 'Unknown'
                removed_rows.append(f"Removed: {url} - Reason: {reason}")
            else:
                keep_indices.append(idx)
                
        remaining_count = len(keep_indices)
        if len(removed_rows) > 0:
            df_cleaned = df.loc[keep_indices]
            df_cleaned.to_excel(output_file, index=False)
            
            logger.info(f"Cleaned matrix {output_file}. Removed {len(removed_rows)} invalid/duplicate rows out of {initial_count}. Retained {remaining_count} unique leads.")
            for msg in removed_rows:
                logger.info(f"  • {msg}")
        else:
            logger.info(f"Matrix {output_file} is already clean and deduplicated. All {initial_count} rows are valid and unique.")

        return {
            "removed_count": len(removed_rows),
            "initial_count": initial_count,
            "remaining_count": remaining_count,
            "removed_details": removed_rows
        }
    except Exception as e:
        logger.error(f"Failed to clean matrix: {e}")
        return {"removed_count": 0, "initial_count": 0, "remaining_count": 0, "error": str(e)}


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


def process_single_warehouse_url(url: str, logger: logging.Logger) -> List[Dict]:
    logger.info(f"Processing Warehouse {url}...")
    from scraper import is_yellowpages_directory, extract_subproperties_from_directory
    
    # If the URL is a yellowpages directory search listing, deep extract individual property URLs
    if is_yellowpages_directory(url):
        logger.info(f"URL is a yellowpages directory. Deep extracting sub-property listings from: {url}")
        sub_urls = extract_subproperties_from_directory(url, logger=logger, max_properties=6)
        if sub_urls:
            logger.info(f"Discovered {len(sub_urls)} sub-property links from directory. Scraping each...")
            sub_results = []
            for s_url in sub_urls:
                try:
                    s_text = scrape_url(s_url, logger)
                    if s_text:
                        s_props = extract_warehouse_info(s_text, logger)
                        if s_props:
                            for p in s_props:
                                sub_results.append({
                                    "property_title": p.property_title or "Commercial Warehouse / Shed",
                                    "property_type": p.property_type or "Warehouse",
                                    "location_area": p.location_area or "",
                                    "city": p.city or "",
                                    "carpet_area_sqft": p.carpet_area_sqft or "",
                                    "clear_height_ft": p.clear_height_ft or "",
                                    "power_load": p.power_load or "",
                                    "monthly_rent": p.monthly_rent or "",
                                    "deposit_terms": p.deposit_terms or "",
                                    "road_access_container": p.road_access_container or "",
                                    "contact_phone": p.contact_phone or "",
                                    "contact_name": p.contact_name or "",
                                    "url": s_url
                                })
                except Exception as sub_err:
                    logger.warning(f"Failed to scrape sub-property {s_url}: {sub_err}")
            if sub_results:
                return sub_results

    # Standard / Individual property page scrape
    text = scrape_url(url, logger)
    if not text:
        return [{"url": url, "error": "Failed to scrape"}]

    extracted_props = extract_warehouse_info(text, logger)
    if not extracted_props:
        return [{"url": url, "error": "Failed to extract warehouse property specifications"}]

    flat_data_list = []
    for p in extracted_props:
        flat_data = {
            "property_title": p.property_title or "Commercial Warehouse / Storage Space",
            "property_type": p.property_type or "Warehouse",
            "location_area": p.location_area or "",
            "city": p.city or "",
            "carpet_area_sqft": p.carpet_area_sqft or "",
            "clear_height_ft": p.clear_height_ft or "",
            "power_load": p.power_load or "",
            "monthly_rent": p.monthly_rent or "",
            "deposit_terms": p.deposit_terms or "",
            "road_access_container": p.road_access_container or "",
            "contact_phone": p.contact_phone or "",
            "contact_name": p.contact_name or "",
            "url": url
        }
        flat_data_list.append(flat_data)

    return flat_data_list

def process_warehouse_urls(urls: List[str], output_excel: str, logger: logging.Logger):
    logger.info(f"Starting batch warehouse property processing for {len(urls)} URLs...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_single_warehouse_url, url, logger): url for url in urls}
        for future in concurrent.futures.as_completed(futures):
            try:
                data_list = future.result()
                results.extend(data_list)
            except Exception as e:
                logger.error(f"Failed to process warehouse URL {futures[future]}: {e}")
                results.append({"url": futures[future], "error": str(e)})

    if results:
        df = pd.DataFrame(results)
        cols = [
            "property_title", "property_type", "location_area", "city", 
            "distance_km", "distance_from_area", "route_notes",
            "carpet_area_sqft", "clear_height_ft", "power_load", "monthly_rent", 
            "deposit_terms", "road_access_container", "contact_phone", "contact_name", 
            "url", "error"
        ]
        existing_cols = [c for c in cols if c in df.columns]
        other_cols = [c for c in df.columns if c not in cols]
        df = df[existing_cols + other_cols]

        if os.path.exists(output_excel):
            try:
                existing_df = pd.read_excel(output_excel)
                df = pd.concat([existing_df, df], ignore_index=True)
            except Exception as e:
                logger.error(f"Error appending to {output_excel}: {e}")

        df.to_excel(output_excel, index=False)
        logger.info(f"Warehouse properties saved to {output_excel} ({len(df)} total rows)")
