# Global PCB Intelligence Agent

An automated, AI-powered desktop application built to map the global supply and demand chain for Printed Circuit Boards (PCBs) and electronic components. 

The application discovers, scrapes, and intelligently extracts complex capabilities from **Indian PCB Suppliers** (supply side) and international **Hardware OEMs/Startups** (demand side) to build a structured, actionable capability matrix.

## 🚀 Features

- **Dual-Strategy URL Discovery Engine**: 
  - **Suppliers Mode**: Automatically targets Indian directories (IndiaMart, TradeIndia, JustDial) and filters specifically for PCB manufacturers, component distributors, and assembly services.
  - **Buyers Mode**: Targets international hardware OEMs, IoT startups, and medical/automotive electronic brands across strategic offshore regions (Australia, Poland, Netherlands, Malaysia, USA).
  - **Smart Suggestions**: Auto-generates high-converting search queries based on selected strategies and geographic regions.
- **AI-Powered Data Extraction**: Utilizes **Google Gemini 1.5 Flash Lite** to read raw website text and strictly extract Pydantic-validated JSON schemas (Company Name, Layer Counts, Surface Finishes, Industry, Certifications, Contact Info, etc.).
- **Headless Stealth Scraping**: Uses **Playwright Stealth** to bypass anti-bot protections and dynamically render JavaScript-heavy company websites.
- **Thread-Safe GUI**: A sleek, modern dashboard built with **CustomTkinter**, featuring real-time logging, interactive data grids, and async background workers to prevent UI freezing.
- **Smart Matrix Management**: Automatically syncs scraped data to local Excel files (`Suppliers_Matrix.xlsx` and `Buyers_Matrix.xlsx`). Features a "Clean Matrix" engine that intelligently scrubs failed scrapes or empty company profiles.

## 🛠️ Technology Stack

- **Frontend / GUI**: `customtkinter`, `tkinter.ttk` (Thread-safe UI polling via queues)
- **Web Scraping**: `playwright`, `playwright-stealth`, `beautifulsoup4`
- **Search Engine API**: `duckduckgo-search` (`ddgs`)
- **AI & LLM Integration**: `google-genai` (Gemini SDK), `pydantic`
- **Data Persistence**: `pandas`, `openpyxl` (Excel)
- **Concurrency**: `concurrent.futures.ThreadPoolExecutor`, `threading`, `queue`

## ⚙️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/fardeenmohd/pcb-import-export.git
   cd pcb-import-export
   ```

2. **Set up a virtual environment (Optional but recommended):**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory and add your Google Gemini API key:
   ```env
   GEMINI_API_KEY=your_google_ai_studio_api_key_here
   ```

## 🖥️ Usage

You can launch the GUI without keeping a persistent console window open by running the provided batch script:

```bash
Run_Scraper_App.bat
```

*(This executes the application via `pythonw.exe` to suppress the terminal).*

### General Workflow:
1. **URL Discovery Tab**: Select either Suppliers or Buyers, pick a region, and hit "Discover URLs".
2. **Scraper Tabs**: Copy the discovered URLs, paste them into the respective Scraper tab (Supplier or Buyer), and click Start. The background agent will invisibly scrape and analyze the websites.
3. **Database Tabs**: Navigate to the Database tabs to view your successfully extracted leads in a clean grid format. Click "Sync" to refresh, or "Clean Matrix" to automatically delete junk data.

## 🧠 Extracted Schemas

**Supplier Capabilities Extracted:**
- PCB Manufacturing vs Assembly
- Max Layer Count
- Materials (FR-4, MCPCB, Rogers, Flexible)
- Advanced Tech (HDI, Blind/Buried Vias, BGA)
- Certifications (ISO 9001, ISO 13485, IATF 16949)
- Contact Info (Emails, Phones)

**Buyer Intelligence Extracted:**
- Hardware OEM Verification (Ensures they build physical products)
- Target Products (e.g., PLCs, EV Chargers, Medical devices)
- Industry Classification
- Estimated Company Size
- Contact Info & Locations

---
*Built with Antigravity AI*
