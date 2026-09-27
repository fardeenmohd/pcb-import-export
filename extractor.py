import os
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class Services(BaseModel):
    bare_pcb_manufacturing: bool = False
    pcb_assembly_smt_dip: bool = False

class AdvancedCapabilities(BaseModel):
    hdi: bool = False
    blind_buried_vias: bool = False
    bga_assembly: bool = False

class SupplierCapabilities(BaseModel):
    company_name: Optional[str] = Field(description="Name of the company")
    contact_emails: List[str] = Field(default_factory=list, description="List of extracted email addresses")
    phone_numbers: List[str] = Field(default_factory=list, description="List of extracted phone numbers")
    locations: List[str] = Field(default_factory=list, description="Manufacturing facilities or office locations")
    services: Services = Field(default_factory=Services, description="Core services offered")
    max_layer_count: Optional[int] = Field(description="Maximum number of PCB layers they can manufacture")
    materials: List[str] = Field(default_factory=list, description="List of materials used (e.g., FR4, Rogers, Aluminum)")
    surface_finishes: List[str] = Field(default_factory=list, description="List of surface finishes (e.g., HASL, ENIG, OSP)")
    certifications: List[str] = Field(default_factory=list, description="List of certifications (e.g., ISO 9001, RoHS)")
    minimum_order_quantity: Optional[str] = Field(description="MOQ constraints if any")
    lead_time_days: Optional[str] = Field(description="Expected turnaround or lead time")
    advanced_capabilities: AdvancedCapabilities = Field(default_factory=AdvancedCapabilities, description="Advanced manufacturing capabilities")

def extract_supplier_info(text: str, logger: logging.Logger = None) -> Optional[SupplierCapabilities]:
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
        client = genai.Client(api_key=api_key)
        
        prompt = (
            "Analyze the following text scraped from a PCB manufacturer's website. "
            "Extract the information required by the JSON schema. If information is not found, leave it empty or false.\n\n"
            f"Website Text:\n{text[:30000]}" # limit to avoid exceeding context too much if absurdly large
        )
        
        response = client.models.generate_content(
            model='gemini-flash-lite-latest',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SupplierCapabilities,
                temperature=0.0
            ),
        )
        
        # Parse the JSON response into our Pydantic model
        if response.text:
            logger.info("Successfully extracted data via Gemini.")
            return SupplierCapabilities.model_validate_json(response.text)
        else:
            logger.error("Gemini returned empty response.")
            return None
            
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return None

class BuyerInfo(BaseModel):
    company_name: str
    industry: str
    target_products: List[str]
    contact_emails: List[str]
    phone_numbers: List[str]
    locations: List[str]
    estimated_company_size: str
    is_hardware_oem: bool

def extract_buyer_info(text: str, logger: logging.Logger) -> Optional[BuyerInfo]:
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    prompt = f'''
    You are an expert B2B lead generation analyst.
    Analyze the following scraped text from a company's website.
    We are looking for OEM (Original Equipment Manufacturer) companies, hardware startups, or medical/automotive brands that BUILD physical electronic products and thus require Printed Circuit Boards (PCBs).
    Extract the following information:
    - company_name: The name of the company (default 'Unknown').
    - industry: E.g., Consumer Electronics, Medical Devices, Automotive, Industrial Automation.
    - target_products: What physical hardware products do they manufacture?
    - contact_emails: List of emails found.
    - phone_numbers: List of phone numbers found.
    - locations: List of their office/factory locations.
    - estimated_company_size: Startup, Mid-Market, Enterprise.
    - is_hardware_oem: True if they actually manufacture physical electronic hardware (i.e. they are a potential buyer of PCBs). False if they are just a software company, a marketing agency, or a PCB supplier themselves.

    TEXT TO ANALYZE:
    {text}
    '''
    try:
        response = client.models.generate_content(
            model='gemini-flash-lite-latest',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BuyerInfo,
            ),
        )
        return BuyerInfo.model_validate_json(response.text)
    except Exception as e:
        logger.error(f"Gemini API extraction failed: {e}")
        return None
