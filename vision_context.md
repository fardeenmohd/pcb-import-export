# Business Vision Context: Industrial Hardware, Power Electronics, and Smart Infrastructure

This document establishes the strategic sourcing framework and targeting parameters for our automated B2B procurement and supply chain discovery platform. Based on an empirical analysis of raw commercial buy leads from global importers, this blueprint defines our target niches, technical specifications, materials, HS codes, and transactional parameters.

---

## 1. Core Target Niches & Market Segments

The scraped lead data reveals five high-value, highly technical product categories. These segments represent the operational core of our target buyers:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               Target Product Universe                                  │
├──────────────────────────┬───────────────────────────┬─────────────────────────────────┤
│ Segment                  │ Key Focus Areas           │ Target Buyers                   │
├──────────────────────────┼───────────────────────────┼─────────────────────────────────┤
│ A. Metrology & Material  │ Hardness, Rheology, UTM,  │ Industrial QA, Laboratories,    │
│    Testing Instruments   │ Electrical calibration    │ Civil Engineering, Telecom      │
├──────────────────────────┼───────────────────────────┼─────────────────────────────────┤
│ B. Power Electronics &   │ VFDs, PLCs, Converters,   │ Automation integrators, Panel   │
│    Industrial Automation │ Control Panels, Gensets   │ builders, Plant operators       │
├──────────────────────────┼───────────────────────────┼─────────────────────────────────┤
│ C. Advanced Batteries &  │ LiFePO4, Sodium-Ion,      │ Robotics, Marine, E-mobility,   │
│    Energy Storage (ESS)  │ Industrial Primary Cells  │ ESS Developers, Retailers       │
├──────────────────────────┼───────────────────────────┼─────────────────────────────────┤
│ D. Electrical Wiring &   │ Infrastructure Cabling,   │ Electrical Contractors, Utility │
│    Smart Connections     │ Industrial Plugs/Sockets  │ Projects, Grid Infrastructure   │
├──────────────────────────┼───────────────────────────┼─────────────────────────────────┤
│ E. Commercial & Domestic │ Food Processing, Kettles, │ Commercial Kitchen Integrators, │
│    Electro-Thermic App.  │ Blenders, Air Fryers      │ Appliance Distributors, Retail  │
└──────────────────────────┴───────────────────────────┴─────────────────────────────────┘
```

### Segment A: Metrology, Material Testing, and Electrical Quality Control Instruments
This segment covers precise physical, structural, and electrical analysis machinery used in industrial labs, civil infrastructure, manufacturing plants, and electrical utilities.
*   **Sub-niches**:
    *   **Mechanical Strength & Hardness Testing**: Leeb rebound (Eco Tip) portable/stationary hardness testers, Universal Testing Machines (UTM) with computer control hydraulic servo systems (e.g., 100-ton capacity).
    *   **Rheology & Asphalt/Polymer Characterization**: Dynamic Shear Rheometers (DSR), Bending Beam Rheometers (BBR), and Pressure Ageing Vessels (PAV) for binder testing.
    *   **Electrical & Thermal Metrology**: Digital Multimeters, Clamp Meters, Oscilloscopes, Insulation Resistance Testers (Megohm meters), Power Analyzers, Cable Tracers, and Calibration Instruments.
    *   **Environmental & Chemical Stress Testing**: Cyclic Corrosion Test (CCT) chambers, Salt Spray chambers, and PVT (Pressure-Volume-Temperature) testing apparatus.

### Segment B: Power Electronics, Industrial Automation, and Motor Control Systems
This segment targets components and integrated assemblies that regulate, convert, and control electrical power in industrial automation, machinery, and power generation.
*   **Sub-niches**:
    *   **Motor Speed Control**: Variable Frequency Drives (VFDs), Variable Speed Drives (VSDs), AC/DC Drives, and Servo Drives.
    *   **Process Automation & Logic Control**: Programmable Logic Controllers (PLCs), Input/Output modules, Control Relays, and HMI units.
    *   **Power Distribution Panels & Switchgear**: Motor Control Center (MCC) panels, PLC panels, and utility-grade power control panels.
    *   **Power Conversion & Generation Control**: AC-DC Switch Mode Power Supplies (SMPS) (e.g., DIN-rail / modular systems), Auto Mains Failure (AMF) control modules (e.g., Deep Sea Electronics DSE7320 series), and high-output industrial AC/DC motors.
    *   **Building & Infrastructure Automation**: Centralized lighting controllers, automated dimming modules, and smart building energy management systems.

### Segment C: High-Capacity Electrochemical Cells and Energy Storage Solutions (ESS)
This segment focuses on advanced chemistry battery packs, individual cells, and micro-grid storage solutions, alongside high-volume commercial primary cells.
*   **Sub-niches**:
    *   **Lithium-Ion / LiFePO4 Packs**: Heavy-duty custom voltage configurations (22.2V, 44.4V, 51.2V) from 15Ah to 100Ah+, designed for Unmanned Ground Vehicles (UGVs), AGVs, robotic systems, electric scooters, and IP67 waterproof marine trolling/trolling motors.
    *   **Emerging Chemistries**: Sodium-Ion battery packs, portable power stations, and solid-state battery cells for next-generation mobile applications.
    *   **Primary Alkaline/Lithium Button & Cylindrical Cells**: High-volume wholesale consumer and industrial battery formats (AA, AAA, C, D, 9V, A76, LR44 button cells), with a focus on tier-one brands (e.g., Duracell, Toshiba) or high-quality OEM white labels.

### Segment D: Electrical Wiring Systems, Infrastructure Cables, and Intelligent Electrical Fittings
This segment focuses on power transmission cables, signal/control cables, and the industrial/residential wiring accessories required to safely connect and route them.
*   **Sub-niches**:
    *   **Bulk Power & Control Cabling**: Low and medium voltage copper and aluminum conductor cables, XLPE and PVC insulated options, control wires, optical fiber cables, and specialized heating cables.
    *   **Industrial Connections & Wiring Accessories**: SAA approved plugs (56 Series), heavy-duty IP44/IP67 industrial sockets (CEE/IEC standards), EV charging plugs (5-pin, 10A–32A), cable glands, power cords, patch cords, and terminal connectors.
    *   **Smart Electrical Hardware**: WiFi-enabled smart home sockets, energy-monitoring plugs (e.g., 20A EU standard outlets with voice/app control), switches, and intelligent distribution boxes.

### Segment E: Specialized Electro-Thermic and Motor-Driven Domestic/Commercial Appliances
This segment addresses commercial processing machinery alongside bulk consumer kitchen electrics.
*   **Sub-niches**:
    *   **Industrial/Commercial Food Processing**: Screw-type fruit/vegetable juicers (0.5t–2.5t/h capacity, 1.1kW+ motors), commercial mango/tomato pureeing systems, and professional-grade stainless steel beverage extractors.
    *   **Small Domestic Appliances (SDA) - Bulk Import**: Electric kettles, countertop blenders, hand mixers, air fryers, induction cooktops, and sandwich makers, primarily sourced for retail and hospitality distribution.

---

## 2. Technical Taxonomy & Sourcing Parameters

To guide our automated systems, scraping agents, and matching pipelines, we use a structured database of targeted keywords, materials, standard industrial HS codes, and transactional profiles.

### 2.1 Keyword & Technical Concept Database
Our platform monitors and extracts opportunities containing the following high-intent keywords:

*   **Metrology & Quality Assurance**: `"Eco Tip"`, `"Hardness Tester"`, `"Dynamic Shear Rheometer"`, `"MCR 92"`, `"Bending Beam Rheometer"`, `"Pressure Ageing Vessel"`, `"Salt Spray"`, `"CCT Chamber"`, `"UTM WAW-1000D"`, `"Digital Multimeter"`, `"Clamp Meter"`, `"Megohm Meter"`, `"Insulation Tester"`, `"Calibration Instrument"`.
*   **Automation & Drive Systems**: `"Variable Frequency Drive"`, `"VFD"`, `"Variable Speed Drive"`, `"VSD"`, `"AC Drive"`, `"Servo Drive"`, `"DSE7320"`, `"Generator Control Module"`, `"PLC Component"`, `"MCC Panel"`, `"Control Panel"`, `"AC-DC Converter"`, `"Lighting Controller"`, `"Dimming Module"`.
*   **Energy Storage & Battery Tech**: `"Li-Ion Battery Pack"`, `"LiFePO4"`, `"Sodium-Ion Battery"`, `"Sodium Power Bank"`, `"18650"`, `"21700"`, `"Marine Battery IP67"`, `"LR44"`, `"A76"`, `"Alkaline Button Battery"`, `"Solid-State Battery"`.
*   **Electrical Infrastructure**: `"Power Cable"`, `"Control Cable"`, `"XLPE Cable"`, `"Copper Conductor"`, `"Industrial Plug"`, `"IP44 Socket"`, `"56 Series SAA Plug"`, `"EV Charger Plug"`, `"Cable Gland"`, `"WiFi Smart Socket 20A"`.
*   **Industrial Processing & Appliances**: `"Screw Juicer"`, `"Pureeing System"`, `"Fruit Processing Plant"`, `"Electric Kettle"`, `"Air Fryer 1800W"`, `"Induction Cooker"`.

### 2.2 Material & Component Taxonomy
We prioritize leads specifying the following materials:
*   **Metals**: Food-Grade Stainless Steel (SUS304, SUS316) for processing machinery and enclosures; Electrolytic Tough Pitch (ETP) Copper and Aluminum for cable conductors and busbars; Mild Steel with protective powder coatings for industrial control panels.
*   **Engineering Plastics**: High-impact ABS Plastic, Flame-Retardant Polycarbonate (PC) for electrical enclosures, plugs, and instrument housings; Cross-linked Polyethylene (XLPE) and Polyvinyl Chloride (PVC) for high-dielectric wiring insulation.
*   **Electronic Hardware**: Silicon semiconductor chips, printed circuit board assemblies (PCBAs), terminal blocks, relays, and heavy-duty contactors.

### 2.3 Reference HS Codes
Our scraping agents use the following Harmonized System (HS) codes to filter, categorize, and validate commercial import intent:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 HS Code Directory                                      │
├──────────┬─────────────────────────────────────────────────────────────────────────────┤
│ HS Code  │ Description                                                                 │
├──────────┼─────────────────────────────────────────────────────────────────────────────┤
│ 9031.80  │ Other measuring or checking instruments, appliances and machines            │
│ 9030.33  │ Instruments & apparatus for measuring or checking voltage, current, resistance│
│ 9024.10  │ Machines & appliances for testing hardness, strength, elasticity of metals  │
│ 8504.40  │ Static converters (Inverters, Rectifiers, VFDs, VSDs, SMPS)                  │
│ 8537.10  │ Boards, panels, consoles, and bases equipped with electrical control gear   │
│ 8507.60  │ Lithium-ion accumulators (including battery packs)                          │
│ 8507.80  │ Other electric accumulators (including Sodium-Ion, Solid-State)              │
│ 8506.00  │ Primary cells and primary batteries (Alkaline, Button Cells, Duracell)       │
│ 8544.49  │ Other electric conductors, for a voltage not exceeding 1,000 V (Unfitted)   │
│ 8544.42  │ Electric conductors, for a voltage <= 1,000 V, fitted with connectors        │
│ 8536.69  │ Plugs and sockets for a voltage not exceeding 1,000 V                       │
│ 8536.90  │ Other electrical apparatus for switching or protecting electrical circuits │
│ 8435.10  │ Presses, crushers and similar machinery used in juice/beverage manufacture  │
│ 8516.79  │ Other electro-thermic domestic appliances (Kettles, Air Fryers, Toasters)   │
│ 8509.40  │ Electromechanical domestic food grinders, mixers, and fruit juice extractors│
└──────────┴─────────────────────────────────────────────────────────────────────────────┘
```

### 2.4 Lead Qualification & Transactional Profiles
To ensure leads are commercially viable and match our target supplier network, they must meet the following criteria:

*   **Transactional Quantities**:
    *   *High-Value Capital Equipment*: 1 to 5 units for initial orders, with clear paths to ongoing support (e.g., UTMs, DSR rheometers, large industrial juice presses).
    *   *Consumable Components / Industrial Parts*: Minimum Order Quantities (MOQs) starting at 100 to 10,000 units (e.g., genset controllers, smart plugs, primary batteries).
    *   *Bulk Commodities & General Goods*: Minimum volumes of 1 Less-than-Container Load (LCL) up to multiple 20-foot or 40-foot Full Container Loads (FCL).
*   **Payment & Shipping Standards**:
    *   *Sourcing Geographies*: Worldwide open sourcing, with a high concentration of demand in the Middle East (Saudi Arabia, UAE, Qatar, Kuwait, Oman), Asia-Pacific (Singapore, Australia, Philippines, Vietnam, Indonesia), Europe (Germany, Italy, France), and North America (Canada).
    *   *Payment Terms*: Strict business-to-business payment methods, prioritizing Letters of Credit (L/C, LC 30-60 Days), Telegraphic Transfers (T/T, e.g., 30% advance / 70% against documents), or Bank Transfers.
    *   *Shipping Terms*: Incoterms 2020 rules: CIF (Cost, Insurance, and Freight), FOB (Free on Board), and CNF/CFR (Cost and Freight) are mandatory.

---

## 3. Scraper Agent System Prompt

Inject the following XML-formatted block directly into the LLM orchestration layer of the Scraper Agent. This prompt instructs the agent to systematically identify, score, extract, and structure leads that match this business context.

```xml
<system_prompt>
  <agent_role>
    You are an elite, autonomous B2B Procurement Intelligence &amp; Data Extraction Agent. Your primary objective is to monitor, parse, qualify, and structure "Buy Leads" and "Requests for Quotations" (RFQs) from B2B trade platforms, filtering for specific high-value industrial hardware, power electronics, advanced energy storage, and smart electrical infrastructure niches.
  </agent_role>

  <target_ontology_and_taxonomy>
    You must capture leads that fall into one of the following five core segments:
    
    1. METROLOGY &amp; MATERIAL TESTING INSTRUMENTS (Segment A)
       - Keywords: Portable/rebound hardness testers, Eco Tip, Leeb, Universal Testing Machines (UTM), Dynamic Shear Rheometers (DSR), Bending Beam Rheometers (BBR), Pressure Ageing Vessels (PAV), cyclic corrosion test chambers, salt spray testers, digital multimeters, insulation resistance testers, megohmmeters, clamp meters, oscilloscopes.
       - Target HS Codes: 903180, 903033, 902410, 903084.
       
    2. POWER ELECTRONICS &amp; INDUSTRIAL AUTOMATION (Segment B)
       - Keywords: Variable Frequency Drives (VFD), Variable Speed Drives (VSD), AC/DC speed controllers, servo drives, PLC modules, I/O boards, automation control panels, MCC panels, AC-DC switch-mode converters, Deep Sea generator control modules (DSE7320), centralized lighting controllers, dimming modules.
       - Target HS Codes: 850440, 853710, 850140, 850131.

    3. ADVANCED BATTERIES &amp; ENERGY STORAGE (Segment C)
       - Keywords: Rechargeable Lithium-Ion battery packs, LiFePO4 cells, Sodium-Ion batteries/power stations, solid-state batteries, high-capacity marine trolling batteries (IP67), customized packs (22.2V, 44.4V, 51.2V), wholesale primary cells (AA, AAA, C, D, 9V, A76, LR44 button cells).
       - Target HS Codes: 850760, 850780, 850600, 850680.

    4. ELECTRICAL WIRING SYSTEMS &amp; SMART CONNECTIONS (Segment D)
       - Keywords: Low/medium voltage power cables, control cables, XLPE/PVC insulation, copper/aluminum conductor wires, industrial plugs/sockets (CEE/IEC IP44/IP67), 56 Series SAA plugs, EV charger plugs (5-pin, 10A-32A), WiFi smart home plugs (20A EU), cable glands, power cords.
       - Target HS Codes: 854449, 854442, 853669, 853690.

    5. COMMERCIAL PROCESSING &amp; ELECTRO-THERMIC APPLIANCES (Segment E)
       - Keywords: Industrial screw juice extractors, commercial mango/tomato pureeing systems, wholesale food preparation appliances (blenders, air fryers, induction cookers, electric kettles).
       - Target HS Codes: 843510, 851679, 850940, 851660.
  </target_ontology_and_taxonomy>

  <exclusion_filters>
    Explicitly ignore and reject leads that contain or are related to:
    - Raw agricultural commodities (unless specifically processed into the heavy machinery machinery listed above).
    - Textiles, apparel, apparel hardware, and fast-moving consumer soft goods.
    - Raw chemicals, bulk minerals, polymers, and fuels (unless packaged specifically as a battery electrolyte or structural enclosure material).
    - General consumer scrap, metal recycling waste, or consumer-grade toys and low-complexity plastic housewares.
  </exclusion_filters>

  <data_extraction_rules>
    For every candidate lead processed, you must extract and compile a structured JSON object with the following schema:
    
    - "lead_id": Generate a deterministic string ID based on platform text.
    - "product_category": Map directly to one of: "Metrology &amp; Testing", "Power Electronics &amp; Automation", "Advanced Batteries", "Electrical Infrastructure", or "Processing &amp; Appliances".
    - "product_name_raw": The raw product title listed by the buyer.
    - "specifications_parsed": A key-value map of all technical specs, including voltages, capacities, sizes, and model numbers (e.g., "MCR 92", "DSE7320", "22.2V").
    - "hs_code_detected": List the primary 6-digit HS code if stated or confidently inferred.
    - "materials": List extracted materials (e.g., "Stainless Steel", "ABS", "Copper").
    - "buyer_profile": {
        "contact_name": Extract the contact person,
        "country": Destination/buyer country,
        "destination_port": Stated port of entry,
        "is_verified": Boolean (true if "VERIFIED" or "GOLD" indicator is in raw text)
      }
    - "transactional_details": {
        "quantity_required": Store quantity along with units (e.g., "1 Twenty-Foot Container", "100 Units"),
        "payment_terms": Stated terms (e.g., "LC", "T/T 30/70", "Bank Transfer"),
        "shipping_terms": Incoterms (e.g., "CIF", "FOB", "CFR")
      }
    - "lead_quality_score": Calculate an integer score from 1 (lowest) to 5 (highest) based on:
        - 5: High verification, concrete technical specifications, clear volumes (e.g., FCL or high unit numbers), and standard payment terms.
        - 3: Moderate detail, generic brand request, missing some technical specifications.
        - 1: Extremely vague requests (e.g., "Testing Machine" with no specs), suspicious payment terms, or lack of commercial intent.
  </data_extraction_rules>

  <processing_instruction>
    Ensure your parsed output is strictly compliant with the schema. Do not generate conversational filler or markdown notes outside of the structured JSON block. Proceed with parsing and analyzing the input stream.
  </processing_instruction>
</system_prompt>
```