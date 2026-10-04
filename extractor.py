import os
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class SupplierList(BaseModel):
    suppliers: List['SupplierCapabilities']

class SupplierCapabilities(BaseModel):
    company_name: Optional[str] = Field(description="Name of the company")
    contact_emails: List[str] = Field(default_factory=list, description="List of extracted email addresses")
    phone_numbers: List[str] = Field(default_factory=list, description="List of extracted phone numbers")
    locations: List[str] = Field(default_factory=list, description="Manufacturing facilities or office locations")
    product_categories: List[str] = Field(default_factory=list, description="Core product categories (e.g., Batteries, Switchgear, PCBs, Appliances, Cables)")
    specific_products: List[str] = Field(default_factory=list, description="Specific items manufactured (e.g., LiFePO4 packs, Molded Case Circuit Breakers, FR4 PCBs)")
    materials: List[str] = Field(default_factory=list, description="List of materials used or handled (e.g., Copper, Lithium, Stainless Steel)")
    certifications: List[str] = Field(default_factory=list, description="List of certifications (e.g., ISO 9001, RoHS, CE, UN38.3)")
    minimum_order_quantity: Optional[str] = Field(description="MOQ constraints if any")
    production_capacity: Optional[str] = Field(description="Production capacity details if explicitly mentioned")
    is_manufacturer: bool = Field(description="True if they are an actual factory/manufacturer. False if they are just a trading company/broker.")

class LogisticsList(BaseModel):
    companies: List['LogisticsCompany']

class LogisticsCompany(BaseModel):
    company_name: Optional[str] = Field(description="Name of the logistics company or freight forwarder")
    contact_emails: List[str] = Field(default_factory=list, description="List of extracted email addresses")
    phone_numbers: List[str] = Field(default_factory=list, description="List of extracted phone numbers")
    locations_hq: List[str] = Field(default_factory=list, description="Headquarters or branch locations in India/globally")
    shipping_routes: List[str] = Field(default_factory=list, description="Regions or countries they ship to (e.g., Worldwide, Europe, USA, Middle East)")
    services_offered: List[str] = Field(default_factory=list, description="Services like FCL, LCL, Air Freight, Customs Clearance, Warehousing")
    container_types: List[str] = Field(default_factory=list, description="Types of containers handled (e.g., 20ft, 40ft, Reefer, Flat Rack)")
    is_logistics_provider: bool = Field(description="True if this is a freight forwarder, shipping line, or logistics company capable of sending containers")
LogisticsList.model_rebuild()

def extract_supplier_info(text: str, logger: logging.Logger = None) -> Optional[List[SupplierCapabilities]]:
    """
    Uses Gemini API to extract structured supplier data from plain text.
    """
    if logger is None:
        logger = logging.getLogger("ScraperAgent")
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        logger.error("GEMINI_API_KEY is missing or invalid in environment variables.")
        return None
        
    if not text.strip():
        logger.warning("Empty text provided to extractor. Skipping.")
        return None

    logger.info("Sending text to Gemini for extraction...")
    try:
        prompt = (
            "Analyze the following text scraped from a PCB manufacturer's website OR a B2B directory page (like IndiaMart). "
            "CRITICAL INSTRUCTION: If the page contains a list of multiple different PCB suppliers/manufacturers, you MUST extract EACH of them as a separate entry in the list! Do NOT name the company 'IndiaMart' or 'JustDial'. "
            "Extract the information required by the JSON schema for each company found. Pay special attention to suppliers across the 9 core niches: Electrical Components, Cables, Switchgear, HVAC Parts, Batteries, Generators, LED Lighting, Appliances, and Testing Equipment.\n\n"
            f"Website Text:\n{text[:30000]}"
        )
        from llm_fallback import generate_with_fallback
        response = generate_with_fallback(
            prompt=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SupplierList,
                temperature=0.0
            ),
            logger=logger
        )
        
        # Parse the JSON response into our Pydantic model
        if response.text:
            logger.info("Successfully extracted data via Gemini.")
            return SupplierList.model_validate_json(response.text).suppliers
        else:
            logger.error("Gemini returned empty response.")
            return None
            
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return None

class BuyerList(BaseModel):
    buyers: List['BuyerInfo']

class BuyerInfo(BaseModel):
    company_name: str
    industry: str
    target_products: List[str]
    contact_emails: List[str]
    phone_numbers: List[str]
    locations: List[str]
    estimated_company_size: str
    is_hardware_oem: bool

def extract_buyer_info(text: str, logger: logging.Logger) -> Optional[List[BuyerInfo]]:
    prompt = f'''
    You are an expert B2B lead generation analyst.
    Analyze the following scraped text from a company's website.
    We are looking for B2B buyers, distributors, and OEMs across 9 core industrial niches:
    1. Electrical Components & Sockets (Glands, Lugs, Terminal Blocks, Switches)
    2. Wires & Cables (LV/MV/HV Power, XLPE, Submersible, Reels)
    3. Switchgear & Control Panels (ACB, MCCB, MCB, VCB, Relays, MCC Panels)
    4. Industrial HVAC & Compressors (Fans, Scroll Compressors, Pumps, Refrigeration Parts)
    5. Batteries & Energy Storage (LiFePO4, Marine IP67, Home ESS, Primary Cells)
    6. Industrial Generators (Cummins Diesel, Gas Gensets, Wind Gen)
    7. LED Lighting & Smart Home (Streetlights, Corax Poultry LED, WiFi Sockets)
    8. Electric Appliances (Commercial Juicers, Vacuums, Kettles, Espresso Machines)
    9. Sensors & Testing Equipment (PIR Sensors, Multimeters, Rheometers, Hardness Testers)
    If they fall into these categories, they are highly qualified buyers.
    CRITICAL INSTRUCTION: You must aggressively scan the text (especially footers/headers) to find ANY email addresses (e.g. sales@, info@) and phone numbers. If the company name is missing, infer it from the domain or copyright text.
    CRITICAL INSTRUCTION: If this is a directory page containing MULTIPLE companies, you MUST extract EACH company as a separate entry in the list! Do NOT skip a company just because you think they aren't a hardware OEM.
    Extract the following information for EVERY company found, EVEN IF they are not an OEM (if they aren't, just extract whatever products or services they offer in the 'target_products' field):
    - company_name: The name of the company (default 'Unknown').
    - industry: E.g., Consumer Electronics, Medical Devices, Automotive, Industrial Automation.
    - target_products: What physical hardware products do they manufacture? (Or what services/software do they offer if not hardware)
    - contact_emails: List of emails found.
    - phone_numbers: List of phone numbers found.
    - locations: List of their office/factory locations.
    - estimated_company_size: Startup, Mid-Market, Enterprise.
    - is_hardware_oem: True if they actually manufacture physical electronic hardware (i.e. they are a potential buyer of PCBs). False if they are just a software company, a marketing agency, or a PCB supplier themselves.

    TEXT TO ANALYZE:
    {text[:30000]}
    '''
    try:
        from llm_fallback import generate_with_fallback
        response = generate_with_fallback(
            prompt=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BuyerList,
            ),
            logger=logger
        )
        return BuyerList.model_validate_json(response.text).buyers
    except Exception as e:
        logger.error(f"Gemini API extraction failed: {e}")
        return None


def extract_logistics_info(text: str, logger: logging.Logger) -> Optional[List[LogisticsCompany]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        logger.error("GEMINI_API_KEY is missing or invalid in environment variables.")
        return None

    try:
        from llm_fallback import generate_with_fallback
        prompt = f"""
            You are a B2B extraction AI. Extract the logistics company details from the following raw text.
            We are looking for freight forwarders, shipping lines, and logistics companies based in India or globally that provide container transport solutions (FCL, LCL, Ocean Freight, Air Freight).
            
            Look closely for contact emails and phones.
            If the page is a directory (like IndiaMart, JustDial, etc.), it may list MULTIPLE logistics companies.
            Extract EVERY single relevant logistics company on the page into a list.
            If the page only contains one company, extract just that one in a list.
            
            TEXT:
            {text[:40000]}
        """
        response = generate_with_fallback(
            prompt=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LogisticsList,
                temperature=0.0
            ),
            logger=logger
        )
        if response and response.text:
            companies = LogisticsList.model_validate_json(response.text).companies
            # Filter out non-logistics companies
            valid = [c for c in companies if c.is_logistics_provider]
            return valid
        return None
    except Exception as e:
        logger.error(f"Error in extract_logistics_info: {e}")
        return None
