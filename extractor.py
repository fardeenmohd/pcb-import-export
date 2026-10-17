import os
import logging
import resource_util
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class SupplierList(BaseModel):
    suppliers: List['SupplierCapabilities']

class SupplierCapabilities(BaseModel):
    company_name: Optional[str] = Field(description="Name of the manufacturing company")
    contact_emails: List[str] = Field(default_factory=list, description="List of extracted email addresses")
    phone_numbers: List[str] = Field(default_factory=list, description="List of extracted phone numbers and WhatsApp numbers")
    locations: List[str] = Field(default_factory=list, description="Manufacturing facilities, industrial estates, or office locations in India or globally")
    product_categories: List[str] = Field(default_factory=list, description="Core product categories manufactured (e.g., Switchgear, Cables, Batteries, Transformers, HVAC Parts, Lighting, Electrical Components)")
    specific_products: List[str] = Field(default_factory=list, description="Specific items or models manufactured (e.g., LiFePO4 packs, Molded Case Circuit Breakers, XLPE power cables, Cable Glands)")
    materials: List[str] = Field(default_factory=list, description="List of materials handled (e.g., Copper, Lithium, Brass, Stainless Steel, Aluminum)")
    certifications: List[str] = Field(default_factory=list, description="List of certifications (e.g., ISO 9001, RoHS, CE, BIS, UN38.3, UL)")
    minimum_order_quantity: Optional[str] = Field(description="MOQ constraints if any")
    production_capacity: Optional[str] = Field(description="Production capacity details if explicitly mentioned")
    export_markets: List[str] = Field(default_factory=list, description="Export countries or regions supplied (e.g., GCC/Middle East, Europe, USA, Africa, Domestic)")
    oem_odm_service: bool = Field(default=False, description="True if they offer OEM, ODM, private label or custom contract manufacturing")
    is_manufacturer: bool = Field(description="True if they are an actual factory/manufacturer with production facilities. False if they are only a trading company/broker.")
SupplierList.model_rebuild()

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

    logger.info("Sending text to Gemini for supplier extraction...")
    try:
        prompt = (
            "You are an elite B2B industrial sourcing specialist for international trade.\n"
            "Analyze the following text scraped from a manufacturer's website OR a B2B directory page (like IndiaMart, TradeIndia, JustDial, etc.).\n\n"
            "We are sourcing from direct MANUFACTURERS, FACTORIES, and OEM MAKERS across 12 core industrial niches:\n"
            "1. Electrical & Electronic Components (Cable Glands, Lugs, Terminal Blocks, Rocker/Toggle Switches, Push Buttons, LCD/OLED Displays, Capacitors, Battery Holders, Fan Motors, Remote Switches, EV plugs, HS 853690, 8528, 8532, 852692)\n"
            "2. Wires & Cables (LV/MV/HV Power, Armored XLPE, Submersible, Binding Wires, Reeling systems, Hoses)\n"
            "3. Power Distribution & Protection Relays (Numerical Protection Relays, SEL-751 Arc-Flash, SEL-787 Transformer, SEL-700G Generator, Circuit Breakers, Contactors, Transformers, Switchgear, ACB, MCCB, MCB, VCB, Relays, PCC/MCC Panels, Feeder Pillars, HS 853649, 853710, 8504)\n"
            "4. Industrial HVAC, Fans & Pumps (Axial/Centrifugal Fans, Scroll/Screw Compressors, Submersible Pumps, Refrigeration Parts)\n"
            "5. Batteries, Solar & Renewable Scrap (Solar Panel Scrap 500 MT, PV Module Scrap, Decommissioned Solar Panels, HS 854143, LiFePO4 battery packs, Home ESS, Marine IP67, GaN Chargers, Solar Inverters)\n"
            "6. Industrial Generators (Cummins Diesel, Gas Gensets, Silent Generators, Wind Turbines)\n"
            "7. LED Lighting & Lighting Controls (Centralized Lighting Controls, Automated Lighting Controllers, Dimming Modules, Streetlight Monitoring Systems, Smart Building Automation, Streetlights, High-Bay LED, Corax Poultry Lighting, Smart WiFi Sockets, Electronic Control Components, HS 853710)\n"
            "8. Electric Home & Commercial Appliances (Industrial Dehumidifiers, Floor Scrubbers, Commercial Laundry & Kitchen Equipment)\n"
            "9. Sensors & Testing Equipment (PIR Sensors, Level Float Switches, Transformer Test Benches, Multimeters)\n"
            "10. Electric Vehicles & EV Infrastructure (EV Chargers, AC Wallbox/DC Fast Chargers, Charging Cables, Type 2/CCS2 Connectors, EV Battery Packs, BMS)\n"
            "11. Printed Circuit Boards (PCB) & PCBA Assembly (Rigid Multi-layer FR4, Flex FPC, Metal Core MCPCB, SMT/THT PCBA, Turnkey EMS, Copper Clad Laminates CCL, Electronic Components)\n"
            "12. Building Materials & Wooden Panels (Plywood Panels, MDF Panels, Decorative Panels, Laminated Boards, Melamine Faced Boards, Marine Plywood, Particle Boards, Veneered Panels, HS 441299, 4411)\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. MULTI-COMPANY DIRECTORIES: If the page contains a list of multiple different suppliers or factories, you MUST extract EACH of them as a separate entry in the list! Do NOT name the company 'IndiaMart' or 'TradeIndia'.\n"
            "2. CONTACT DETAILS: Aggressively search headers, footers, sidebars, and body text to extract ALL email addresses (sales@, info@, export@), phone numbers, and WhatsApp numbers.\n"
            "3. FACTORY LOCATION: Extract the specific industrial city, state, or manufacturing estate in India or internationally (e.g. Jamnagar, Rajkot, Ahmedabad, Peenya Bangalore, Pune, Noida, Coimbatore, etc.).\n"
            "4. MANUFACTURER VS TRADER: Set is_manufacturer=True if they produce, assemble, or fabricate goods; False if they are purely a middleman or trading company.\n"
            "5. CAPABILITIES & SERVICES: Extract export markets served and whether they support OEM/ODM or private label manufacturing.\n\n"
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
            logger.info("Successfully extracted supplier data via Gemini.")
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
    We are looking for B2B buyers, distributors, and OEMs across 12 core industrial niches:
    1. Electrical & Electronic Components (Glands, Lugs, Terminal Blocks, Switches, Push Buttons, Toggle Switches, LCD/OLED Displays, Capacitors, Battery Holders, Fan Motors, HS 853690, 8528, 8532)
    2. Wires & Cables (LV/MV/HV Power, XLPE, Submersible, Reels)
    3. Power Distribution & Protection Relays (Numerical Protection Relays, SEL-751 Arc-Flash, SEL-787 Transformer, SEL-700G Generator, Circuit Breakers, Contactors, Transformers, Switchgear, ACB, MCCB, MCB, VCB, Relays, MCC Panels, HS 853649, 853710, 8504)
    4. Industrial HVAC & Compressors (Fans, Scroll Compressors, Pumps, Refrigeration Parts)
    5. Batteries, Solar & Renewable Scrap (Solar Panel Scrap 500 MT, PV Module Scrap, Decommissioned Solar Panels, HS 854143, LiFePO4, Marine IP67, Home ESS, Primary Cells)
    6. Industrial Generators (Cummins Diesel, Gas Gensets, Wind Gen)
    7. LED Lighting & Lighting Controls (Centralized Controls, Automated Lighting Controllers, Dimming Modules, Streetlight Monitoring, Smart Building Automation, DALI/0-10V, Streetlights, High-Bay, Luminaires, HS 853710)
    8. Electric Appliances (Commercial Juicers, Vacuums, Kettles, Espresso Machines)
    9. Sensors & Testing Equipment (PIR Sensors, Multimeters, Rheometers, Hardness Testers)
    10. Electric Vehicles & EV Infrastructure (EV Chargers, Fast Charging Stations, Cables, Connectors, EV Batteries)
    11. Printed Circuit Boards (PCB) & PCBA Assembly (Bare PCBs, Rigid FR4, Flex FPC, SMT Assembly, PCBA, Turnkey EMS, Electronic Hardware)
    12. Building Materials & Wooden Panels (Plywood Panels, MDF Panels, Laminated Boards, Decorative Panels, Melamine Boards, Marine Plywood, Retailer/Distribution, HS 441299, 4411)
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
