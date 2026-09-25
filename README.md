# NCR PCB Supplier Discovery Agent

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-blueviolet.svg)
![Playwright](https://img.shields.io/badge/Automation-Playwright-green.svg)
![Gemini API](https://img.shields.io/badge/LLM-Gemini_1.5_Flash-orange.svg)

## Project Overview
This project is an automated Python pipeline and local desktop GUI application designed to scrape, analyze, and qualify Printed Circuit Board (PCB) and PCBA manufacturers in the Delhi-NCR region.

The goal is to generate a highly structured capability matrix of Indian suppliers to match with mid-tier international buyers. The agent bypasses basic anti-bot protections, extracts raw text from corporate B2B websites, and uses the Gemini API via Pydantic structured outputs to extract technical specifications. All operations are managed via a modern local GUI with realtime logging, progress tracking, and integrated Excel data visualization.

## Technology Stack

### 🎨 Frontend (GUI)
* **[CustomTkinter](https://customtkinter.tomschimansky.com/)**: Used to build a modern, responsive local desktop interface with built-in dark mode and premium aesthetics.
* **Tkinter Treeview**: Used for displaying the Supplier Matrix directly inside the app natively in a spreadsheet-like grid.

### ⚙️ Backend (Scraping & Data Processing)
* **[Playwright](https://playwright.dev/python/)**: Used in headless mode to programmatically navigate websites, wait for dynamic DOM content, and extract HTML.
* **[Playwright Stealth](https://github.com/Atelier-Nunn/playwright-stealth)**: Applies evasions to the Playwright browser context to successfully bypass basic anti-bot protections like Cloudflare.
* **[BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)**: Used to parse the DOM and strip out unnecessary tokens (`<script>`, `<style>`, `<nav>`, `<header>`) to reduce LLM context windows and costs.
* **[Pandas](https://pandas.pydata.org/) & OpenPyXL**: Used to flatten the Pydantic schemas and append structured supplier data to local Excel (`.xlsx`) files.
* **DuckDuckGo-Search**: Used to programmatically discover targeted URLs (e.g. from B2B Yellow Pages like IndiaMart and TradeIndia) without requiring paid search APIs.
* **Concurrent Futures (Threading)**: The pipeline uses a `ThreadPoolExecutor` to process multiple URLs in parallel on background threads to ensure the GUI remains responsive.

### 🧠 AI & LLM Extraction
* **[Google GenAI SDK](https://ai.google.dev/docs)**: Integrates with the Gemini API to analyze the raw, unstructured scraped text.
* **[Pydantic](https://docs.pydantic.dev/latest/)**: Enforces strict JSON Schema requirements on the LLM's output. The pipeline extracts booleans and arrays for technical specs (e.g., HDI capabilities, layer counts, surface finishes, certifications, MOQs).
* **Gemini Flash-Lite Model**: Configured to use the cost-effective `gemini-flash-lite-latest` model (compatible with Google AI Studio Free Tier).

---

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/fardeenmohd/pcb-import-export.git
   cd pcb-import-export
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows
   .\venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Set up API Keys:**
   Create a `.env` file in the root directory and add your Google Gemini API key:
   ```env
   GEMINI_API_KEY="your_google_ai_studio_api_key_here"
   ```

5. **Run the Application:**
   You can either run the Python file directly:
   ```bash
   python main.py
   ```
   *Or use the provided `Run_Scraper_App.bat` script on Windows to launch it without a persistent console window.*
