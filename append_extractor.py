import os

code = """
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
"""

with open('extractor.py', 'a', encoding='utf-8') as f:
    f.write(code)
