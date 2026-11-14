import customtkinter as ctk
import threading
import queue
import sys
import subprocess
import pandas as pd
import os
from dotenv import load_dotenv
from ddgs import DDGS
from tkinter import ttk

import resource_util
from resource_util import resource_path
from logger_util import setup_logger
from processor import run_pipeline, run_buyer_pipeline, clean_matrix

def sanitize_email_body(text: str) -> str:
    import re
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    text = re.sub(r'^\s*[\*\-]\s+', '• ', text, flags=re.MULTILINE)
    return text.strip()

def parse_email_response(raw_text: str, default_to: str = ""):
    import json
    import re
    try:
        clean_json = raw_text.strip()
        if clean_json.startswith("```"):
            clean_json = re.sub(r'^```(?:json)?\s*', '', clean_json)
            clean_json = re.sub(r'\s*```$', '', clean_json)
        data = json.loads(clean_json)
        to_val = data.get("to_email", "") or default_to
        subj_val = data.get("subject", "").strip()
        body_val = data.get("body", "").strip()
        return to_val, subj_val, sanitize_email_body(body_val)
    except Exception:
        to_val = default_to
        subj_val = ""
        body_val = raw_text
        
        match_subj = re.search(r'^(?:Subject|Re):\s*(.+)$', raw_text, flags=re.MULTILINE | re.IGNORECASE)
        if match_subj:
            subj_val = match_subj.group(1).strip()
            body_val = re.sub(r'^(?:Subject|Re):\s*.+$\n?', '', body_val, flags=re.MULTILINE | re.IGNORECASE).strip()
            
        match_to = re.search(r'^(?:To):\s*(.+)$', body_val, flags=re.MULTILINE | re.IGNORECASE)
        if match_to:
            if not to_val:
                to_val = match_to.group(1).strip()
            body_val = re.sub(r'^(?:To):\s*.+$\n?', '', body_val, flags=re.MULTILINE | re.IGNORECASE).strip()
            
        return to_val, subj_val, sanitize_email_body(body_val)


# Complete 13 Core Industrial Niches Metadata for Product Sourcing Portfolio
NICHES_METADATA = [
    {
        "id": 1,
        "key": "Niche 1: Electrical & Electronic Components",
        "title": "Niche 1: Electrical & Components",
        "icon": "⚡",
        "subproducts": "Rocker Switches, Cable Glands, RTC ICs, Terminal Lugs",
        "hubs": "Gujarat, Maharashtra, Bangalore"
    },
    {
        "id": 2,
        "key": "Niche 2: Wires & Cables",
        "title": "Niche 2: Wires & Cables",
        "icon": "🔌",
        "subproducts": "Armored XLPE Cables, Submersible Flat, Copper Winding",
        "hubs": "Gujarat, Silvassa, Coimbatore"
    },
    {
        "id": 3,
        "key": "Niche 3: Power Distribution & Protection Relays",
        "title": "Niche 3: Power & Relays",
        "icon": "🛡️",
        "subproducts": "Numerical Relays (SEL), CRP Panels, VCB Switchgear",
        "hubs": "Vadodara, Bangalore, Nashik"
    },
    {
        "id": 4,
        "key": "Niche 4: HVAC, Fans, Pumps & Actuators",
        "title": "Niche 4: HVAC & Actuators",
        "icon": "🌀",
        "subproducts": "Hydraulic Actuators, Speed Motors, Submersible Pumps",
        "hubs": "Pune, Coimbatore, Bangalore"
    },
    {
        "id": 5,
        "key": "Niche 5: Batteries, Solar Energy & Renewable Scrap",
        "title": "Niche 5: Solar & Batteries",
        "icon": "☀️",
        "subproducts": "TOPCon PV Modules, LiFePO4 ESS, Solar Scrap 500MT",
        "hubs": "Gujarat, Bangalore, Nhava Sheva"
    },
    {
        "id": 6,
        "key": "Niche 6: Industrial Generators",
        "title": "Niche 6: Industrial Gensets",
        "icon": "⚙️",
        "subproducts": "Cummins Silent Diesel Gensets, Containerized Power",
        "hubs": "Pune, Kolhapur, Faridabad"
    },
    {
        "id": 7,
        "key": "Niche 7: LED Lighting & Lighting Controls",
        "title": "Niche 7: LED & Smart Controls",
        "icon": "💡",
        "subproducts": "Smart Streetlight SCADA, High-Bay LEDs, Dimming",
        "hubs": "Delhi NCR, Mumbai, Bangalore"
    },
    {
        "id": 8,
        "key": "Niche 8: Commercial Appliances",
        "title": "Niche 8: Commercial Appliances",
        "icon": "🧼",
        "subproducts": "Ride-On Floor Scrubbers, Industrial Dehumidifiers",
        "hubs": "Coimbatore, Pune, Delhi NCR"
    },
    {
        "id": 9,
        "key": "Niche 9: Sensors & Testing",
        "title": "Niche 9: Sensors & Testing",
        "icon": "📡",
        "subproducts": "PIR Motion Sensors, Transformer Test Benches",
        "hubs": "Vadodara, Bangalore, Delhi NCR"
    },
    {
        "id": 10,
        "key": "Niche 10: Electric Vehicles & EV Infrastructure",
        "title": "Niche 10: EV & Charging Infra",
        "icon": "🚗",
        "subproducts": "Fast DC Dual-Gun Chargers, Type 2 Cables, EV Battery",
        "hubs": "Bangalore, Pune, Gurgaon"
    },
    {
        "id": 11,
        "key": "Niche 11: Printed Circuit Boards (PCB) & PCBA",
        "title": "Niche 11: PCBs & SMT PCBA",
        "icon": "📟",
        "subproducts": "Multi-Layer FR4 PCBs, Turnkey PCBA, Aluminum MCPCB",
        "hubs": "Bangalore, Gandhinagar, Chennai"
    },
    {
        "id": 12,
        "key": "Niche 12: Building Materials & Wooden Panels",
        "title": "Niche 12: Building & Panels",
        "icon": "🪵",
        "subproducts": "Marine Hardwood Plywood, Laminated MDF, Particle",
        "hubs": "Yamunanagar, Perumbavoor, Gujarat"
    },
    {
        "id": 13,
        "key": "Niche 13: Automotive & Car Parts / Auto Components",
        "title": "Niche 13: Automotive & Car Parts",
        "icon": "🏎️",
        "subproducts": "Brake Pads/Discs, Shock Absorbers, Wiring, Radiators",
        "hubs": "Pune, Chennai, Gurgaon, Rajkot"
    },
    {
        "id": 14,
        "key": "Miscellaneous Niche",
        "title": "Miscellaneous & Other",
        "icon": "📦",
        "subproducts": "Other Uncategorized Industrial Products & General Trade",
        "hubs": "All India & Global Sourcing"
    }
]

def classify_product_niche(product_name, specifications="", hs_code=""):
    """
    Intelligently maps a product to one of the 13 core industrial niches based on
    product name, technical specifications, and HS tariff codes.
    Returns the exact niche key string, or 'Miscellaneous Niche' if no match.
    """
    text = f"{product_name} {specifications}".lower()
    hs = str(hs_code).strip()

    # Niche 13: Automotive & Car Parts / Auto Components
    if any(k in text for k in [
        "brake pad", "brake disc", "rotor", "brake drum", "caliper", "brake lining",
        "shock absorber", "strut", "suspension", "wishbone", "control arm", "ball joint",
        "tie rod", "steering rack", "air filter", "oil filter", "fuel filter", "cabin filter",
        "radiator", "intercooler", "cooling fan", "spark plug", "glow plug", "ignition coil",
        "wiring harness", "automotive sensor", "car sensor", "oxygen sensor", "abs sensor",
        "headlamp", "tail lamp", "car lighting", "alternator", "starter motor", "clutch plate",
        "clutch kit", "friction disc", "engine valve", "piston ring", "cylinder liner",
        "auto parts", "car spare", "automotive", "auto component"
    ]) or hs.startswith(("8708", "8409", "8511", "8512")):
        return "Niche 13: Automotive & Car Parts / Auto Components"

    # Niche 11: Printed Circuit Boards (PCB) & PCBA
    if any(k in text for k in [
        "pcb", "printed circuit board", "pcba", "smt assembly", "surface mount",
        "fr4", "mcpcb", "fpc", "copper clad laminate", "ccl", "ems manufacturing",
        "multilayer pcb", "rigid pcb", "flexible pcb"
    ]) or hs.startswith("8534"):
        return "Niche 11: Printed Circuit Boards (PCB) & PCBA"

    # Niche 10: Electric Vehicles & EV Infrastructure
    if any(k in text for k in [
        "ev charger", "electric vehicle charger", "ev charging", "dc fast charger",
        "ac wallbox", "ccs2", "type 2 cable", "type 2 connector", "chademo",
        "ev battery pack", "bms controller", "evse"
    ]) or (any(k in text for k in ["ev ", "electric vehicle"]) and any(k in text for k in ["battery", "charger", "station", "cable"])):
        return "Niche 10: Electric Vehicles & EV Infrastructure"

    # Niche 5: Batteries, Solar Energy & Renewable Scrap
    if any(k in text for k in [
        "solar panel", "pv module", "photovoltaic", "topcon", "perc", "bifacial",
        "solar energy", "solar scrap", "pv scrap", "decommissioned panel",
        "lifepo4", "lithium battery pack", "energy storage", "solar inverter", "ess pack"
    ]) or hs.startswith(("854143", "8548", "8507")):
        return "Niche 5: Batteries, Solar Energy & Renewable Scrap"

    # Niche 3: Power Distribution & Protection Relays
    if any(k in text for k in [
        "protection relay", "numerical relay", "feeder protection", "transformer protection",
        "sel-", "arc-flash", "crp panel", "control and relay panel", "switchgear panel",
        "circuit breaker", "vcb", "acb", "mccb", "pcc panel", "mcc panel",
        "distribution transformer", "substation panel"
    ]) or hs.startswith(("853649", "8537", "8504")):
        return "Niche 3: Power Distribution & Protection Relays"

    # Niche 2: Wires & Cables
    if any(k in text for k in [
        "xlpe cable", "power cable", "armored cable", "submersible cable", "flat cable",
        "copper wire", "winding wire", "hv cable", "mv cable", "lv cable", "hose reel",
        "binding wire", "cable wire"
    ]) or (hs.startswith("8544") and not any(k in text for k in ["harness", "ev charging"])):
        return "Niche 2: Wires & Cables"

    # Niche 4: HVAC, Fans, Pumps & Actuators
    if any(k in text for k in [
        "actuator", "hydraulic actuator", "speed regulating motor", "motor governor",
        "groschopp", "axial fan", "centrifugal fan", "submersible pump", "borehole pump",
        "water pump", "compressor", "hvac", "refrigeration part"
    ]) or hs.startswith(("850110", "8413", "8414")):
        return "Niche 4: HVAC, Fans, Pumps & Actuators"

    # Niche 1: Electrical & Electronic Components
    if any(k in text for k in [
        "rocker switch", "power switch", "toggle switch", "push button", "cable gland",
        "terminal lug", "crimp", "terminal block", "real time clock", "rtc",
        "integrated circuit", "epson ra-", "microcontroller", "capacitor",
        "battery holder", "fan motor", "oled display", "lcd module", "rf remote", "cqc"
    ]) or hs.startswith(("853650", "853690", "8542", "8528", "8532")):
        return "Niche 1: Electrical & Electronic Components"

    # Niche 7: LED Lighting & Lighting Controls
    if any(k in text for k in [
        "lighting control", "dimming module", "streetlight monitoring", "dali",
        "smart lighting", "high-bay", "luminaire", "led streetlight", "floodlight",
        "smart wifi socket", "poultry lighting"
    ]) or hs.startswith("9405"):
        return "Niche 7: LED Lighting & Lighting Controls"

    # Niche 6: Industrial Generators
    if any(k in text for k in [
        "generator set", "genset", "diesel generator", "cummins generator",
        "silent generator", "gas generator", "wind turbine"
    ]) or hs.startswith("8502"):
        return "Niche 6: Industrial Generators"

    # Niche 8: Commercial Appliances
    if any(k in text for k in [
        "floor scrubber", "scrubber dryer", "cleaning machine", "dehumidifier",
        "commercial laundry", "industrial kitchen"
    ]) or hs.startswith(("8479", "8415")):
        return "Niche 8: Commercial Appliances"

    # Niche 9: Sensors & Testing
    if any(k in text for k in [
        "pir sensor", "motion sensor", "float switch", "test bench", "turns ratio",
        "winding resistance", "multimeter", "testing equipment", "data logger"
    ]) or hs.startswith("9030"):
        return "Niche 9: Sensors & Testing"

    # Niche 12: Building Materials & Wooden Panels
    if any(k in text for k in [
        "plywood", "mdf", "particle board", "laminated board", "decorative panel",
        "melamine board", "marine plywood", "veneer panel", "wood panel"
    ]) or hs.startswith(("4412", "4411")):
        return "Niche 12: Building Materials & Wooden Panels"

    # Fallback to Miscellaneous Niche if outside all 13 niches
    return "Miscellaneous Niche"



INDIAN_CITY_AREAS = {
    'Mumbai': ['All Areas', 'Bhiwandi', 'Kurla', 'Andheri', 'Kanjurmarg', 'Goregaon', 'Bhandup', 'Sakinaka', 'Govandi', 'Dadar', 'Borivali'],
    'Bhiwandi': ['All Areas', 'Mankoli', 'Rahnal', 'Vashere', 'Purna', 'Sonale', 'Anjur Phata', 'Dapode', 'Val Village', 'Kasheli'],
    'Navi Mumbai': ['All Areas', 'Turbhe', 'Taloja', 'Mahape', 'Rabale', 'Pawane', 'Panvel', 'Nerul', 'Koparkhairane', 'Airoli', 'Dronagiri'],
    'Thane': ['All Areas', 'Wagle Estate', 'Ghubunder Road', 'Kolshet', 'Manpada', 'Balkum', 'Kalwa', 'Majiwada'],
    'Pune': ['All Areas', 'Chakan', 'Bhosari', 'Talegaon', 'Hinjewadi', 'Hadapsar', 'Wagholi', 'Shikrapur', 'Pimpri', 'Markal', 'Pirangut', 'Sanaswadi', 'Fursungi'],
    'Chakan': ['All Areas', 'Chakan MIDC Phase 1', 'Chakan MIDC Phase 2', 'Mahalunge', 'Kharabwadi', 'Kuruli', 'Vasuli', 'Ambethan'],
    'Delhi NCR': ['All Areas', 'Okhla Industrial Area', 'Udyog Vihar', 'Manesar IMT', 'Sector 37 Gurgaon', 'Greater Noida Ecotech', 'Kasna', 'Sahibabad', 'Faridabad Sector 24', 'Mohan Cooperative', 'Mayapuri', 'Patparganj', 'Kirti Nagar', 'Narela'],
    'Gurgaon': ['All Areas', 'Udyog Vihar', 'IMT Manesar', 'Sector 37', 'Pace City', 'Sector 18', 'Kadipur', 'Daulatabad', 'Sohna Road'],
    'Noida': ['All Areas', 'Sector 63', 'Sector 80', 'Sector 81', 'Sector 83', 'Greater Noida Ecotech', 'Kasna', 'Sector 10', 'Sector 59'],
    'Faridabad': ['All Areas', 'Sector 24', 'Sector 25', 'Sector 58', 'Sector 59', 'Ballabhgarh', 'NH-5', 'Prithla', 'Mathura Road'],
    'Ghaziabad': ['All Areas', 'Sahibabad Industrial Area', 'Loni Road', 'Kavi Nagar', 'Bulandshahr Road', 'Dasna', 'Mohan Nagar', 'Meerut Road'],
    'Bangalore': ['All Areas', 'Peenya Industrial Area', 'Nelamangala', 'Hoskote', 'Bommasandra', 'Electronic City', 'Whitefield', 'Jigani', 'Attibele', 'Dobbspet', 'Yelahanka', 'Rajajinagar'],
    'Hyderabad': ['All Areas', 'Medchal', 'Patancheru', 'Cherlapally', 'Jeedimetla', 'Uppal', 'Shamshabad', 'Kothur', 'Balanagar', 'Sanathnagar', 'Nacharam'],
    'Chennai': ['All Areas', 'Sriperumbudur', 'Oragadam', 'Ambattur', 'Guindy', 'Madhavaram', 'Red Hills', 'Ennore', 'Maraimalai Nagar', 'Poonamallee', 'Thirumudivakkam'],
    'Ahmedabad': ['All Areas', 'Sanand GIDC', 'Changodar', 'Aslali', 'Moraiya', 'Narol', 'Odhav', 'Vatva GIDC', 'Sarkhej', 'Bakrol', 'Kathwada'],
    'Surat': ['All Areas', 'Sachin GIDC', 'Pandesara', 'Hazira', 'Udhna', 'Kamrej', 'Katargam', 'Kim', 'Olpad'],
    'Kolkata': ['All Areas', 'Dankuni', 'Dhulagarh', 'Taratala', 'Kasba', 'Howrah', 'Kalyani', 'Barasat', 'Maheshtala', 'Uluberia'],
    'Jaipur': ['All Areas', 'Sitapura Industrial Area', 'Vishwakarma VKI', 'Mansarovar', 'Bindayaka', 'Bagru', 'Jhotwara', 'Hirawala'],
    'Indore': ['All Areas', 'Pithampur', 'Sanwer Road Industrial Area', 'Palda', 'Dewas Naka', 'Rau', 'Laxmi Bai Nagar', 'Manglia'],
    'Nagpur': ['All Areas', 'Butibori MIDC', 'Hingna MIDC', 'MIHAN', 'Kalmeshwar', 'Wadi', 'Kamptee'],
    'Coimbatore': ['All Areas', 'Saravanampatti', 'Peelamedu', 'Kurichi SIDCO', 'Ganapathy', 'Singanallur', 'Malumichampatti', 'Sulur'],
    'Vadodara': ['All Areas', 'Makarpura GIDC', 'Nandesari', 'Manjusar GIDC', 'Savli GIDC', 'Waghodia', 'Gorwa', 'Ranoli'],
    'Nashik': ['All Areas', 'Ambad MIDC', 'Satpur MIDC', 'Sinnar MIDC', 'Gonde', 'Dindori', 'Vilholi'],
    'Chandigarh': ['All Areas', 'Industrial Area Phase 1', 'Industrial Area Phase 2', 'Mohali Phase 7', 'Mohali Phase 8', 'Panchkula Sector 19', 'Derabassi', 'Zirakpur'],
    'Ludhiana': ['All Areas', 'Focal Point Phase 1-8', 'Industrial Area A', 'Industrial Area B', 'Sahnewal', 'Doraha', 'Gill Road', 'Transport Nagar'],
    'Kochi': ['All Areas', 'Kalamassery', 'Eloor', 'Willingdon Island', 'Aluva', 'Angamaly', 'Kundannoor', 'Maradu', 'Kakkanad']
}

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SinoMagan Global Trade Intelligence")
        self.geometry("1100x800")
        
        icon_path = resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.ui_queue = queue.Queue()
        
        self.logger = setup_logger(self.log_callback)
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        self.tab_discovery = self.tabview.add("URL Discovery")
        self.tab_prod_sourcing = self.tabview.add("Product Sourcing")
        self.tab_suppliers = self.tabview.add("Suppliers Scraper")
        self.tab_sup_db = self.tabview.add("Suppliers Database")
        self.tab_buyers = self.tabview.add("Buyers Scraper")
        self.tab_buy_db = self.tabview.add("Buyers Database")
        self.tab_warehouses = self.tabview.add("Warehouses Scraper")
        self.tab_wh_db = self.tabview.add("Warehouses Database")
        self.tab_logistics = self.tabview.add("Logistics Scraper")
        self.tab_log_db = self.tabview.add("Logistics Database")
        self.tab_logs = self.tabview.add("Agent Logs")
        
        self.setup_discovery_tab()
        self.setup_prod_sourcing_tab()
        self.setup_suppliers_tab()
        self.setup_sup_db_tab()
        self.setup_buyers_tab()
        self.setup_buy_db_tab()
        self.setup_warehouses_tab()
        self.setup_wh_db_tab()
        self.setup_logistics_tab()
        self.setup_log_db_tab()
        self.setup_logs_tab()
        
        self.btn_restart = ctk.CTkButton(self, text="Restart App", command=self.restart_app, width=100, fg_color="#b35900", hover_color="#804000")
        self.btn_restart.grid(row=1, column=0, pady=(0, 10), padx=20, sticky="e")
        
        # Start UI event polling loop
        self.poll_queue()

    def poll_queue(self):
        # Safely execute background thread UI tasks on the main thread
        while not self.ui_queue.empty():
            try:
                task, args = self.ui_queue.get_nowait()
                task(*args)
            except queue.Empty:
                break
        self.after(100, self.poll_queue)

    def restart_app(self):
        self.logger.info("Restarting application...")
        self.destroy()
        subprocess.Popen([sys.executable] + sys.argv)

    def setup_discovery_tab(self):
        self.tab_discovery.grid_columnconfigure(0, weight=1)
        self.tab_discovery.grid_rowconfigure(3, weight=1)
        
        control_frame = ctk.CTkFrame(self.tab_discovery)
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.country_regions = [
            'Worldwide (wt-wt)', 'India (in-en)', 'USA (us-en)', 'Germany (de-de)', 
            'China (cn-zh)', 'United Kingdom (uk-en)', 'UAE (ae-en)', 'Saudi Arabia (sa-ar)', 
            'Australia (au-en)', 'Canada (ca-en)', 'Japan (jp-jp)', 'South Korea (kr-kr)',
            'Vietnam (vn-en)', 'Singapore (sg-en)', 'Hong Kong (hk-en)', 'Malaysia (my-en)', 
            'Indonesia (id-en)', 'Philippines (ph-en)', 'Thailand (th-en)', 'Poland (pl-pl)', 
            'Netherlands (nl-nl)', 'France (fr-fr)', 'Spain (es-es)', 'Qatar (qa-en)', 
            'Kuwait (kw-en)', 'Oman (om-en)', 'Bahrain (bh-en)', 'South Africa (za-en)', 
            'Romania (ro-ro)', 'Finland (fi-fi)', 'Albania (al-al)', 'Moldova (md-ro)'
        ]
        self.indian_city_regions = [
            'Mumbai', 'Bhiwandi', 'Navi Mumbai', 'Thane', 'Pune', 'Chakan', 'Delhi NCR', 
            'Gurgaon', 'Noida', 'Faridabad', 'Ghaziabad', 'Bangalore', 'Hyderabad', 
            'Chennai', 'Ahmedabad', 'Surat', 'Kolkata', 'Jaipur', 'Indore', 'Nagpur', 
            'Coimbatore', 'Vadodara', 'Nashik', 'Chandigarh', 'Ludhiana', 'Kochi'
        ]
        self.radius_options = ['5 km', '10 km', '15 km', '20 km', '25 km', '30 km', '50 km', '75 km', '100 km']
        self.indian_city_areas = INDIAN_CITY_AREAS

        self.strategy_var = ctk.StringVar(value="Buyers")
        self.strategy_dropdown = ctk.CTkOptionMenu(
            control_frame, 
            values=["Buyers", "Suppliers", "Warehouses", "Logistics"],
            variable=self.strategy_var, width=115,
            command=self.on_strategy_change
        )
        self.strategy_dropdown.pack(side="left", padx=4)

        self.region_var = ctk.StringVar(value="Worldwide (wt-wt)")
        self.region_dropdown = ctk.CTkOptionMenu(
            control_frame, 
            values=self.country_regions,
            variable=self.region_var, width=130,
            command=self.on_region_change
        )
        self.region_dropdown.pack(side="left", padx=4)

        self.radius_var = ctk.StringVar(value="15 km")
        self.radius_dropdown = ctk.CTkOptionMenu(
            control_frame,
            values=self.radius_options,
            variable=self.radius_var, width=80,
            command=self.on_radius_change
        )
        self.radius_dropdown.pack(side="left", padx=4)
        self.radius_dropdown.configure(state="disabled")

        self.area_var = ctk.StringVar(value="All Areas")
        self.area_dropdown = ctk.CTkOptionMenu(
            control_frame,
            values=["All Areas"],
            variable=self.area_var, width=115,
            command=self.on_area_change
        )
        self.area_dropdown.pack(side="left", padx=4)
        self.area_dropdown.configure(state="disabled")
        
        self.query_entry = ctk.CTkTextbox(control_frame, width=245, height=60, wrap="word")
        self.query_entry.insert("0.0", "Enter base query...")
        self.query_entry.pack(side="left", padx=10, pady=10)
        
        self.btn_suggest = ctk.CTkButton(control_frame, text="💡 Suggest", width=70, command=self.suggest_query, fg_color="#4B0082", hover_color="#300050")
        self.btn_suggest.pack(side="left", padx=5)
        
        slider_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        slider_frame.pack(side="left", padx=6)

        self.lbl_slider_val = ctk.CTkLabel(slider_frame, text="Max: 25 URLs", font=("Arial", 11, "bold"), text_color="#3a86ff")
        self.lbl_slider_val.pack(anchor="center", pady=(0, 2))

        def on_slider_change(val):
            val_int = int(round(val))
            self.lbl_slider_val.configure(text=f"Max: {val_int} URLs")

        self.results_slider = ctk.CTkSlider(
            slider_frame, 
            from_=5, 
            to=100, 
            number_of_steps=19, 
            width=110,
            command=on_slider_change
        )
        self.results_slider.set(25)
        self.results_slider.pack(anchor="center")
        
        self.btn_search = ctk.CTkButton(control_frame, text="Discover URLs", command=self.start_discovery)
        self.btn_search.pack(side="left", padx=10)
        
        def get_disc_mode():
            s = self.strategy_var.get()
            if s == "Suppliers":
                return "supplier"
            elif s == "Logistics":
                return "logistics"
            elif s == "Warehouses":
                return "warehouse"
            return "buyer"

        self.btn_disc_prop = ctk.CTkButton(
            control_frame, 
            text="🌐 Quick URL Proposal", 
            command=lambda: self.open_url_proposal_window(mode=get_disc_mode()), 
            fg_color="#005b96", 
            hover_color="#003f66"
        )
        self.btn_disc_prop.pack(side="left", padx=10)
        
        self.lbl_disc_status = ctk.CTkLabel(control_frame, text="Status: Idle", text_color="gray")
        self.lbl_disc_status.pack(side="left", padx=10)
        
        self.spec_frame = ctk.CTkFrame(self.tab_discovery)
        self.spec_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        lbl_spec = ctk.CTkLabel(self.spec_frame, text="Or paste raw Buyer/Supplier Requirement Spec:")
        lbl_spec.pack(side="left", padx=10, pady=5)
        
        self.spec_textbox = ctk.CTkTextbox(self.spec_frame, height=40, width=400, wrap="word")
        self.spec_textbox.pack(side="left", fill="x", expand=True, padx=10, pady=5)
        
        self.btn_spec_gen = ctk.CTkButton(self.spec_frame, text="Generate Query", width=120, command=self.generate_from_spec)
        self.btn_spec_gen.pack(side="left", padx=10, pady=5)
        
        lbl = ctk.CTkLabel(self.tab_discovery, text="Select a suggested query from the left or discover URLs to view raw & vetted results side-by-side:", text_color="gray")
        lbl.grid(row=2, column=0, padx=10, sticky="w")
        
        results_container = ctk.CTkFrame(self.tab_discovery, fg_color="transparent")
        results_container.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")
        results_container.grid_columnconfigure(0, weight=0, minsize=290)
        results_container.grid_columnconfigure(1, weight=1)
        results_container.grid_columnconfigure(2, weight=1)
        results_container.grid_rowconfigure(1, weight=1)
        
        # Column 0: Suggested Queries Panel (Left Side)
        self.lbl_suggested_queries = ctk.CTkLabel(results_container, text="💡 Suggested Queries:", font=("Arial", 12, "bold"))
        self.lbl_suggested_queries.grid(row=0, column=0, padx=(0, 5), pady=(0, 5), sticky="w")
        
        self.queries_list_frame = ctk.CTkScrollableFrame(results_container, width=280)
        self.queries_list_frame.grid(row=1, column=0, padx=(0, 5), pady=0, sticky="nsew")
        
        # Column 1: Raw Search Results
        self.lbl_raw_urls = ctk.CTkLabel(results_container, text="🌐 Raw Search Results (DuckDuckGo):", font=("Arial", 12, "bold"))
        self.lbl_raw_urls.grid(row=0, column=1, padx=(5, 5), pady=(0, 5), sticky="w")
        
        self.raw_urls_textbox = ctk.CTkTextbox(results_container, wrap="none")
        self.raw_urls_textbox.grid(row=1, column=1, padx=(5, 5), pady=0, sticky="nsew")
        
        # Column 2: High-Quality Filtered URLs
        hq_header_frame = ctk.CTkFrame(results_container, fg_color="transparent")
        hq_header_frame.grid(row=0, column=2, padx=(5, 0), pady=(0, 5), sticky="ew")
        
        self.lbl_hq_urls = ctk.CTkLabel(hq_header_frame, text="⭐ High-Quality URLs (AI Filtered):", font=("Arial", 12, "bold"))
        self.lbl_hq_urls.pack(side="left")
        
        self.btn_copy_all_hq = ctk.CTkButton(
            hq_header_frame, 
            text="📋 Copy All", 
            width=70, 
            height=22, 
            font=("Arial", 10), 
            command=self.copy_all_hq_urls, 
            fg_color="#3a3a3a", 
            hover_color="#2b2b2b"
        )
        self.btn_copy_all_hq.pack(side="right")

        self.btn_send_to_scraper = ctk.CTkButton(
            hq_header_frame, 
            text="➔ Send to Scraper", 
            width=105, 
            height=22, 
            font=("Arial", 10), 
            command=self.send_hq_urls_to_scraper, 
            fg_color="#005b96", 
            hover_color="#003f66"
        )
        self.btn_send_to_scraper.pack(side="right", padx=(0, 6))

        self.discovery_urls_frame = ctk.CTkScrollableFrame(results_container)
        self.discovery_urls_frame.grid(row=1, column=2, padx=(5, 0), pady=0, sticky="nsew")
        self.current_hq_urls = []
        self.populate_hq_urls([])

        # Initial starter queries (covering all 13 product niches including Car Parts, PCBs & Electric Vehicles)
        starter_queries = [
            "switchgear panel distributors USA",
            "commercial lighting importers UAE",
            "power distribution equipment distributors Qatar",
            "electrical control equipment contactors importers Qatar",
            "CAME TOP-433EE remote control transmitters Qatar",
            "gate automation remote control switches distributors Qatar",
            "electronic components display LCD OLED distributors Hong Kong",
            "switches push button toggle switch wholesalers Hong Kong",
            "rechargeable battery holder capacitor importers Hong Kong",
            "fan motor pump air cooler components suppliers Hong Kong",
            "illuminated rocker power switches 16A 20A distributors Hong Kong",
            "round square big rocker switch suppliers Hong Kong",
            "rocker switches CQC TUV CE red green button wholesalers Hong Kong",
            "power switches 6A 10A 16A 20A importers Hong Kong",
            "plywood panels MDF laminated boards distributors Philippines",
            "wooden decorative panels wholesaler Philippines",
            "MDF panels laminated board importers Manila Philippines",
            "plywood sheets building materials dealers Cebu Philippines",
            "Epson RA-8565SA PURE SN integrated circuit distributors Poland",
            "electronic components IC distributors Poland",
            "RA-8565SA real time clock IC tape reel Poland",
            "brand new original integrated circuit suppliers Poland",
            "photovoltaic solar panels distributors Spain",
            "solar energy panels importers Seville Spain",
            "commercial PV module suppliers Spain",
            "solar panel wholesale container suppliers Spain",
            "Groschopp hydraulic actuator speed regulating motor distributors Philippines",
            "Groschopp WK0920702 motor governor suppliers Philippines",
            "hydraulic actuator speed motor distributors Manila Philippines",
            "electric motor speed regulating governor importers Philippines",
            "433MHz wireless RF transmitter switches importers Qatar",
            "solar panel scrap importers India",
            "PV module scrap buyers 500 MT India",
            "decommissioned solar panels scrap recyclers India",
            "circuit breaker distribution transformer wholesalers Qatar",
            "industrial power management switchboard dealers Qatar",
            "centralized lighting control systems distributors Bahrain",
            "automated lighting controls importers Bahrain",
            "dimming modules lighting controllers UAE",
            "smart building automation lighting controllers Saudi Arabia",
            "streetlight monitoring control systems Qatar",
            "industrial wire cable wholesalers Germany",
            "lithium battery pack distributors UK",
            "HVAC equipment wholesalers Australia",
            "solar inverter distributors Canada",
            "diesel generator dealers Saudi Arabia",
            "cable gland terminal block importers Oman",
            "numerical protection relays SEL distributors Oman",
            "feeder protection relay SEL 751 importers Oman",
            "transformer protection relay SEL 787 suppliers Oman",
            "generator protection relay SEL 700G dealers Oman",
            "floor scrubber cleaning equipment distributors Qatar",
            "PIR sensor testing equipment wholesalers Singapore",
            "industrial fan pump suppliers Kuwait",
            "home energy storage importers Poland",
            "EV charging station distributors USA",
            "electric vehicle charger importers UAE",
            "PCB assembly PCBA turnkey services Germany",
            "printed circuit board distributors USA",
            "rigid multi layer FR4 PCB board importers UK",
            "flexible PCB FPC distributors Canada",
            "automotive brake pads discs distributors USA",
            "car suspension shock absorber wholesalers UAE",
            "automotive spare parts distributors Qatar",
            "car engine components auto parts importers Germany",
            "automotive filters oil air fuel wholesalers Saudi Arabia",
            "car radiators cooling system distributors UK",
            "automotive ignition coil spark plug importers Australia",
            "car steering suspension parts distributors Canada",
            "aftermarket auto parts wholesale distributors USA"
        ]
        self.populate_suggested_queries(starter_queries)
        self.select_suggested_query(starter_queries[0])

    def populate_suggested_queries(self, queries):
        for widget in self.queries_list_frame.winfo_children():
            widget.destroy()
            
        if not queries:
            lbl_empty = ctk.CTkLabel(
                self.queries_list_frame, 
                text="No suggestions available.", 
                text_color="gray", 
                font=("Arial", 11, "italic")
            )
            lbl_empty.pack(pady=15, padx=5)
            return

        for q in queries:
            q_clean = q.strip()
            if not q_clean:
                continue
                
            row_frame = ctk.CTkFrame(self.queries_list_frame, fg_color=("#EAEAEA", "#2B2B2B"), corner_radius=6)
            row_frame.pack(fill="x", padx=4, pady=3)
            
            lbl_q = ctk.CTkLabel(
                row_frame, 
                text=q_clean, 
                anchor="w", 
                justify="left", 
                wraplength=170,
                font=("Arial", 11)
            )
            lbl_q.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=5)
            
            btn_use = ctk.CTkButton(
                row_frame, 
                text="Use ➔", 
                width=46, 
                height=24, 
                font=("Arial", 10, "bold"),
                fg_color="#1f538d", 
                hover_color="#14375e",
                command=lambda text=q_clean: self.select_suggested_query(text)
            )
            btn_use.pack(side="right", padx=(2, 6), pady=5)
            
            row_frame.bind("<Button-1>", lambda e, text=q_clean: self.select_suggested_query(text))
            lbl_q.bind("<Button-1>", lambda e, text=q_clean: self.select_suggested_query(text))

    def select_suggested_query(self, query):
        self.query_entry.delete("0.0", "end")
        self.query_entry.insert("0.0", query)
        preview = query[:30] + "..." if len(query) > 30 else query
        self.lbl_disc_status.configure(text=f"Selected: {preview}")

    def populate_hq_urls(self, urls):
        self.current_hq_urls = list(urls) if urls else []
        for widget in self.discovery_urls_frame.winfo_children():
            widget.destroy()
            
        if not urls:
            lbl_empty = ctk.CTkLabel(
                self.discovery_urls_frame, 
                text="No high-quality URLs discovered yet.\nRun 'Discover URLs' above to search and filter leads.", 
                text_color="gray", 
                font=("Arial", 11, "italic"),
                justify="center"
            )
            lbl_empty.pack(pady=30, padx=10)
            return

        strategy = self.strategy_var.get()
        if strategy == "Suppliers":
            prop_btn_text = "📝 Sourcing RFQ"
            current_mode = "supplier"
        elif strategy == "Warehouses":
            prop_btn_text = "🏢 Rental Inquiry"
            current_mode = "warehouse"
        elif strategy == "Logistics":
            prop_btn_text = "📝 Freight RFQ"
            current_mode = "logistics"
        else:
            prop_btn_text = "📝 Create Proposal"
            current_mode = "buyer"

        for u in urls:
            url_str = u.strip()
            if not url_str:
                continue
                
            row_frame = ctk.CTkFrame(self.discovery_urls_frame, fg_color=("#EAEAEA", "#2B2B2B"), corner_radius=6)
            row_frame.pack(fill="x", padx=4, pady=3)
            
            # Action button: 📝 Sourcing RFQ / 📝 Freight RFQ / 📝 Create Proposal / 🏢 Rental Inquiry
            btn_prop = ctk.CTkButton(
                row_frame, 
                text=prop_btn_text, 
                width=125, 
                height=28, 
                font=("Arial", 11, "bold"),
                fg_color="#1f7a1f", 
                hover_color="#145214",
                command=lambda target=url_str, m=current_mode: self.open_url_proposal_window(target, auto_generate=True, mode=m)
            )
            btn_prop.pack(side="right", padx=(4, 6), pady=4)

            # Yellowpages directory deep extraction button: 📦 Extract Properties
            from scraper import is_yellowpages_directory
            if strategy == "Warehouses" and is_yellowpages_directory(url_str):
                btn_extract = ctk.CTkButton(
                    row_frame,
                    text="📦 Extract Properties",
                    width=135,
                    height=28,
                    font=("Arial", 11, "bold"),
                    fg_color="#6a0dad",
                    hover_color="#4b0082",
                    command=lambda target=url_str: self.scrape_properties_from_card(target)
                )
                btn_extract.pack(side="right", padx=(2, 4), pady=4)
            
            # Action button: 📋 Copy single URL
            btn_copy = ctk.CTkButton(
                row_frame,
                text="📋",
                width=30,
                height=28,
                font=("Arial", 11),
                fg_color="#3a3a3a",
                hover_color="#2b2b2b",
                command=lambda target=url_str: self.copy_single_url(target)
            )
            btn_copy.pack(side="right", padx=(2, 2), pady=4)
            
            # URL text label
            lbl_url = ctk.CTkLabel(
                row_frame, 
                text=url_str, 
                anchor="w", 
                justify="left", 
                wraplength=270,
                font=("Arial", 11)
            )
            lbl_url.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=4)

    def scrape_properties_from_card(self, directory_url):
        self.lbl_disc_status.configure(text=f"Status: Deep scraping properties from directory...")
        import threading
        def worker():
            try:
                from scraper import extract_subproperties_from_directory
                sub_props = extract_subproperties_from_directory(directory_url, logger=self.logger, max_properties=12)
                if sub_props:
                    current = list(self.current_hq_urls) if hasattr(self, 'current_hq_urls') else []
                    new_added = [p for p in sub_props if p not in current]
                    updated_urls = new_added + current
                    self.current_hq_urls = updated_urls
                    def on_success():
                        self.populate_hq_urls(updated_urls)
                        self.lbl_disc_status.configure(text=f"Extracted {len(new_added)} properties from directory! ✅")
                    self.ui_queue.put((on_success, ()))
                else:
                    def on_fail():
                        self.lbl_disc_status.configure(text="No direct property listings found on directory page.")
                    self.ui_queue.put((on_fail, ()))
            except Exception as e:
                self.logger.error(f"Directory property extraction failed: {e}")
                self.ui_queue.put((lambda: self.lbl_disc_status.configure(text="Error extracting properties."), ()))
                
        threading.Thread(target=worker, daemon=True).start()

    def copy_single_url(self, url_str):
        self.clipboard_clear()
        self.clipboard_append(url_str)
        preview = url_str[:30] + "..." if len(url_str) > 30 else url_str
        self.lbl_disc_status.configure(text=f"Copied: {preview}")

    def copy_all_hq_urls(self):
        if hasattr(self, 'current_hq_urls') and self.current_hq_urls:
            self.clipboard_clear()
            self.clipboard_append("\n".join(self.current_hq_urls))
            self.btn_copy_all_hq.configure(text="Copied! ✅")
            self.lbl_disc_status.configure(text=f"Copied {len(self.current_hq_urls)} URLs to clipboard")
            self.after(1500, lambda: self.btn_copy_all_hq.configure(text="📋 Copy All"))

    def send_hq_urls_to_scraper(self):
        if not hasattr(self, 'current_hq_urls') or not self.current_hq_urls:
            return
        strategy = self.strategy_var.get()
        urls_joined = "\n".join(self.current_hq_urls) + "\n"
        if strategy == "Suppliers":
            self.sup_urls_textbox.delete("0.0", "end")
            self.sup_urls_textbox.insert("0.0", urls_joined)
            self.tabview.set("Suppliers Scraper")
            self.lbl_sup_status.configure(text=f"Loaded {len(self.current_hq_urls)} URLs from Discovery")
        elif strategy == "Warehouses":
            self.wh_urls_textbox.delete("0.0", "end")
            self.wh_urls_textbox.insert("0.0", urls_joined)
            self.tabview.set("Warehouses Scraper")
            self.lbl_wh_status.configure(text=f"Loaded {len(self.current_hq_urls)} Warehouse URLs from Discovery")
        elif strategy == "Logistics":
            self.log_urls_textbox.delete("0.0", "end")
            self.log_urls_textbox.insert("0.0", urls_joined)
            self.tabview.set("Logistics Scraper")
            self.lbl_log_status.configure(text=f"Loaded {len(self.current_hq_urls)} Logistics URLs from Discovery")
        else:
            self.buy_urls_textbox.delete("0.0", "end")
            self.buy_urls_textbox.insert("0.0", urls_joined)
            self.tabview.set("Buyers Scraper")
            self.lbl_buy_status.configure(text=f"Loaded {len(self.current_hq_urls)} URLs from Discovery")

    def on_area_change(self, choice):
        strategy = self.strategy_var.get()
        if strategy == "Warehouses":
            city = self.region_var.get()
            radius = self.radius_var.get()
            queries = self.get_warehouse_starter_queries(city, radius, choice)
            self.populate_suggested_queries(queries)
            self.select_suggested_query(queries[0])

    def on_radius_change(self, choice):
        strategy = self.strategy_var.get()
        if strategy == "Warehouses":
            city = self.region_var.get()
            radius = choice
            area = self.area_var.get() if hasattr(self, 'area_var') else "All Areas"
            queries = self.get_warehouse_starter_queries(city, radius, area)
            self.populate_suggested_queries(queries)
            self.select_suggested_query(queries[0])

    def get_supplier_starter_queries(self, dest):
        """Returns 13-niche starter queries for suppliers tailored to the chosen region (India, specific country, or Worldwide)."""
        dest_clean = dest.strip()
        if dest_clean.lower() == "india":
            return [
                "distribution transformer manufacturers India",
                "numerical protection relay suppliers India",
                "substation control and relay panel CRP manufacturers Gujarat",
                "power distribution equipment manufacturers India",
                "electrical contactors circuit breaker factories Gujarat",
                "switchgear panel factories Gujarat",
                "industrial power control panel makers Maharashtra",
                "centralized lighting control system manufacturers India",
                "automated lighting controllers dimming modules factories India",
                "streetlight monitoring control panel makers India",
                "copper wire cable manufacturers India",
                "solar panel PV module manufacturers Gujarat",
                "monocrystalline TOPCon solar panel factories India",
                "Tier 1 solar panel exporters India",
                "photovoltaic module manufacturers Bangalore",
                "solar panel scrap suppliers exporters",
                "PV module scrap suppliers 500 MT",
                "lithium battery pack makers Bangalore",
                "HVAC components suppliers Maharashtra",
                "circuit breaker factories India",
                "diesel generator manufacturers Pune",
                "brass cable glands manufacturers Jamnagar",
                "RF remote control switch manufacturers India",
                "gate automation transmitter receiver factories India",
                "electronic displays LCD OLED module suppliers India",
                "toggle switches push button manufacturers India",
                "illuminated rocker switch manufacturers India",
                "power switches 16A 20A CQC CE factories India",
                "round square rocker switch makers Gujarat",
                "electrolytic ceramic capacitor manufacturers Gujarat",
                "fan motor air cooler pump manufacturers Coimbatore",
                "hydraulic actuator motor manufacturers India",
                "speed regulating motor governor factories Pune",
                "fractional horsepower electric motor manufacturers Coimbatore",
                "integrated circuit IC component distributors India",
                "electronic component authorized distributors Bangalore",
                "Epson timing devices RTC distributors India",
                "plywood panel MDF board manufacturers Yamunanagar",
                "decorative laminated sheets manufacturers Gujarat",
                "commercial marine plywood factories Kerala",
                "MDF panel particle board suppliers India",
                "LED streetlight luminaire factories India",
                "industrial pump motor manufacturers Coimbatore",
                "floor scrubber cleaning machine suppliers India",
                "sensor testing equipment manufacturers Delhi NCR",
                "EV charging station manufacturers India",
                "electric vehicle battery pack manufacturers Pune",
                "printed circuit board PCB manufacturers India",
                "PCB assembly SMT PCBA factories Bangalore",
                "multi layer FR4 PCB board factories Gujarat",
                "copper clad laminate CCL suppliers India",
                "metal core aluminum MCPCB makers India",
                "automotive brake pads brake discs manufacturers India",
                "car suspension shock absorber factories Pune",
                "auto component precision CNC machined parts Rajkot",
                "automotive wiring harness manufacturers Gurgaon",
                "car radiator cooling fan factories Chennai",
                "automotive filter oil air fuel manufacturers Delhi NCR",
                "car steering rack tie rod ball joint factories Coimbatore",
                "automotive ignition coil starter motor manufacturers India",
                "clutch plate friction disc factories Aurangabad",
                "aftermarket car spare parts exporters India"
            ]
        else:
            return [
                f"distribution transformer manufacturers {dest_clean}",
                f"numerical protection relay suppliers {dest_clean}",
                f"power distribution equipment manufacturers {dest_clean}",
                f"switchgear panel manufacturers {dest_clean}",
                f"electrical contactor circuit breaker factories {dest_clean}",
                f"power cables wiring manufacturers {dest_clean}",
                f"centralized lighting control system manufacturers {dest_clean}",
                f"automated lighting controllers dimming modules factories {dest_clean}",
                f"solar panel PV module manufacturers {dest_clean}",
                f"commercial solar energy systems factories {dest_clean}",
                f"lithium battery pack manufacturers {dest_clean}",
                f"industrial diesel generator manufacturers {dest_clean}",
                f"cable glands terminal blocks manufacturers {dest_clean}",
                f"electronic components display LCD OLED suppliers {dest_clean}",
                f"rocker power switches 16A 20A factories {dest_clean}",
                f"hydraulic actuator speed regulating motor manufacturers {dest_clean}",
                f"integrated circuit IC semiconductor makers {dest_clean}",
                f"plywood panel MDF board manufacturers {dest_clean}",
                f"floor scrubber cleaning equipment manufacturers {dest_clean}",
                f"PIR sensor testing equipment manufacturers {dest_clean}",
                f"EV charging station manufacturers {dest_clean}",
                f"electric vehicle battery pack factories {dest_clean}",
                f"printed circuit board PCB manufacturers {dest_clean}",
                f"PCB assembly SMT PCBA turnkey factories {dest_clean}",
                f"multi layer FR4 PCB board factories {dest_clean}",
                f"automotive brake pads brake discs manufacturers {dest_clean}",
                f"car suspension shock absorber factories {dest_clean}",
                f"auto component precision CNC machined parts {dest_clean}",
                f"car radiator cooling fan factories {dest_clean}",
                f"automotive wiring harness manufacturers {dest_clean}",
                f"automotive filter oil air fuel factories {dest_clean}",
                f"car steering rack tie rod ball joint factories {dest_clean}",
                f"automotive ignition coil starter motor manufacturers {dest_clean}",
                f"clutch plate friction disc factories {dest_clean}",
                f"aftermarket car spare parts manufacturers {dest_clean}"
            ]

    def get_warehouse_starter_queries(self, city, radius, area="All Areas"):
        if area and area != "All Areas":
            return [
                f"warehouse for rent under {radius} {area} {city}",
                f"garage storage space under {radius} {area} {city}",
                f"godown on lease under {radius} {area} {city}",
                f"industrial shed for rent under {radius} {area} {city}",
                f"commercial storage unit under {radius} {area} olx",
                f"warehouse for rent under {radius} {area} {city} olx",
                f"garage for rent under {radius} {area} olx",
                f"godown for rent under {radius} {area} 99acres",
                f"industrial warehouse lease under {radius} {area} magicbricks",
                f"storage space for rent under {radius} {area} nobroker",
                f"warehouse shed on rent under {radius} {area} justdial",
                f"logistics park warehouse lease under {radius} {area} {city}",
                f"heavy vehicle parking garage yard under {radius} {area}",
                f"small warehouse storage for rent under {radius} {area} olx",
                f"RCC godown storage space under {radius} {area} {city}",
                f"container trailer accessible warehouse under {radius} {area}"
            ]

        # All Areas: dynamically distribute across top industrial/storage areas in this city
        city_areas = getattr(self, "indian_city_areas", INDIAN_CITY_AREAS).get(city, []) if self else INDIAN_CITY_AREAS.get(city, [])
        sub_areas = [a for a in city_areas if a != "All Areas"]
        if not sub_areas:
            sub_areas = [f"{city} Industrial Area", f"{city} MIDC"]

        def a(idx):
            return sub_areas[idx % len(sub_areas)]

        return [
            f"warehouse for rent under {radius} {a(0)} {city}",
            f"garage storage space under {radius} {a(1)} {city}",
            f"godown on lease under {radius} {a(2)} {city}",
            f"industrial shed for rent under {radius} {a(3)} {city}",
            f"commercial storage unit under {radius} {a(4)} olx",
            f"warehouse for rent under {radius} {a(0)} {city} olx",
            f"garage for rent under {radius} {a(1)} olx",
            f"godown for rent under {radius} {a(2)} 99acres",
            f"industrial warehouse lease under {radius} {a(3)} magicbricks",
            f"storage space for rent under {radius} {a(4)} nobroker",
            f"warehouse shed on rent under {radius} {a(5)} justdial",
            f"logistics park warehouse lease under {radius} {a(0)} {city}",
            f"heavy vehicle parking garage yard under {radius} {a(1)}",
            f"small warehouse storage for rent under {radius} {a(2)} olx",
            f"RCC godown storage space under {radius} {a(3)} {city}",
            f"container trailer accessible warehouse under {radius} {a(0)}"
        ]

    def on_region_change(self, choice):
        strategy = self.strategy_var.get()
        if strategy == "Suppliers":
            dest = choice.split(" (")[0].strip()
            queries = self.get_supplier_starter_queries(dest)
            self.populate_suggested_queries(queries)
            self.select_suggested_query(queries[0])
            return
        if strategy == "Warehouses":
            city = choice
            radius = self.radius_var.get()
            area_options = self.indian_city_areas.get(city, ["All Areas"])
            if hasattr(self, 'area_dropdown'):
                self.area_dropdown.configure(values=area_options)
                self.area_var.set("All Areas")
            queries = self.get_warehouse_starter_queries(city, radius, "All Areas")
            self.populate_suggested_queries(queries)
            self.select_suggested_query(queries[0])
            return
        dest = choice.split(" (")[0]
        if "Worldwide" in dest or "Global" in dest:
            dest = "worldwide"
        if strategy == "Logistics":
            queries = [
                f"freight forwarders India to {dest} container shipping",
                f"sea cargo forwarders Mumbai to {dest}",
                f"container logistics agents India {dest}",
                f"FCL shipping lines India {dest}"
            ]
        else:
            queries = [
                f"switchgear panel distributors {dest}",
                f"numerical protection relays distributors {dest}",
                f"feeder protection relay SEL arc flash importers {dest}",
                f"transformer differential protection relay suppliers {dest}",
                f"generator intertie protection relay dealers {dest}",
                f"power distribution equipment distributors {dest}",
                f"electrical control gear contactors wholesalers {dest}",
                f"circuit breaker switchboard importers {dest}",
                f"distribution transformer dealers {dest}",
                f"industrial power management panel distributors {dest}",
                f"commercial lighting importers {dest}",
                f"centralized lighting control systems distributors {dest}",
                f"automated lighting controllers importers {dest}",
                f"dimming modules smart lighting wholesalers {dest}",
                f"streetlight monitoring control systems {dest}",
                f"industrial wire cable wholesalers {dest}",
                f"lithium battery pack distributors {dest}",
                f"HVAC equipment wholesalers {dest}",
                f"solar inverter distributors {dest}",
                f"diesel generator dealers {dest}",
                f"cable gland terminal block importers {dest}",
                f"gate automation remote control switches distributors {dest}",
                f"wireless RF transmitter switches 433MHz importers {dest}",
                f"electronic components display LCD OLED distributors {dest}",
                f"switches push button toggle capacitor wholesalers {dest}",
                f"illuminated rocker power switch 16A 20A distributors {dest}",
                f"round square rocker switches suppliers {dest}",
                f"rechargeable battery holder components importers {dest}",
                f"integrated circuit IC electronic components distributors {dest}",
                f"real time clock RTC microcontroller suppliers {dest}",
                f"fan motor pump cooler components suppliers {dest}",
                f"hydraulic actuator speed regulating motor distributors {dest}",
                f"electric motor governor actuator suppliers {dest}",
                f"plywood panels MDF laminated boards distributors {dest}",
                f"wooden decorative panels wholesalers {dest}",
                f"floor scrubber cleaning equipment distributors {dest}",
                f"PIR sensor testing equipment wholesalers {dest}",
                f"industrial fan pump suppliers {dest}",
                f"home energy storage importers {dest}",
                f"photovoltaic solar panels distributors {dest}",
                f"commercial solar energy systems importers {dest}",
                f"solar panel scrap importers {dest}",
                f"PV module scrap buyers {dest}",
                f"EV charging station distributors {dest}",
                f"electric vehicle charger importers {dest}",
                f"PCB assembly PCBA turnkey services {dest}",
                f"printed circuit board distributors {dest}",
                f"rigid multi layer FR4 PCB importers {dest}",
                f"flexible PCB FPC manufacturers {dest}",
                f"automotive spare parts distributors {dest}",
                f"car brake pads brake discs importers {dest}",
                f"automotive suspension shock absorber wholesalers {dest}",
                f"car engine components auto parts dealers {dest}",
                f"automotive filters oil air fuel distributors {dest}",
                f"car radiators cooling fans importers {dest}",
                f"auto electronics sensors wiring harness wholesalers {dest}",
                f"car steering tie rod ball joint distributors {dest}",
                f"aftermarket auto parts wholesale distributors {dest}"
            ]
        self.populate_suggested_queries(queries)
        self.select_suggested_query(queries[0])

    def on_strategy_change(self, choice):
        if choice == "Suppliers":
            self.btn_disc_prop.configure(text="🌐 Quick URL Inquiry")
            self.region_dropdown.configure(values=self.country_regions, state="normal")
            if self.region_var.get() not in self.country_regions:
                self.region_var.set("India (in-en)")
            self.radius_dropdown.configure(state="disabled")
            if hasattr(self, 'area_dropdown'):
                self.area_dropdown.configure(values=["All Areas"], state="disabled")
                self.area_var.set("All Areas")
            self.btn_suggest.configure(state="normal")
            dest = self.region_var.get().split(" (")[0].strip()
            queries = self.get_supplier_starter_queries(dest)
            self.populate_suggested_queries(queries)
            self.select_suggested_query(queries[0])
        elif choice == "Logistics":
            self.btn_disc_prop.configure(text="🌐 Quick Freight RFQ")
            self.region_dropdown.configure(values=self.country_regions, state="normal")
            if self.region_var.get() not in self.country_regions:
                self.region_var.set("Worldwide (wt-wt)")
            self.radius_dropdown.configure(state="disabled")
            if hasattr(self, 'area_dropdown'):
                self.area_dropdown.configure(values=["All Areas"], state="disabled")
                self.area_var.set("All Areas")
            self.btn_suggest.configure(state="disabled")
            dest = self.region_var.get().split(" (")[0]
            if "Worldwide" in dest or "Global" in dest:
                dest = "worldwide"
            queries = [
                f"freight forwarders India to {dest} container shipping",
                f"sea cargo forwarders Mumbai to {dest}",
                f"container logistics agents India {dest}",
                f"FCL shipping lines India {dest}"
            ]
            self.populate_suggested_queries(queries)
            self.select_suggested_query(queries[0])
        elif choice == "Warehouses":
            self.btn_disc_prop.configure(text="🌐 Quick Rental Inquiry")
            self.region_dropdown.configure(values=self.indian_city_regions, state="normal")
            if self.region_var.get() not in self.indian_city_regions:
                self.region_var.set("Mumbai")
            self.radius_dropdown.configure(state="normal")
            city = self.region_var.get()
            area_options = self.indian_city_areas.get(city, ["All Areas"])
            if hasattr(self, 'area_dropdown'):
                self.area_dropdown.configure(values=area_options, state="normal")
                self.area_var.set("All Areas")
            self.btn_suggest.configure(state="normal")
            radius = self.radius_var.get()
            queries = self.get_warehouse_starter_queries(city, radius, "All Areas")
            self.populate_suggested_queries(queries)
            self.select_suggested_query(queries[0])
        else:
            self.btn_disc_prop.configure(text="🌐 Quick URL Proposal")
            self.region_dropdown.configure(values=self.country_regions, state="normal")
            if self.region_var.get() not in self.country_regions:
                self.region_var.set("Worldwide (wt-wt)")
            self.radius_dropdown.configure(state="disabled")
            if hasattr(self, 'area_dropdown'):
                self.area_dropdown.configure(values=["All Areas"], state="disabled")
                self.area_var.set("All Areas")
            self.btn_suggest.configure(state="normal")
            dest = self.region_var.get().split(" (")[0]
            if "Worldwide" in dest or "Global" in dest:
                dest = "worldwide"
            queries = [
                f"switchgear panel distributors {dest}",
                f"numerical protection relays distributors {dest}",
                f"feeder protection relay SEL arc flash importers {dest}",
                f"transformer differential protection relay suppliers {dest}",
                f"generator intertie protection relay dealers {dest}",
                f"power distribution equipment distributors {dest}",
                f"electrical control gear contactors wholesalers {dest}",
                f"circuit breaker switchboard importers {dest}",
                f"distribution transformer dealers {dest}",
                f"industrial power management panel distributors {dest}",
                f"commercial lighting importers {dest}",
                f"centralized lighting control systems distributors {dest}",
                f"automated lighting controllers importers {dest}",
                f"dimming modules smart lighting wholesalers {dest}",
                f"streetlight monitoring control systems {dest}",
                f"industrial wire cable wholesalers {dest}",
                f"lithium battery pack distributors {dest}",
                f"HVAC equipment wholesalers {dest}",
                f"solar inverter distributors {dest}",
                f"diesel generator dealers {dest}",
                f"cable gland terminal block importers {dest}",
                f"gate automation remote control switches distributors {dest}",
                f"wireless RF transmitter switches 433MHz importers {dest}",
                f"electronic components display LCD OLED distributors {dest}",
                f"switches push button toggle capacitor wholesalers {dest}",
                f"illuminated rocker power switch 16A 20A distributors {dest}",
                f"round square rocker switches suppliers {dest}",
                f"rechargeable battery holder components importers {dest}",
                f"integrated circuit IC electronic components distributors {dest}",
                f"real time clock RTC microcontroller suppliers {dest}",
                f"fan motor pump cooler components suppliers {dest}",
                f"hydraulic actuator speed regulating motor distributors {dest}",
                f"electric motor governor actuator suppliers {dest}",
                f"plywood panels MDF laminated boards distributors {dest}",
                f"wooden decorative panels wholesalers {dest}",
                f"floor scrubber cleaning equipment distributors {dest}",
                f"PIR sensor testing equipment wholesalers {dest}",
                f"industrial fan pump suppliers {dest}",
                f"home energy storage importers {dest}",
                f"photovoltaic solar panels distributors {dest}",
                f"commercial solar energy systems importers {dest}",
                f"EV charging station distributors {dest}",
                f"electric vehicle charger importers {dest}",
                f"PCB assembly PCBA turnkey services {dest}",
                f"printed circuit board distributors {dest}",
                f"rigid multi layer FR4 PCB importers {dest}",
                f"flexible PCB FPC manufacturers {dest}",
                f"automotive spare parts distributors {dest}",
                f"car brake pads brake discs importers {dest}",
                f"automotive suspension shock absorber wholesalers {dest}",
                f"car engine components auto parts dealers {dest}",
                f"automotive filters oil air fuel distributors {dest}",
                f"car radiators cooling fans importers {dest}",
                f"auto electronics sensors wiring harness wholesalers {dest}",
                f"car steering tie rod ball joint distributors {dest}",
                f"aftermarket auto parts wholesale distributors {dest}"
            ]
            self.populate_suggested_queries(queries)
            self.select_suggested_query(queries[0])

        if hasattr(self, 'current_hq_urls') and self.current_hq_urls:
            self.populate_hq_urls(self.current_hq_urls)

    def generate_from_spec(self):
        spec_text = self.spec_textbox.get("0.0", "end").strip()
        if not spec_text:
            return
            
        strategy = self.strategy_var.get()
        region = self.region_var.get()
        
        self.btn_spec_gen.configure(state="disabled")
        self.query_entry.delete("0.0", "end")
        self.query_entry.insert("0.0", "Generating AI query from spec...")
        
        import threading
        threading.Thread(target=self.generate_from_spec_thread, args=(spec_text, strategy, region), daemon=True).start()

    def generate_from_spec_thread(self, spec_text, strategy, region):
        try:
            if strategy == "Suppliers":
                region_name = region.split(" (")[0].strip()
                if "Worldwide" in region_name or "Global" in region_name:
                    target_desc = "global / international MANUFACTURERS and FACTORIES worldwide"
                elif region_name.lower() == "india":
                    target_desc = "MANUFACTURERS and FACTORIES across ALL of India"
                else:
                    target_desc = f"MANUFACTURERS, FACTORIES, and OEM MAKERS in {region_name}"
            elif strategy == "Logistics":
                dest = region.split(" (")[0]
                if "Worldwide" in dest or "Global" in dest:
                    dest = "worldwide"
                target_desc = f"freight forwarders or shipping lines from India to {dest}"
            elif strategy == "Warehouses":
                city_name = region if region in self.indian_city_regions else "Mumbai"
                rad_val = self.radius_var.get() if hasattr(self, 'radius_var') else "15 km"
                area_val = self.area_var.get() if hasattr(self, 'area_var') else "All Areas"
                area_desc = f"in {area_val}, {city_name}" if (area_val and area_val != "All Areas") else f"across industrial areas in {city_name}"
                target_desc = f"commercial warehouses, godowns, industrial sheds, or garage storage spaces for rent/lease under {rad_val} {area_desc} on Indian real estate portals & classifieds like OLX, MagicBricks, 99acres, JustDial"
            else:
                region_name = region.split(" (")[0]
                if "Worldwide" in region_name or "Global" in region_name:
                    target_desc = "B2B BUYERS, DISTRIBUTORS, or OEMs globally"
                else:
                    target_desc = f"B2B BUYERS, DISTRIBUTORS, or OEMs in {region_name}"
            
            prompt = f"""You are an elite B2B sourcing expert.
The user has provided the following raw requirement specification / RFQ message:

{spec_text}

Analyze the requirements and generate a single, highly specific DuckDuckGo search query to find {target_desc} that match this requirement.
Do not include quotes, explanations, or markdown. Return ONLY the raw query string.
"""
            from llm_fallback import generate_with_fallback
            response = generate_with_fallback(prompt, logger=self.logger)
            query = response.text.strip().replace('"', '').replace('\n', '')
            self.ui_queue.put((self.on_spec_complete, (query,)))
        except Exception as e:
            self.logger.error(f"Spec gen failed: {e}")
            self.ui_queue.put((self.on_spec_complete, ("Error generating query",)))
            
    def on_spec_complete(self, query):
        self.query_entry.delete("0.0", "end")
        self.query_entry.insert("0.0", query)
        self.btn_spec_gen.configure(state="normal")
        
    def suggest_query(self):
        strategy = self.strategy_var.get()
        region = self.region_var.get()
        self.btn_suggest.configure(state="disabled")
        self.lbl_disc_status.configure(text="Status: Generating AI suggestions...")
        
        # Show loading indicator in suggested queries list
        for widget in self.queries_list_frame.winfo_children():
            widget.destroy()
        lbl_loading = ctk.CTkLabel(
            self.queries_list_frame, 
            text="⏳ Generating 14-18 diverse search queries with Gemini...", 
            font=("Arial", 11, "italic"), 
            text_color="gray",
            wraplength=240
        )
        lbl_loading.pack(pady=20, padx=5)
        
        threading.Thread(target=self.suggest_query_thread, args=(strategy, region), daemon=True).start()

    def suggest_query_thread(self, strategy, region):
        try:
            from google.genai import types
            from pydantic import BaseModel
            from typing import List

            class SuggestedQueriesList(BaseModel):
                queries: List[str]

            if strategy == "Suppliers":
                region_name = region.split(" (")[0].strip()
                if "Worldwide" in region_name or "Global" in region_name:
                    region_target = "global / international MANUFACTURERS, FACTORIES, and OEM MAKERS worldwide"
                    region_kw = "worldwide"
                    hub_guidance = "Rotate between diverse international manufacturing countries (e.g. Germany, USA, China, Vietnam, Poland, Japan, India, South Korea)."
                elif region_name.lower() == "india":
                    region_target = "Indian MANUFACTURERS and FACTORIES across India"
                    region_kw = "India"
                    hub_guidance = "Rotate between different Indian industrial hubs (e.g. Gujarat, Maharashtra, Delhi NCR, Bangalore, Tamil Nadu, Coimbatore, Pune, Jamnagar, Yamunanagar, Kerala, Rajkot, Gurgaon, Chennai, Aurangabad)."
                else:
                    region_target = f"MANUFACTURERS, FACTORIES, and OEM MAKERS in {region_name}"
                    region_kw = region_name
                    hub_guidance = f"Focus specifically on reputable industrial manufacturers, production plants, and factories located in {region_name}."

                prompt = f"""You are an elite B2B sourcing expert for international trade.
Our company sources from direct manufacturers, factories, and OEM suppliers across these 13 core industrial niches:

NICHE 1 - Electrical & Electronic Components: Cable glands, crimping lugs, terminal blocks, rocker switches (round/square big rocker power switches, 6A-20A, illuminated red/green buttons, CQC/TUV/CE/RoHS, HS 853650), toggle/push switches, LCD/LED/OLED display modules, capacitors, battery holders, fan motors, integrated circuits (ICs, Real-Time Clocks like Epson RA-8565SA PURE SN, microcontrollers, semiconductors, HS 854200), remote switches (CAME TOP-433EE), EV plugs, wiring sockets (HS 853650, 8542, 853690, 8528, 8532)
NICHE 2 - Wires & Cables: LV/MV/HV power cables, armored XLPE cables, submersible cables, binding wires, hose reels
NICHE 3 - Power Distribution & Protection Relays: Numerical protection relays (SEL-751 arc-flash feeder protection, SEL-787 transformer protection, SEL-700G generator intertie protection, differential/overcurrent relays, HS 853649), power distribution equipment, circuit breakers (ACB, MCCB, MCB, VCB), contactors, distribution transformers, switchgear, relays, PCC/MCC panels, CRP panels (HS 853710, 8504)
NICHE 4 - HVAC, Fans, Pumps & Actuators: Hydraulic actuators (Groschopp WK0920702 1767-367, speed regulating motors, motor governors, HS 850110), axial/centrifugal fans, scroll/screw compressors, submersible pumps, refrigeration parts
NICHE 5 - Batteries, Solar Energy & Renewable Scrap: Solar panels (photovoltaic PV modules, monocrystalline PERC, TOPCon, bifacial, Tier-1 brands, solar energy systems, container shipments, HS 854143), solar panel scrap (PV module scrap, decommissioned panels, 500 MT lots), LiFePO4 battery packs, home energy storage, solar inverters, marine batteries, GaN chargers
NICHE 6 - Industrial Generators: Cummins diesel gensets, gas generators, silent generators, wind turbines
NICHE 7 - LED Lighting & Lighting Controls: Centralized controls, automated lighting controllers, dimming modules, DALI/0-10V controllers, streetlight monitoring systems, smart building automation, streetlights, high-bay LED, poultry lighting systems, smart WiFi sockets, luminaires (HS 853710)
NICHE 8 - Commercial Appliances: Industrial dehumidifiers, floor scrubbers, commercial laundry machines, kitchen equipment
NICHE 9 - Sensors & Testing: PIR sensors, float switches, transformer test benches, multimeters, data loggers
NICHE 10 - Electric Vehicles & EV Infrastructure: EV chargers (AC wallbox, DC fast chargers), EV charging cables, Type 2 & CCS2 connectors, EV battery packs (2W/3W/4W LiFePO4), BMS controllers, EV charging stations
NICHE 11 - Printed Circuit Boards (PCB) & PCBA: Multi-layer rigid FR4 PCBs, flexible FPC, aluminum MCPCB, turn-key SMT PCBA assembly, electronic EMS manufacturing, copper clad laminates (CCL)
NICHE 12 - Building Materials & Wooden Panels: Plywood panels, MDF panels, particle boards, laminated boards, decorative panels, melamine faced boards, marine plywood, veneered panels (HS 441299, 4411)
NICHE 13 - Automotive & Car Parts / Auto Components: Brake pads, brake discs & rotors, brake drums, shock absorbers, struts, suspension wishbones, control arms, ball joints, tie rod ends, steering racks, automotive filters (oil, fuel, air, cabin), radiators, intercoolers, cooling fans, water pumps, spark plugs, glow plugs, ignition coils, automotive wiring harness, auto sensors (oxygen, MAP, MAF, ABS, crankshaft, throttle), car lighting, headlamps, tail lamps, LED car bulbs, alternators, starter motors, clutch kits, pressure plates, flywheel, engine valves, pistons, piston rings, cylinder liners, gaskets, automotive precision CNC machined parts, aluminum die castings, automotive stampings (HS 8708, 8409, 8511, 8512, 854430)

Generate 14 to 18 short, simple, natural DuckDuckGo search queries to find {region_target}.

RULES:
1. Each query must be short and clean (3 to 6 words only).
   Examples of good queries:
   - "distribution transformer manufacturers {region_kw}"
   - "numerical protection relay suppliers {region_kw}"
   - "switchgear panel factories {region_kw}"
   - "power distribution equipment manufacturers {region_kw}"
   - "electrical contactors circuit breaker factories {region_kw}"
   - "brass cable glands manufacturers {region_kw}"
   - "electronic displays LCD OLED module suppliers {region_kw}"
   - "power switches 16A 20A CQC CE factories {region_kw}"
   - "hydraulic actuator motor manufacturers {region_kw}"
   - "integrated circuit IC component distributors {region_kw}"
   - "plywood panel MDF board manufacturers {region_kw}"
   - "solar panel PV module manufacturers {region_kw}"
   - "diesel generator manufacturers {region_kw}"
   - "centralized lighting control manufacturers {region_kw}"
   - "EV charging station manufacturers {region_kw}"
   - "multi layer FR4 PCB manufacturers {region_kw}"
   - "PCB assembly SMT PCBA factories {region_kw}"
   - "automotive brake pads manufacturers {region_kw}"
   - "car suspension shock absorber factories {region_kw}"
   - "car radiator cooling fan factories {region_kw}"
   - "auto component precision CNC parts {region_kw}"
   - "automotive wiring harness makers {region_kw}"
2. CRITICAL: You MUST cover ALL 13 niches above. Pick a DIFFERENT specific sub-product from each niche. Do NOT repeat the same niche twice until all 13 are covered.
3. {hub_guidance}
4. Do NOT use boolean operators (no AND, OR, NOT, site:).
5. Do NOT use quotation marks or plus/minus signs.
6. Keep queries realistic, diverse, and search-engine friendly.
"""
            elif strategy == "Logistics":
                dest = region.split(" (")[0]
                if "Worldwide" in dest or "Global" in dest:
                    dest = "worldwide"
                prompt = f"""You are an international freight and logistics expert.
We are shipping electrical, PCB/PCBA, and industrial goods from India to {dest}.

Generate 6 to 8 short, simple, natural DuckDuckGo search queries to find freight forwarders, shipping lines, container logistics agents, or customs clearing agents handling cargo from India to {dest}.

RULES:
1. Each query must be short and clean (3 to 6 words only).
   Examples of good queries:
   - "freight forwarders India to {dest} container shipping"
   - "sea cargo forwarders Mumbai to {dest}"
   - "customs clearing agents India to {dest}"
   - "FCL container shipping lines India {dest}"
   - "air cargo logistics India to {dest}"
2. Do NOT use boolean operators (no AND, OR, NOT, site:).
3. Do NOT use quotation marks or plus/minus signs.
"""
            elif strategy == "Warehouses":
                city_name = region if region in self.indian_city_regions else "Mumbai"
                rad_val = self.radius_var.get() if hasattr(self, 'radius_var') else "15 km"
                area_val = self.area_var.get() if hasattr(self, 'area_var') else "All Areas"
                known_areas = self.indian_city_areas.get(city_name, ["MIDC", "Industrial Area"])[1:]
                known_areas_str = ", ".join(known_areas[:8])
                if area_val and area_val != "All Areas":
                    area_focus = f"FOCUS SPECIFICALLY on the area/locality '{area_val}' in {city_name}."
                else:
                    area_focus = f"DISTRIBUTE queries across prominent industrial/storage areas inside {city_name} such as: {known_areas_str}."

                prompt = f"""You are an elite Indian commercial real estate, warehousing, and industrial logistics broker.
We are looking to lease, rent, or acquire commercial warehouses, godowns, industrial sheds, and garage storage spaces under {rad_val} inside {city_name}, India.
{area_focus}

These spaces will be used for inventory storage, export container staging, packaging, light assembly, or secure garage/vehicle parking.
We specifically utilize India's premier real estate yellowpages and classifieds: OLX India (olx.in), MagicBricks (magicbricks.com), 99acres (99acres.com), JustDial (justdial.com), NoBroker (nobroker.in), Housing.com (housing.com), Quikr (quikr.com), and IndiaMart (indiamart.com).

Generate 14 to 18 short, simple, natural DuckDuckGo search queries.

CRITICAL RULES:
1. Every query MUST explicitly include the phrase "under {rad_val}" to restrict the radius.
2. Every query MUST target specific areas/localities inside {city_name} (e.g. {known_areas_str}).
3. Cover diverse property types: commercial warehouse, godown, industrial shed, garage storage space, RCC storage godown, logistics park unit, container accessible warehouse.
4. Incorporate mentions of key Indian real estate yellowpages (e.g. olx, 99acres, magicbricks, nobroker, justdial) naturally across several queries.
5. Examples of good queries:
   - "warehouse for rent under {rad_val} {known_areas[0] if known_areas else 'MIDC'} {city_name} olx"
   - "godown on lease under {rad_val} {known_areas[1] if len(known_areas) > 1 else 'Industrial Area'} 99acres"
   - "garage storage space under {rad_val} {known_areas[0] if known_areas else 'MIDC'} {city_name}"
   - "industrial shed for rent under {rad_val} {known_areas[2] if len(known_areas) > 2 else 'Bhosari'} magicbricks"
   - "storage space for rent under {rad_val} {known_areas[1] if len(known_areas) > 1 else 'Chakan'} nobroker"
   - "warehouse shed on lease under {rad_val} {known_areas[0] if known_areas else 'MIDC'} justdial"
   - "commercial godown under {rad_val} {known_areas[0] if known_areas else 'MIDC'} olx"
   - "small warehouse garage under {rad_val} {known_areas[1] if len(known_areas) > 1 else 'Chakan'} olx"
6. Do NOT use boolean operators (no AND, OR, NOT, site:).
7. Do NOT use quotation marks or plus/minus signs.
8. Keep queries realistic, search-engine friendly, and under 8 words.
"""
            else:
                region_name = region.split(" (")[0]
                if "Worldwide" in region_name or "Global" in region_name:
                    region_target = "global / worldwide"
                    region_kw = "worldwide"
                else:
                    region_target = region_name
                    region_kw = region_name

                prompt = f"""You are an elite B2B export sales director.
We are an Indian manufacturer and exporter supplying international buyers across these 13 core industrial niches:

NICHE 1 - Electrical & Electronic Components: Cable glands, crimping lugs, terminal blocks, rocker switches (round/square big rocker power switches, 6A-20A, illuminated red/green buttons, CQC/TUV/CE/RoHS, HS 853650), toggle/push switches, LCD/LED/OLED display modules, capacitors, battery holders, fan motors, integrated circuits (ICs, Real-Time Clocks like Epson RA-8565SA PURE SN, microcontrollers, semiconductors, HS 854200), remote switches (CAME TOP-433EE), EV plugs, wiring sockets (HS 853650, 8542, 853690, 8528, 8532)
NICHE 2 - Wires & Cables: LV/MV/HV power cables, armored XLPE cables, submersible cables, binding wires, hose reels
NICHE 3 - Power Distribution & Protection Relays: Numerical protection relays (SEL-751 arc-flash feeder protection, SEL-787 transformer protection, SEL-700G generator intertie protection, differential/overcurrent relays, HS 853649), power distribution equipment, circuit breakers (ACB, MCCB, MCB, VCB), contactors, distribution transformers, switchgear, relays, PCC/MCC panels, CRP panels (HS 853710, 8504)
NICHE 4 - HVAC, Fans, Pumps & Actuators: Hydraulic actuators (Groschopp WK0920702 1767-367, speed regulating motors, motor governors, HS 850110), axial/centrifugal fans, scroll/screw compressors, submersible pumps, refrigeration parts
NICHE 5 - Batteries, Solar Energy & Renewable Scrap: Solar panels (photovoltaic PV modules, monocrystalline PERC, TOPCon, bifacial, Tier-1 brands, solar energy systems, container shipments, HS 854143), solar panel scrap (PV module scrap, decommissioned panels, 500 MT lots), LiFePO4 battery packs, home energy storage, solar inverters, marine batteries, GaN chargers
NICHE 6 - Industrial Generators: Cummins diesel gensets, gas generators, silent generators, wind turbines
NICHE 7 - LED Lighting & Lighting Controls: Centralized controls, automated lighting controllers, dimming modules, DALI/0-10V controllers, streetlight monitoring systems, smart building automation, streetlights, high-bay LED, poultry lighting systems, smart WiFi sockets, luminaires (HS 853710)
NICHE 8 - Commercial Appliances: Industrial dehumidifiers, floor scrubbers, commercial laundry machines, kitchen equipment
NICHE 9 - Sensors & Testing: PIR sensors, float switches, transformer test benches, multimeters, data loggers
NICHE 10 - Electric Vehicles & EV Infrastructure: EV chargers (AC wallbox, DC fast chargers), EV charging cables, Type 2 & CCS2 connectors, EV battery packs (2W/3W/4W LiFePO4), BMS controllers, EV charging stations
NICHE 11 - Printed Circuit Boards (PCB) & PCBA: Multi-layer rigid FR4 PCBs, flexible FPC, aluminum MCPCB, turn-key SMT PCBA assembly, electronic EMS manufacturing, copper clad laminates (CCL)
NICHE 12 - Building Materials & Wooden Panels: Plywood panels, MDF panels, particle boards, laminated decorative boards, melamine faced boards, marine plywood, veneered panels, retailer distribution (HS 441299, 4411)
NICHE 13 - Automotive & Car Parts / Auto Components: Brake systems (pads, discs, calipers), suspension & steering (shock absorbers, control arms, tie rods, ball joints, steering racks), engine & cooling (radiators, cooling fans, water pumps, thermostats, pistons, engine valves), filters (air, oil, fuel, cabin), electrical & sensors (alternators, starter motors, ignition coils, spark plugs, wiring harnesses, oxygen/ABS sensors), automotive lighting (headlights, tail lamps, fog lamps, LED bulbs), transmission & driveline (clutch kits, CV joints, drive shafts), precision CNC machined parts & stampings (HS 8708, 8409, 8511, 8512)

Generate 14 to 18 short, simple, natural DuckDuckGo search queries to find real B2B BUYERS, DISTRIBUTORS, IMPORTERS, WHOLESALERS, or CONTRACTORS in {region_target}.

RULES:
1. Each query must be short and clean (3 to 6 words only).
   Examples of good queries:
   - "switchgear panel distributors {region_kw}"
   - "numerical protection relays distributors {region_kw}"
   - "feeder protection relay SEL 751 importers {region_kw}"
   - "transformer protection relay SEL 787 suppliers {region_kw}"
   - "power distribution equipment distributors {region_kw}"
   - "electrical control gear contactors wholesalers {region_kw}"
   - "circuit breaker switchboard importers {region_kw}"
   - "distribution transformer dealers {region_kw}"
   - "commercial lighting importers {region_kw}"
   - "centralized lighting controls distributors {region_kw}"
   - "automated lighting controllers importers {region_kw}"
   - "dimming modules smart lighting {region_kw}"
   - "streetlight monitoring control systems {region_kw}"
   - "diesel generator dealers {region_kw}"
   - "cable gland terminal block importers {region_kw}"
   - "CAME TOP-433EE remote control distributors {region_kw}"
   - "gate automation remote switches importers {region_kw}"
   - "electronic components display LCD OLED distributors {region_kw}"
   - "switches push button toggle capacitor wholesalers {region_kw}"
   - "illuminated rocker power switches 16A 20A distributors {region_kw}"
   - "round square big rocker switch suppliers {region_kw}"
   - "battery holder components importers {region_kw}"
   - "Groschopp hydraulic actuator motor distributors {region_kw}"
   - "hydraulic actuator speed regulating motor importers {region_kw}"
   - "Epson RA-8565SA integrated circuit distributors {region_kw}"
   - "electronic components IC distributors {region_kw}"
   - "brand new original integrated circuit suppliers {region_kw}"
   - "plywood panels MDF laminated boards distributors {region_kw}"
   - "wooden decorative panels wholesalers {region_kw}"
   - "floor scrubber equipment distributors {region_kw}"
   - "PIR sensor wholesalers {region_kw}"
   - "home energy storage importers {region_kw}"
   - "photovoltaic solar panels distributors {region_kw}"
   - "solar energy panels importers {region_kw}"
   - "solar panel scrap importers {region_kw}"
   - "PV module scrap buyers {region_kw}"
   - "EV charging station distributors {region_kw}"
   - "electric vehicle charger importers {region_kw}"
   - "PCB assembly PCBA turnkey services {region_kw}"
   - "printed circuit board distributors {region_kw}"
   - "rigid multi layer FR4 PCB importers {region_kw}"
   - "flexible PCB FPC manufacturers {region_kw}"
2. CRITICAL: You MUST cover ALL 13 niches above. Pick a DIFFERENT specific sub-product from each niche. Do NOT repeat the same niche twice until all 12 are covered.
3. Use varied buyer types (distributors, importers, wholesalers, dealers, contractors, suppliers).
4. Do NOT use boolean operators (no AND, OR, NOT, site:).
5. Do NOT use quotation marks or plus/minus signs.
6. Keep queries realistic, diverse, and search-engine friendly.
"""

            from llm_fallback import generate_with_fallback
            response = generate_with_fallback(
                prompt=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SuggestedQueriesList,
                ),
                logger=self.logger
            )

            queries = []
            try:
                data = SuggestedQueriesList.model_validate_json(response.text)
                queries = [q.strip() for q in data.queries if q.strip()]
            except Exception:
                import json, re
                clean_text = response.text.strip()
                if clean_text.startswith("```"):
                    clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text)
                    clean_text = re.sub(r'\s*```$', '', clean_text)
                try:
                    parsed = json.loads(clean_text)
                    if isinstance(parsed, dict) and "queries" in parsed:
                        queries = [str(q).strip() for q in parsed["queries"] if str(q).strip()]
                    elif isinstance(parsed, list):
                        queries = [str(q).strip() for q in parsed if str(q).strip()]
                except Exception:
                    queries = [
                        re.sub(r'^\s*[\d\.\-\*\•]+\s*', '', line).strip().strip('"\'')
                        for line in response.text.splitlines()
                        if line.strip() and not line.strip().startswith('{') and not line.strip().startswith('}')
                    ]
                    queries = [q for q in queries if q and len(q) > 3]

            if not queries:
                if strategy == "Suppliers":
                    dest_term = region.split(" (")[0].strip()
                    queries = self.get_supplier_starter_queries(dest_term)
                elif strategy == "Logistics":
                    dest_term = region.split(" (")[0]
                    queries = [
                        f"freight forwarders India to {dest_term} container shipping",
                        f"sea cargo forwarders Mumbai to {dest_term}",
                        f"container logistics agents India {dest_term}",
                        f"FCL shipping lines India {dest_term}"
                    ]
                elif strategy == "Warehouses":
                    city_name = region if region in self.indian_city_regions else "Mumbai"
                    rad_val = self.radius_var.get() if hasattr(self, 'radius_var') else "15 km"
                    area_val = self.area_var.get() if hasattr(self, 'area_var') else "All Areas"
                    queries = self.get_warehouse_starter_queries(city_name, rad_val, area_val)
                else:
                    dest_term = region.split(" (")[0]
                    queries = [
                        f"switchgear panel distributors {dest_term}",
                        f"numerical protection relays distributors {dest_term}",
                        f"feeder protection relay SEL arc flash importers {dest_term}",
                        f"transformer differential protection relay suppliers {dest_term}",
                        f"power distribution equipment distributors {dest_term}",
                        f"electrical control gear contactors wholesalers {dest_term}",
                        f"circuit breaker switchboard importers {dest_term}",
                        f"distribution transformer dealers {dest_term}",
                        f"industrial power management panel distributors {dest_term}",
                        f"commercial lighting importers {dest_term}",
                        f"centralized lighting control systems distributors {dest_term}",
                        f"automated lighting controllers importers {dest_term}",
                        f"dimming modules smart lighting wholesalers {dest_term}",
                        f"streetlight monitoring control systems {dest_term}",
                        f"industrial wire cable wholesalers {dest_term}",
                        f"lithium battery pack distributors {dest_term}",
                        f"HVAC equipment wholesalers {dest_term}",
                        f"solar inverter distributors {dest_term}",
                        f"diesel generator dealers {dest_term}",
                        f"cable gland terminal block importers {dest_term}",
                        f"gate automation remote control switches distributors {dest_term}",
                        f"wireless RF transmitter switches 433MHz importers {dest_term}",
                        f"electronic components display LCD OLED distributors {dest_term}",
                        f"switches push button toggle capacitor wholesalers {dest_term}",
                        f"battery holder components importers {dest_term}",
                        f"integrated circuit IC electronic components distributors {dest_term}",
                        f"real time clock RTC microcontroller suppliers {dest_term}",
                        f"plywood panels MDF laminated boards distributors {dest_term}",
                        f"wooden decorative panels wholesalers {dest_term}",
                        f"floor scrubber cleaning equipment distributors {dest_term}",
                        f"PIR sensor testing equipment wholesalers {dest_term}",
                        f"industrial fan pump suppliers {dest_term}",
                        f"home energy storage importers {dest_term}",
                        f"photovoltaic solar panels distributors {dest_term}",
                        f"solar energy panels importers {dest_term}",
                        f"solar panel scrap importers {dest_term}",
                        f"PV module scrap buyers {dest_term}",
                        f"EV charging station distributors {dest_term}",
                        f"electric vehicle charger importers {dest_term}",
                        f"PCB assembly PCBA turnkey services {dest_term}",
                        f"printed circuit board distributors {dest_term}",
                        f"rigid multi layer FR4 PCB importers {dest_term}",
                        f"flexible PCB FPC manufacturers {dest_term}"
                    ]

            self.ui_queue.put((self.on_suggest_complete, (queries,)))
        except Exception as e:
            self.logger.error(f"Suggest failed: {e}")
            fallback_dest = region.split(" (")[0]
            if strategy == "Suppliers":
                fallback_queries = [
                    "distribution transformer manufacturers India",
                    "numerical protection relay suppliers India",
                    "substation control and relay panel CRP manufacturers Gujarat",
                    "power distribution equipment manufacturers India",
                    "electrical contactors circuit breaker factories Gujarat",
                    "switchgear panel factories Gujarat",
                    "centralized lighting control system manufacturers India",
                    "automated lighting controllers dimming modules factories India",
                    "streetlight monitoring control panel makers India",
                    "copper wire cable manufacturers India",
                    "solar panel scrap suppliers exporters",
                    "PV module scrap suppliers 500 MT",
                    "lithium battery pack makers Bangalore",
                    "HVAC components suppliers Maharashtra",
                    "circuit breaker factories India",
                    "diesel generator manufacturers Pune",
                    "brass cable glands manufacturers Jamnagar",
                    "RF remote control switch manufacturers India",
                    "gate automation transmitter receiver factories India",
                    "electronic displays LCD OLED module suppliers India",
                    "toggle switches push button manufacturers India",
                    "electrolytic ceramic capacitor manufacturers Gujarat",
                    "LED streetlight luminaire factories India",
                    "industrial pump motor manufacturers Coimbatore",
                    "floor scrubber cleaning machine suppliers India",
                    "sensor testing equipment manufacturers Delhi NCR",
                    "EV charging station manufacturers India",
                    "electric vehicle battery pack manufacturers Pune",
                    "printed circuit board PCB manufacturers India",
                    "PCB assembly SMT PCBA factories Bangalore",
                    "multi layer FR4 PCB board factories Gujarat",
                    "copper clad laminate CCL suppliers India",
                    "metal core aluminum MCPCB makers India"
                ]
            elif strategy == "Logistics":
                fallback_queries = [
                    f"freight forwarders India to {fallback_dest} container shipping",
                    f"sea cargo forwarders Mumbai to {fallback_dest}",
                    f"container logistics agents India {fallback_dest}",
                    f"FCL shipping lines India {fallback_dest}"
                ]
            elif strategy == "Warehouses":
                city_name = region if region in self.indian_city_regions else "Mumbai"
                rad_val = self.radius_var.get() if hasattr(self, 'radius_var') else "15 km"
                area_val = self.area_var.get() if hasattr(self, 'area_var') else "All Areas"
                fallback_queries = self.get_warehouse_starter_queries(city_name, rad_val, area_val)
            else:
                fallback_queries = [
                    f"switchgear panel distributors {fallback_dest}",
                    f"numerical protection relays distributors {fallback_dest}",
                    f"feeder protection relay SEL arc flash importers {fallback_dest}",
                    f"transformer differential protection relay suppliers {fallback_dest}",
                    f"power distribution equipment distributors {fallback_dest}",
                    f"electrical control gear contactors wholesalers {fallback_dest}",
                    f"circuit breaker switchboard importers {fallback_dest}",
                    f"distribution transformer dealers {fallback_dest}",
                    f"industrial power management panel distributors {fallback_dest}",
                    f"commercial lighting importers {fallback_dest}",
                    f"centralized lighting control systems distributors {fallback_dest}",
                    f"automated lighting controllers importers {fallback_dest}",
                    f"dimming modules smart lighting wholesalers {fallback_dest}",
                    f"streetlight monitoring control systems {fallback_dest}",
                    f"industrial wire cable wholesalers {fallback_dest}",
                    f"lithium battery pack distributors {fallback_dest}",
                    f"HVAC equipment wholesalers {fallback_dest}",
                    f"solar inverter distributors {fallback_dest}",
                    f"diesel generator dealers {fallback_dest}",
                    f"cable gland terminal block importers {fallback_dest}",
                    f"gate automation remote control switches distributors {fallback_dest}",
                    f"wireless RF transmitter switches 433MHz importers {fallback_dest}",
                    f"electronic components display LCD OLED distributors {fallback_dest}",
                    f"switches push button toggle capacitor wholesalers {fallback_dest}",
                    f"battery holder components importers {fallback_dest}",
                    f"integrated circuit IC electronic components distributors {fallback_dest}",
                    f"real time clock RTC microcontroller suppliers {fallback_dest}",
                    f"plywood panels MDF laminated boards distributors {fallback_dest}",
                    f"wooden decorative panels wholesalers {fallback_dest}",
                    f"floor scrubber cleaning equipment distributors {fallback_dest}",
                    f"PIR sensor testing equipment wholesalers {fallback_dest}",
                    f"industrial fan pump suppliers {fallback_dest}",
                    f"home energy storage importers {fallback_dest}",
                    f"photovoltaic solar panels distributors {fallback_dest}",
                    f"solar energy panels importers {fallback_dest}",
                    f"solar panel scrap importers {fallback_dest}",
                    f"PV module scrap buyers {fallback_dest}",
                    f"EV charging station distributors {fallback_dest}",
                    f"electric vehicle charger importers {fallback_dest}",
                    f"PCB assembly PCBA turnkey services {fallback_dest}",
                    f"printed circuit board distributors {fallback_dest}",
                    f"rigid multi layer FR4 PCB importers {fallback_dest}",
                    f"flexible PCB FPC manufacturers {fallback_dest}"
                ]
            self.ui_queue.put((self.on_suggest_complete, (fallback_queries,)))

    def on_suggest_complete(self, queries):
        self.btn_suggest.configure(state="normal")
        if queries:
            self.populate_suggested_queries(queries)
            self.select_suggested_query(queries[0])
            self.lbl_disc_status.configure(text=f"Status: {len(queries)} queries suggested")
        else:
            self.lbl_disc_status.configure(text="Status: No suggestions generated")

    def start_discovery(self):
        query = self.query_entry.get("0.0", "end").strip()
        if query == "Enter base query...":
            query = ""
        if not query:
            return
            
        strategy = self.strategy_var.get()
        selected_region_val = self.region_var.get()
        try:
            selected_region_code = selected_region_val.split(" (")[1].replace(")", "")
            selected_country_name = selected_region_val.split(" (")[0].strip()
        except Exception:
            selected_region_code = "in-en"
            selected_country_name = "India"

        if strategy == "Suppliers":
            region_code = selected_region_code
            if selected_country_name.lower() == "india" and "site:" not in query.lower():
                query += " (site:indiamart.com OR site:tradeindia.com OR site:justdial.com OR site:exportersindia.com)"
        elif strategy == "Warehouses":
            region_code = "in-en"
            if "site:" not in query.lower():
                query += " (site:olx.in/item OR site:olx.in OR site:99acres.com OR site:magicbricks.com OR site:justdial.com OR site:housing.com OR site:nobroker.in OR site:quikr.com OR site:indiamart.com)"
        elif strategy == "Logistics":
            region_code = "in-en"
        else:
            region_code = selected_region_code
            
        max_results = int(self.results_slider.get())
        
        self.btn_search.configure(state="disabled")
        self.lbl_disc_status.configure(text="Status: Searching...")
        self.raw_urls_textbox.delete("0.0", "end")
        for widget in self.discovery_urls_frame.winfo_children():
            widget.destroy()
        lbl_loading = ctk.CTkLabel(
            self.discovery_urls_frame, 
            text="⏳ Searching DuckDuckGo and vetting leads with Gemini AI...", 
            font=("Arial", 11, "italic"), 
            text_color="gray"
        )
        lbl_loading.pack(pady=30, padx=10)
        self.lbl_raw_urls.configure(text="🌐 Raw Search Results (DuckDuckGo):")
        self.lbl_hq_urls.configure(text="⭐ High-Quality URLs (AI Filtered):")
        
        threading.Thread(target=self.discover_urls_thread, args=(query, max_results, region_code), daemon=True).start()

    def discover_urls_thread(self, query, max_results, region_code):
        try:
            self.logger.info(f"Searching DuckDuckGo for: {query} [Region: {region_code}, Target Max: {max_results}]")
            results = []
            seen_hrefs = set()
            pages_needed = max(1, (max_results + 7) // 8)

            with DDGS() as ddgs:
                for page_num in range(1, pages_needed + 1):
                    if len(results) >= max_results:
                        break
                    try:
                        page_res = list(ddgs.text(query, region=region_code, page=page_num, max_results=20))
                        if not page_res:
                            break
                        for r in page_res:
                            href = r.get('href')
                            if href and href not in seen_hrefs:
                                seen_hrefs.add(href)
                                results.append(r)
                                if len(results) >= max_results:
                                    break
                    except Exception as dde:
                        self.logger.warning(f"DuckDuckGo page {page_num} search failed: {dde}")
                        break

                # If no results found and query had restrictive site filters, retry with broader query
                if not results and "site:" in query:
                    import re
                    clean_query = re.sub(r'\(?site:[^\)]+\)?', '', query).strip()
                    self.logger.info(f"Retrying DuckDuckGo search with broader query: {clean_query}")
                    for page_num in range(1, pages_needed + 1):
                        if len(results) >= max_results:
                            break
                        try:
                            page_res = list(ddgs.text(clean_query, region=region_code, page=page_num, max_results=20))
                            if not page_res:
                                break
                            for r in page_res:
                                href = r.get('href')
                                if href and href not in seen_hrefs:
                                    seen_hrefs.add(href)
                                    results.append(r)
                                    if len(results) >= max_results:
                                        break
                        except Exception as fallback_err:
                            self.logger.warning(f"Fallback search page {page_num} failed: {fallback_err}")
                            break
            
            if not results:
                self.ui_queue.put((self.on_discovery_complete, ([], [], None)))
                return
                
            raw_urls = [r.get('href') for r in results if r.get('href')]
            self.ui_queue.put((self.update_raw_discovery_results, (raw_urls,)))
            
            self.logger.info("Sending results to Gemini for smart filtering...")
            self.ui_queue.put((self.update_discovery_status, ("Status: AI Filtering...",)))
            
            strategy = self.strategy_var.get()
            
            # Format results for Gemini
            search_context = ""
            for i, r in enumerate(results):
                search_context += f"[{i}] URL: {r.get('href')}\\nTitle: {r.get('title')}\\nSnippet: {r.get('body')}\\n\\n"
                
            from google import genai
            from google.genai import types
            from pydantic import BaseModel
            from typing import List
            
            class FilteredURLs(BaseModel):
                urls: List[str]
                
            if strategy == "Logistics":
                filter_goal = "Actual company websites of Indian logistics companies, freight forwarders, or shipping lines providing container transport solutions. REMOVE news, Wikipedia, and non-logistics sites."
            elif strategy == "Warehouses":
                city_name = self.region_var.get()
                rad_val = self.radius_var.get() if hasattr(self, 'radius_var') else "15 km"
                area_val = self.area_var.get() if hasattr(self, 'area_var') else "All Areas"
                loc_desc = f"{area_val}, {city_name}" if (area_val and area_val != "All Areas") else f"areas inside {city_name}"
                filter_goal = f"Direct property listings, classified ads, or yellowpages entries for commercial warehouses, godowns, industrial sheds, garage storage spaces, or logistics parks available for rent or lease under {rad_val} in {loc_desc}. KEEP listings from OLX, MagicBricks, 99acres, JustDial, NoBroker, Housing.com, Quikr, IndiaMart, and direct commercial property owners/brokers. REMOVE non-real estate articles, purely residential apartments without garage/storage, Wikipedia, and generic news."
            elif strategy == "Suppliers":
                region_name = self.region_var.get().split(" (")[0].strip()
                if "Worldwide" in region_name or "Global" in region_name:
                    loc_target = "worldwide / internationally"
                    dir_hint = "KEEP legitimate B2B factory directories and direct manufacturing company portals."
                elif region_name.lower() == "india":
                    loc_target = "across all of India (nationwide)"
                    dir_hint = "KEEP directories like IndiaMart or TradeIndia if they lead to suppliers."
                else:
                    loc_target = f"in {region_name}"
                    dir_hint = f"KEEP direct manufacturer websites and reputable industrial supplier directories in {region_name}."

                filter_goal = f"Direct manufacturers, factories, and OEM makers {loc_target} of Automotive & Car Parts (Brake Pads/Discs, Shock Absorbers, Suspension Parts, Steering Racks, Auto Filters, Radiators, Water Pumps, Spark Plugs, Ignition Coils, Wiring Harnesses, Auto Sensors, Headlamps, Alternators, Starter Motors, Clutch Kits, Engine Valves, Pistons, CNC Machined Auto Parts), Power Distribution Equipment, Hydraulic Actuators & Speed Regulating Motors (Groschopp WK0920702, Motor Governors, HS 850110), Solar Panels (Photovoltaic Energy Panels, PV Modules, HS 854143), Wooden Panels (Plywood, MDF, Laminated Decorative Boards, HS 441299), Integrated Circuits (ICs, Epson RA-8565SA, Microcontrollers, HS 8542), Remote Control Switches, Displays (LCD/OLED), Capacitors, Rocker Switches & Power Switches (6A-20A, CQC/TUV/CE, HS 853650), Toggle Switches, Fan Motors, Battery Holders, Numerical Protection Relays (SEL-751, SEL-787, SEL-700G), Electrical Control Equipment (Circuit Breakers, Contactors, Transformers), Cables, Switchgear, Lighting Control Systems (centralized/automated controls, dimming modules, streetlight monitoring), HVAC Parts, Batteries, Solar Panel Scrap (PV module scrap), Solar Inverters, Generators, LED Lighting, Appliances, PCBs/PCBA, or Testing Equipment. {dir_hint}"
            else:
                filter_goal = "Actual company websites for buyers/distributors/OEMs of Automotive & Car Parts (Car Parts Wholesalers, Aftermarket Auto Spares Distributors, Brake Pads/Discs, Shock Absorbers, Suspension & Steering Parts, Auto Filters, Radiators, Water Pumps, Spark Plugs, Ignition Coils, Wiring Harnesses, Auto Sensors, Car Lighting/Headlamps, Alternators, Starter Motors, Clutch Kits, Engine Components, Precision Auto CNC Parts), Power Distribution Equipment, Hydraulic Actuators & Speed Regulating Motors (Groschopp WK0920702, Motor Governors, HS 850110), Solar Panels (Photovoltaic Energy Panels, PV Modules, HS 854143), Wooden Panels (Plywood, MDF, Laminated Decorative Boards, HS 441299), Integrated Circuits (ICs, Epson RA-8565SA, Microcontrollers, HS 8542), Remote Control Switches, Displays (LCD/OLED), Capacitors, Rocker Switches & Power Switches (6A-20A, CQC/TUV/CE, HS 853650), Toggle Switches, Fan Motors, Battery Holders, Numerical Protection Relays (SEL-751, SEL-787, SEL-700G), Electrical Control Equipment (Circuit Breakers, Contactors, Transformers), Cables, Switchgear, Lighting Control Systems (centralized/automated controls, dimming modules, streetlight monitoring), HVAC Parts, Batteries, Solar Panel Scrap (PV module scrap), Solar Inverters, Generators, LED Lighting, Appliances, PCBs/PCBA, or Testing Equipment. REMOVE news articles, Wikipedia, Amazon, PDFs, and generic directories."
                
            prompt = "You are an expert lead generation AI.\nThe user is searching for: " + filter_goal + "\n\nHere are the raw search results from DuckDuckGo:\n" + search_context + "\n\nFilter the list based on the goal. Return ONLY the URLs that strongly match."
                
            from llm_fallback import generate_with_fallback
            response = generate_with_fallback(
                prompt=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FilteredURLs,
                ),
                logger=self.logger
            )
            
            filtered_data = FilteredURLs.model_validate_json(response.text)
            urls = filtered_data.urls
            
            # OPPORTUNITY EXTRACTION: If strategy == "Warehouses", check for yellowpages directory URLs
            # and scrape the raw page to discover multiple individual property listings
            if strategy == "Warehouses":
                try:
                    from scraper import extract_subproperties_from_directory, is_yellowpages_directory
                    candidate_dirs = [u for u in (urls + raw_urls) if is_yellowpages_directory(u)]
                    if candidate_dirs:
                        self.logger.info(f"Found {len(candidate_dirs)} yellowpages directory URLs. Deep scraping for individual properties...")
                        self.ui_queue.put((self.update_discovery_status, ("Status: Deep scraping properties from directories...",)))
                        
                        extracted_props = []
                        for d_url in candidate_dirs[:3]:
                            try:
                                sub_props = extract_subproperties_from_directory(d_url, logger=self.logger, max_properties=8)
                                for sp in sub_props:
                                    if sp not in urls and sp not in extracted_props:
                                        extracted_props.append(sp)
                            except Exception as de:
                                self.logger.warning(f"Deep directory scrape failed on {d_url}: {de}")
                        
                        if extracted_props:
                            self.logger.info(f"Extracted {len(extracted_props)} individual property leads from directory pages!")
                            urls = extracted_props + [u for u in urls if u not in extracted_props]
                except Exception as ex:
                    self.logger.warning(f"Deep property extraction process encountered an issue: {ex}")

            self.logger.info(f"AI filtered {len(results)} raw results down to {len(urls)} high-quality URLs.")
            self.ui_queue.put((self.on_discovery_complete, (raw_urls, urls, None)))
        except Exception as e:
            self.logger.error(f"Search/Filter failed: {e}")
            self.ui_queue.put((self.on_discovery_complete, ([], [], str(e))))
            
    def update_raw_discovery_results(self, raw_urls):
        self.raw_urls_textbox.delete("0.0", "end")
        if raw_urls:
            self.raw_urls_textbox.insert("end", "\n".join(raw_urls) + "\n")
        self.lbl_raw_urls.configure(text=f"🌐 Raw Search Results ({len(raw_urls)} Found):")

    def update_discovery_status(self, text):
        self.lbl_disc_status.configure(text=text)

    def on_discovery_complete(self, raw_urls, urls, error):
        self.btn_search.configure(state="normal")
        if error:
            self.lbl_disc_status.configure(text="Status: Error")
            for widget in self.discovery_urls_frame.winfo_children():
                widget.destroy()
            lbl_err = ctk.CTkLabel(
                self.discovery_urls_frame, 
                text=f"Error: {error}", 
                font=("Arial", 11), 
                text_color="#ff5555"
            )
            lbl_err.pack(pady=20, padx=10)
        else:
            self.lbl_disc_status.configure(text=f"Status: Found {len(urls)} High-Quality ({len(raw_urls)} Raw)")
            self.raw_urls_textbox.delete("0.0", "end")
            if raw_urls:
                self.raw_urls_textbox.insert("end", "\n".join(raw_urls) + "\n")
            self.lbl_raw_urls.configure(text=f"🌐 Raw Search Results ({len(raw_urls)}):")
            
            self.populate_hq_urls(urls)
            self.lbl_hq_urls.configure(text=f"⭐ High-Quality URLs ({len(urls)}):")

    def setup_suppliers_tab(self):
        self.tab_suppliers.grid_columnconfigure(0, weight=1)
        self.tab_suppliers.grid_rowconfigure(3, weight=1)
        
        criteria_text = "Supplier Context: Extracting Manufacturers, Factories, Capabilities, MOQs, & Certifications across all 13 Industrial Niches (Car Parts & Auto Components, Lighting Controls, PCBs, PCBA, Electrical, Cables, Switchgear, Batteries, HVAC, Electric Vehicles, etc.)."
        lbl_criteria = ctk.CTkLabel(self.tab_suppliers, text=criteria_text, font=("Arial", 12, "bold"))
        lbl_criteria.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.sup_urls_textbox = ctk.CTkTextbox(self.tab_suppliers, height=80)
        self.sup_urls_textbox.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.sup_urls_textbox.insert("0.0", "https://www.sahasraelectronics.com\nhttps://www.polycab.com\nhttps://www.havells.com\n")
        
        control_frame = ctk.CTkFrame(self.tab_suppliers)
        control_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        self.btn_sup_start = ctk.CTkButton(control_frame, text="Start Supplier Scraping", command=lambda: self.start_scraping("supplier"))
        self.btn_sup_start.pack(side="left", padx=10)
        
        self.btn_sup_prop = ctk.CTkButton(control_frame, text="🌐 Quick URL Inquiry", command=lambda: self.open_url_proposal_window(is_supplier=True), fg_color="#005b96", hover_color="#003f66")
        self.btn_sup_prop.pack(side="left", padx=10)

        self.lbl_sup_status = ctk.CTkLabel(control_frame, text="Status: Idle", text_color="gray")
        self.lbl_sup_status.pack(side="left", padx=10)
        
        self.sup_output_textbox = ctk.CTkTextbox(self.tab_suppliers, wrap="none")
        self.sup_output_textbox.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")

    def setup_buyers_tab(self):
        self.tab_buyers.grid_columnconfigure(0, weight=1)
        self.tab_buyers.grid_rowconfigure(3, weight=1)
        
        criteria_text = "Buyer Context: Extracting Target Products, Industry, Size, and filtering for true OEMs & Distributors across all 13 Industrial Niches (Car Parts, Electronics, PCBs, Electrical, Energy, etc.)."
        lbl_criteria = ctk.CTkLabel(self.tab_buyers, text=criteria_text, font=("Arial", 12, "bold"))
        lbl_criteria.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.buy_urls_textbox = ctk.CTkTextbox(self.tab_buyers, height=80)
        self.buy_urls_textbox.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        control_frame = ctk.CTkFrame(self.tab_buyers)
        control_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        self.btn_buy_start = ctk.CTkButton(control_frame, text="Start Buyer Scraping", command=lambda: self.start_scraping("buyer"))
        self.btn_buy_start.pack(side="left", padx=10)
        
        self.btn_buy_prop = ctk.CTkButton(control_frame, text="🌐 Quick URL Proposal", command=self.open_url_proposal_window, fg_color="#005b96", hover_color="#003f66")
        self.btn_buy_prop.pack(side="left", padx=10)
        
        self.lbl_buy_status = ctk.CTkLabel(control_frame, text="Status: Idle", text_color="gray")
        self.lbl_buy_status.pack(side="left", padx=10)
        
        self.buy_output_textbox = ctk.CTkTextbox(self.tab_buyers, wrap="none")
        self.buy_output_textbox.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")

    def start_scraping(self, pipeline_type):
        if pipeline_type == "logistics":
            urls_text = self.log_urls_textbox.get("0.0", "end").strip()
            self.btn_log_start.configure(state="disabled")
            self.lbl_log_status.configure(text="Status: Starting pipeline...")
            self.log_output_textbox.delete("0.0", "end")
        elif pipeline_type == "warehouse":
            urls_text = self.wh_urls_textbox.get("0.0", "end").strip()
            self.btn_wh_start.configure(state="disabled")
            self.lbl_wh_status.configure(text="Status: Starting pipeline...")
            self.wh_output_textbox.delete("0.0", "end")
        elif pipeline_type == "supplier":
            urls_text = self.sup_urls_textbox.get("0.0", "end").strip()
            self.btn_sup_start.configure(state="disabled")
            self.lbl_sup_status.configure(text="Status: Starting pipeline...")
            self.sup_output_textbox.delete("0.0", "end")
        else:
            urls_text = self.buy_urls_textbox.get("0.0", "end").strip()
            self.btn_buy_start.configure(state="disabled")
            self.lbl_buy_status.configure(text="Status: Starting pipeline...")
            self.buy_output_textbox.delete("0.0", "end")
            
        if not urls_text:
            return
            
        urls = [url.strip() for url in urls_text.split("\n") if url.strip()]
        threading.Thread(target=self.run_pipeline_thread, args=(urls, pipeline_type), daemon=True).start()

    def run_pipeline_thread(self, urls, pipeline_type):
        if pipeline_type == "logistics":
            output_file = "Logistics_Matrix.xlsx"
            import processor
            processor.process_logistics_urls(urls, output_file, self.logger)
        elif pipeline_type == "warehouse":
            output_file = "Warehouses_Matrix.xlsx"
            import processor
            processor.process_warehouse_urls(urls, output_file, self.logger)
        elif pipeline_type == "supplier":
            output_file = "Suppliers_Matrix.xlsx"
            run_pipeline(urls, self.logger, output_file=output_file)
        else:
            output_file = "Buyers_Matrix.xlsx"
            run_buyer_pipeline(urls, self.logger, output_file=output_file)
            
        self.ui_queue.put((self.on_pipeline_complete, (output_file, pipeline_type)))
        
    def on_pipeline_complete(self, output_file, pipeline_type):
        if pipeline_type == "logistics":
            self.btn_log_start.configure(state="normal")
            self.lbl_log_status.configure(text="Status: Completed.")
            self.load_matrix(self.log_tree, "Logistics_Matrix.xlsx")
            self.display_matrix_text(output_file, self.log_output_textbox)
        elif pipeline_type == "warehouse":
            self.btn_wh_start.configure(state="normal")
            self.lbl_wh_status.configure(text="Status: Completed.")
            self.load_matrix(self.wh_tree, "Warehouses_Matrix.xlsx")
            self.display_matrix_text(output_file, self.wh_output_textbox)
        elif pipeline_type == "supplier":
            self.btn_sup_start.configure(state="normal")
            self.lbl_sup_status.configure(text="Status: Completed.")
            self.load_matrix(self.sup_tree, "Suppliers_Matrix.xlsx")
            self.display_matrix_text(output_file, self.sup_output_textbox)
        else:
            self.btn_buy_start.configure(state="normal")
            self.lbl_buy_status.configure(text="Status: Completed.")
            self.load_matrix(self.buy_tree, "Buyers_Matrix.xlsx")
            self.display_matrix_text(output_file, self.buy_output_textbox)

    def display_matrix_text(self, output_file, textbox):
        if os.path.exists(output_file):
            try:
                df = pd.read_excel(output_file)
                textbox.insert("0.0", df.to_string())
            except Exception as e:
                textbox.insert("0.0", f"Error loading Excel file: {e}")
        else:
            textbox.insert("0.0", "Output file not found. Scraper may have failed.")

    def create_database_tab_ui(self, tab, sync_cmd, clean_cmd, delete_all_cmd, proposal_cmd=None, is_supplier=False, mode=None):
        import tkinter as tk
        import tkinter.messagebox as messagebox
        import webbrowser

        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        if mode is None:
            mode = "supplier" if is_supplier else "buyer"

        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=0, column=0, pady=10, padx=10, sticky="w")
        
        btn_sync = ctk.CTkButton(btn_frame, text="Sync / Load Matrix", command=sync_cmd, width=120)
        btn_sync.pack(side="left", padx=(0, 6))
        
        if proposal_cmd:
            if mode == "logistics":
                btn_prop_text = "📝 Create Freight RFQ"
                btn_url_prop_text = "🌐 Freight RFQ from URL"
                url_cmd = lambda: self.open_url_proposal_window(mode="logistics")
            elif mode == "warehouse":
                btn_prop_text = "🏢 Create Rental Inquiry"
                btn_url_prop_text = "🌐 Rental Inquiry from URL"
                url_cmd = lambda: self.open_url_proposal_window(mode="warehouse")
            elif mode == "supplier":
                btn_prop_text = "📝 Create Sourcing Inquiry"
                btn_url_prop_text = "🌐 Inquiry from URL"
                url_cmd = lambda: self.open_url_proposal_window(mode="supplier")
            else:
                btn_prop_text = "📝 Create Proposal"
                btn_url_prop_text = "🌐 Proposal from URL"
                url_cmd = lambda: self.open_url_proposal_window(mode="buyer")

            btn_prop = ctk.CTkButton(btn_frame, text=btn_prop_text, command=proposal_cmd, fg_color="#1f7a1f", hover_color="#145214")
            btn_prop.pack(side="left", padx=(0, 6))

            btn_url_prop = ctk.CTkButton(btn_frame, text=btn_url_prop_text, command=url_cmd, fg_color="#005b96", hover_color="#003f66")
            btn_url_prop.pack(side="left", padx=(0, 6))

        def get_url_from_item(item_id):
            if not item_id:
                return ""
            row_vals = tree.item(item_id)["values"]
            cols = list(tree["columns"])
            data = dict(zip(cols, row_vals))
            url_val = str(data.get("url", "")).strip()
            if url_val in ["None", "nan", ""]:
                return ""
            if not (url_val.startswith("http://") or url_val.startswith("https://")):
                url_val = "https://" + url_val
            return url_val

        def copy_url_to_clipboard(url_val, feedback_btn=None):
            if url_val:
                self.clipboard_clear()
                self.clipboard_append(url_val)
                if feedback_btn:
                    orig_text = feedback_btn.cget("text")
                    feedback_btn.configure(text="Copied! ✅")
                    tab.after(1500, lambda: feedback_btn.configure(text=orig_text))
                self.logger.info(f"Copied URL to clipboard: {url_val}")
                return True
            return False

        def on_copy_btn_clicked():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select Row", "Please select a row from the table first to copy its URL.")
                return
            u = get_url_from_item(sel[0])
            if u:
                copy_url_to_clipboard(u, feedback_btn=btn_copy_url)
            else:
                messagebox.showinfo("No URL", "No URL found for the selected row.")

        def on_open_btn_clicked():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select Row", "Please select a row from the table first to open its URL.")
                return
            u = get_url_from_item(sel[0])
            if u and (u.startswith("http://") or u.startswith("https://")):
                webbrowser.open(u)
            else:
                messagebox.showinfo("Invalid URL", f"No valid URL found for the selected row: {u}")

        btn_copy_url = ctk.CTkButton(
            btn_frame, 
            text="📋 Copy URL", 
            command=on_copy_btn_clicked, 
            width=100, 
            fg_color="#3a3a3a", 
            hover_color="#2b2b2b"
        )
        btn_copy_url.pack(side="left", padx=(0, 6))

        btn_open_url = ctk.CTkButton(
            btn_frame, 
            text="🌐 Open URL", 
            command=on_open_btn_clicked, 
            width=100, 
            fg_color="#005b96", 
            hover_color="#003f66"
        )
        btn_open_url.pack(side="left", padx=(0, 6))

        btn_clean = ctk.CTkButton(btn_frame, text="Clean Matrix", command=clean_cmd, width=100, fg_color="#b30000", hover_color="#800000")
        btn_clean.pack(side="left", padx=(0, 6))
        
        btn_delete_all = ctk.CTkButton(btn_frame, text="Delete All Entries", command=delete_all_cmd, width=115, fg_color="#660000", hover_color="#4d0000")
        btn_delete_all.pack(side="left", padx=6)

        if mode == "warehouse":
            tab.grid_rowconfigure(1, weight=0)
            tab.grid_rowconfigure(2, weight=1)

            dist_frame = ctk.CTkFrame(tab, fg_color="#1e2229", corner_radius=6)
            dist_frame.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")

            lbl_ref_icon = ctk.CTkLabel(
                dist_frame, 
                text="📍 Reference Area / Landmark:", 
                font=("Arial", 12, "bold"),
                text_color="#e0e0e0"
            )
            lbl_ref_icon.pack(side="left", padx=(12, 6), pady=6)

            self.wh_ref_area_entry = ctk.CTkEntry(
                dist_frame, 
                placeholder_text="Enter area or landmark (e.g. Bandra West, Cyber City, Whitefield, Okhla)...", 
                width=340,
                height=32
            )
            self.wh_ref_area_entry.pack(side="left", padx=(0, 10), pady=6)
            self.wh_ref_area_entry.bind("<Return>", lambda event: self.start_warehouse_distance_calculation())

            self.wh_calc_dist_btn = ctk.CTkButton(
                dist_frame, 
                text="📏 Calculate Road Distances (Gemini)", 
                command=self.start_warehouse_distance_calculation,
                width=245,
                height=32,
                fg_color="#006699",
                hover_color="#004c73",
                font=("Arial", 12, "bold")
            )
            self.wh_calc_dist_btn.pack(side="left", padx=(0, 10), pady=6)

            self.wh_dist_status_lbl = ctk.CTkLabel(
                dist_frame, 
                text="", 
                font=("Arial", 11, "italic"),
                text_color="#a0a0a0"
            )
            self.wh_dist_status_lbl.pack(side="left", padx=(5, 10), pady=6)

            frame_row = 2
        else:
            frame_row = 1

        frame = ctk.CTkFrame(tab)
        frame.grid(row=frame_row, column=0, sticky="nsew", padx=10, pady=10)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.map('Treeview', background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#343638')])
        
        tree = ttk.Treeview(frame, show='headings')
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        def on_tree_click(event):
            region = tree.identify("region", event.x, event.y)
            if region == "cell":
                col_id = tree.identify_column(event.x)
                item = tree.identify_row(event.y)
                if item:
                    tree.selection_set(item)
                    if col_id == "#1":
                        if proposal_cmd:
                            proposal_cmd()
                    elif col_id == "#2":
                        u = get_url_from_item(item)
                        if u:
                            copy_url_to_clipboard(u, feedback_btn=btn_copy_url)
                        else:
                            messagebox.showinfo("No URL", "No URL found for this property.")
                    else:
                        # Check if user clicked directly on the "url" data column
                        try:
                            col_idx = int(col_id.replace("#", "")) - 1
                            cols = list(tree["columns"])
                            if 0 <= col_idx < len(cols) and cols[col_idx].lower() == "url":
                                u = get_url_from_item(item)
                                if u:
                                    copy_url_to_clipboard(u, feedback_btn=btn_copy_url)
                        except Exception:
                            pass

        tree.bind("<ButtonRelease-1>", on_tree_click)

        if proposal_cmd:
            def on_tree_double_click(event):
                region = tree.identify("region", event.x, event.y)
                if region == "cell":
                    col_id = tree.identify_column(event.x)
                    if col_id == "#2":
                        return
                proposal_cmd()
            tree.bind("<Double-1>", on_tree_double_click)

        # Right-click context menu
        menu = tk.Menu(tab, tearoff=0)
        menu.add_command(label="📋 Copy Property URL", command=on_copy_btn_clicked)
        menu.add_command(label="🌐 Open URL in Browser", command=on_open_btn_clicked)
        if proposal_cmd:
            menu.add_separator()
            if mode == "warehouse":
                prop_label = "🏢 Create Rental Inquiry"
            elif mode == "logistics":
                prop_label = "📝 Create Freight RFQ"
            elif mode == "supplier":
                prop_label = "📝 Create Sourcing Inquiry"
            else:
                prop_label = "📝 Create Proposal"
            menu.add_command(label=prop_label, command=proposal_cmd)

        def on_tree_right_click(event):
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                try:
                    menu.tk_popup(event.x_root, event.y_root)
                finally:
                    menu.grab_release()

        tree.bind("<Button-3>", on_tree_right_click)

        return tree

    def setup_sup_db_tab(self):
        self.sup_tree = self.create_database_tab_ui(
            self.tab_sup_db, 
            lambda: self.load_matrix(self.sup_tree, "Suppliers_Matrix.xlsx"),
            lambda: self.clean_local_matrix("Suppliers_Matrix.xlsx", self.sup_tree),
            lambda: self.delete_all_entries("Suppliers_Matrix.xlsx", self.sup_tree),
            proposal_cmd=self.open_supplier_inquiry_window,
            is_supplier=True
        )
        self.load_matrix(self.sup_tree, "Suppliers_Matrix.xlsx")
        
    def setup_buy_db_tab(self):
        self.buy_tree = self.create_database_tab_ui(
            self.tab_buy_db, 
            lambda: self.load_matrix(self.buy_tree, "Buyers_Matrix.xlsx"),
            lambda: self.clean_local_matrix("Buyers_Matrix.xlsx", self.buy_tree),
            lambda: self.delete_all_entries("Buyers_Matrix.xlsx", self.buy_tree),
            proposal_cmd=self.open_proposal_window,
            is_supplier=False
        )
        self.load_matrix(self.buy_tree, "Buyers_Matrix.xlsx")

    def open_proposal_window(self):
        selected_items = self.buy_tree.selection()
        if not selected_items:
            import tkinter.messagebox as messagebox
            messagebox.showinfo("Select Buyer", "Please select a buyer from the table to generate a proposal.")
            return

        selected_item = selected_items[0]
        row_values = self.buy_tree.item(selected_item)["values"]
        cols = list(self.buy_tree["columns"])
        data = dict(zip(cols, row_values))

        company_name = str(data.get("company_name", "Valued Partner")).strip()
        target_products = str(data.get("target_products", "Industrial Products")).strip()
        industry = str(data.get("industry", "")).strip()
        locations = str(data.get("locations", "")).strip()
        url = str(data.get("url", "")).strip()
        contact_emails = str(data.get("contact_emails", "")).strip()

        win = ctk.CTkToplevel(self)
        win.title(f"Trade Proposal - {company_name}")
        win.geometry("820x720")
        win.attributes("-topmost", True)
        win.focus_set()

        header_frame = ctk.CTkFrame(win, fg_color="#1f232a", corner_radius=8)
        header_frame.pack(fill="x", padx=15, pady=(15, 8))

        lbl_title = ctk.CTkLabel(
            header_frame, 
            text=f"B2B Commercial Proposal for {company_name}", 
            font=("Arial", 16, "bold"),
            text_color="#ffffff"
        )
        lbl_title.pack(anchor="w", padx=15, pady=(10, 2))

        lbl_sub = ctk.CTkLabel(
            header_frame, 
            text=f"Target: {target_products}  |  Industry: {industry or 'General Trade'}  |  Region: {locations or 'Global'}", 
            font=("Arial", 11),
            text_color="#a0a0a0"
        )
        lbl_sub.pack(anchor="w", padx=15, pady=(0, 10))

        # To Row
        to_frame = ctk.CTkFrame(win, fg_color="transparent")
        to_frame.pack(fill="x", padx=15, pady=(4, 3))
        lbl_to = ctk.CTkLabel(to_frame, text="To:", width=65, anchor="w", font=("Arial", 12, "bold"))
        lbl_to.pack(side="left")
        entry_to = ctk.CTkEntry(to_frame, font=("Arial", 12), height=32)
        entry_to.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if contact_emails:
            entry_to.insert(0, contact_emails)
        btn_copy_to = ctk.CTkButton(to_frame, text="📋 Copy", width=75, height=32)
        btn_copy_to.pack(side="right")

        # Subject Row
        subj_frame = ctk.CTkFrame(win, fg_color="transparent")
        subj_frame.pack(fill="x", padx=15, pady=(3, 5))
        lbl_subj = ctk.CTkLabel(subj_frame, text="Subject:", width=65, anchor="w", font=("Arial", 12, "bold"))
        lbl_subj.pack(side="left")
        entry_subj = ctk.CTkEntry(subj_frame, font=("Arial", 12), height=32)
        entry_subj.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry_subj.insert(0, "Generating Subject line...")
        btn_copy_subj = ctk.CTkButton(subj_frame, text="📋 Copy", width=75, height=32)
        btn_copy_subj.pack(side="right")

        # Body Header Row
        body_hdr = ctk.CTkFrame(win, fg_color="transparent")
        body_hdr.pack(fill="x", padx=15, pady=(4, 2))
        lbl_body = ctk.CTkLabel(body_hdr, text="Email Body (Gmail Ready):", font=("Arial", 12, "bold"))
        lbl_body.pack(side="left")
        btn_copy_body = ctk.CTkButton(body_hdr, text="📋 Copy Body", width=105, height=28, fg_color="#1f7a1f", hover_color="#145214")
        btn_copy_body.pack(side="right")

        # Body Textbox
        txt_body = ctk.CTkTextbox(win, wrap="word", font=("Arial", 12))
        txt_body.pack(fill="both", expand=True, padx=15, pady=(2, 8))
        txt_body.insert("0.0", "⏳ Generating personalized commercial proposal using Gemini AI...\nPlease wait a few seconds.")

        # Copy handlers
        def copy_widget_text(widget, btn, default_txt):
            if isinstance(widget, ctk.CTkTextbox):
                val = widget.get("0.0", "end").strip()
            else:
                val = widget.get().strip()
            if val and not val.startswith("⏳"):
                self.clipboard_clear()
                self.clipboard_append(val)
                btn.configure(text="Copied! ✅")
                win.after(1500, lambda: btn.configure(text=default_txt))

        btn_copy_to.configure(command=lambda: copy_widget_text(entry_to, btn_copy_to, "📋 Copy"))
        btn_copy_subj.configure(command=lambda: copy_widget_text(entry_subj, btn_copy_subj, "📋 Copy"))
        btn_copy_body.configure(command=lambda: copy_widget_text(txt_body, btn_copy_body, "📋 Copy Body"))

        # Bottom Bar
        btn_bar = ctk.CTkFrame(win, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(5, 12))

        def copy_all():
            s = entry_subj.get().strip()
            b = txt_body.get("0.0", "end").strip()
            if b and not b.startswith("⏳"):
                self.clipboard_clear()
                self.clipboard_append(f"Subject: {s}\n\n{b}")
                btn_copy_all.configure(text="All Copied! ✅")
                win.after(1500, lambda: btn_copy_all.configure(text="📋 Copy Subject + Body"))

        btn_copy_all = ctk.CTkButton(btn_bar, text="📋 Copy Subject + Body", command=copy_all, width=170, fg_color="#005b96", hover_color="#003f66")
        btn_copy_all.pack(side="left", padx=5)

        def start_generation():
            entry_subj.delete(0, "end")
            entry_subj.insert(0, "Generating Subject line...")
            txt_body.delete("0.0", "end")
            txt_body.insert("0.0", "⏳ Generating personalized commercial proposal using Gemini AI...\nPlease wait a few seconds.")
            btn_regen.configure(state="disabled")

            def generate_worker():
                try:
                    from google.genai import types
                    from pydantic import BaseModel, Field
                    from llm_fallback import generate_with_fallback

                    class EmailProposal(BaseModel):
                        to_email: str = Field(default="", description="Recipient contact email if found in context, otherwise empty string")
                        subject: str = Field(description="Clean, compelling email subject line without any markdown or quotes")
                        body: str = Field(description="Full clean email body ready to paste directly into Gmail composer. Do NOT include markdown bold/italics (no asterisks). Use simple bullet points with • if listing technical specifications.")

                    prompt = f"""You are Fardin Mohammed, Partner at SinoMagan Indus Global Trade LLP, writing a personalized, direct B2B commercial export proposal to a prospective client.

Target Client Details:
- Target Buyer / Client: {company_name}
- Industry: {industry}
- Products Demanded / Target Products: {target_products}
- Client Location: {locations}
- Client Website: {url}
- Known Contact Emails: {contact_emails}

Your Company:
- SinoMagan Indus Global Trade LLP (Global sourcing, contract manufacturing, export & logistics management across Automotive Components, Power Electronics, PCBs, Solar, and Industrial Equipment)
- Authorized Signatory: Fardin Mohammed, Partner

CRITICAL INSTRUCTIONS FOR GMAIL-READY PLAIN TEXT:
1. SUBJECT LINE:
   - Provide a concise, highly relevant email Subject line tailored to {company_name} and {target_products}. No quotes or markdown.
2. RECIPIENT EMAIL:
   - If an email is listed in Known Contact Emails or context, provide it. Otherwise leave empty string.
3. EMAIL BODY (STRICT GMAIL PLAIN TEXT FORMAT):
   - The body MUST be 100% ready to paste directly into the Gmail composer.
   - ABSOLUTELY NO MARKDOWN FORMATTING:
     * NEVER use asterisks for bold or italic (NO **word** or *word*).
     * NEVER use markdown headings (# or ##).
     * NEVER use markdown horizontal rules (---).
     * NEVER use markdown links [text](url).
   - TECHNICAL SPECIFICATIONS:
     * When listing technical parameters, components, certifications, or tolerances, format them using clean bullet points starting with '• ' (e.g. '• Technical Standard: ISO 9001, CE, RoHS', '• Production Tolerances: Precision Grade').
   - HUMAN TONE:
     * Sound like a real senior partner (Fardin Mohammed).
     * BANNED PHRASES: "I hope this email finds you well", "In today's fast-paced world", "Look no further", "delve", "testament to", "thrilled to connect".
     * Open directly by addressing {company_name} and their specific product/component demands.
   - COMMERCIAL & LOGISTICS REALISM:
     * Mention direct factory sourcing, container logistics (20ft/40ft FCL & LCL), Incoterms (FOB, CIF, CFR), sample dispatch for testing, and pre-shipment quality inspection.
   - SIGN-OFF:
     The sign-off MUST strictly be formatted as:

Warm regards,

Fardin Mohammed
Partner
SinoMagan Indus Global Trade LLP
"""
                    response = generate_with_fallback(
                        prompt=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=EmailProposal,
                        ),
                        logger=self.logger
                    )
                    to_val, subj_val, body_val = parse_email_response(response.text, default_to=contact_emails)

                    def on_done():
                        if to_val:
                            entry_to.delete(0, "end")
                            entry_to.insert(0, to_val)
                        entry_subj.delete(0, "end")
                        entry_subj.insert(0, subj_val)
                        txt_body.delete("0.0", "end")
                        txt_body.insert("0.0", body_val)
                        btn_regen.configure(state="normal")
                    win.after(0, on_done)
                except Exception as e:
                    def on_err():
                        txt_body.delete("0.0", "end")
                        txt_body.insert("0.0", f"Error generating proposal: {e}")
                        btn_regen.configure(state="normal")
                    win.after(0, on_err)

            threading.Thread(target=generate_worker, daemon=True).start()

        btn_regen = ctk.CTkButton(btn_bar, text="🔄 Regenerate", command=start_generation, width=120, fg_color="#3a3a3a", hover_color="#2b2b2b")
        btn_regen.pack(side="left", padx=5)

        btn_close = ctk.CTkButton(btn_bar, text="Close", command=win.destroy, width=90, fg_color="#555555", hover_color="#444444")
        btn_close.pack(side="right", padx=5)

        start_generation()

    def open_supplier_inquiry_window(self):
        selected_items = self.sup_tree.selection()
        if not selected_items:
            import tkinter.messagebox as messagebox
            messagebox.showinfo("Select Supplier", "Please select a supplier from the table to generate a sourcing inquiry.")
            return

        selected_item = selected_items[0]
        row_values = self.sup_tree.item(selected_item)["values"]
        cols = list(self.sup_tree["columns"])
        data = dict(zip(cols, row_values))

        company_name = str(data.get("company_name", "Valued Supplier")).strip()
        product_categories = str(data.get("product_categories", "")).strip()
        specific_products = str(data.get("specific_products", "Industrial Products")).strip()
        materials = str(data.get("materials", "")).strip()
        certifications = str(data.get("certifications", "")).strip()
        production_capacity = str(data.get("production_capacity", "")).strip()
        moq = str(data.get("minimum_order_quantity", "")).strip()
        export_markets = str(data.get("export_markets", "")).strip()
        oem_odm_service = str(data.get("oem_odm_service", "")).strip()
        locations = str(data.get("locations", "")).strip()
        url = str(data.get("url", "")).strip()
        contact_emails = str(data.get("contact_emails", "")).strip()

        win = ctk.CTkToplevel(self)
        win.title(f"Sourcing Inquiry / RFQ - {company_name}")
        win.geometry("820x720")
        win.attributes("-topmost", True)
        win.focus_set()

        header_frame = ctk.CTkFrame(win, fg_color="#1f232a", corner_radius=8)
        header_frame.pack(fill="x", padx=15, pady=(15, 8))

        lbl_title = ctk.CTkLabel(
            header_frame, 
            text=f"B2B Sourcing RFQ & Vendor Partnership for {company_name}", 
            font=("Arial", 16, "bold"),
            text_color="#ffffff"
        )
        lbl_title.pack(anchor="w", padx=15, pady=(10, 2))

        sub_desc = f"Products: {specific_products or product_categories}  |  Location: {locations or 'India'}  |  OEM/ODM: {oem_odm_service or 'N/A'}"
        lbl_sub = ctk.CTkLabel(
            header_frame, 
            text=sub_desc, 
            font=("Arial", 11),
            text_color="#a0a0a0"
        )
        lbl_sub.pack(anchor="w", padx=15, pady=(0, 10))

        # To Row
        to_frame = ctk.CTkFrame(win, fg_color="transparent")
        to_frame.pack(fill="x", padx=15, pady=(4, 3))
        lbl_to = ctk.CTkLabel(to_frame, text="To:", width=65, anchor="w", font=("Arial", 12, "bold"))
        lbl_to.pack(side="left")
        entry_to = ctk.CTkEntry(to_frame, font=("Arial", 12), height=32)
        entry_to.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if contact_emails:
            entry_to.insert(0, contact_emails)
        btn_copy_to = ctk.CTkButton(to_frame, text="📋 Copy", width=75, height=32)
        btn_copy_to.pack(side="right")

        # Subject Row
        subj_frame = ctk.CTkFrame(win, fg_color="transparent")
        subj_frame.pack(fill="x", padx=15, pady=(3, 5))
        lbl_subj = ctk.CTkLabel(subj_frame, text="Subject:", width=65, anchor="w", font=("Arial", 12, "bold"))
        lbl_subj.pack(side="left")
        entry_subj = ctk.CTkEntry(subj_frame, font=("Arial", 12), height=32)
        entry_subj.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry_subj.insert(0, "Generating Subject line...")
        btn_copy_subj = ctk.CTkButton(subj_frame, text="📋 Copy", width=75, height=32)
        btn_copy_subj.pack(side="right")

        # Body Header Row
        body_hdr = ctk.CTkFrame(win, fg_color="transparent")
        body_hdr.pack(fill="x", padx=15, pady=(4, 2))
        lbl_body = ctk.CTkLabel(body_hdr, text="Email Body (Gmail Ready):", font=("Arial", 12, "bold"))
        lbl_body.pack(side="left")
        btn_copy_body = ctk.CTkButton(body_hdr, text="📋 Copy Body", width=105, height=28, fg_color="#1f7a1f", hover_color="#145214")
        btn_copy_body.pack(side="right")

        # Body Textbox
        txt_body = ctk.CTkTextbox(win, wrap="word", font=("Arial", 12))
        txt_body.pack(fill="both", expand=True, padx=15, pady=(2, 8))
        txt_body.insert("0.0", "⏳ Generating tailored Sourcing RFQ / vendor inquiry using Gemini AI...\nPlease wait a few seconds.")

        # Copy handlers
        def copy_widget_text(widget, btn, default_txt):
            if isinstance(widget, ctk.CTkTextbox):
                val = widget.get("0.0", "end").strip()
            else:
                val = widget.get().strip()
            if val and not val.startswith("⏳"):
                self.clipboard_clear()
                self.clipboard_append(val)
                btn.configure(text="Copied! ✅")
                win.after(1500, lambda: btn.configure(text=default_txt))

        btn_copy_to.configure(command=lambda: copy_widget_text(entry_to, btn_copy_to, "📋 Copy"))
        btn_copy_subj.configure(command=lambda: copy_widget_text(entry_subj, btn_copy_subj, "📋 Copy"))
        btn_copy_body.configure(command=lambda: copy_widget_text(txt_body, btn_copy_body, "📋 Copy Body"))

        # Bottom Bar
        btn_bar = ctk.CTkFrame(win, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(5, 12))

        def copy_all():
            s = entry_subj.get().strip()
            b = txt_body.get("0.0", "end").strip()
            if b and not b.startswith("⏳"):
                self.clipboard_clear()
                self.clipboard_append(f"Subject: {s}\n\n{b}")
                btn_copy_all.configure(text="All Copied! ✅")
                win.after(1500, lambda: btn_copy_all.configure(text="📋 Copy Subject + Body"))

        btn_copy_all = ctk.CTkButton(btn_bar, text="📋 Copy Subject + Body", command=copy_all, width=170, fg_color="#005b96", hover_color="#003f66")
        btn_copy_all.pack(side="left", padx=5)

        def start_generation():
            entry_subj.delete(0, "end")
            entry_subj.insert(0, "Generating Subject line...")
            txt_body.delete("0.0", "end")
            txt_body.insert("0.0", "⏳ Generating tailored Sourcing RFQ / vendor inquiry using Gemini AI...\nPlease wait a few seconds.")
            btn_regen.configure(state="disabled")

            def generate_worker():
                try:
                    from google.genai import types
                    from pydantic import BaseModel, Field
                    from llm_fallback import generate_with_fallback

                    class EmailProposal(BaseModel):
                        to_email: str = Field(default="", description="Recipient contact email if found in context, otherwise empty string")
                        subject: str = Field(description="Clean, compelling email subject line without any markdown or quotes")
                        body: str = Field(description="Full clean email body ready to paste directly into Gmail composer. Do NOT include markdown bold/italics (no asterisks). Use simple bullet points with • if listing technical specifications.")

                    prompt = f"""You are Fardin Mohammed, Partner at SinoMagan Indus Global Trade LLP, writing an official B2B Sourcing RFQ / vendor partnership inquiry to an industrial manufacturer / supplier.

Supplier Profile:
- Company Name: {company_name}
- Specific Products Manufactured: {specific_products}
- Product Categories: {product_categories}
- Materials / Capabilities: {materials}
- Certifications Held: {certifications}
- Production Capacity: {production_capacity}
- Minimum Order Quantity (MOQ): {moq}
- Export Experience / Markets: {export_markets}
- OEM / ODM Capability: {oem_odm_service}
- Factory / Facility Location: {locations}
- Website: {url}
- Contact Email: {contact_emails}

Your Company:
- SinoMagan Indus Global Trade LLP (Global sourcing, contract manufacturing, export & logistics management across Automotive Components, Power Electronics, PCBs, Solar, and Industrial Equipment)
- Authorized Signatory: Fardin Mohammed, Partner

PURPOSE OF THIS EMAIL:
You represent active international commercial buyer and infrastructure project demands (across GCC/Middle East, Europe, North America) seeking reliable factory suppliers for ongoing export orders. You are reaching out to establish a direct B2B vendor partnership with {company_name}.

CRITICAL INSTRUCTIONS FOR GMAIL-READY PLAIN TEXT:
1. SUBJECT LINE:
   - Provide a concise, highly professional B2B inquiry Subject line referencing RFQ / Export Sourcing / Vendor Partnership for {company_name} and their specific products ({specific_products or product_categories}). No quotes or markdown.
2. RECIPIENT EMAIL:
   - If an email is listed in Contact Email or context, provide it. Otherwise leave empty string.
3. EMAIL BODY (STRICT GMAIL PLAIN TEXT FORMAT):
   - The body MUST be 100% ready to paste directly into the Gmail composer.
   - ABSOLUTELY NO MARKDOWN FORMATTING:
     * NEVER use asterisks for bold or italic (NO **word** or *word*).
     * NEVER use markdown headings (# or ##).
     * NEVER use markdown horizontal rules (---).
     * NEVER use markdown links [text](url).
   - INQUIRY SPECIFICATIONS:
     * State our overseas client project requirements clearly and ask for:
       • Product catalog / technical data sheets (TDS)
       • Export pricing & commercial terms (FOB Indian port / CIF)
       • Minimum Order Quantities (MOQ) and production lead times
       • OEM / private-label custom branding options
       • Compliance test reports & international certifications ({certifications or 'ISO / CE / RoHS / UL'})
       • Sample dispatch procedure for overseas client inspection
     * Format these bullet points cleanly with '• '.
   - HUMAN TONE:
     * Sound like an authentic, seasoned B2B partner (Fardin Mohammed).
     * BANNED PHRASES: "I hope this email finds you well", "In today's fast-paced world", "Look no further", "delve", "testament to", "thrilled to connect".
     * Open directly by introducing SinoMagan Indus Global Trade LLP and highlighting specific interest in {company_name}'s manufacturing capabilities.
   - COMMERCIAL & LOGISTICS REALISM:
     * Mention full container load (FCL) export potential, regular monthly off-take for qualified vendors, pre-shipment third-party inspections, and standard international trade terms.
   - SIGN-OFF:
     The sign-off MUST strictly be formatted as:

Warm regards,

Fardin Mohammed
Partner
SinoMagan Indus Global Trade LLP
"""
                    response = generate_with_fallback(
                        prompt=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=EmailProposal,
                        ),
                        logger=self.logger
                    )
                    to_val, subj_val, body_val = parse_email_response(response.text, default_to=contact_emails)

                    def on_done():
                        if to_val:
                            entry_to.delete(0, "end")
                            entry_to.insert(0, to_val)
                        entry_subj.delete(0, "end")
                        entry_subj.insert(0, subj_val)
                        txt_body.delete("0.0", "end")
                        txt_body.insert("0.0", body_val)
                        btn_regen.configure(state="normal")
                    win.after(0, on_done)
                except Exception as e:
                    def on_err():
                        txt_body.delete("0.0", "end")
                        txt_body.insert("0.0", f"Error generating inquiry: {e}")
                        btn_regen.configure(state="normal")
                    win.after(0, on_err)

            threading.Thread(target=generate_worker, daemon=True).start()

        btn_regen = ctk.CTkButton(btn_bar, text="🔄 Regenerate", command=start_generation, width=120, fg_color="#3a3a3a", hover_color="#2b2b2b")
        btn_regen.pack(side="left", padx=5)

        btn_close = ctk.CTkButton(btn_bar, text="Close", command=win.destroy, width=90, fg_color="#555555", hover_color="#444444")
        btn_close.pack(side="right", padx=5)

        start_generation()

    def open_logistics_inquiry_window(self):
        selected_items = self.log_tree.selection()
        if not selected_items:
            import tkinter.messagebox as messagebox
            messagebox.showinfo("Select Logistics Provider", "Please select a logistics company from the table to generate a freight inquiry.")
            return

        selected_item = selected_items[0]
        row_values = self.log_tree.item(selected_item)["values"]
        cols = list(self.log_tree["columns"])
        data = dict(zip(cols, row_values))

        company_name = str(data.get("company_name", "Freight Forwarder / Logistics Provider")).strip()
        shipping_routes = str(data.get("shipping_routes", "")).strip()
        services_offered = str(data.get("services_offered", "Ocean & Air Freight")).strip()
        container_types = str(data.get("container_types", "Standard 20ft/40ft Containers")).strip()
        locations_hq = str(data.get("locations_hq", "")).strip()
        url = str(data.get("url", "")).strip()
        contact_emails = str(data.get("contact_emails", "")).strip()
        phone_numbers = str(data.get("phone_numbers", "")).strip()

        win = ctk.CTkToplevel(self)
        win.title(f"Freight & Logistics RFQ - {company_name}")
        win.geometry("820x720")
        win.attributes("-topmost", True)
        win.focus_set()

        header_frame = ctk.CTkFrame(win, fg_color="#1f232a", corner_radius=8)
        header_frame.pack(fill="x", padx=15, pady=(15, 8))

        lbl_title = ctk.CTkLabel(
            header_frame, 
            text=f"Freight Cargo & Logistics RFQ for {company_name}", 
            font=("Arial", 16, "bold"),
            text_color="#ffffff"
        )
        lbl_title.pack(anchor="w", padx=15, pady=(10, 2))

        sub_desc = f"Routes: {shipping_routes or 'Global Trade Lanes'}  |  Services: {services_offered or 'Freight Forwarding'}  |  HQ: {locations_hq or 'India'}"
        lbl_sub = ctk.CTkLabel(
            header_frame, 
            text=sub_desc, 
            font=("Arial", 11),
            text_color="#a0a0a0"
        )
        lbl_sub.pack(anchor="w", padx=15, pady=(0, 10))

        # To Row
        to_frame = ctk.CTkFrame(win, fg_color="transparent")
        to_frame.pack(fill="x", padx=15, pady=(4, 3))
        lbl_to = ctk.CTkLabel(to_frame, text="To:", width=65, anchor="w", font=("Arial", 12, "bold"))
        lbl_to.pack(side="left")
        entry_to = ctk.CTkEntry(to_frame, font=("Arial", 12), height=32)
        entry_to.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if contact_emails:
            entry_to.insert(0, contact_emails)
        btn_copy_to = ctk.CTkButton(to_frame, text="📋 Copy", width=75, height=32)
        btn_copy_to.pack(side="right")

        # Subject Row
        subj_frame = ctk.CTkFrame(win, fg_color="transparent")
        subj_frame.pack(fill="x", padx=15, pady=(3, 5))
        lbl_subj = ctk.CTkLabel(subj_frame, text="Subject:", width=65, anchor="w", font=("Arial", 12, "bold"))
        lbl_subj.pack(side="left")
        entry_subj = ctk.CTkEntry(subj_frame, font=("Arial", 12), height=32)
        entry_subj.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry_subj.insert(0, "Generating Subject line...")
        btn_copy_subj = ctk.CTkButton(subj_frame, text="📋 Copy", width=75, height=32)
        btn_copy_subj.pack(side="right")

        # Body Header Row
        body_hdr = ctk.CTkFrame(win, fg_color="transparent")
        body_hdr.pack(fill="x", padx=15, pady=(4, 2))
        lbl_body = ctk.CTkLabel(body_hdr, text="Email Body (Gmail Ready):", font=("Arial", 12, "bold"))
        lbl_body.pack(side="left")
        btn_copy_body = ctk.CTkButton(body_hdr, text="📋 Copy Body", width=105, height=28, fg_color="#1f7a1f", hover_color="#145214")
        btn_copy_body.pack(side="right")

        # Body Textbox
        txt_body = ctk.CTkTextbox(win, wrap="word", font=("Arial", 12))
        txt_body.pack(fill="both", expand=True, padx=15, pady=(2, 8))
        txt_body.insert("0.0", "⏳ Generating tailored Freight Cargo & Logistics RFQ using Gemini AI...\nPlease wait a few seconds.")

        # Copy handlers
        def copy_widget_text(widget, btn, default_txt):
            if isinstance(widget, ctk.CTkTextbox):
                val = widget.get("0.0", "end").strip()
            else:
                val = widget.get().strip()
            if val and not val.startswith("⏳"):
                self.clipboard_clear()
                self.clipboard_append(val)
                btn.configure(text="Copied! ✅")
                win.after(1500, lambda: btn.configure(text=default_txt))

        btn_copy_to.configure(command=lambda: copy_widget_text(entry_to, btn_copy_to, "📋 Copy"))
        btn_copy_subj.configure(command=lambda: copy_widget_text(entry_subj, btn_copy_subj, "📋 Copy"))
        btn_copy_body.configure(command=lambda: copy_widget_text(txt_body, btn_copy_body, "📋 Copy Body"))

        # Bottom Bar
        btn_bar = ctk.CTkFrame(win, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(5, 12))

        def copy_all():
            s = entry_subj.get().strip()
            b = txt_body.get("0.0", "end").strip()
            if b and not b.startswith("⏳"):
                self.clipboard_clear()
                self.clipboard_append(f"Subject: {s}\n\n{b}")
                btn_copy_all.configure(text="All Copied! ✅")
                win.after(1500, lambda: btn_copy_all.configure(text="📋 Copy Subject + Body"))

        btn_copy_all = ctk.CTkButton(btn_bar, text="📋 Copy Subject + Body", command=copy_all, width=170, fg_color="#005b96", hover_color="#003f66")
        btn_copy_all.pack(side="left", padx=5)

        def start_generation():
            entry_subj.delete(0, "end")
            entry_subj.insert(0, "Generating Subject line...")
            txt_body.delete("0.0", "end")
            txt_body.insert("0.0", "⏳ Generating tailored Freight Cargo & Logistics RFQ using Gemini AI...\nPlease wait a few seconds.")
            btn_regen.configure(state="disabled")

            def generate_worker():
                try:
                    from google.genai import types
                    from pydantic import BaseModel, Field
                    from llm_fallback import generate_with_fallback

                    class EmailProposal(BaseModel):
                        to_email: str = Field(default="", description="Recipient contact email if found in context, otherwise empty string")
                        subject: str = Field(description="Clean, compelling email subject line without any markdown or quotes")
                        body: str = Field(description="Full clean email body ready to paste directly into Gmail composer. Do NOT include markdown bold/italics (no asterisks). Use simple bullet points with • if listing technical specifications.")

                    prompt = f"""You are Fardin Mohammed, Partner at SinoMagan Indus Global Trade LLP, writing an official B2B freight cargo RFQ & inquiry to a logistics company / freight forwarder.

Logistics Provider Profile:
- Company Name: {company_name}
- Known Shipping Routes / Trade Lanes: {shipping_routes}
- Services Offered: {services_offered}
- Container Equipment Handled: {container_types}
- Headquarters / Port Locations: {locations_hq}
- Website: {url}
- Contact Email: {contact_emails}

Your Company:
- SinoMagan Indus Global Trade LLP (International trade, export sourcing, contract manufacturing, containerized freight operations)
- Authorized Signatory: Fardin Mohammed, Partner

PURPOSE OF THIS EMAIL (FREIGHT CARGO & SERVICE EXTENT INQUIRY):
SinoMagan Indus Global Trade LLP regularly moves commercial export containerized freight (such as car parts & auto components (brake pads, brake discs, shock absorbers, suspension parts, automotive filters, radiators, engine components), hydraulic actuators & speed regulating motors (Groschopp WK0920702 motor governors), photovoltaic solar panels (monocrystalline & TOPCon PV modules for solar energy systems), wooden panels (plywood, MDF, decorative laminated boards), integrated circuits (brand new original ICs, microcontrollers, RTCs), consolidated electronic components (displays, capacitors, illuminated rocker & power switches 6A-20A, battery holders, fan motors), remote control switches, power distribution equipment, numerical protection relays & substation automation, electrical control gear, circuit breakers, contactors, transformers, switchgear, centralized lighting control systems & dimming modules, solar panel scrap (PV module scrap for industrial recycling), cables, battery storage systems, HVAC equipment, and industrial hardware) from major Indian ports (e.g. Nhava Sheva / JNPT, Mundra, Chennai) to international destinations (including GCC / Middle East, Europe, North America, Southeast Asia, and Africa).
We are reaching out to inquire in detail about:
1. The full EXTENT OF LOGISTICS SERVICES they provide (e.g. Ocean FCL & LCL, Air Cargo, Customs Clearance / CHA in India, Inland Transportation / CFS handling, Warehousing, Door-to-Door DDP/DAP vs Port-to-Port FOB/CIF, Cargo Marine Insurance).
2. The specific LOCATIONS AND DESTINATIONS THEY SUPPORT for sending our freight cargo (origin ports in India, supported destination discharge ports, inland delivery capabilities).
3. Container equipment availability (standard 20ft GP, 40ft GP / High Cube, special equipment), sailing frequencies, typical transit times, and ocean freight rate structure / tariff quote procedure.

CRITICAL INSTRUCTIONS FOR GMAIL-READY PLAIN TEXT:
1. SUBJECT LINE:
   - Provide a concise, professional Subject line referencing Freight Inquiry / Container Shipping RFQ for SinoMagan Indus Global Trade LLP. No quotes or markdown.
2. RECIPIENT EMAIL:
   - If an email is listed in Contact Email or context, provide it. Otherwise leave empty string.
3. EMAIL BODY (STRICT GMAIL PLAIN TEXT FORMAT):
   - The body MUST be 100% ready to paste directly into the Gmail composer.
   - ABSOLUTELY NO MARKDOWN FORMATTING:
     * NEVER use asterisks for bold or italic (NO **word** or *word*).
     * NEVER use markdown headings (# or ##).
     * NEVER use markdown horizontal rules (---).
     * NEVER use markdown links [text](url).
   - INQUIRY SPECIFICATIONS:
     * Request specific information on:
       • Extent of freight forwarding services (Ocean FCL/LCL, Air Freight, CHA Customs House Brokerage, CFS origin handling)
       • Supported origin ports in India (Nhava Sheva/JNPT, Mundra, Hazira, Chennai) and global destination discharge ports / trade lanes covered
       • 20ft and 40ft container availability and current ocean freight rates
       • Transit times, sailing schedules, and shipping line carriers used
       • Value-added services (cargo insurance, export documentation support, destination clearance)
     * Format these bullet points cleanly with '• '.
   - HUMAN TONE:
     * Sound like an authentic, seasoned commercial trade partner (Fardin Mohammed).
     * BANNED PHRASES: "I hope this email finds you well", "In today's fast-paced world", "Look no further", "delve", "testament to", "thrilled to connect".
     * Open directly by introducing SinoMagan Indus Global Trade LLP and stating our requirement for regular export freight handling.
   - COMMERCIAL & LOGISTICS REALISM:
     * Mention regular container volume movements, FCL/LCL requirements, prompt documentation, and interest in establishing an ongoing logistics agency relationship.
   - SIGN-OFF:
     The sign-off MUST strictly be formatted as:

Warm regards,

Fardin Mohammed
Partner
SinoMagan Indus Global Trade LLP
"""
                    response = generate_with_fallback(
                        prompt=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=EmailProposal,
                        ),
                        logger=self.logger
                    )
                    to_val, subj_val, body_val = parse_email_response(response.text, default_to=contact_emails)

                    def on_done():
                        if to_val:
                            entry_to.delete(0, "end")
                            entry_to.insert(0, to_val)
                        entry_subj.delete(0, "end")
                        entry_subj.insert(0, subj_val)
                        txt_body.delete("0.0", "end")
                        txt_body.insert("0.0", body_val)
                        btn_regen.configure(state="normal")
                    win.after(0, on_done)
                except Exception as e:
                    def on_err():
                        txt_body.delete("0.0", "end")
                        txt_body.insert("0.0", f"Error generating inquiry: {e}")
                        btn_regen.configure(state="normal")
                    win.after(0, on_err)

            threading.Thread(target=generate_worker, daemon=True).start()

        btn_regen = ctk.CTkButton(btn_bar, text="🔄 Regenerate", command=start_generation, width=120, fg_color="#3a3a3a", hover_color="#2b2b2b")
        btn_regen.pack(side="left", padx=5)

        btn_close = ctk.CTkButton(btn_bar, text="Close", command=win.destroy, width=90, fg_color="#555555", hover_color="#444444")
        btn_close.pack(side="right", padx=5)

        start_generation()

    def open_url_proposal_window(self, initial_url="", auto_generate=False, is_supplier=False, mode=None):
        if mode is None:
            mode = "supplier" if is_supplier else "buyer"

        win = ctk.CTkToplevel(self)
        if mode == "logistics":
            win.title("Instant Logistics & Freight RFQ Generator")
        elif mode == "supplier":
            win.title("Instant Supplier Sourcing Inquiry Generator")
        elif mode == "warehouse":
            win.title("Instant Warehouse & Garage Rental Inquiry Generator")
        else:
            win.title("Instant B2B Trade Proposal Generator")
        win.geometry("820x760")
        win.attributes("-topmost", True)
        win.focus_set()
        
        icon_path = resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            try:
                win.iconbitmap(icon_path)
            except Exception:
                pass

        # Top Header Banner
        header_frame = ctk.CTkFrame(win, fg_color="#1f232a", corner_radius=8)
        header_frame.pack(fill="x", padx=15, pady=(15, 8))

        if mode == "logistics":
            lbl_title_text = "🚢 Instant Freight Inquiry from Logistics Website"
            lbl_sub_text = "Enter logistics or freight forwarder website to analyze shipping routes, container services, and generate an official Freight Cargo RFQ from SinoMagan Indus Global Trade LLP."
            btn_gen_text = "⚡ Generate Freight RFQ"
            default_placeholder = "Your generated freight cargo inquiry will appear here..."
        elif mode == "warehouse":
            lbl_title_text = "🏢 Instant Warehouse / Garage Rental Inquiry"
            lbl_sub_text = "Enter real estate listing or warehouse portal URL (OLX, MagicBricks, 99acres, etc.) to analyze property specs and generate an official Commercial Rental / Lease Inquiry from SinoMagan Indus Global Trade LLP."
            btn_gen_text = "⚡ Generate Rental Inquiry"
            default_placeholder = "Your generated warehouse / garage rental inquiry will appear here..."
        elif mode == "supplier":
            lbl_title_text = "🏭 Instant Sourcing RFQ from Supplier Website"
            lbl_sub_text = "Enter supplier website to scrape manufacturing capabilities and generate an official Sourcing RFQ from SinoMagan Indus Global Trade LLP."
            btn_gen_text = "⚡ Generate Sourcing RFQ"
            default_placeholder = "Your generated sourcing inquiry will appear here..."
        else:
            lbl_title_text = "🌐 Instant B2B Proposal from Website URL"
            lbl_sub_text = "Enter any company website to scrape their products and generate a tailored proposal from SinoMagan Indus Global Trade LLP."
            btn_gen_text = "⚡ Generate Proposal"
            default_placeholder = "Your generated commercial proposal will appear here..."

        lbl_title = ctk.CTkLabel(
            header_frame, 
            text=lbl_title_text, 
            font=("Arial", 16, "bold"),
            text_color="#ffffff"
        )
        lbl_title.pack(anchor="w", padx=15, pady=(10, 2))

        lbl_sub = ctk.CTkLabel(
            header_frame, 
            text=lbl_sub_text, 
            font=("Arial", 11),
            text_color="#a0a0a0"
        )
        lbl_sub.pack(anchor="w", padx=15, pady=(0, 10))

        # URL Input Bar
        url_frame = ctk.CTkFrame(win, fg_color="transparent")
        url_frame.pack(fill="x", padx=15, pady=(0, 3))

        url_entry = ctk.CTkEntry(
            url_frame, 
            placeholder_text="Enter website URL (e.g. https://www.example.com)...", 
            font=("Arial", 12),
            height=36
        )
        url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if initial_url:
            url_entry.insert(0, initial_url)

        btn_generate = ctk.CTkButton(
            url_frame, 
            text=btn_gen_text, 
            width=175 if mode in ["supplier", "logistics", "warehouse"] else 160, 
            height=36,
            fg_color="#1f7a1f", 
            hover_color="#145214",
            font=("Arial", 12, "bold")
        )
        btn_generate.pack(side="right")

        # Status Label
        lbl_status = ctk.CTkLabel(win, text="Status: Ready. Paste a URL and click Generate.", text_color="#a0a0a0", font=("Arial", 11))
        lbl_status.pack(anchor="w", padx=18, pady=(0, 4))

        # To Row
        to_frame = ctk.CTkFrame(win, fg_color="transparent")
        to_frame.pack(fill="x", padx=15, pady=(3, 3))
        lbl_to = ctk.CTkLabel(to_frame, text="To:", width=65, anchor="w", font=("Arial", 12, "bold"))
        lbl_to.pack(side="left")
        entry_to = ctk.CTkEntry(to_frame, font=("Arial", 12), height=32)
        entry_to.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn_copy_to = ctk.CTkButton(to_frame, text="📋 Copy", width=75, height=32)
        btn_copy_to.pack(side="right")

        # Subject Row
        subj_frame = ctk.CTkFrame(win, fg_color="transparent")
        subj_frame.pack(fill="x", padx=15, pady=(3, 5))
        lbl_subj = ctk.CTkLabel(subj_frame, text="Subject:", width=65, anchor="w", font=("Arial", 12, "bold"))
        lbl_subj.pack(side="left")
        entry_subj = ctk.CTkEntry(subj_frame, font=("Arial", 12), height=32)
        entry_subj.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn_copy_subj = ctk.CTkButton(subj_frame, text="📋 Copy", width=75, height=32)
        btn_copy_subj.pack(side="right")

        # Body Header Row
        body_hdr = ctk.CTkFrame(win, fg_color="transparent")
        body_hdr.pack(fill="x", padx=15, pady=(4, 2))
        lbl_body = ctk.CTkLabel(body_hdr, text="Email Body (Gmail Ready):", font=("Arial", 12, "bold"))
        lbl_body.pack(side="left")
        btn_copy_body = ctk.CTkButton(body_hdr, text="📋 Copy Body", width=105, height=28, fg_color="#1f7a1f", hover_color="#145214")
        btn_copy_body.pack(side="right")

        # Body Textbox
        txt_body = ctk.CTkTextbox(win, wrap="word", font=("Arial", 12))
        txt_body.pack(fill="both", expand=True, padx=15, pady=(2, 8))
        txt_body.insert("0.0", default_placeholder)

        # Copy handlers
        def copy_widget_text(widget, btn, default_txt):
            if isinstance(widget, ctk.CTkTextbox):
                val = widget.get("0.0", "end").strip()
            else:
                val = widget.get().strip()
            placeholders = [
                default_placeholder, 
                "Your generated commercial proposal will appear here...",
                "Your generated sourcing inquiry will appear here...",
                "Your generated freight cargo inquiry will appear here...",
                "Your generated warehouse / garage rental inquiry will appear here..."
            ]
            if val and not val.startswith("⏳") and val not in placeholders:
                self.clipboard_clear()
                self.clipboard_append(val)
                btn.configure(text="Copied! ✅")
                win.after(1500, lambda: btn.configure(text=default_txt))

        btn_copy_to.configure(command=lambda: copy_widget_text(entry_to, btn_copy_to, "📋 Copy"))
        btn_copy_subj.configure(command=lambda: copy_widget_text(entry_subj, btn_copy_subj, "📋 Copy"))
        btn_copy_body.configure(command=lambda: copy_widget_text(txt_body, btn_copy_body, "📋 Copy Body"))

        # Bottom Action Bar
        btn_bar = ctk.CTkFrame(win, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(5, 12))

        def copy_all():
            s = entry_subj.get().strip()
            b = txt_body.get("0.0", "end").strip()
            placeholders = [
                default_placeholder, 
                "Your generated commercial proposal will appear here...",
                "Your generated sourcing inquiry will appear here...",
                "Your generated freight cargo inquiry will appear here...",
                "Your generated warehouse / garage rental inquiry will appear here..."
            ]
            if b and not b.startswith("⏳") and b not in placeholders:
                self.clipboard_clear()
                self.clipboard_append(f"Subject: {s}\n\n{b}")
                btn_copy_all.configure(text="All Copied! ✅")
                win.after(1500, lambda: btn_copy_all.configure(text="📋 Copy Subject + Body"))

        btn_copy_all = ctk.CTkButton(btn_bar, text="📋 Copy Subject + Body", command=copy_all, width=170, fg_color="#005b96", hover_color="#003f66")
        btn_copy_all.pack(side="left", padx=5)

        def clear_fields():
            url_entry.delete(0, "end")
            entry_to.delete(0, "end")
            entry_subj.delete(0, "end")
            txt_body.delete("0.0", "end")
            lbl_status.configure(text="Status: Ready.")

        btn_clear = ctk.CTkButton(btn_bar, text="Clear", command=clear_fields, width=80, fg_color="#3a3a3a", hover_color="#2b2b2b")
        btn_clear.pack(side="left", padx=5)

        btn_close = ctk.CTkButton(btn_bar, text="Close", command=win.destroy, width=80, fg_color="#555555", hover_color="#444444")
        btn_close.pack(side="right", padx=5)

        def start_url_generation():
            raw_url = url_entry.get().strip()
            if not raw_url:
                lbl_status.configure(text="Status: Please enter a valid website URL first.")
                return

            if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
                target_url = "https://" + raw_url
            else:
                target_url = raw_url

            btn_generate.configure(state="disabled")
            lbl_status.configure(text=f"Status: Scraping {target_url}...")
            entry_subj.delete(0, "end")
            entry_subj.insert(0, "Generating Subject line...")
            txt_body.delete("0.0", "end")
            if mode == "logistics":
                action_step = "shipping routes and freight services"
            elif mode == "warehouse":
                action_step = "warehouse facility specs and lease terms"
            elif mode == "supplier":
                action_step = "manufacturing capabilities"
            else:
                action_step = "product portfolio"
            txt_body.insert("0.0", f"⏳ Step 1: Scraping website content from {target_url}...\n⏳ Step 2: Analyzing {action_step} with Gemini AI...\n\nPlease wait a moment.")

            def worker():
                try:
                    import re
                    from scraper import scrape_url
                    scraped_text = scrape_url(target_url, self.logger)
                    
                    scraped_email = ""
                    if scraped_text:
                        found_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', scraped_text)
                        valid_emails = [e for e in found_emails if not any(e.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.css', '.js'])]
                        if valid_emails:
                            scraped_email = valid_emails[0]

                    def update_status_ai():
                        if mode == "logistics":
                            target_type = "freight inquiry"
                        elif mode == "warehouse":
                            target_type = "rental inquiry"
                        elif mode == "supplier":
                            target_type = "sourcing inquiry"
                        else:
                            target_type = "proposal"
                        lbl_status.configure(text=f"Status: Website scraped. Generating {target_type} with Gemini AI...")
                    win.after(0, update_status_ai)

                    from google.genai import types
                    from pydantic import BaseModel, Field
                    from llm_fallback import generate_with_fallback

                    class EmailProposal(BaseModel):
                        to_email: str = Field(default="", description="Recipient contact email if found in context, otherwise empty string")
                        subject: str = Field(description="Clean, compelling email subject line without any markdown or quotes")
                        body: str = Field(description="Full clean email body ready to paste directly into Gmail composer. Do NOT include markdown bold/italics (no asterisks). Use simple bullet points with • if listing technical specifications.")

                    if scraped_text and len(scraped_text.strip()) > 100:
                        content_block = f"Scraped Website Content of the Target Company:\n\"\"\"\n{scraped_text[:25000]}\n\"\"\""
                    else:
                        content_block = f"Note: Website text was minimal or protected. Tailor communication to the company domain/URL: {target_url}."

                    if mode == "logistics":
                        prompt = f"""You are Fardin Mohammed, Partner at SinoMagan Indus Global Trade LLP, writing an official B2B freight cargo RFQ & inquiry to a logistics company / freight forwarder.

Target Logistics Provider Website: {target_url}
Known Scraped Email: {scraped_email}

{content_block}

Your Company:
- SinoMagan Indus Global Trade LLP (International trade, export sourcing, contract manufacturing, containerized freight operations)
- Authorized Signatory: Fardin Mohammed, Partner

PURPOSE OF THIS EMAIL (FREIGHT CARGO & SERVICE EXTENT INQUIRY):
SinoMagan Indus Global Trade LLP regularly moves commercial export containerized freight (such as hydraulic actuators & speed regulating motors (Groschopp WK0920702 motor governors), photovoltaic solar panels (monocrystalline & TOPCon PV modules for solar energy systems), wooden panels (plywood, MDF, decorative laminated boards), integrated circuits (brand new original ICs, microcontrollers, RTCs), consolidated electronic components (displays, capacitors, illuminated rocker & power switches 6A-20A, battery holders, fan motors), remote control switches, power distribution equipment, numerical protection relays & substation automation, electrical control gear, circuit breakers, contactors, transformers, switchgear, centralized lighting control systems & dimming modules, solar panel scrap (PV module scrap for industrial recycling), cables, battery storage systems, HVAC equipment, and industrial hardware) from major Indian ports (e.g. Nhava Sheva / JNPT, Mundra, Chennai) to international destinations (including GCC / Middle East, Europe, North America, Southeast Asia, and Africa).
Based on the logistics services and trade lanes shown on their website, we are reaching out to inquire in detail about:
1. The full EXTENT OF LOGISTICS SERVICES they provide (e.g. Ocean FCL & LCL, Air Cargo, Customs Clearance / CHA in India, Inland Transportation / CFS handling, Warehousing, Door-to-Door DDP/DAP vs Port-to-Port FOB/CIF, Cargo Marine Insurance).
2. The specific LOCATIONS AND DESTINATIONS THEY SUPPORT for sending our freight cargo (origin ports in India, supported destination discharge ports, inland delivery capabilities).
3. Container equipment availability (standard 20ft GP, 40ft GP / High Cube, special equipment), sailing frequencies, typical transit times, and ocean freight rate structure / tariff quote procedure.

CRITICAL INSTRUCTIONS FOR GMAIL-READY PLAIN TEXT:
1. SUBJECT LINE:
   - Provide a concise, professional Subject line referencing Freight Inquiry / Container Shipping RFQ for SinoMagan Indus Global Trade LLP. No quotes or markdown.
2. RECIPIENT EMAIL:
   - If a contact email is found in the scraped content or Known Scraped Email, provide it. Otherwise leave empty string.
3. EMAIL BODY (STRICT GMAIL PLAIN TEXT FORMAT):
   - The body MUST be 100% ready to paste directly into the Gmail composer.
   - ABSOLUTELY NO MARKDOWN FORMATTING:
     * NEVER use asterisks for bold or italic (NO **word** or *word*).
     * NEVER use markdown headings (# or ##).
     * NEVER use markdown horizontal rules (---).
     * NEVER use markdown links [text](url).
   - INQUIRY SPECIFICATIONS:
     * Request specific information on:
       • Extent of freight forwarding services (Ocean FCL/LCL, Air Freight, CHA Customs House Brokerage, CFS origin handling)
       • Supported origin ports in India (Nhava Sheva/JNPT, Mundra, Hazira, Chennai) and global destination discharge ports / trade lanes covered
       • 20ft and 40ft container availability and current ocean freight rates
       • Transit times, sailing schedules, and shipping line carriers used
       • Value-added services (cargo insurance, export documentation support, destination clearance)
     * Format these bullet points cleanly with '• '.
   - HUMAN TONE:
     * Sound like an authentic, seasoned commercial trade partner (Fardin Mohammed).
     * BANNED PHRASES: "I hope this email finds you well", "In today's fast-paced world", "Look no further", "delve", "testament to", "thrilled to connect".
     * Open directly by introducing SinoMagan Indus Global Trade LLP and referencing their shipping solutions observed on their website.
   - COMMERCIAL & LOGISTICS REALISM:
     * Mention regular container volume movements, FCL/LCL requirements, prompt documentation, and interest in establishing an ongoing logistics agency relationship.
   - SIGN-OFF:
     The sign-off MUST strictly be formatted as:

Warm regards,

Fardin Mohammed
Partner
SinoMagan Indus Global Trade LLP
"""
                    elif mode == "warehouse":
                        prompt = f"""You are Fardin Mohammed, Partner at SinoMagan Indus Global Trade LLP, writing an official Commercial Lease / Rental Inquiry for a warehouse, godown, industrial shed, or garage storage space.

Target Property / Portal Listing URL: {target_url}
Known Scraped Email: {scraped_email}

{content_block}

Your Company:
- SinoMagan Indus Global Trade LLP (International trade, export sourcing, contract manufacturing, containerized freight operations)
- Authorized Signatory: Fardin Mohammed, Partner

PURPOSE OF THIS EMAIL (WAREHOUSE / GARAGE LEASE & RENTAL INQUIRY):
SinoMagan Indus Global Trade LLP is actively seeking suitable commercial premises for immediate/near-term lease to support our export-import staging, inventory warehousing (electrical components, power equipment, solar panels, wooden panels, hardware), and vehicle/garage storage needs in India.
Based on the property listing or real estate contact observed at their URL, we are reaching out to verify property availability, technical specifications, and commercial leasing terms.

CRITICAL INSTRUCTIONS FOR GMAIL-READY PLAIN TEXT:
1. SUBJECT LINE:
   - Provide a concise, highly professional Subject line referencing Commercial Warehouse / Godown / Garage Rental Inquiry for SinoMagan Indus Global Trade LLP. Include location if detected. No quotes or markdown.
2. RECIPIENT EMAIL:
   - If a contact email is found in the scraped content or Known Scraped Email, provide it. Otherwise leave empty string.
3. EMAIL BODY (STRICT GMAIL PLAIN TEXT FORMAT):
   - The body MUST be 100% ready to paste directly into the Gmail composer.
   - ABSOLUTELY NO MARKDOWN FORMATTING:
     * NEVER use asterisks for bold or italic (NO **word** or *word*).
     * NEVER use markdown headings (# or ##).
     * NEVER use markdown horizontal rules (---).
     * NEVER use markdown links [text](url).
   - INQUIRY SPECIFICATIONS:
     * Request specific confirmation regarding:
       • Total usable carpet area (sq ft) and open yard / vehicle parking area
       • Clear ceiling height (ft) and wide rolling shutter / ground-level dock access
       • Heavy-duty industrial flooring condition and 3-phase electric power load (HP/kVA)
       • Access road width and commercial container trailer (20ft / 40ft) turnaround capability
       • Monthly rent (per sq ft or lump sum), maintenance charges, security deposit, and minimum lease lock-in
       • Permitted commercial storage & garage operations, 24/7 access, and security / CCTV provisions
       • Fire safety NOC and local municipal industrial licensing status
     * Format these bullet points cleanly with '• '.
   - HUMAN TONE:
     * Sound like an authentic, decisive commercial principal (Fardin Mohammed).
     * BANNED PHRASES: "I hope this email finds you well", "In today's fast-paced world", "Look no further", "delve", "testament to", "thrilled to connect".
     * Open directly by introducing SinoMagan Indus Global Trade LLP and referencing the property listing seen online.
   - COMMERCIAL LEASING REALISM:
     * Mention readiness for prompt site inspection and immediate lease execution for qualified spaces.
   - SIGN-OFF:
     The sign-off MUST strictly be formatted as:

Warm regards,

Fardin Mohammed
Partner
SinoMagan Indus Global Trade LLP
"""
                    elif mode == "supplier":
                        prompt = f"""You are Fardin Mohammed, Partner at SinoMagan Indus Global Trade LLP, writing an official B2B Sourcing RFQ / vendor partnership inquiry to an industrial manufacturer / supplier.

Target Supplier Website: {target_url}
Known Scraped Email: {scraped_email}

{content_block}

Your Company:
- SinoMagan Indus Global Trade LLP (Global sourcing, contract manufacturing, export & logistics management across Automotive Components, Power Electronics, PCBs, Solar, and Industrial Equipment)
- Authorized Signatory: Fardin Mohammed, Partner

PURPOSE OF THIS EMAIL:
You represent active international commercial buyer and infrastructure project demands (across GCC/Middle East, Europe, North America) seeking reliable factory suppliers for ongoing export orders. You are reaching out to establish a direct B2B vendor partnership based on the products found on their website.

CRITICAL INSTRUCTIONS FOR GMAIL-READY PLAIN TEXT:
1. SUBJECT LINE:
   - Provide a concise, highly professional B2B inquiry Subject line referencing RFQ / Export Sourcing / Vendor Partnership tailored to their manufactured products. No quotes or markdown.
2. RECIPIENT EMAIL:
   - If a contact email is found in the scraped content or Known Scraped Email, provide it. Otherwise leave empty string.
3. EMAIL BODY (STRICT GMAIL PLAIN TEXT FORMAT):
   - The body MUST be 100% ready to paste directly into the Gmail composer.
   - ABSOLUTELY NO MARKDOWN FORMATTING:
     * NEVER use asterisks for bold or italic (NO **word** or *word*).
     * NEVER use markdown headings (# or ##).
     * NEVER use markdown horizontal rules (---).
     * NEVER use markdown links [text](url).
   - INQUIRY SPECIFICATIONS:
     * Reference specific products, components, or industrial equipment identified from their website.
     * Inquire regarding:
       • Product catalog and technical data sheets (TDS)
       • Export price list (FOB Indian port / CIF)
       • Minimum Order Quantities (MOQ) and production lead times
       • OEM / private-label custom branding options
       • Compliance certifications and quality test reports
       • Sample dispatch procedure for client inspection
     * Format these bullet points cleanly with '• '.
   - HUMAN TONE:
     * Sound like an authentic, seasoned B2B partner (Fardin Mohammed).
     * BANNED PHRASES: "I hope this email finds you well", "In today's fast-paced world", "Look no further", "delve", "testament to", "thrilled to connect".
     * Open directly by introducing SinoMagan Indus Global Trade LLP and highlighting specific interest in their manufacturing capabilities.
   - COMMERCIAL & LOGISTICS REALISM:
     * Mention full container load (FCL) export potential, regular monthly off-take, pre-shipment inspections, and standard international trade terms.
   - SIGN-OFF:
     The sign-off MUST strictly be formatted as:

Warm regards,

Fardin Mohammed
Partner
SinoMagan Indus Global Trade LLP
"""
                    else:
                        prompt = f"""You are Fardin Mohammed, Partner at SinoMagan Indus Global Trade LLP, writing a personalized, direct B2B commercial export proposal to a prospective client.

Target Client Website: {target_url}
Known Scraped Email: {scraped_email}

{content_block}

Your Company:
- SinoMagan Indus Global Trade LLP (Global sourcing, contract manufacturing, export & logistics management across Automotive Components, Power Electronics, PCBs, Solar, and Industrial Equipment)
- Authorized Signatory: Fardin Mohammed, Partner

CRITICAL INSTRUCTIONS FOR GMAIL-READY PLAIN TEXT:
1. SUBJECT LINE:
   - Provide a concise, highly relevant email Subject line tailored to their products or industry. No quotes or markdown.
2. RECIPIENT EMAIL:
   - If a contact email is found in the scraped content or Known Scraped Email, provide it. Otherwise leave empty string.
3. EMAIL BODY (STRICT GMAIL PLAIN TEXT FORMAT):
   - The body MUST be 100% ready to paste directly into the Gmail composer.
   - ABSOLUTELY NO MARKDOWN FORMATTING:
     * NEVER use asterisks for bold or italic (NO **word** or *word*).
     * NEVER use markdown headings (# or ##).
     * NEVER use markdown horizontal rules (---).
     * NEVER use markdown links [text](url).
   - TECHNICAL SPECIFICATIONS:
     * When listing technical parameters, components, certifications, or tolerances, format them using clean bullet points starting with '• ' (e.g. '• Technical Standard: ISO 9001, CE, RoHS', '• Production Tolerances: Precision Grade').
   - HUMAN TONE:
     * Sound like a real senior partner (Fardin Mohammed).
     * BANNED PHRASES: "I hope this email finds you well", "In today's fast-paced world", "Look no further", "delve", "testament to", "thrilled to connect".
     * Open directly by demonstrating genuine familiarity with their products, equipment, or components from their website.
   - COMMERCIAL & LOGISTICS REALISM:
     * Mention direct factory sourcing, container logistics (20ft/40ft FCL & LCL), Incoterms (FOB, CIF, CFR), sample dispatch for testing, and pre-shipment quality inspection.
   - SIGN-OFF:
     The sign-off MUST strictly be formatted as:

Warm regards,

Fardin Mohammed
Partner
SinoMagan Indus Global Trade LLP
"""
                    response = generate_with_fallback(
                        prompt=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=EmailProposal,
                        ),
                        logger=self.logger
                    )
                    to_val, subj_val, body_val = parse_email_response(response.text, default_to=scraped_email)

                    def on_done():
                        entry_to.delete(0, "end")
                        if to_val:
                            entry_to.insert(0, to_val)
                        entry_subj.delete(0, "end")
                        entry_subj.insert(0, subj_val)
                        txt_body.delete("0.0", "end")
                        txt_body.insert("0.0", body_val)
                        if mode == "logistics":
                            status_msg = "Status: Freight RFQ generated successfully! ✅"
                        elif mode == "warehouse":
                            status_msg = "Status: Rental Inquiry generated successfully! ✅"
                        elif mode == "supplier":
                            status_msg = "Status: Sourcing RFQ generated successfully! ✅"
                        else:
                            status_msg = "Status: Proposal generated successfully! ✅"
                        lbl_status.configure(text=status_msg)
                        btn_generate.configure(state="normal")
                    win.after(0, on_done)
                except Exception as e:
                    def on_err():
                        txt_body.delete("0.0", "end")
                        txt_body.insert("0.0", f"Error generating: {e}")
                        lbl_status.configure(text="Status: Error during generation.")
                        btn_generate.configure(state="normal")
                    win.after(0, on_err)

            threading.Thread(target=worker, daemon=True).start()

        btn_generate.configure(command=start_url_generation)
        url_entry.bind("<Return>", lambda event: start_url_generation())
        
        if initial_url and auto_generate:
            win.after(150, start_url_generation)

    def delete_all_entries(self, output_file, tree):
        import tkinter.messagebox as messagebox
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to completely delete {output_file}?\\nThis action cannot be undone."):
            if os.path.exists(output_file):
                os.remove(output_file)
                self.logger.info(f"Deleted {output_file}.")
            tree.delete(*tree.get_children())
            tree["columns"] = []
            self.ui_queue.put((self._append_log, (f"Cleared database {output_file}",)))

    def load_matrix(self, tree, output_file):
        if os.path.exists(output_file):
            try:
                df = pd.read_excel(output_file)
                tree.delete(*tree.get_children())
                
                has_action_col = (output_file in ["Buyers_Matrix.xlsx", "Suppliers_Matrix.xlsx", "Logistics_Matrix.xlsx", "Warehouses_Matrix.xlsx"])
                if output_file in ["Suppliers_Matrix.xlsx", "Logistics_Matrix.xlsx", "Warehouses_Matrix.xlsx"]:
                    action_col_name = "Inquiry"
                else:
                    action_col_name = "Proposal"
                cols = list(df.columns)
                if has_action_col:
                    cols = [action_col_name, "Copy URL"] + cols
                    
                tree["columns"] = cols
                for col in cols:
                    tree.heading(col, text=col, command=lambda _c=col: self.sort_tree_column(tree, _c, False))
                    if col in ["Proposal", "Inquiry"]:
                        tree.column(col, width=110, minwidth=90, anchor="center")
                    elif col == "Copy URL":
                        tree.column(col, width=95, minwidth=80, anchor="center")
                    elif col in ["Product Name", "product_name"]:
                        tree.column(col, width=190, minwidth=130)
                    elif col in ["Niche", "niche"]:
                        tree.column(col, width=175, minwidth=120)
                    elif col in ["Target Region", "target_region"]:
                        tree.column(col, width=125, minwidth=90)
                    elif col in ["Supplier Type", "supplier_type"]:
                        tree.column(col, width=130, minwidth=90, anchor="center")
                    elif col in ["Supplier Country", "supplier_country"]:
                        tree.column(col, width=110, minwidth=80, anchor="center")
                    elif col in ["HS Code", "hs_code"]:
                        tree.column(col, width=90, minwidth=70, anchor="center")
                    elif col in ["Key Specifications", "specifications"]:
                        tree.column(col, width=240, minwidth=150)
                    elif col in ["Export Potential", "export_potential"]:
                        tree.column(col, width=110, minwidth=85, anchor="center")
                    elif col in ["Indian Manufacturing Hubs", "indian_manufacturing_hubs"]:
                        tree.column(col, width=180, minwidth=120)
                    elif col in ["Foreign Competitors / Notes", "foreign_competitors_notes"]:
                        tree.column(col, width=190, minwidth=120)
                    elif col in ["Source Reference", "source_reference"]:
                        tree.column(col, width=140, minwidth=100)
                    elif col in ["Date Added", "date_added"]:
                        tree.column(col, width=95, minwidth=80, anchor="center")
                    elif col == "distance_km":
                        tree.column(col, width=110, minwidth=90, anchor="center")
                    elif col == "distance_from_area":
                        tree.column(col, width=140, minwidth=110, anchor="w")
                    elif col == "route_notes":
                        tree.column(col, width=180, minwidth=120, anchor="w")
                    else:
                        tree.column(col, width=150, minwidth=100)
                        
                for _, row in df.iterrows():
                    values = list(row)
                    if has_action_col:
                        values = ["📝 Create", "📋 Copy"] + values
                    tree.insert("", "end", values=values)
                    
                if output_file == "Warehouses_Matrix.xlsx":
                    self.init_warehouse_reference_area()
                self.logger.info(f"Successfully synced {output_file} with UI.")
            except Exception as e:
                self.logger.error(f"Failed to load matrix: {e}")
        else:
            self.logger.warning(f"No local matrix found to load: {output_file}")

    def sort_tree_column(self, tree, col, reverse):
        """
        Sorts the ttk.Treeview rows when clicking on a column header.
        Supports automatic numeric/currency/sqft detection, Indian lakh/crore units,
        case-insensitive string sorting, and toggles between ascending and descending order.
        Empty rows remain neatly at the bottom.
        """
        items = tree.get_children('')
        if not items:
            return

        cols = list(tree['columns'])
        try:
            col_idx = cols.index(col)
        except ValueError:
            return

        import re

        def is_empty_val(v):
            if v is None:
                return True
            s = str(v).strip().lower()
            return s in ["", "none", "nan", "null", "-", "n/a"]

        def parse_sort_val(v):
            s = str(v).strip()
            clean_s = re.sub(r'^[^\d+-]+', '', s)
            m = re.match(r'^[-+]?\d+(?:,\d+)*(?:\.\d+)?', clean_s)
            if m:
                num_str = m.group(0).replace(',', '')
                try:
                    val_num = float(num_str)
                    lower_s = s.lower()
                    if 'lakh' in lower_s or 'lac' in lower_s:
                        val_num *= 100000
                    elif 'crore' in lower_s or ' cr' in lower_s:
                        val_num *= 10000000
                    return (0, val_num)
                except ValueError:
                    pass
            return (1, s.lower())

        data = []
        for item_id in items:
            row_vals = tree.item(item_id, 'values')
            val = row_vals[col_idx] if col_idx < len(row_vals) else ""
            data.append((val, item_id))

        valid_items = [x for x in data if not is_empty_val(x[0])]
        empty_items = [x for x in data if is_empty_val(x[0])]

        valid_items.sort(key=lambda x: parse_sort_val(x[0]), reverse=reverse)
        sorted_data = valid_items + empty_items

        for index, (_, item_id) in enumerate(sorted_data):
            tree.move(item_id, '', index)

        arrow = " ▼" if reverse else " ▲"
        for c in cols:
            clean_c = c.replace(" ▲", "").replace(" ▼", "")
            if c == col:
                tree.heading(c, text=clean_c + arrow, command=lambda _c=c: self.sort_tree_column(tree, _c, not reverse))
            else:
                tree.heading(c, text=clean_c, command=lambda _c=c: self.sort_tree_column(tree, _c, False))
            
    def clean_local_matrix(self, output_file, tree):
        stats = clean_matrix(output_file, self.logger)
        self.load_matrix(tree, output_file)
        
        import tkinter.messagebox as messagebox
        if stats and stats.get("removed_count", 0) > 0:
            msg = (
                f"Successfully cleaned and deduplicated {output_file}!\n\n"
                f"• Removed {stats['removed_count']} invalid/duplicate entries.\n"
                f"• Retained {stats['remaining_count']} unique leads."
            )
            messagebox.showinfo("Matrix Cleaned & Deduplicated", msg)
        else:
            msg = (
                f"{output_file} is already completely clean and deduplicated!\n"
                f"All entries are unique and valid."
            )
            messagebox.showinfo("Matrix Clean", msg)

    # =========================================================================
    # PRODUCT SOURCING TAB IMPLEMENTATION
    # =========================================================================

    def setup_prod_sourcing_tab(self):
        """Sets up the Product Sourcing tab with region selector, foreign suppliers toggle, niche filter, interactive niche grid, and product matrix."""
        import tkinter as tk
        from tkinter import ttk
        import tkinter.messagebox as messagebox

        self.tab_prod_sourcing.grid_columnconfigure(0, weight=1)
        self.tab_prod_sourcing.grid_rowconfigure(0, weight=0)
        self.tab_prod_sourcing.grid_rowconfigure(1, weight=0)
        self.tab_prod_sourcing.grid_rowconfigure(2, weight=0)
        self.tab_prod_sourcing.grid_rowconfigure(3, weight=1)

        # 1. Top Control / Search Bar (Row 0)
        search_frame = ctk.CTkFrame(self.tab_prod_sourcing)
        search_frame.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")

        lbl_region = ctk.CTkLabel(search_frame, text="🌍 Target Region (Supply from India):", font=("Arial", 12, "bold"))
        lbl_region.pack(side="left", padx=(10, 4), pady=7)

        self.prod_region_var = ctk.StringVar(value="Worldwide (wt-wt)")
        self.prod_region_dropdown = ctk.CTkOptionMenu(
            search_frame, 
            values=self.country_regions, 
            variable=self.prod_region_var, 
            width=140
        )
        self.prod_region_dropdown.pack(side="left", padx=4, pady=7)

        self.prod_foreign_sup_var = ctk.BooleanVar(value=False)
        self.prod_foreign_sup_check = ctk.CTkCheckBox(
            search_frame, 
            text="Foreign Suppliers", 
            variable=self.prod_foreign_sup_var,
            font=("Arial", 11, "bold"),
            fg_color="#005b96",
            hover_color="#003f66"
        )
        self.prod_foreign_sup_check.pack(side="left", padx=(10, 10), pady=7)

        lbl_niche = ctk.CTkLabel(search_frame, text="📦 Niche:", font=("Arial", 12, "bold"))
        lbl_niche.pack(side="left", padx=(6, 4), pady=7)

        self.industrial_niches_list = ["All Niches"] + [m["key"] for m in NICHES_METADATA]
        self.prod_niche_var = ctk.StringVar(value="All Niches")
        self.prod_niche_dropdown = ctk.CTkOptionMenu(
            search_frame, 
            values=self.industrial_niches_list, 
            variable=self.prod_niche_var, 
            command=self.on_niche_filter_changed,
            width=210
        )
        self.prod_niche_dropdown.pack(side="left", padx=4, pady=7)

        self.prod_keyword_entry = ctk.CTkEntry(
            search_frame, 
            placeholder_text="Keyword / Specific Product...", 
            width=165
        )
        self.prod_keyword_entry.pack(side="left", padx=4, pady=7)
        self.prod_keyword_entry.bind("<Return>", lambda event: self.start_product_sourcing_search())

        self.btn_prod_search = ctk.CTkButton(
            search_frame, 
            text="✨ Find Products (AI)", 
            command=self.start_product_sourcing_search,
            width=150,
            fg_color="#1f7a1f",
            hover_color="#145214",
            font=("Arial", 12, "bold")
        )
        self.btn_prod_search.pack(side="left", padx=(6, 10), pady=7)

        self.lbl_prod_status = ctk.CTkLabel(
            search_frame, 
            text="", 
            font=("Arial", 11, "italic"),
            text_color="#2ecc71"
        )
        self.lbl_prod_status.pack(side="left", padx=4, pady=7)

        # 2. CURRENT SELECTED NICHES GRID SECTION (Row 1)
        self.niche_grid_visible = True
        self.niche_grid_container = ctk.CTkFrame(self.tab_prod_sourcing, fg_color="#181b20", corner_radius=8, border_width=1, border_color="#282e36")
        self.niche_grid_container.grid(row=1, column=0, padx=10, pady=(2, 6), sticky="ew")

        # Grid Section Header Bar
        grid_hdr = ctk.CTkFrame(self.niche_grid_container, fg_color="transparent")
        grid_hdr.pack(fill="x", padx=10, pady=(6, 4))

        lbl_grid_title = ctk.CTkLabel(
            grid_hdr, 
            text="🏷️ Current Selected Niches & Trade Portfolio (What We Have For Now):", 
            font=("Arial", 12, "bold"), 
            text_color="#ffffff"
        )
        lbl_grid_title.pack(side="left")

        self.lbl_niche_summary = ctk.CTkLabel(
            grid_hdr, 
            text="13 Industrial Niches | Loading Matrix...", 
            font=("Arial", 11, "italic"), 
            text_color="#58a6ff"
        )
        self.lbl_niche_summary.pack(side="left", padx=(12, 10))

        btn_show_all_niches = ctk.CTkButton(
            grid_hdr, 
            text="🌟 Show All Niches", 
            command=lambda: self.on_niche_filter_changed("All Niches"), 
            width=120, 
            height=24, 
            fg_color="#005b96", 
            hover_color="#003f66",
            font=("Arial", 11, "bold")
        )
        btn_show_all_niches.pack(side="right", padx=(6, 0))

        self.btn_toggle_grid = ctk.CTkButton(
            grid_hdr, 
            text="👁️ Hide Grid", 
            command=self.toggle_niche_grid, 
            width=90, 
            height=24, 
            fg_color="#3a3a3a", 
            hover_color="#2b2b2b",
            font=("Arial", 11)
        )
        self.btn_toggle_grid.pack(side="right", padx=4)

        # Grid of Niche Cards (5 columns x 3 rows = 15 tiles)
        self.niche_cards_frame = ctk.CTkFrame(self.niche_grid_container, fg_color="transparent")
        self.niche_cards_frame.pack(fill="x", padx=8, pady=(2, 8))
        for col_idx in range(5):
            self.niche_cards_frame.grid_columnconfigure(col_idx, weight=1, uniform="niche_col")

        self.niche_cards = {}
        self.build_niche_cards_grid()

        # 3. Action Buttons Bar (Row 2)
        btn_bar = ctk.CTkFrame(self.tab_prod_sourcing, fg_color="transparent")
        btn_bar.grid(row=2, column=0, padx=10, pady=(2, 6), sticky="w")

        btn_sync = ctk.CTkButton(
            btn_bar, 
            text="🔄 Sync Matrix", 
            command=lambda: self.load_products_matrix(self.prod_niche_var.get()), 
            width=110
        )
        btn_sync.pack(side="left", padx=(0, 6))

        btn_add = ctk.CTkButton(
            btn_bar, 
            text="➕ Add Custom Product", 
            command=self.open_add_product_window, 
            width=150, 
            fg_color="#1f7a1f", 
            hover_color="#145214"
        )
        btn_add.pack(side="left", padx=(0, 6))

        btn_copy = ctk.CTkButton(
            btn_bar, 
            text="📋 Copy Details", 
            command=self.copy_selected_product_details, 
            width=110, 
            fg_color="#3a3a3a", 
            hover_color="#2b2b2b"
        )
        btn_copy.pack(side="left", padx=(0, 6))

        btn_source = ctk.CTkButton(
            btn_bar, 
            text="🔍 Source in URL Discovery", 
            command=self.source_selected_product_in_discovery, 
            width=175, 
            fg_color="#005b96", 
            hover_color="#003f66"
        )
        btn_source.pack(side="left", padx=(0, 6))

        btn_open_excel = ctk.CTkButton(
            btn_bar, 
            text="📂 Open Excel", 
            command=lambda: self.open_excel_file("Products_Matrix.xlsx"), 
            width=100, 
            fg_color="#2d572c", 
            hover_color="#1f3d1e"
        )
        btn_open_excel.pack(side="left", padx=(0, 6))

        btn_sort_niches = ctk.CTkButton(
            btn_bar, 
            text="🏷️ Sort Products to Niches", 
            command=self.sort_unassigned_products_to_niches, 
            width=180, 
            fg_color="#b35900", 
            hover_color="#804000",
            font=("Arial", 11, "bold")
        )
        btn_sort_niches.pack(side="left", padx=(0, 6))

        btn_clean = ctk.CTkButton(
            btn_bar, 
            text="🧹 Clean Matrix", 
            command=lambda: self.clean_local_matrix("Products_Matrix.xlsx", self.prod_tree), 
            width=100, 
            fg_color="#b30000", 
            hover_color="#800000"
        )
        btn_clean.pack(side="left", padx=(0, 6))

        btn_delete_all = ctk.CTkButton(
            btn_bar, 
            text="🗑️ Delete All", 
            command=lambda: self.delete_all_entries("Products_Matrix.xlsx", self.prod_tree), 
            width=100, 
            fg_color="#660000", 
            hover_color="#4d0000"
        )
        btn_delete_all.pack(side="left", padx=6)

        # 4. Interactive Treeview Frame (Row 3)
        tree_frame = ctk.CTkFrame(self.tab_prod_sourcing)
        tree_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.map('Treeview', background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#343638')])

        self.prod_tree = ttk.Treeview(tree_frame, show='headings')
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.prod_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.prod_tree.xview)
        self.prod_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.prod_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        # Double click to inspect or source product
        def on_prod_double_click(event):
            sel = self.prod_tree.selection()
            if sel:
                self.copy_selected_product_details()
        self.prod_tree.bind("<Double-1>", on_prod_double_click)

        # Right click context menu
        prod_menu = tk.Menu(self.tab_prod_sourcing, tearoff=0)
        prod_menu.add_command(label="📋 Copy Product Details", command=self.copy_selected_product_details)
        prod_menu.add_command(label="🔍 Source Suppliers in URL Discovery", command=self.source_selected_product_in_discovery)
        prod_menu.add_separator()
        prod_menu.add_command(label="📂 Open Products_Matrix.xlsx", command=lambda: self.open_excel_file("Products_Matrix.xlsx"))

        def on_prod_right_click(event):
            item = self.prod_tree.identify_row(event.y)
            if item:
                self.prod_tree.selection_set(item)
                try:
                    prod_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    prod_menu.grab_release()

        self.prod_tree.bind("<Button-3>", on_prod_right_click)

        # 5. Initialize and load Products_Matrix.xlsx
        self.ensure_products_matrix_exists()
        self.load_products_matrix(self.prod_niche_var.get())

    def toggle_niche_grid(self):
        """Toggles the visibility of the Niches Grid section to maximize datatable space when desired."""
        if self.niche_grid_visible:
            self.niche_cards_frame.pack_forget()
            self.btn_toggle_grid.configure(text="👁️ Show Grid")
            self.niche_grid_visible = False
        else:
            self.niche_cards_frame.pack(fill="x", padx=8, pady=(2, 8))
            self.btn_toggle_grid.configure(text="👁️ Hide Grid")
            self.niche_grid_visible = True

    def build_niche_cards_grid(self):
        """Constructs the interactive 5-column grid of niche cards displaying current portfolio status."""
        # Tile 0: All Niches Card (Row 0, Col 0)
        self.create_niche_card(
            grid_row=0, grid_col=0,
            niche_key="All Niches",
            icon="🌟",
            title="All Niches",
            subtext="Complete Export Catalog Portfolio",
            hubs="Nationwide Indian Hubs"
        )

        # Tiles 1 to 14 (Niches 1 to 13 + Miscellaneous Niche)
        for idx, item in enumerate(NICHES_METADATA):
            slot = idx + 1
            r = slot // 5
            c = slot % 5
            self.create_niche_card(
                grid_row=r, grid_col=c,
                niche_key=item["key"],
                icon=item["icon"],
                title=item["title"],
                subtext=item["subproducts"],
                hubs=item["hubs"]
            )

    def create_niche_card(self, grid_row, grid_col, niche_key, icon, title, subtext, hubs):
        """Creates an individual interactive niche card in the grid with click filtering and dynamic counts."""
        card = ctk.CTkFrame(
            self.niche_cards_frame, 
            fg_color="#22272e", 
            corner_radius=6, 
            border_width=1, 
            border_color="#30363d", 
            height=54
        )
        card.grid(row=grid_row, column=grid_col, padx=3, pady=3, sticky="nsew")

        top_f = ctk.CTkFrame(card, fg_color="transparent")
        top_f.pack(fill="x", padx=6, pady=(3, 1))

        lbl_title = ctk.CTkLabel(
            top_f, 
            text=f"{icon} {title}", 
            font=("Arial", 11, "bold"), 
            text_color="#e6edf3", 
            anchor="w"
        )
        lbl_title.pack(side="left", fill="x", expand=True)

        lbl_count = ctk.CTkLabel(
            top_f, 
            text="(0)", 
            font=("Arial", 10, "bold"), 
            text_color="#3498db"
        )
        lbl_count.pack(side="right", padx=(4, 0))

        lbl_sub = ctk.CTkLabel(
            card, 
            text=subtext, 
            font=("Arial", 9), 
            text_color="#8b949e", 
            anchor="w"
        )
        lbl_sub.pack(fill="x", padx=6, pady=(0, 3))

        # Click interaction: clicking anywhere on the card or labels selects that niche
        def on_click(event=None):
            self.on_niche_filter_changed(niche_key)

        card.bind("<Button-1>", on_click)
        top_f.bind("<Button-1>", on_click)
        lbl_title.bind("<Button-1>", on_click)
        lbl_count.bind("<Button-1>", on_click)
        lbl_sub.bind("<Button-1>", on_click)

        # Store widgets for dynamic updates
        self.niche_cards[niche_key] = {
            "card": card,
            "lbl_title": lbl_title,
            "lbl_count": lbl_count,
            "lbl_sub": lbl_sub,
            "icon": icon,
            "title": title
        }

    def on_niche_filter_changed(self, choice):
        """Called when a niche is selected via the dropdown or by clicking a niche card in the grid."""
        if hasattr(self, 'prod_niche_var') and self.prod_niche_var.get() != choice:
            self.prod_niche_var.set(choice)

        # Highlight active card in grid
        self.highlight_active_niche_card(choice)

        # Filter the treeview table
        self.load_products_matrix(niche_filter=choice)

    def highlight_active_niche_card(self, active_choice):
        """Updates the visual border and background highlight on the selected niche card in the grid."""
        for key, w in self.niche_cards.items():
            card = w["card"]
            lbl_count = w["lbl_count"]
            cur_txt = lbl_count.cget("text").replace("✓ ", "")
            if key == active_choice:
                card.configure(border_color="#00d26a", border_width=2, fg_color="#162a3d")
                lbl_count.configure(text_color="#00e676", text=f"✓ {cur_txt}")
            else:
                card.configure(border_color="#30363d", border_width=1, fg_color="#22272e")
                lbl_count.configure(text_color="#3498db", text=cur_txt)

    def load_products_matrix(self, niche_filter=None):
        """Loads and filters Products_Matrix.xlsx into the treeview and updates niche grid product counts."""
        matrix_file = "Products_Matrix.xlsx"
        if not os.path.exists(matrix_file):
            return

        try:
            import pandas as pd
            df = pd.read_excel(matrix_file)

            # Apply niche filter if selected
            if niche_filter and niche_filter not in ["All Niches", "All 13 Niches"]:
                niche_num = niche_filter.split(":")[0].strip()
                df_filtered = df[df['Niche'].astype(str).str.contains(niche_num, case=False, na=False)]
            else:
                df_filtered = df

            self.prod_tree.delete(*self.prod_tree.get_children())
            cols = list(df.columns)
            self.prod_tree["columns"] = cols

            for col in cols:
                self.prod_tree.heading(col, text=col, command=lambda _c=col: self.sort_tree_column(self.prod_tree, _c, False))
                if col in ["Product Name", "product_name"]:
                    self.prod_tree.column(col, width=190, minwidth=130)
                elif col in ["Niche", "niche"]:
                    self.prod_tree.column(col, width=175, minwidth=120)
                elif col in ["Target Region", "target_region"]:
                    self.prod_tree.column(col, width=125, minwidth=90)
                elif col in ["Supplier Type", "supplier_type"]:
                    self.prod_tree.column(col, width=130, minwidth=90, anchor="center")
                elif col in ["Supplier Country", "supplier_country"]:
                    self.prod_tree.column(col, width=110, minwidth=80, anchor="center")
                elif col in ["HS Code", "hs_code"]:
                    self.prod_tree.column(col, width=90, minwidth=70, anchor="center")
                elif col in ["Key Specifications", "specifications"]:
                    self.prod_tree.column(col, width=240, minwidth=150)
                elif col in ["Export Potential", "export_potential"]:
                    self.prod_tree.column(col, width=110, minwidth=85, anchor="center")
                elif col in ["Indian Manufacturing Hubs", "indian_manufacturing_hubs"]:
                    self.prod_tree.column(col, width=180, minwidth=120)
                elif col in ["Foreign Competitors / Notes", "foreign_competitors_notes"]:
                    self.prod_tree.column(col, width=190, minwidth=120)
                elif col in ["Source Reference", "source_reference"]:
                    self.prod_tree.column(col, width=140, minwidth=100)
                elif col in ["Date Added", "date_added"]:
                    self.prod_tree.column(col, width=95, minwidth=80, anchor="center")
                else:
                    self.prod_tree.column(col, width=150, minwidth=100)

            for _, row in df_filtered.iterrows():
                self.prod_tree.insert("", "end", values=list(row))

            # Update counts on all niche grid cards
            self.update_niche_grid_counts(df, niche_filter or "All Niches")

            if hasattr(self, 'lbl_prod_status'):
                if niche_filter and niche_filter not in ["All Niches", "All 13 Niches"]:
                    self.lbl_prod_status.configure(
                        text=f"Showing {len(df_filtered)} products for {niche_filter.split(':')[0]} (Total: {len(df)})",
                        text_color="#3498db"
                    )
                else:
                    self.lbl_prod_status.configure(
                        text=f"Showing all {len(df_filtered)} products across all niches",
                        text_color="#2ecc71"
                    )

        except Exception as e:
            self.logger.error(f"Failed to load products matrix: {e}")

    def update_niche_grid_counts(self, df, active_filter):
        """Refreshes product count badges across all cards in the Niches Grid section."""
        total_products = len(df)
        counts_by_niche = df['Niche'].astype(str).value_counts().to_dict()

        # Update Tile 0: All Niches
        for all_key in ["All Niches", "All 13 Niches"]:
            if all_key in self.niche_cards:
                w = self.niche_cards[all_key]
                is_active = (active_filter in ["All Niches", "All 13 Niches"])
                prefix = "✓ " if is_active else ""
                w["lbl_count"].configure(
                    text=f"{prefix}({total_products})",
                    text_color="#00e676" if is_active else "#3498db"
                )

        # Update Tiles 1 to 14
        for item in NICHES_METADATA:
            key = item["key"]
            if key in self.niche_cards:
                w = self.niche_cards[key]
                niche_num = key.split(":")[0].strip()
                # Find matching count
                c_val = 0
                for n_name, c in counts_by_niche.items():
                    n_lower = n_name.lower().strip()
                    if key == "Miscellaneous Niche":
                        if "miscellaneous" in n_lower or "unassigned" in n_lower or not n_lower or n_lower in ["nan", "none", "unknown"]:
                            c_val += c
                    else:
                        if niche_num.lower() in n_lower:
                            c_val += c
                is_active = (active_filter == key)
                prefix = "✓ " if is_active else ""
                w["lbl_count"].configure(
                    text=f"{prefix}({c_val})",
                    text_color="#00e676" if is_active else "#3498db"
                )

        # Update Summary Label
        if hasattr(self, 'lbl_niche_summary'):
            clean_active = active_filter.split(":")[0].strip() if ":" in active_filter else active_filter
            self.lbl_niche_summary.configure(
                text=f"14 Niches | {total_products} Products Stored | Active: {clean_active}",
                text_color="#58a6ff"
            )

    def ensure_products_matrix_exists(self):
        """Ensures Products_Matrix.xlsx exists and is pre-seeded with all 13 industrial niches."""
        matrix_file = "Products_Matrix.xlsx"
        if not os.path.exists(matrix_file):
            try:
                import pandas as pd
                from datetime import datetime
                today_str = datetime.now().strftime("%Y-%m-%d")
                baseline_data = [
                    # Niche 1
                    {"Product Name": "Illuminated Big Rocker Power Switches (16A/20A, CQC/CE/RoHS)", "Niche": "Niche 1: Electrical & Electronic Components", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "853650", "Key Specifications": "Round and rectangular rocker power switches, 16A/20A 250VAC, illuminated red/green buttons, snap-in panel mount, CQC/TUV/CE/RoHS certified", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Gujarat, Maharashtra, Bangalore", "Foreign Competitors / Notes": "Competes with Chinese manufacturers; Indian manufacturers offer high endurance rating (50k cycles) and RoHS compliance", "Source Reference": "EEPC India / Industrial Electrical Catalog", "Date Added": today_str},
                    {"Product Name": "Brass Cable Glands & Compression Terminal Lugs", "Niche": "Niche 1: Electrical & Electronic Components", "Target Region": "UAE & Middle East", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "853690", "Key Specifications": "Metric (M20-M75) & PG threads, nickel plated brass, IP68 ingress protection, weatherproof sealing for armored XLPE industrial cables", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Jamnagar (Gujarat), Mumbai", "Foreign Competitors / Notes": "Jamnagar brass hub is globally price-competitive with Turkey and Germany; high GCC export volume", "Source Reference": "Jamnagar Brass Association / DGFT Export Matrix", "Date Added": today_str},
                    {"Product Name": "Real-Time Clock IC Modules (Epson RA-8565SA Compatible)", "Niche": "Niche 1: Electrical & Electronic Components", "Target Region": "Worldwide", "Supplier Type": "Foreign Supplier", "Supplier Country": "Japan / Taiwan", "HS Code": "854200", "Key Specifications": "I2C-bus interface RTC, 32.768 kHz built-in crystal unit, ultra-low current consumption (0.45 uA), SOP-14 package", "Export Potential": "High (Sourcing)", "Indian Manufacturing Hubs": "Bangalore / Hyderabad (Distribution & PCB Assembly)", "Foreign Competitors / Notes": "Key foreign component for Indian PCBA exports; sourced via authorized semiconductor channels", "Source Reference": "Semiconductor Component Directory", "Date Added": today_str},
                    # Niche 2
                    {"Product Name": "Armored Low/Medium Voltage XLPE Power Cables (1.1kV - 33kV)", "Niche": "Niche 2: Wires & Cables", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "854449", "Key Specifications": "Stranded electrolytic copper / aluminum conductors, cross-linked polyethylene (XLPE) insulation, galvanized steel strip armoring, flame retardant PVC sheath", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Gujarat, Silvassa, Maharashtra", "Foreign Competitors / Notes": "India is a major global exporter of copper & aluminum power cables; competes with Turkey and UAE mills", "Source Reference": "IEEMA / Indian Cable Manufacturers Association", "Date Added": today_str},
                    {"Product Name": "Submersible 3-Core Flat Copper Pump Cables", "Niche": "Niche 2: Wires & Cables", "Target Region": "USA & North America", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "854411", "Key Specifications": "99.97% pure bright annealed copper conductors, flexible water-resistant PVC/rubber insulation, high abrasion resistance for deep-well submersible pumps", "Export Potential": "High", "Indian Manufacturing Hubs": "Coimbatore (Tamil Nadu), Gujarat", "Foreign Competitors / Notes": "High agricultural and industrial borehole pump replacement market in North America and Australia", "Source Reference": "Coimbatore Pump & Cable Cluster", "Date Added": today_str},
                    # Niche 3
                    {"Product Name": "Numerical Protection Relays & Feeder Management Relays", "Niche": "Niche 3: Power Distribution & Protection Relays", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "853649", "Key Specifications": "Microprocessor-based multi-function overcurrent, earth fault, arc-flash detection (SEL-751 compatible), IEC 61850 substation communication", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Vadodara (Gujarat), Bangalore, Nashik", "Foreign Competitors / Notes": "Schweitzer (USA), Siemens (Germany), ABB (Switzerland); Indian switchgear OEMs offer highly cost-effective CRP integration", "Source Reference": "Vadodara Power Equipment Hub", "Date Added": today_str},
                    {"Product Name": "Substation Control and Relay Panels (CRP) 11kV - 132kV", "Niche": "Niche 3: Power Distribution & Protection Relays", "Target Region": "Saudi Arabia & GCC", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "853710", "Key Specifications": "Simplex / Duplex control and relay panels, wired with numerical relays, mimic diagrams, test blocks, and annunciators for power transmission substations", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Gujarat, Maharashtra, Chennai", "Foreign Competitors / Notes": "High demand in Middle Eastern grid expansions; Indian panel builders have SEC / DEWA pre-qualifications", "Source Reference": "Central Power Research Institute (CPRI) Certified", "Date Added": today_str},
                    # Niche 4
                    {"Product Name": "Hydraulic Actuators & Speed Regulating Motors (Groschopp Compatible)", "Niche": "Niche 4: HVAC, Fans, Pumps & Actuators", "Target Region": "Germany & Europe", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "850110", "Key Specifications": "Fractional horsepower PMDC / brushless motor governors, precision speed control, heavy duty die-cast aluminum housing, WK0920702 equivalent", "Export Potential": "High", "Indian Manufacturing Hubs": "Pune, Coimbatore, Bangalore", "Foreign Competitors / Notes": "Groschopp (Germany), Maxon (Switzerland); Indian precision motor manufacturers provide 35% lower BOM cost", "Source Reference": "Precision Actuator Trade Analysis", "Date Added": today_str},
                    {"Product Name": "Stainless Steel Submersible Multistage Borehole Pumps", "Niche": "Niche 4: HVAC, Fans, Pumps & Actuators", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "841370", "Key Specifications": "SS 304/316 impellers and diffusers, 50Hz/60Hz rewound motors, discharge heads up to 450m, capacity up to 120 m3/h", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Coimbatore (Tamil Nadu), Ahmedabad", "Foreign Competitors / Notes": "Competes directly with Italian (Grundfos/DAB) and Chinese pump manufacturers; Coimbatore hub is world-renowned", "Source Reference": "Coimbatore District Small Industries Association", "Date Added": today_str},
                    # Niche 5
                    {"Product Name": "Monocrystalline TOPCon Bifacial Solar PV Modules (550W - 700W)", "Niche": "Niche 5: Batteries, Solar Energy & Renewable Scrap", "Target Region": "USA & North America", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "854143", "Key Specifications": "N-Type TOPCon cells, 16BB, dual-glass bifacial (up to 80% bifaciality), 22.5%+ module efficiency, Tier-1 ALMM / IEC / UL certified", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Gujarat (Mundra, Surat), Bangalore, Noida", "Foreign Competitors / Notes": "Indian solar modules enjoy strong demand in US due to AD/CVD and UFLPA restrictions on Chinese solar panels", "Source Reference": "National Solar Energy Federation of India (NSEFI)", "Date Added": today_str},
                    {"Product Name": "Decommissioned Solar PV Module Scrap (500 MT Container Lots)", "Niche": "Niche 5: Batteries, Solar Energy & Renewable Scrap", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "854800", "Key Specifications": "Decommissioned silicon solar panels, sorted by cell type, baled / palletized for secondary silicon, silver, and copper recycling", "Export Potential": "High", "Indian Manufacturing Hubs": "Nhava Sheva, Mundra, Kandla port regions", "Foreign Competitors / Notes": "Global circular economy recycling demand in Europe, Japan, and Southeast Asia", "Source Reference": "Renewable Material Recovery Network", "Date Added": today_str},
                    {"Product Name": "LiFePO4 Energy Storage Battery Packs (48V / 100Ah - 200Ah)", "Niche": "Niche 5: Batteries, Solar Energy & Renewable Scrap", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "850760", "Key Specifications": "Prismatic LiFePO4 cells, 6000+ deep cycles, integrated smart BMS with RS485/CAN communication, telecom and residential solar ESS", "Export Potential": "High", "Indian Manufacturing Hubs": "Pune, Bangalore, Manesar", "Foreign Competitors / Notes": "China (CATL, BYD); Indian battery pack assemblers offer local customization, BIS, and export warranties", "Source Reference": "India Energy Storage Alliance (IESA)", "Date Added": today_str},
                    # Niche 6
                    {"Product Name": "Silent Containerized Diesel Generator Sets (25kVA - 500kVA)", "Niche": "Niche 6: Industrial Generators", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "850211", "Key Specifications": "Heavy duty 4-stroke diesel engine (Cummins/Kirloskar), acoustic weatherproof soundproof enclosure (<75 dBA at 1m), digital auto-mains failure (AMF) controller", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Pune, Kolhapur, Faridabad", "Foreign Competitors / Notes": "Perkins (UK), Caterpillar (USA); India is a major exporter of diesel power gensets across Africa, Middle East, and APAC", "Source Reference": "Indian Diesel Engine Manufacturers", "Date Added": today_str},
                    # Niche 7
                    {"Product Name": "Centralized Smart Streetlight Monitoring & Dimming Systems", "Niche": "Niche 7: LED Lighting & Lighting Controls", "Target Region": "United Kingdom & Europe", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "853710", "Key Specifications": "LoRaWAN / GSM wireless telemetry, DALI & 0-10V automated dimming controllers, astronomical timer, cloud SCADA energy monitoring", "Export Potential": "High", "Indian Manufacturing Hubs": "Delhi NCR, Bangalore, Pune", "Foreign Competitors / Notes": "Signify (Netherlands), Telensa (UK); Indian smart city lighting controllers offer open protocols and lower software license fees", "Source Reference": "Smart Lighting Export Consortium", "Date Added": today_str},
                    {"Product Name": "Industrial High-Bay LED Luminaires & Floodlights (100W - 400W)", "Niche": "Niche 7: LED Lighting & Lighting Controls", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "940542", "Key Specifications": "High-pressure die-cast aluminum housing, 140-160 lm/W high efficacy, Meanwell / Philips drivers, IP66 / IK08 surge protection 10kV", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Delhi NCR, Mumbai, Gujarat", "Foreign Competitors / Notes": "China LED lighting hubs; Indian luminaires have superior thermal dissipation for hot climate applications", "Source Reference": "ELCOMA India Lighting Trade Directory", "Date Added": today_str},
                    # Niche 8
                    {"Product Name": "Commercial Ride-On & Walk-Behind Floor Scrubber Dryers", "Niche": "Niche 8: Commercial Appliances", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "847989", "Key Specifications": "Heavy duty rotomolded polyethylene recovery tanks, parabolic squeegee, twin counter-rotating disc brushes, battery powered traction drive", "Export Potential": "High", "Indian Manufacturing Hubs": "Coimbatore, Pune, Delhi NCR", "Foreign Competitors / Notes": "Kärcher (Germany), Nilfisk (Denmark), Tennant (USA); Indian machines provide rugged reliability at 40% lower initial cost", "Source Reference": "Commercial Cleaning Equipment Council", "Date Added": today_str},
                    # Niche 9
                    {"Product Name": "Industrial PIR Motion & Daylight Sensors (IP65 Outdoor)", "Niche": "Niche 9: Sensors & Testing", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "853650", "Key Specifications": "Pyroelectric dual-element sensor, 360-degree coverage, 15m detection radius, zero-crossing switching for LED capacitive loads", "Export Potential": "High", "Indian Manufacturing Hubs": "Delhi NCR, Bangalore", "Foreign Competitors / Notes": "Germany (Theben, Steinel); Indian building automation sensors offer competitive pricing for retrofit projects", "Source Reference": "Building Automation Sensor Trade Network", "Date Added": today_str},
                    {"Product Name": "Transformer Turns Ratio & Winding Resistance Test Benches", "Niche": "Niche 9: Sensors & Testing", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "903089", "Key Specifications": "Automated turns ratio range 0.8 to 10,000, 4-wire Kelvin micro-ohmmeter, built-in thermal printer and USB interface for utility testing", "Export Potential": "High", "Indian Manufacturing Hubs": "Vadodara, Bangalore, Mumbai", "Foreign Competitors / Notes": "Haefely (Switzerland), Megger (UK); Indian electrical test instrument makers have high credibility across Asian and African utilities", "Source Reference": "CPRI Electrical Testing Standards", "Date Added": today_str},
                    # Niche 10
                    {"Product Name": "Dual-Gun DC Fast EV Charging Stations (60kW - 180kW)", "Niche": "Niche 10: Electric Vehicles & EV Infrastructure", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "850440", "Key Specifications": "Dual CCS2 connectors, dynamic load balancing, OCPP 1.6J/2.0.1, 7-inch sunlight readable touchscreen, IP54 outdoor ingress protection", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Bangalore, Pune, Gurgaon", "Foreign Competitors / Notes": "ABB (Switzerland), Tritium (Australia), Chinese EVSE; Indian EV chargers provide certified European standards at lower costs", "Source Reference": "Society of Indian Automobile Manufacturers (SIAM)", "Date Added": today_str},
                    {"Product Name": "Type 2 to Type 2 EV Charging Cables (32A 3-Phase 22kW)", "Niche": "Niche 10: Electric Vehicles & EV Infrastructure", "Target Region": "Germany & Europe", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "854442", "Key Specifications": "TPU jacket flexible cable, silver plated copper alloy terminals, IP55 mated, CE & TUV certified according to IEC 62196-2", "Export Potential": "High", "Indian Manufacturing Hubs": "Pune, Gurgaon", "Foreign Competitors / Notes": "Phoenix Contact (Germany), Mennekes (Germany); high aftermarket and OEM bundle demand across Europe", "Source Reference": "Automotive Component Manufacturers Association (ACMA)", "Date Added": today_str},
                    # Niche 11
                    {"Product Name": "Multi-Layer Rigid FR4 PCBs (4 to 16 Layers)", "Niche": "Niche 11: Printed Circuit Boards (PCB) & PCBA", "Target Region": "USA & North America", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "853400", "Key Specifications": "TG170/TG180 FR4 material, ENIG / Lead-Free HASL surface finish, controlled impedance +/-10%, IPC-A-600 Class 2/3 certified", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Bangalore, Gandhinagar (Gujarat), Chennai", "Foreign Competitors / Notes": "China (Shennan, Kinwong); Indian PCB fabricators are gaining significant market share under China+1 diversification strategies", "Source Reference": "IPCA (Indian Printed Circuit Association)", "Date Added": today_str},
                    {"Product Name": "Turnkey SMT PCBA Assembly & Electronics Manufacturing Services (EMS)", "Niche": "Niche 11: Printed Circuit Boards (PCB) & PCBA", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "853400", "Key Specifications": "High-speed SMT lines handling 01005 passives, BGA 0.4mm pitch, 3D SPI & AOI, conformal coating, automated functional testing", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Bangalore, Noida, Chennai, Sriperumbudur", "Foreign Competitors / Notes": "Vietnam, Taiwan, China; Indian EMS facilities have ISO 13485, AS9100, and IATF 16949 international accreditations", "Source Reference": "ELCINA (Electronic Industries Association of India)", "Date Added": today_str},
                    {"Product Name": "Metal Core Aluminum MCPCBs (Thermal Conductivity 2.0W/mK)", "Niche": "Niche 11: Printed Circuit Boards (PCB) & PCBA", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "853400", "Key Specifications": "1.5mm aluminum base alloy 5052, high dielectric strength dielectric layer, 1oz/2oz copper foil, white reflective solder mask for automotive LED lighting", "Export Potential": "High", "Indian Manufacturing Hubs": "Gujarat, Bangalore", "Foreign Competitors / Notes": "China; Indian MCPCBs serve global automotive LED headlamp and industrial luminaire manufacturers", "Source Reference": "IPCA / Automotive Lighting Standards", "Date Added": today_str},
                    # Niche 12
                    {"Product Name": "Commercial Marine Grade Plywood (IS 710 BWP Hardwood)", "Niche": "Niche 12: Building Materials & Wooden Panels", "Target Region": "UAE & Middle East", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "441233", "Key Specifications": "100% calibrated hardwood core, unextended phenol formaldehyde (BWP) synthetic resin, 72 hours boiling water proof, borer and termite proof", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Yamunanagar (Haryana), Perumbavoor (Kerala), Gandhidham (Gujarat)", "Foreign Competitors / Notes": "Indonesia, Russia, Vietnam; Indian marine plywood is the gold standard across GCC construction and interior decoration", "Source Reference": "Federation of All India Timber Merchants", "Date Added": today_str},
                    {"Product Name": "Melamine Faced Laminated MDF & Decorative Particle Boards", "Niche": "Niche 12: Building Materials & Wooden Panels", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "441114", "Key Specifications": "E1 low formaldehyde emission grade, scratch-resistant suede/woodgrain textured melamine paper, thickness 6mm to 25mm, size 8ft x 4ft", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Yamunanagar, Gujarat, Chennai", "Foreign Competitors / Notes": "Kronospan (Germany), Kastamonu (Turkey), China; Indian panel boards offer superior moisture resistance", "Source Reference": "Indian Plywood Industries Research and Training Institute (IPIRTI)", "Date Added": today_str},
                    # Niche 13
                    {"Product Name": "Ceramic Low-Metallic Brake Pads & Ventilated Brake Discs", "Niche": "Niche 13: Automotive & Car Parts / Auto Components", "Target Region": "USA & North America", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "870830", "Key Specifications": "ECE R90 certified, copper-free ceramic formulation, low noise & low dust, precision CNC balanced ventilated rotors with anti-rust coating", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Pune, Chennai, Aurangabad", "Foreign Competitors / Notes": "Bosch (Germany), Brembo (Italy), China; India is a premier global hub for OEM friction materials and aftermarket brake systems", "Source Reference": "Automotive Component Manufacturers Association (ACMA)", "Date Added": today_str},
                    {"Product Name": "Hydraulic Suspension Shock Absorbers & MacPherson Struts", "Niche": "Niche 13: Automotive & Car Parts / Auto Components", "Target Region": "Germany & Europe", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "870880", "Key Specifications": "Twin-tube gas pressurized, hard chrome plated micro-crack piston rod, multi-lip Japanese NOK oil seal, precision damping valves for passenger vehicles", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Pune, Gurgaon, Rajkot", "Foreign Competitors / Notes": "KYB (Japan), Monroe (USA), Bilstein (Germany); Indian auto tier-1 suppliers export millions of units to European car platforms", "Source Reference": "ACMA Automotive Sourcing Directory", "Date Added": today_str},
                    {"Product Name": "Automotive Wiring Harnesses & Engine Sensors", "Niche": "Niche 13: Automotive & Car Parts / Auto Components", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "854430", "Key Specifications": "Thin-wall FLRY automotive copper cables, ultrasonic wire splicing, waterproof sealed connector assemblies, temperature range -40°C to +125°C", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Gurgaon, Pune, Noida, Chennai", "Foreign Competitors / Notes": "Yazaki (Japan), Sumitomo (Japan), Leoni (Germany); Motherson and Indian tier-1 harness makers have global market leadership", "Source Reference": "Motherson / ACMA Supply Chain Index", "Date Added": today_str},
                    {"Product Name": "Aluminum Brazed Car Radiators & Intercoolers (Controlled Atmosphere Brazing)", "Niche": "Niche 13: Automotive & Car Parts / Auto Components", "Target Region": "Worldwide", "Supplier Type": "Indian Supplier (Supply from India)", "Supplier Country": "India", "HS Code": "870891", "Key Specifications": "CAB aluminum core with louvered fins, PA66 GF30 glass-reinforced polyamide tanks, burst pressure tested to 3.5 bar, high heat exchange efficiency", "Export Potential": "Very High", "Indian Manufacturing Hubs": "Chennai, Coimbatore, Delhi NCR", "Foreign Competitors / Notes": "Denso (Japan), Valeo (France), China; Indian cooling system plants supply major European and Japanese carmakers", "Source Reference": "ACMA Engine Cooling Systems Group", "Date Added": today_str}
                ]
                df = pd.DataFrame(baseline_data)
                df.to_excel(matrix_file, index=False)
                self.logger.info(f"Initialized {matrix_file} with {len(df)} products across all 13 niches.")
            except Exception as e:
                self.logger.error(f"Failed to initialize {matrix_file}: {e}")

    def start_product_sourcing_search(self):
        """Initiates AI export product sourcing search in a background thread."""
        import tkinter.messagebox as messagebox
        import threading

        region = self.prod_region_var.get()
        include_foreign = self.prod_foreign_sup_var.get()
        niche = self.prod_niche_var.get()
        keyword = self.prod_keyword_entry.get().strip()

        region_name = region.split(" (")[0].strip()
        self.btn_prod_search.configure(state="disabled")
        self.lbl_prod_status.configure(
            text=f"⏳ Finding export products for {region_name} via Gemini...",
            text_color="#f39c12"
        )

        threading.Thread(
            target=self.product_sourcing_search_thread,
            args=(region_name, include_foreign, niche, keyword),
            daemon=True
        ).start()

    def product_sourcing_search_thread(self, region_name, include_foreign, niche, keyword):
        """Background worker that calls Gemini to discover export products to supply from India."""
        try:
            import pandas as pd
            from datetime import datetime
            from google.genai import types
            from pydantic import BaseModel, Field
            from typing import List
            from llm_fallback import generate_with_fallback

            class ProductItem(BaseModel):
                product_name: str = Field(description="Specific technical product name")
                niche: str = Field(description="One of the 13 industrial niches")
                target_region: str = Field(default=region_name, description="Target destination market")
                supplier_type: str = Field(description="'Indian Supplier (Supply from India)' or 'Foreign Supplier'")
                supplier_country: str = Field(description="'India' or foreign country like China, Germany, USA, Japan")
                hs_code: str = Field(description="Valid 6-digit HS tariff code")
                specifications: str = Field(description="1-2 sentences of key technical specifications, standards, or ratings")
                export_potential: str = Field(description="'Very High', 'High', or 'Growing'")
                indian_manufacturing_hubs: str = Field(description="Indian industrial clusters (e.g. Pune, Gujarat, Jamnagar, Coimbatore, Yamunanagar)")
                foreign_competitors_notes: str = Field(description="Foreign competitor countries and Indian competitive advantage")
                source_reference: str = Field(description="Market intelligence source or trade council")

            class ProductListResponse(BaseModel):
                products: List[ProductItem]

            foreign_instruction = (
                "INCLUDE BOTH Indian manufacturing export products AND competitive foreign suppliers (e.g. China, Germany, Japan, USA) "
                "that supply this destination market, highlighting opportunities for Indian manufacturers to substitute them."
                if include_foreign else
                "FOCUS EXCLUSIVELY on high-potential products that can be manufactured and supplied from India to this target market."
            )

            prompt = f"""You are an elite international trade intelligence and export product sourcing consultant for Indian B2B trade.
Our company sources and exports industrial goods from Indian manufacturing hubs to global markets across these 13 core niches:
Niche 1: Electrical & Electronic Components
Niche 2: Wires & Cables
Niche 3: Power Distribution & Protection Relays
Niche 4: HVAC, Fans, Pumps & Actuators
Niche 5: Batteries, Solar Energy & Renewable Scrap
Niche 6: Industrial Generators
Niche 7: LED Lighting & Lighting Controls
Niche 8: Commercial Appliances
Niche 9: Sensors & Testing
Niche 10: Electric Vehicles & EV Infrastructure
Niche 11: Printed Circuit Boards (PCB) & PCBA
Niche 12: Building Materials & Wooden Panels
Niche 13: Automotive & Car Parts / Auto Components

Target Destination Market: {region_name}
Foreign Suppliers Mode: {foreign_instruction}
Niche Filter: {niche}
Optional Keyword / Specific Sub-product: {keyword or 'None (Analyze top high-margin export products)'}

Analyze international trade demand in {region_name} and India's manufacturing strengths (Gujarat, Maharashtra, Bangalore, Pune, Coimbatore, Jamnagar, Yamunanagar, Chennai, Delhi NCR).
Generate 6 to 10 actionable, specific, real-world product supply opportunities.
Ensure each product maps cleanly to one of the 13 niches above. If a product falls outside these 13 categories, set its niche explicitly to "Miscellaneous Niche". Provide a realistic 6-digit HS code and technical specifications.
"""

            response = generate_with_fallback(
                prompt=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ProductListResponse,
                    temperature=0.2
                ),
                logger=self.logger
            )

            new_products = []
            if hasattr(response, 'parsed') and response.parsed and hasattr(response.parsed, 'products'):
                for item in response.parsed.products:
                    new_products.append(item.model_dump())
            elif response and response.text:
                import json
                cleaned_text = response.text.strip()
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text[7:]
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3]
                data = json.loads(cleaned_text.strip())
                if isinstance(data, dict) and "products" in data:
                    new_products = data["products"]
                elif isinstance(data, list):
                    new_products = data

            matrix_file = "Products_Matrix.xlsx"
            self.ensure_products_matrix_exists()
            df_existing = pd.read_excel(matrix_file)

            today_str = datetime.now().strftime("%Y-%m-%d")
            added_count = 0

            # Normalize column names in existing df
            existing_keys = set()
            col_p = 'Product Name' if 'Product Name' in df_existing.columns else 'product_name'
            col_r = 'Target Region' if 'Target Region' in df_existing.columns else 'target_region'
            for _, r in df_existing.iterrows():
                p_val = str(r.get(col_p, '')).strip().lower()
                r_val = str(r.get(col_r, '')).strip().lower()
                if p_val:
                    existing_keys.add((p_val, r_val))

            rows_to_add = []
            for p in new_products:
                p_name = p.get("product_name", "").strip()
                p_reg = p.get("target_region", region_name).strip()
                if not p_name:
                    continue
                key = (p_name.lower(), p_reg.lower())
                if key not in existing_keys:
                    existing_keys.add(key)
                    rows_to_add.append({
                        "Product Name": p_name,
                        "Niche": self.resolve_product_niche_link(p.get("product_name", ""), p.get("niche", ""), p.get("specifications", ""), p.get("hs_code", ""), niche),
                        "Target Region": p_reg,
                        "Supplier Type": p.get("supplier_type", "Indian Supplier (Supply from India)"),
                        "Supplier Country": p.get("supplier_country", "India"),
                        "HS Code": str(p.get("hs_code", "")).strip(),
                        "Key Specifications": p.get("specifications", ""),
                        "Export Potential": p.get("export_potential", "High"),
                        "Indian Manufacturing Hubs": p.get("indian_manufacturing_hubs", "Gujarat, Maharashtra, Bangalore"),
                        "Foreign Competitors / Notes": p.get("foreign_competitors_notes", ""),
                        "Source Reference": p.get("source_reference", "Gemini Export Intelligence"),
                        "Date Added": today_str
                    })
                    added_count += 1

            if rows_to_add:
                df_new = pd.DataFrame(rows_to_add)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined.to_excel(matrix_file, index=False)
                self.logger.info(f"Appended {added_count} new product opportunities to {matrix_file}.")

            self.ui_queue.put((self.on_product_search_completed, (added_count, region_name)))

        except Exception as e:
            self.logger.error(f"Product sourcing search failed: {e}")
            self.ui_queue.put((self.on_product_search_failed, (str(e), region_name)))

    def on_product_search_completed(self, added_count, region_name):
        """Called on main thread when product discovery search completes."""
        self.btn_prod_search.configure(state="normal")
        if added_count > 0:
            self.lbl_prod_status.configure(
                text=f"✅ Added {added_count} products for {region_name}! (Matrix Updated)",
                text_color="#2ecc71"
            )
        else:
            self.lbl_prod_status.configure(
                text=f"ℹ️ Found products already exist in matrix.",
                text_color="#3498db"
            )
        self.load_products_matrix(self.prod_niche_var.get())

    def on_product_search_failed(self, err_msg, region_name):
        """Called on main thread when product discovery search encounters an error."""
        self.btn_prod_search.configure(state="normal")
        self.lbl_prod_status.configure(
            text=f"❌ Error: {err_msg[:45]}...",
            text_color="#e74c3c"
        )

    def open_excel_file(self, filename):
        """Cross-platform helper to open an Excel file directly in default application."""
        import tkinter.messagebox as messagebox
        if not os.path.exists(filename):
            messagebox.showinfo("File Not Found", f"'{filename}' was not found. Please sync or create matrix first.")
            return
        try:
            if sys.platform == 'win32':
                os.startfile(filename)
            elif sys.platform == 'darwin':
                import subprocess
                subprocess.Popen(['open', filename])
            else:
                import subprocess
                subprocess.Popen(['xdg-open', filename])
            self.logger.info(f"Opened {filename} in default application.")
        except Exception as e:
            self.logger.error(f"Failed to open {filename}: {e}")
            messagebox.showerror("Error", f"Could not open file: {e}")

    def copy_selected_product_details(self):
        """Copies the selected product row's full details to the clipboard."""
        import tkinter.messagebox as messagebox
        sel = self.prod_tree.selection()
        if not sel:
            messagebox.showinfo("Select Product", "Please select a product from the table first.")
            return
        item_id = sel[0]
        row_vals = self.prod_tree.item(item_id)["values"]
        cols = list(self.prod_tree["columns"])
        data = dict(zip(cols, row_vals))

        lines = [f"=== {data.get('Product Name', 'Product Details')} ==="]
        for k, v in data.items():
            if str(v).strip() and str(v).strip() not in ['None', 'nan']:
                lines.append(f"{k}: {v}")
        summary_text = "\n".join(lines)

        self.clipboard_clear()
        self.clipboard_append(summary_text)
        self.lbl_prod_status.configure(
            text="📋 Copied product details to clipboard!",
            text_color="#2ecc71"
        )
        self.tab_prod_sourcing.after(2500, lambda: self.lbl_prod_status.configure(text=""))

    def source_selected_product_in_discovery(self):
        """Takes the selected product from the matrix, populates URL Discovery query, and switches tabs."""
        import tkinter.messagebox as messagebox
        sel = self.prod_tree.selection()
        if not sel:
            messagebox.showinfo("Select Product", "Please select a product from the table first.")
            return
        item_id = sel[0]
        row_vals = self.prod_tree.item(item_id)["values"]
        cols = list(self.prod_tree["columns"])
        data = dict(zip(cols, row_vals))

        pname = str(data.get("Product Name", "")).strip()
        stype = str(data.get("Supplier Type", "")).strip()
        country = str(data.get("Supplier Country", "India")).strip()
        if not pname:
            messagebox.showinfo("No Product", "Selected row does not have a valid product name.")
            return

        # Configure URL Discovery tab for this product
        self.strategy_var.set("Suppliers")
        self.on_strategy_change("Suppliers")

        if "Indian" in stype or country.lower() == "india":
            search_query = f"{pname} manufacturers India"
            # Ensure India is chosen in discovery region
            for r in self.country_regions:
                if "India" in r:
                    self.region_var.set(r)
                    break
        else:
            search_query = f"{pname} manufacturers {country}"
            for r in self.country_regions:
                if country.lower() in r.lower():
                    self.region_var.set(r)
                    break

        self.query_entry.delete("0.0", "end")
        self.query_entry.insert("0.0", search_query)
        self.tabview.set("URL Discovery")
        self.lbl_disc_status.configure(
            text=f"Loaded product sourcing query from Product Sourcing tab.",
            text_color="#2ecc71"
        )
        self.logger.info(f"Loaded '{search_query}' into URL Discovery for scraping.")

    def resolve_product_niche_link(self, product_name, raw_niche, specifications, hs_code, active_niche_filter="All Niches"):
        """Ensures newly found products are linked to one of the 13 core niches, or falls back to 'Miscellaneous Niche'."""
        raw_clean = str(raw_niche).strip()
        if raw_clean:
            for item in NICHES_METADATA:
                k = item["key"].lower()
                t = item["title"].lower()
                r = raw_clean.lower()
                if (r in k or k in r or r in t or t in r or f"niche {item['id']}" in r):
                    return item["key"]
        
        # If user was filtering for a specific niche, prefer that niche
        if active_niche_filter and active_niche_filter not in ["All Niches", "All 13 Niches", "Miscellaneous Niche"]:
            for item in NICHES_METADATA:
                if item["key"] == active_niche_filter:
                    return item["key"]

        # Run intelligent classifier
        classified = classify_product_niche(product_name, specifications, hs_code)
        return classified

    def sort_unassigned_products_to_niches(self):
        """Scans Products_Matrix.xlsx for any products lacking a proper niche (or marked as Miscellaneous),
        and automatically classifies/sorts them into the appropriate industrial niche."""
        import tkinter.messagebox as messagebox
        import pandas as pd

        matrix_file = "Products_Matrix.xlsx"
        if not os.path.exists(matrix_file):
            messagebox.showinfo("Matrix Not Found", f"'{matrix_file}' was not found. Please sync or create matrix first.")
            return

        try:
            df = pd.read_excel(matrix_file)
            if df.empty:
                messagebox.showinfo("Empty Matrix", f"'{matrix_file}' contains no products.")
                return

            col_niche = 'Niche' if 'Niche' in df.columns else 'niche'
            col_name = 'Product Name' if 'Product Name' in df.columns else 'product_name'
            col_spec = 'Key Specifications' if 'Key Specifications' in df.columns else 'specifications'
            col_hs = 'HS Code' if 'HS Code' in df.columns else 'hs_code'

            unassigned_indices = []
            for idx, row in df.iterrows():
                val = str(row.get(col_niche, '')).strip()
                # Check if niche is empty, NaN, Unknown, Unassigned, Miscellaneous Niche, or unformatted
                if (not val or val.lower() in ['nan', 'none', 'unknown', 'unassigned', '', 'general'] or
                    'miscellaneous' in val.lower() or not val.startswith("Niche ")):
                    unassigned_indices.append(idx)

            if not unassigned_indices:
                messagebox.showinfo(
                    "All Products Assigned", 
                    "All products in Products_Matrix.xlsx are already successfully assigned to specific industrial niches!"
                )
                return

            sorted_details = []
            changed_count = 0
            for idx in unassigned_indices:
                row = df.loc[idx]
                p_name = str(row.get(col_name, '')).strip()
                p_spec = str(row.get(col_spec, '')).strip() if pd.notna(row.get(col_spec)) else ""
                p_hs = str(row.get(col_hs, '')).strip() if pd.notna(row.get(col_hs)) else ""
                old_val = str(row.get(col_niche, '')).strip()

                new_niche = classify_product_niche(p_name, p_spec, p_hs)
                df.at[idx, col_niche] = new_niche
                if new_niche != old_val:
                    changed_count += 1
                sorted_details.append(f"• {p_name} ➔ {new_niche}")

            # Save updated matrix
            df.to_excel(matrix_file, index=False)
            self.logger.info(f"Sorted {len(unassigned_indices)} products into niches in {matrix_file}.")

            # Reload treeview and update niche grid counts
            self.load_products_matrix(self.prod_niche_var.get())

            summary_msg = f"Processed {len(unassigned_indices)} products ({changed_count} updated into niches):\n\n" + "\n".join(sorted_details[:15])
            if len(sorted_details) > 15:
                summary_msg += f"\n...and {len(sorted_details) - 15} more."
            messagebox.showinfo("Niches Sorted Successfully", summary_msg)

        except Exception as e:
            self.logger.error(f"Failed to sort unassigned products: {e}")
            messagebox.showerror("Sorting Error", f"An error occurred while sorting niches: {e}")

    def open_add_product_window(self):
        """Opens a modal dialog to manually add a custom product to Products_Matrix.xlsx."""
        import tkinter.messagebox as messagebox
        from datetime import datetime

        win = ctk.CTkToplevel(self)
        win.title("➕ Add Custom Product to Sourcing Matrix")
        win.geometry("640x680")
        win.attributes("-topmost", True)
        win.focus_set()

        hdr = ctk.CTkFrame(win, fg_color="#1f232a", corner_radius=8)
        hdr.pack(fill="x", padx=15, pady=(15, 10))

        lbl_t = ctk.CTkLabel(hdr, text="Add New Product to Products_Matrix.xlsx", font=("Arial", 15, "bold"), text_color="#ffffff")
        lbl_t.pack(anchor="w", padx=15, pady=(10, 2))
        lbl_sub = ctk.CTkLabel(hdr, text="Define product specs, niche classification, target export markets, and manufacturing hubs.", font=("Arial", 11), text_color="#a0a0a0")
        lbl_sub.pack(anchor="w", padx=15, pady=(0, 10))

        content = ctk.CTkScrollableFrame(win, height=480)
        content.pack(fill="both", expand=True, padx=15, pady=5)

        def make_field(label, default=""):
            f = ctk.CTkFrame(content, fg_color="transparent")
            f.pack(fill="x", pady=4)
            lbl = ctk.CTkLabel(f, text=label, width=170, anchor="w", font=("Arial", 12, "bold"))
            lbl.pack(side="left")
            entry = ctk.CTkEntry(f, height=30)
            entry.pack(side="left", fill="x", expand=True)
            if default:
                entry.insert(0, default)
            return entry

        def make_option(label, values, default=None):
            f = ctk.CTkFrame(content, fg_color="transparent")
            f.pack(fill="x", pady=4)
            lbl = ctk.CTkLabel(f, text=label, width=170, anchor="w", font=("Arial", 12, "bold"))
            lbl.pack(side="left")
            var = ctk.StringVar(value=default or values[0])
            opt = ctk.CTkOptionMenu(f, values=values, variable=var, height=30)
            opt.pack(side="left", fill="x", expand=True)
            return var

        entry_name = make_field("Product Name *:", "")
        var_niche = make_option("Industrial Niche *:", self.industrial_niches_list[1:], self.industrial_niches_list[1])
        entry_reg = make_field("Target Region:", "Worldwide")
        var_stype = make_option("Supplier Type:", ["Indian Supplier (Supply from India)", "Foreign Supplier"], "Indian Supplier (Supply from India)")
        entry_country = make_field("Supplier Country:", "India")
        entry_hscode = make_field("HS Tariff Code:", "")
        entry_specs = make_field("Key Specifications:", "")
        var_potential = make_option("Export Potential:", ["Very High", "High", "Growing", "Medium"], "Very High")
        entry_hubs = make_field("Indian Hubs:", "Gujarat, Maharashtra, Bangalore")
        entry_foreign = make_field("Foreign Notes / Competitors:", "")
        entry_source = make_field("Source Reference:", "Manual Entry")

        btn_bar = ctk.CTkFrame(win, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=12)

        def save_product():
            pname = entry_name.get().strip()
            if not pname:
                messagebox.showwarning("Product Name Required", "Please enter a product name.")
                return

            new_row = {
                "Product Name": pname,
                "Niche": var_niche.get(),
                "Target Region": entry_reg.get().strip() or "Worldwide",
                "Supplier Type": var_stype.get(),
                "Supplier Country": entry_country.get().strip() or "India",
                "HS Code": entry_hscode.get().strip(),
                "Key Specifications": entry_specs.get().strip(),
                "Export Potential": var_potential.get(),
                "Indian Manufacturing Hubs": entry_hubs.get().strip(),
                "Foreign Competitors / Notes": entry_foreign.get().strip(),
                "Source Reference": entry_source.get().strip() or "Manual Entry",
                "Date Added": datetime.now().strftime("%Y-%m-%d")
            }

            try:
                import pandas as pd
                matrix_file = "Products_Matrix.xlsx"
                self.ensure_products_matrix_exists()
                df = pd.read_excel(matrix_file)
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_excel(matrix_file, index=False)
                self.load_matrix(self.prod_tree, matrix_file)
                self.lbl_prod_status.configure(
                    text=f"✅ Added '{pname}' to Products_Matrix.xlsx!",
                    text_color="#2ecc71"
                )
                win.destroy()
            except Exception as e:
                messagebox.showerror("Save Error", f"Could not save product: {e}")

        btn_save = ctk.CTkButton(btn_bar, text="💾 Save to Matrix", command=save_product, fg_color="#1f7a1f", hover_color="#145214", width=140)
        btn_save.pack(side="right", padx=5)

        btn_cancel = ctk.CTkButton(btn_bar, text="Cancel", command=win.destroy, fg_color="#565b5e", hover_color="#343638", width=90)
        btn_cancel.pack(side="right", padx=5)

    def setup_wh_db_tab(self):
        self.wh_tree = self.create_database_tab_ui(
            self.tab_wh_db, 
            lambda: self.load_matrix(self.wh_tree, "Warehouses_Matrix.xlsx"),
            lambda: self.clean_local_matrix("Warehouses_Matrix.xlsx", self.wh_tree),
            lambda: self.delete_all_entries("Warehouses_Matrix.xlsx", self.wh_tree),
            proposal_cmd=self.open_warehouse_inquiry_window,
            mode="warehouse"
        )
        self.load_matrix(self.wh_tree, "Warehouses_Matrix.xlsx")
        self.init_warehouse_reference_area()

    def init_warehouse_reference_area(self):
        """Initializes the reference area text box and status label from Warehouses_Matrix.xlsx if available."""
        matrix_file = "Warehouses_Matrix.xlsx"
        if os.path.exists(matrix_file):
            try:
                import pandas as pd
                df = pd.read_excel(matrix_file)
                if "distance_from_area" in df.columns:
                    valid_areas = df["distance_from_area"].dropna().astype(str).str.strip()
                    valid_areas = valid_areas[~valid_areas.isin(["", "nan", "None"])]
                    if not valid_areas.empty:
                        last_area = valid_areas.iloc[0]
                        if hasattr(self, "wh_ref_area_entry"):
                            cur_val = self.wh_ref_area_entry.get().strip()
                            if not cur_val:
                                self.wh_ref_area_entry.delete(0, "end")
                                self.wh_ref_area_entry.insert(0, last_area)
                        if hasattr(self, "wh_dist_status_lbl"):
                            self.wh_dist_status_lbl.configure(
                                text=f"Last reference: '{last_area}'",
                                text_color="#2ecc71"
                            )
            except Exception as e:
                self.logger.debug(f"Could not load saved warehouse reference area: {e}")

    def start_warehouse_distance_calculation(self):
        """Initiates Gemini road distance estimation from the user-entered reference area."""
        import tkinter.messagebox as messagebox
        ref_area = self.wh_ref_area_entry.get().strip() if hasattr(self, "wh_ref_area_entry") else ""
        if not ref_area:
            messagebox.showwarning(
                "Reference Area Required",
                "Please enter an area name or landmark in the text box\n(e.g., 'Bandra West, Mumbai', 'Cyber City, Gurgaon', or 'Whitefield, Bangalore')."
            )
            return

        matrix_file = "Warehouses_Matrix.xlsx"
        if not os.path.exists(matrix_file):
            messagebox.showinfo("Matrix Not Found", f"'{matrix_file}' was not found. Please scrape warehouse properties first.")
            return

        try:
            import pandas as pd
            df = pd.read_excel(matrix_file)
        except Exception as e:
            messagebox.showerror("Read Error", f"Could not read {matrix_file}: {e}")
            return

        if df.empty:
            messagebox.showinfo("Matrix Empty", f"'{matrix_file}' contains no properties.")
            return

        self.wh_calc_dist_btn.configure(state="disabled", text="⏳ Calculating via Gemini...")
        self.wh_dist_status_lbl.configure(
            text=f"Analyzing driving distances from '{ref_area}' with Gemini AI...",
            text_color="#ffbb33"
        )
        self.logger.info(f"Starting Gemini road distance calculation from reference area '{ref_area}' for {len(df)} properties...")

        threading.Thread(
            target=self._run_warehouse_distance_worker,
            args=(ref_area, matrix_file, df),
            daemon=True
        ).start()

    def _run_warehouse_distance_worker(self, ref_area, matrix_file, df):
        import traceback
        from pydantic import BaseModel, Field
        from typing import List, Optional
        from google.genai import types
        from llm_fallback import generate_with_fallback

        class LocationDistItem(BaseModel):
            index: int = Field(description="The index number from the prompt list, e.g. 1, 2, 3")
            location_area: str = Field(description="The exact location area name from the prompt")
            city: Optional[str] = Field(default="", description="The city name from the prompt")
            distance_km: str = Field(description="Road driving distance with unit, e.g. '35 km' or '12 km'")
            route_notes: Optional[str] = Field(default="", description="Short route corridor hint, e.g. 'via NH48'")

        class DistanceList(BaseModel):
            items: List[LocationDistItem]

        try:
            # Group unique location_area and city pairs
            unique_locs = []
            loc_to_id = {}
            for idx, row in df.iterrows():
                loc = str(row.get('location_area', '')).strip()
                city = str(row.get('city', '')).strip()
                if loc in ['nan', 'None']: loc = ''
                if city in ['nan', 'None']: city = ''
                key = (loc.lower(), city.lower())
                if key not in loc_to_id:
                    unique_locs.append((loc, city, key))
                    loc_to_id[key] = len(unique_locs)

            # Build prompt
            prompt = f"""You are an elite Indian geographic road routing and distance estimation AI.
The user wants to measure the realistic driving road distance (in kilometers) from a reference area to warehouse locations in India.

User Reference Area: "{ref_area}"

List of Warehouse Locations to Measure:
"""
            for i, (loc, city, key) in enumerate(unique_locs, 1):
                loc_disp = loc if loc else "Unspecified Area"
                city_disp = city if city else "India"
                prompt += f"[{i}] Location Area: \"{loc_disp}\" | City: \"{city_disp}\"\n"

            prompt += f"""
INSTRUCTIONS:
1. Determine the primary city/metropolitan region of the User Reference Area "{ref_area}". (e.g. if 'Bandra', it is Mumbai; if 'Cyber City', it is Gurgaon/NCR; if 'Whitefield', it is Bangalore; if 'Okhla', it is Delhi; or use whatever city is explicitly provided in the area name).
2. For each warehouse location:
   - If the warehouse is in the same city or greater metropolitan region as "{ref_area}" (e.g. both in Mumbai MMR / Thane / Navi Mumbai, or both in Bengaluru, or both in Delhi NCR / Gurgaon / Noida / Faridabad):
     Provide the realistic driving road distance in kilometers as a clean number followed by 'km' (e.g. '18 km', '35 km', '42 km').
   - If the warehouse is in a clearly different city or state:
     Provide the inter-city driving road distance (e.g. '140 km', '980 km', '1380 km').
   - If the warehouse location is unspecified, invalid or unknown:
     Set distance_km to 'N/A'.
3. In 'route_notes', provide a concise highway corridor or major arterial road hint (e.g. 'via NH48', 'via Western Express Hwy', 'via Mumbai-Nashik Expy', 'via Outer Ring Rd').
4. Return an entry for every indexed location matching the schema with the exact index number.
"""

            response = generate_with_fallback(
                prompt=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DistanceList,
                    temperature=0.0
                ),
                logger=self.logger
            )

            parsed = DistanceList.model_validate_json(response.text)
            id_to_result = {}
            for item in parsed.items:
                id_to_result[item.index] = (item.distance_km, item.route_notes or "")

            # Build review rows for every row in df
            review_rows = []
            for idx, row in df.iterrows():
                loc = str(row.get('location_area', '')).strip()
                city = str(row.get('city', '')).strip()
                if loc in ['nan', 'None']: loc = ''
                if city in ['nan', 'None']: city = ''
                key = (loc.lower(), city.lower())
                loc_id = loc_to_id.get(key)
                dist_val, route_val = id_to_result.get(loc_id, ("N/A", ""))
                review_rows.append({
                    "row_idx": idx,
                    "property_title": str(row.get("property_title", "Commercial Property")),
                    "location_area": loc,
                    "city": city,
                    "distance_km": dist_val,
                    "route_notes": route_val,
                    "carpet_area_sqft": str(row.get("carpet_area_sqft", "")),
                    "monthly_rent": str(row.get("monthly_rent", ""))
                })

            self.ui_queue.put(lambda: self._on_distance_calculation_success(ref_area, matrix_file, df, review_rows))

        except Exception as e:
            self.logger.error(f"Error calculating warehouse distances: {e}\n{traceback.format_exc()}")
            err_msg = str(e)
            self.ui_queue.put(lambda: self._on_distance_calculation_failed(err_msg))

    def _on_distance_calculation_success(self, ref_area, matrix_file, df, review_rows):
        if hasattr(self, "wh_calc_dist_btn"):
            self.wh_calc_dist_btn.configure(state="normal", text="📏 Calculate Road Distances (Gemini)")
        if hasattr(self, "wh_dist_status_lbl"):
            self.wh_dist_status_lbl.configure(
                text=f"Review window opened for '{ref_area}'",
                text_color="#33b5e5"
            )
        self.open_warehouse_distance_review_window(ref_area, matrix_file, df, review_rows)

    def _on_distance_calculation_failed(self, err_msg):
        import tkinter.messagebox as messagebox
        if hasattr(self, "wh_calc_dist_btn"):
            self.wh_calc_dist_btn.configure(state="normal", text="📏 Calculate Road Distances (Gemini)")
        if hasattr(self, "wh_dist_status_lbl"):
            self.wh_dist_status_lbl.configure(text="Distance calculation failed.", text_color="#ff4444")
        messagebox.showerror("Calculation Error", f"Gemini distance calculation encountered an error:\n{err_msg}")

    def open_warehouse_distance_review_window(self, ref_area, matrix_file, df, review_rows):
        """Opens an interactive review dialog to inspect and edit Gemini road distance estimates before saving."""
        import tkinter as tk
        from tkinter import ttk
        import tkinter.messagebox as messagebox

        win = ctk.CTkToplevel(self)
        win.title(f"Review Driving Distances from '{ref_area}'")
        win.geometry("980x640")
        win.attributes("-topmost", True)
        win.focus_set()

        # Header Frame
        header = ctk.CTkFrame(win, fg_color="#1f232a", corner_radius=8)
        header.pack(fill="x", padx=15, pady=(15, 8))

        lbl_title = ctk.CTkLabel(
            header, 
            text=f"📍 Review Road Distances from Reference Area: \"{ref_area}\"", 
            font=("Arial", 16, "bold"),
            text_color="#ffffff"
        )
        lbl_title.pack(anchor="w", padx=15, pady=(12, 4))

        lbl_desc = ctk.CTkLabel(
            header,
            text=f"Gemini estimated road driving distances for {len(review_rows)} warehouse listings relative to '{ref_area}'.\n"
                 f"Review the computed distances and route corridors below. Double-click any row to edit its distance.\n"
                 f"Click 'Confirm & Save to Matrix' to append these distances and search term into {matrix_file}.",
            font=("Arial", 12),
            text_color="#a0a0a0",
            justify="left"
        )
        lbl_desc.pack(anchor="w", padx=15, pady=(0, 12))

        # Table Frame
        tbl_frame = ctk.CTkFrame(win)
        tbl_frame.pack(fill="both", expand=True, padx=15, pady=8)
        tbl_frame.grid_columnconfigure(0, weight=1)
        tbl_frame.grid_rowconfigure(0, weight=1)

        cols = ["#", "Property Title", "Location Area", "City", "Driving Distance", "Route Corridor", "Carpet Area", "Monthly Rent"]
        review_tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", selectmode="browse")
        
        vsb = ttk.Scrollbar(tbl_frame, orient="vertical", command=review_tree.yview)
        hsb = ttk.Scrollbar(tbl_frame, orient="horizontal", command=review_tree.xview)
        review_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        review_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Column widths & headings
        widths = {
            "#": 45, 
            "Property Title": 210, 
            "Location Area": 150, 
            "City": 100, 
            "Driving Distance": 120, 
            "Route Corridor": 160, 
            "Carpet Area": 100, 
            "Monthly Rent": 100
        }
        for c in cols:
            review_tree.heading(c, text=c, command=lambda _c=c: self.sort_tree_column(review_tree, _c, False))
            review_tree.column(c, width=widths.get(c, 120), anchor="center" if c in ["#", "Driving Distance"] else "w")

        # Insert rows
        for i, item in enumerate(review_rows, 1):
            review_tree.insert(
                "", 
                "end", 
                iid=str(i), 
                values=(
                    i,
                    item["property_title"],
                    item["location_area"],
                    item["city"],
                    item["distance_km"],
                    item["route_notes"],
                    item["carpet_area_sqft"],
                    item["monthly_rent"]
                )
            )

        # Allow quick editing of distance by double click
        def on_edit_distance(event=None):
            sel = review_tree.selection()
            if not sel:
                return
            item_id = sel[0]
            vals = list(review_tree.item(item_id)["values"])
            current_dist = str(vals[4])
            prop_name = str(vals[1])
            
            dialog = ctk.CTkInputDialog(
                title="Edit Distance",
                text=f"Edit driving distance for:\n'{prop_name}'\n(e.g. '14 km' or '25 km'):"
            )
            dialog.geometry("460x220")
            new_val = dialog.get_input()
            if new_val and new_val.strip():
                vals[4] = new_val.strip()
                review_tree.item(item_id, values=vals)
                row_idx = int(vals[0]) - 1
                review_rows[row_idx]["distance_km"] = new_val.strip()

        review_tree.bind("<Double-1>", on_edit_distance)

        # Action Buttons Frame
        action_frame = ctk.CTkFrame(win, fg_color="transparent")
        action_frame.pack(fill="x", padx=15, pady=(8, 15))

        def on_confirm():
            final_distances = []
            final_notes = []
            for i in range(1, len(review_rows) + 1):
                item_vals = review_tree.item(str(i))["values"]
                final_distances.append(str(item_vals[4]))
                final_notes.append(str(item_vals[5]))

            df["distance_km"] = final_distances
            df["distance_from_area"] = ref_area
            df["route_notes"] = final_notes

            # Position distance columns right after city
            cols_list = list(df.columns)
            for c in ["route_notes", "distance_from_area", "distance_km"]:
                if c in cols_list:
                    cols_list.remove(c)
            if "city" in cols_list:
                pos = cols_list.index("city") + 1
                cols_list.insert(pos, "distance_km")
                cols_list.insert(pos + 1, "distance_from_area")
                cols_list.insert(pos + 2, "route_notes")
            else:
                cols_list.extend(["distance_km", "distance_from_area", "route_notes"])

            df_ordered = df[[c for c in cols_list if c in df.columns]]
            try:
                df_ordered.to_excel(matrix_file, index=False)
            except Exception as e:
                messagebox.showerror("Save Error", f"Could not write to {matrix_file}: {e}")
                return

            # Refresh table in UI
            self.load_matrix(self.wh_tree, matrix_file)

            # Update status label & text entry
            if hasattr(self, "wh_ref_area_entry"):
                self.wh_ref_area_entry.delete(0, "end")
                self.wh_ref_area_entry.insert(0, ref_area)
            if hasattr(self, "wh_dist_status_lbl"):
                self.wh_dist_status_lbl.configure(
                    text=f"Last calculated from: '{ref_area}' ({len(review_rows)} properties updated)",
                    text_color="#00cc66"
                )

            self.logger.info(f"Successfully appended driving distances from '{ref_area}' to {len(review_rows)} rows in {matrix_file}")
            win.destroy()
            messagebox.showinfo(
                "Matrix Updated Successfully",
                f"Successfully appended road driving distances and search term '{ref_area}' to {len(review_rows)} properties in {matrix_file}!"
            )

        btn_confirm = ctk.CTkButton(
            action_frame, 
            text="✅ Confirm & Save to Matrix", 
            command=on_confirm, 
            fg_color="#1f7a1f", 
            hover_color="#145214", 
            width=220, 
            height=36, 
            font=("Arial", 13, "bold")
        )
        btn_confirm.pack(side="left", padx=(0, 10))

        btn_edit = ctk.CTkButton(
            action_frame,
            text="✏️ Edit Selected Distance",
            command=on_edit_distance,
            width=170,
            height=36,
            fg_color="#3a3a3a",
            hover_color="#2b2b2b"
        )
        btn_edit.pack(side="left", padx=(0, 10))

        btn_cancel = ctk.CTkButton(
            action_frame, 
            text="❌ Cancel", 
            command=win.destroy, 
            fg_color="#555555", 
            hover_color="#333333", 
            width=100, 
            height=36
        )
        btn_cancel.pack(side="right")


    def setup_warehouses_tab(self):
        self.tab_warehouses.grid_columnconfigure(0, weight=1)
        self.tab_warehouses.grid_rowconfigure(3, weight=1)
        
        criteria_text = "Warehouse Context: Extracting Commercial Warehouses, Industrial Sheds, Godowns, and Garage Storage Spaces across Indian Hubs (Carpet Area, Clear Height, 3-Phase Power, Monthly Rent, Road Access, Contact Info)."
        lbl_info = ctk.CTkLabel(self.tab_warehouses, text=criteria_text, font=("Arial", 12, "italic"))
        lbl_info.grid(row=0, column=0, pady=(10,0), sticky="w", padx=20)
        
        self.wh_urls_textbox = ctk.CTkTextbox(self.tab_warehouses, height=150)
        self.wh_urls_textbox.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.wh_urls_textbox.insert("0.0", "Paste Warehouse, Storage, & Yellowpages URLs here (one per line)...\n")
        
        btn_frame = ctk.CTkFrame(self.tab_warehouses, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        self.btn_wh_start = ctk.CTkButton(btn_frame, text="Start Warehouse Extraction", command=lambda: self.start_scraping("warehouse"))
        self.btn_wh_start.pack(side="left", padx=5)

        self.btn_wh_prop = ctk.CTkButton(btn_frame, text="🏢 Quick Rental Inquiry", command=lambda: self.open_url_proposal_window(mode="warehouse"), fg_color="#005b96", hover_color="#003f66")
        self.btn_wh_prop.pack(side="left", padx=5)
        
        self.lbl_wh_status = ctk.CTkLabel(btn_frame, text="Status: Ready")
        self.lbl_wh_status.pack(side="left", padx=20)
        
        self.wh_output_textbox = ctk.CTkTextbox(self.tab_warehouses)
        self.wh_output_textbox.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")

    def open_warehouse_inquiry_window(self):
        selected_items = self.wh_tree.selection()
        if not selected_items:
            import tkinter.messagebox as messagebox
            messagebox.showinfo("Select Warehouse Property", "Please select a warehouse property from the table to generate a rental inquiry.")
            return

        selected_item = selected_items[0]
        row_values = self.wh_tree.item(selected_item)["values"]
        cols = list(self.wh_tree["columns"])
        data = dict(zip(cols, row_values))

        prop_title = str(data.get("property_title", "Commercial Warehouse / Shed")).strip()
        prop_type = str(data.get("property_type", "Warehouse")).strip()
        loc_area = str(data.get("location_area", "")).strip()
        city = str(data.get("city", "India")).strip()
        sqft = str(data.get("carpet_area_sqft", "")).strip()
        height = str(data.get("clear_height_ft", "")).strip()
        power = str(data.get("power_load", "")).strip()
        rent = str(data.get("monthly_rent", "")).strip()
        deposit = str(data.get("deposit_terms", "")).strip()
        road = str(data.get("road_access_container", "")).strip()
        url = str(data.get("url", "")).strip()
        phone = str(data.get("contact_phone", "")).strip()
        name = str(data.get("contact_name", "Property Owner / Broker")).strip()
        dist_km = str(data.get("distance_km", "")).strip()
        dist_ref = str(data.get("distance_from_area", "")).strip()
        has_dist = dist_km and dist_km not in ["", "nan", "None", "N/A"]

        win = ctk.CTkToplevel(self)
        win.title(f"Commercial Rental Inquiry - {prop_title[:35]}")
        win.geometry("820x720")
        win.attributes("-topmost", True)
        win.focus_set()

        header_frame = ctk.CTkFrame(win, fg_color="#1f232a", corner_radius=8)
        header_frame.pack(fill="x", padx=15, pady=(15, 8))

        lbl_title = ctk.CTkLabel(
            header_frame, 
            text=f"🏢 Rental / Lease Inquiry: {prop_title}", 
            font=("Arial", 16, "bold"),
            text_color="#ffffff"
        )
        lbl_title.pack(anchor="w", padx=15, pady=(10, 2))

        dist_str = f"  |  Distance: {dist_km} from {dist_ref}" if has_dist else ""
        sub_desc = f"Location: {loc_area}, {city}{dist_str}  |  Area: {sqft or 'Custom'}  |  Height: {height or 'Standard'}  |  Rent: {rent or 'On Request'}"
        lbl_sub = ctk.CTkLabel(
            header_frame, 
            text=sub_desc, 
            font=("Arial", 11),
            text_color="#a0a0a0"
        )
        lbl_sub.pack(anchor="w", padx=15, pady=(0, 10))

        # To Row
        to_frame = ctk.CTkFrame(win, fg_color="transparent")
        to_frame.pack(fill="x", padx=15, pady=(4, 3))
        lbl_to = ctk.CTkLabel(to_frame, text="To / Contact:", width=90, anchor="w", font=("Arial", 12, "bold"))
        lbl_to.pack(side="left")
        entry_to = ctk.CTkEntry(to_frame, font=("Arial", 12), height=32)
        entry_to.pack(side="left", fill="x", expand=True, padx=(0, 8))
        to_display = f"{name} ({phone})" if phone else name
        entry_to.insert(0, to_display)
        btn_copy_to = ctk.CTkButton(to_frame, text="📋 Copy", width=75, height=32)
        btn_copy_to.pack(side="right")

        # Subject Row
        subj_frame = ctk.CTkFrame(win, fg_color="transparent")
        subj_frame.pack(fill="x", padx=15, pady=(3, 5))
        lbl_subj = ctk.CTkLabel(subj_frame, text="Subject:", width=90, anchor="w", font=("Arial", 12, "bold"))
        lbl_subj.pack(side="left")
        entry_subj = ctk.CTkEntry(subj_frame, font=("Arial", 12), height=32)
        entry_subj.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry_subj.insert(0, "Generating Subject line...")
        btn_copy_subj = ctk.CTkButton(subj_frame, text="📋 Copy", width=75, height=32)
        btn_copy_subj.pack(side="right")

        # Body Header Row
        body_hdr = ctk.CTkFrame(win, fg_color="transparent")
        body_hdr.pack(fill="x", padx=15, pady=(4, 2))
        lbl_body = ctk.CTkLabel(body_hdr, text="Inquiry Body (Gmail Ready):", font=("Arial", 12, "bold"))
        lbl_body.pack(side="left")
        btn_copy_body = ctk.CTkButton(body_hdr, text="📋 Copy Body", width=105, height=28, fg_color="#1f7a1f", hover_color="#145214")
        btn_copy_body.pack(side="right")

        # Body Textbox
        txt_body = ctk.CTkTextbox(win, wrap="word", font=("Arial", 12))
        txt_body.pack(fill="both", expand=True, padx=15, pady=(2, 8))
        txt_body.insert("0.0", "⏳ Generating tailored Commercial Warehouse & Garage Rental Inquiry using Gemini AI...\nPlease wait a few seconds.")

        # Copy handlers
        def copy_widget_text(widget, btn, default_txt):
            if isinstance(widget, ctk.CTkTextbox):
                val = widget.get("0.0", "end").strip()
            else:
                val = widget.get().strip()
            if val and not val.startswith("⏳"):
                self.clipboard_clear()
                self.clipboard_append(val)
                btn.configure(text="Copied! ✅")
                win.after(1500, lambda: btn.configure(text=default_txt))

        btn_copy_to.configure(command=lambda: copy_widget_text(entry_to, btn_copy_to, "📋 Copy"))
        btn_copy_subj.configure(command=lambda: copy_widget_text(entry_subj, btn_copy_subj, "📋 Copy"))
        btn_copy_body.configure(command=lambda: copy_widget_text(txt_body, btn_copy_body, "📋 Copy Body"))

        # Bottom Bar
        btn_bar = ctk.CTkFrame(win, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(5, 12))

        def copy_all():
            s = entry_subj.get().strip()
            b = txt_body.get("0.0", "end").strip()
            if b and not b.startswith("⏳"):
                self.clipboard_clear()
                self.clipboard_append(f"Subject: {s}\n\n{b}")
                btn_copy_all.configure(text="All Copied! ✅")
                win.after(1500, lambda: btn_copy_all.configure(text="📋 Copy Subject + Body"))

        btn_copy_all = ctk.CTkButton(btn_bar, text="📋 Copy Subject + Body", command=copy_all, width=170, fg_color="#005b96", hover_color="#003f66")
        btn_copy_all.pack(side="left", padx=5)

        def start_generation():
            entry_subj.delete(0, "end")
            entry_subj.insert(0, "Generating Subject line...")
            txt_body.delete("0.0", "end")
            txt_body.insert("0.0", "⏳ Generating tailored Commercial Warehouse & Garage Rental Inquiry using Gemini AI...\nPlease wait a few seconds.")
            btn_regen.configure(state="disabled")

            def generate_worker():
                try:
                    from google.genai import types
                    from pydantic import BaseModel, Field
                    from llm_fallback import generate_with_fallback

                    class EmailProposal(BaseModel):
                        to_email: str = Field(default="", description="Recipient contact email or phone note")
                        subject: str = Field(description="Clean, compelling inquiry subject line without any markdown or quotes")
                        body: str = Field(description="Full clean email body ready to paste directly into Gmail composer. Do NOT include markdown bold/italics (no asterisks). Use simple bullet points with • if listing parameters.")

                    prompt = f"""You are Fardin Mohammed, Partner at SinoMagan Indus Global Trade LLP, writing an official Commercial Lease / Rental Inquiry for a warehouse, godown, industrial shed, or garage storage space.

Target Property Profile:
- Property Title: {prop_title}
- Property Type: {prop_type}
- Location & City: {loc_area}, {city}{f" (approx. {dist_km} driving distance from {dist_ref})" if has_dist else ""}
- Carpet Area: {sqft}
- Clear Ceiling Height: {height}
- Industrial Power Load: {power}
- Quoted Monthly Rent: {rent}
- Deposit & Lease Lock-in: {deposit}
- Road Access: {road}
- Contact / Broker: {name} ({phone})
- Listing URL: {url}

Your Company:
- SinoMagan Indus Global Trade LLP (International trade, export sourcing, contract manufacturing, containerized freight operations)
- Authorized Signatory: Fardin Mohammed, Partner

PURPOSE OF THIS EMAIL (COMMERCIAL LEASING INQUIRY):
SinoMagan Indus Global Trade LLP is actively looking to lease/rent this commercial space in {loc_area}, {city} for our export container staging, inventory storage (electrical components, power distribution equipment, solar panels, wooden panels), and vehicle/garage storage operations.
Reach out to confirm availability, schedule an immediate site inspection, and discuss commercial leasing terms.

CRITICAL INSTRUCTIONS:
1. SUBJECT LINE: Concise professional Subject line referencing Commercial Warehouse / Godown / Garage Rental Inquiry for SinoMagan Indus Global Trade LLP - {loc_area}, {city}. No quotes or markdown.
2. EMAIL BODY: Strict Gmail plain text (NO asterisks for bold/italics). Use clean bullet points with '• '. Polite, professional commercial principal tone.
3. SIGN-OFF: Strict format:

Warm regards,

Fardin Mohammed
Partner
SinoMagan Indus Global Trade LLP
"""
                    response = generate_with_fallback(
                        prompt=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=EmailProposal,
                        ),
                        logger=self.logger
                    )
                    from main import parse_email_response
                    to_val, subj_val, body_val = parse_email_response(response.text)
                    def on_done():
                        entry_subj.delete(0, "end")
                        entry_subj.insert(0, subj_val)
                        txt_body.delete("0.0", "end")
                        txt_body.insert("0.0", body_val)
                        btn_regen.configure(state="normal")
                    win.after(0, on_done)
                except Exception as e:
                    def on_err():
                        txt_body.delete("0.0", "end")
                        txt_body.insert("0.0", f"Error generating: {e}")
                        btn_regen.configure(state="normal")
                    win.after(0, on_err)

            threading.Thread(target=generate_worker, daemon=True).start()

        btn_regen = ctk.CTkButton(btn_bar, text="⚡ Regenerate", command=start_generation, width=110, fg_color="#1f7a1f", hover_color="#145214")
        btn_regen.pack(side="left", padx=5)

        btn_close = ctk.CTkButton(btn_bar, text="Close", command=win.destroy, width=80, fg_color="#555555", hover_color="#444444")
        btn_close.pack(side="right", padx=5)

        win.after(200, start_generation)

    def setup_log_db_tab(self):
        self.log_tree = self.create_database_tab_ui(
            self.tab_log_db, 
            lambda: self.load_matrix(self.log_tree, "Logistics_Matrix.xlsx"),
            lambda: self.clean_local_matrix("Logistics_Matrix.xlsx", self.log_tree),
            lambda: self.delete_all_entries("Logistics_Matrix.xlsx", self.log_tree),
            proposal_cmd=self.open_logistics_inquiry_window,
            mode="logistics"
        )
        self.load_matrix(self.log_tree, "Logistics_Matrix.xlsx")

    def setup_logs_tab(self):
        self.tab_logs.grid_columnconfigure(0, weight=1)
        self.tab_logs.grid_rowconfigure(0, weight=1)
        
        self.log_textbox = ctk.CTkTextbox(self.tab_logs, wrap="word")
        self.log_textbox.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        if os.path.exists("workflow_logs.txt"):
            with open("workflow_logs.txt", "r", encoding='utf-8') as f:
                self.log_textbox.insert("0.0", f.read())
                
    def log_callback(self, message):
        self.ui_queue.put((self._append_log, (message,)))
        
    def _append_log(self, message):
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        
        active_tab = self.tabview.get()
        if active_tab == "Suppliers Scraper":
            self.lbl_sup_status.configure(text=f"Status: {message[:50]}...")
        elif active_tab == "Buyers Scraper":
            self.lbl_buy_status.configure(text=f"Status: {message[:50]}...")
        elif active_tab == "Warehouses Scraper":
            self.lbl_wh_status.configure(text=f"Status: {message[:50]}...")
        elif active_tab == "Logistics Scraper":
            self.lbl_log_status.configure(text=f"Status: {message[:50]}...")
        elif active_tab == "URL Discovery":
            self.lbl_disc_status.configure(text=f"Status: {message[:50]}...")
        elif active_tab == "Product Sourcing":
            if hasattr(self, 'lbl_prod_status'):
                self.lbl_prod_status.configure(text=f"Status: {message[:50]}...")

    def setup_logistics_tab(self):
        self.tab_logistics.grid_columnconfigure(0, weight=1)
        self.tab_logistics.grid_rowconfigure(3, weight=1)
        
        criteria_text = "Logistics Context: Extracting Routes, Container Types, Services, Contact Details."
        lbl_info = ctk.CTkLabel(self.tab_logistics, text=criteria_text, font=("Arial", 12, "italic"))
        lbl_info.grid(row=0, column=0, pady=(10,0), sticky="w", padx=20)
        
        self.log_urls_textbox = ctk.CTkTextbox(self.tab_logistics, height=150)
        self.log_urls_textbox.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.log_urls_textbox.insert("0.0", "Paste Logistics URLs here (one per line)...\n")
        
        btn_frame = ctk.CTkFrame(self.tab_logistics, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        self.btn_log_start = ctk.CTkButton(btn_frame, text="Start Extraction", command=lambda: self.start_scraping("logistics"))
        self.btn_log_start.pack(side="left", padx=5)

        self.btn_log_prop = ctk.CTkButton(btn_frame, text="🌐 Quick Freight RFQ", command=lambda: self.open_url_proposal_window(mode="logistics"), fg_color="#005b96", hover_color="#003f66")
        self.btn_log_prop.pack(side="left", padx=5)
        
        self.lbl_log_status = ctk.CTkLabel(btn_frame, text="Status: Ready")
        self.lbl_log_status.pack(side="left", padx=20)
        
        self.log_output_textbox = ctk.CTkTextbox(self.tab_logistics)
        self.log_output_textbox.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")



if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()


