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

from logger_util import setup_logger
from processor import run_pipeline, run_buyer_pipeline, clean_matrix

# Load environment variables
load_dotenv()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Global PCB Intelligence Agent")
        self.geometry("1100x800")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.ui_queue = queue.Queue()
        
        self.logger = setup_logger(self.log_callback)
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        self.tab_discovery = self.tabview.add("URL Discovery")
        self.tab_suppliers = self.tabview.add("Suppliers Scraper")
        self.tab_sup_db = self.tabview.add("Suppliers Database")
        self.tab_buyers = self.tabview.add("Buyers Scraper")
        self.tab_buy_db = self.tabview.add("Buyers Database")
        self.tab_logistics = self.tabview.add("Logistics Scraper")
        self.tab_log_db = self.tabview.add("Logistics Database")
        self.tab_logs = self.tabview.add("Agent Logs")
        
        self.setup_discovery_tab()
        self.setup_suppliers_tab()
        self.setup_sup_db_tab()
        self.setup_buyers_tab()
        self.setup_buy_db_tab()
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
        
        self.strategy_var = ctk.StringVar(value="Buyers")
        self.strategy_dropdown = ctk.CTkOptionMenu(
            control_frame, 
            values=["Suppliers", "Buyers", "Logistics"],
            variable=self.strategy_var, width=120,
            command=self.on_strategy_change
        )
        self.strategy_dropdown.pack(side="left", padx=5)

        self.region_var = ctk.StringVar(value="Global (wt-wt)")
        self.region_dropdown = ctk.CTkOptionMenu(
            control_frame, 
            values=['Worldwide (wt-wt)', 'Australia (au-en)', 'Poland (pl-pl)', 'Netherlands (nl-nl)', 'Malaysia (my-en)', 'USA (us-en)', 'Canada (ca-en)', 'Germany (de-de)', 'France (fr-fr)', 'United Kingdom (uk-en)', 'UAE (ae-en)', 'Saudi Arabia (sa-ar)', 'Qatar (qa-en)', 'Kuwait (kw-en)', 'Oman (om-en)', 'Bahrain (bh-en)', 'Singapore (sg-en)', 'Vietnam (vn-en)', 'Indonesia (id-en)', 'Philippines (ph-en)', 'Thailand (th-en)', 'South Korea (kr-kr)', 'China (cn-zh)', 'India (in-en)', 'South Africa (za-en)', 'Romania (ro-ro)', 'Finland (fi-fi)', 'Albania (al-al)', 'Moldova (md-ro)'],
            variable=self.region_var, width=120
        )
        self.region_dropdown.pack(side="left", padx=5)
        
        self.query_entry = ctk.CTkTextbox(control_frame, width=350, height=60, wrap="word")
        self.query_entry.insert("0.0", "Enter base query...")
        self.query_entry.pack(side="left", padx=10, pady=10)
        
        self.btn_suggest = ctk.CTkButton(control_frame, text="💡 Suggest", width=70, command=self.suggest_query, fg_color="#4B0082", hover_color="#300050")
        self.btn_suggest.pack(side="left", padx=5)
        
        self.results_slider = ctk.CTkSlider(control_frame, from_=5, to=50, number_of_steps=9, width=100)
        self.results_slider.set(15)
        self.results_slider.pack(side="left", padx=10)
        
        self.btn_search = ctk.CTkButton(control_frame, text="Discover URLs", command=self.start_discovery)
        self.btn_search.pack(side="left", padx=10)
        
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
        
        lbl = ctk.CTkLabel(self.tab_discovery, text="Compare raw search engine results with AI-vetted high-quality URLs side-by-side:", text_color="gray")
        lbl.grid(row=2, column=0, padx=10, sticky="w")
        
        results_container = ctk.CTkFrame(self.tab_discovery, fg_color="transparent")
        results_container.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")
        results_container.grid_columnconfigure(0, weight=1)
        results_container.grid_columnconfigure(1, weight=1)
        results_container.grid_rowconfigure(1, weight=1)
        
        # Left column: Raw Search Results
        self.lbl_raw_urls = ctk.CTkLabel(results_container, text="🌐 Raw Search Results (DuckDuckGo):", font=("Arial", 12, "bold"))
        self.lbl_raw_urls.grid(row=0, column=0, padx=(0, 5), pady=(0, 5), sticky="w")
        
        self.raw_urls_textbox = ctk.CTkTextbox(results_container, wrap="none")
        self.raw_urls_textbox.grid(row=1, column=0, padx=(0, 5), pady=0, sticky="nsew")
        
        # Right column: High-Quality Filtered URLs
        self.lbl_hq_urls = ctk.CTkLabel(results_container, text="⭐ High-Quality URLs (AI Filtered):", font=("Arial", 12, "bold"))
        self.lbl_hq_urls.grid(row=0, column=1, padx=(5, 0), pady=(0, 5), sticky="w")
        
        self.discovery_textbox = ctk.CTkTextbox(results_container, wrap="none")
        self.discovery_textbox.grid(row=1, column=1, padx=(5, 0), pady=0, sticky="nsew")

    def on_strategy_change(self, choice):
        if choice == "Suppliers":
            self.region_dropdown.configure(state="disabled")
            self.btn_suggest.configure(state="normal")
        elif choice == "Logistics":
            self.region_dropdown.configure(state="normal")
            self.btn_suggest.configure(state="disabled")
            self.query_entry.delete("0.0", "end")
            dest = self.region_var.get().split(" (")[0]
            if "Worldwide" in dest or "Global" in dest:
                dest = "worldwide"
            self.query_entry.insert("0.0", f"freight forwarders India to {dest} container shipping")
        else:
            self.region_dropdown.configure(state="normal")
            self.btn_suggest.configure(state="normal")

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
                target_desc = "MANUFACTURERS and FACTORIES across ALL of India"
            elif strategy == "Logistics":
                dest = region.split(" (")[0]
                if "Worldwide" in dest or "Global" in dest:
                    dest = "worldwide"
                target_desc = f"freight forwarders or shipping lines from India to {dest}"
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
        self.query_entry.delete("0.0", "end")
        self.query_entry.insert("0.0", "Generating AI suggestion...")
        threading.Thread(target=self.suggest_query_thread, args=(strategy, region), daemon=True).start()

    def suggest_query_thread(self, strategy, region):
        try:
            import random
            
            # True randomization: Read the context file, extract all product bullet points, pick ONE randomly.
            product_niche = "Electrical Components"
            try:
                with open("vision_context_v2.md", "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    # Grab product description lines
                    product_lines = [line.strip() for line in lines if line.startswith("* **") and ":" in line]
                    # Cut off the list before the 'Compliance' section begins
                    product_lines = product_lines[:22] 
                    if product_lines:
                        product_niche = random.choice(product_lines)
            except Exception as e:
                self.logger.error(f"Failed to read context for randomization: {e}")

            if strategy == "Suppliers":
                prompt = f"""You are an elite B2B sourcing expert.
Generate a single, highly specific DuckDuckGo search query to find MANUFACTURERS and FACTORIES across ALL of India for the following specific product niche:

{product_niche}

Include terms like "manufacturer India" or "factory India". Do not restrict to Delhi NCR.
Do not include any quotes, markdown, or explanations. Return ONLY the raw query string.
"""
            else:
                region_name = region.split(" (")[0]
                if "Worldwide" in region_name or "Global" in region_name:
                    region_target = "globally"
                else:
                    region_target = f"in {region_name}"
                    
                prompt = f"""You are an elite B2B sourcing expert.
Generate a single, highly specific DuckDuckGo search query to find actual B2B BUYERS, DISTRIBUTORS, or OEMs for the following specific product niche {region_target}:

{product_niche}

The query should look for companies that buy, import, or distribute this product (e.g. "distributors", "importers", "buyers").
Do not include any quotes, markdown, or explanations. Return ONLY the raw query string.
"""
            
            from llm_fallback import generate_with_fallback
            response = generate_with_fallback(prompt, logger=self.logger)
            query = response.text.strip().replace('"', '').replace('\n', '')
            self.ui_queue.put((self.on_suggest_complete, (query,)))
        except Exception as e:
            self.logger.error(f"Suggest failed: {e}")
            self.ui_queue.put((self.on_suggest_complete, ("Error generating query",)))
            
    def on_suggest_complete(self, query):
        self.query_entry.delete("0.0", "end")
        self.query_entry.insert("0.0", query)
        self.btn_suggest.configure(state="normal")

    def start_discovery(self):
        query = self.query_entry.get("0.0", "end").strip()
        if query == "Enter base query...":
            query = ""
        if not query:
            return
            
        strategy = self.strategy_var.get()
        if strategy == "Suppliers":
            query += " (site:indiamart.com OR site:tradeindia.com OR site:justdial.com OR site:exportersindia.com)"
            region_code = "in-en"
        elif strategy == "Logistics":
            region_code = "in-en"
        else:
            query += " -\"PCB manufacturer\" -\"PCB assembly\" -\"printed circuit board\""
            region_code = self.region_var.get().split(" (")[1].replace(")", "")
            
        max_results = int(self.results_slider.get())
        
        self.btn_search.configure(state="disabled")
        self.lbl_disc_status.configure(text="Status: Searching...")
        self.raw_urls_textbox.delete("0.0", "end")
        self.discovery_textbox.delete("0.0", "end")
        self.lbl_raw_urls.configure(text="🌐 Raw Search Results (DuckDuckGo):")
        self.lbl_hq_urls.configure(text="⭐ High-Quality URLs (AI Filtered):")
        
        threading.Thread(target=self.discover_urls_thread, args=(query, max_results, region_code), daemon=True).start()

    def discover_urls_thread(self, query, max_results, region_code):
        try:
            self.logger.info(f"Searching DuckDuckGo for: {query} [Region: {region_code}]")
            with DDGS() as ddgs:
                results = list(ddgs.text(query, region=region_code, max_results=max_results))
            
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
            elif strategy == "Suppliers":
                filter_goal = "Manufacturers across all of India (nationwide) of Electrical Components, Cables, Switchgear, HVAC Parts, Batteries, Generators, LED Lighting, Appliances, or Testing Equipment. KEEP directories like IndiaMart or TradeIndia if they lead to suppliers."
            else:
                filter_goal = "Actual company websites for buyers/OEMs of Electrical Components, Cables, Switchgear, HVAC Parts, Batteries, Generators, LED Lighting, Appliances, or Testing Equipment. REMOVE news articles, Wikipedia, Amazon, PDFs, and generic directories."
                
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
            self.discovery_textbox.insert("end", f"Error: {error}\n")
        else:
            self.lbl_disc_status.configure(text=f"Status: Found {len(urls)} High-Quality ({len(raw_urls)} Raw)")
            self.raw_urls_textbox.delete("0.0", "end")
            if raw_urls:
                self.raw_urls_textbox.insert("end", "\n".join(raw_urls) + "\n")
            self.lbl_raw_urls.configure(text=f"🌐 Raw Search Results ({len(raw_urls)}):")
            
            self.discovery_textbox.delete("0.0", "end")
            if urls:
                self.discovery_textbox.insert("end", "\n".join(urls) + "\n")
            self.lbl_hq_urls.configure(text=f"⭐ High-Quality URLs ({len(urls)}):")

    def setup_suppliers_tab(self):
        self.tab_suppliers.grid_columnconfigure(0, weight=1)
        self.tab_suppliers.grid_rowconfigure(3, weight=1)
        
        criteria_text = "Supplier Context: Extracting PCB Manufacturing Services, Layers, Finishes, Certifications."
        lbl_criteria = ctk.CTkLabel(self.tab_suppliers, text=criteria_text, font=("Arial", 12, "bold"))
        lbl_criteria.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.sup_urls_textbox = ctk.CTkTextbox(self.tab_suppliers, height=80)
        self.sup_urls_textbox.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.sup_urls_textbox.insert("0.0", "https://www.sahasraelectronics.com\n")
        
        control_frame = ctk.CTkFrame(self.tab_suppliers)
        control_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        self.btn_sup_start = ctk.CTkButton(control_frame, text="Start Supplier Scraping", command=lambda: self.start_scraping("supplier"))
        self.btn_sup_start.pack(side="left", padx=10)
        
        self.lbl_sup_status = ctk.CTkLabel(control_frame, text="Status: Idle", text_color="gray")
        self.lbl_sup_status.pack(side="left", padx=10)
        
        self.sup_output_textbox = ctk.CTkTextbox(self.tab_suppliers, wrap="none")
        self.sup_output_textbox.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")

    def setup_buyers_tab(self):
        self.tab_buyers.grid_columnconfigure(0, weight=1)
        self.tab_buyers.grid_rowconfigure(3, weight=1)
        
        criteria_text = "Buyer Context: Extracting Target Products, Industry, Size, and filtering for true OEMs."
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

    def create_database_tab_ui(self, tab, sync_cmd, clean_cmd, delete_all_cmd, proposal_cmd=None):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=0, column=0, pady=10, padx=10, sticky="w")
        
        btn_sync = ctk.CTkButton(btn_frame, text="Sync / Load Matrix", command=sync_cmd)
        btn_sync.pack(side="left", padx=(0, 10))
        
        if proposal_cmd:
            btn_prop = ctk.CTkButton(btn_frame, text="📝 Create Proposal", command=proposal_cmd, fg_color="#1f7a1f", hover_color="#145214")
            btn_prop.pack(side="left", padx=(0, 10))

            btn_url_prop = ctk.CTkButton(btn_frame, text="🌐 Proposal from URL", command=self.open_url_proposal_window, fg_color="#005b96", hover_color="#003f66")
            btn_url_prop.pack(side="left", padx=(0, 10))

        btn_clean = ctk.CTkButton(btn_frame, text="Clean Matrix", command=clean_cmd, fg_color="#b30000", hover_color="#800000")
        btn_clean.pack(side="left")
        
        btn_delete_all = ctk.CTkButton(btn_frame, text="Delete All Entries", command=delete_all_cmd, fg_color="#660000", hover_color="#4d0000")
        btn_delete_all.pack(side="left", padx=10)
        
        frame = ctk.CTkFrame(tab)
        frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
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

        if proposal_cmd:
            def on_tree_click(event):
                region = tree.identify("region", event.x, event.y)
                if region == "cell":
                    col = tree.identify_column(event.x)
                    if col == "#1":
                        item = tree.identify_row(event.y)
                        if item:
                            tree.selection_set(item)
                            proposal_cmd()
            tree.bind("<ButtonRelease-1>", on_tree_click)
            tree.bind("<Double-1>", lambda event: proposal_cmd())

        return tree

    def setup_sup_db_tab(self):
        self.sup_tree = self.create_database_tab_ui(
            self.tab_sup_db, 
            lambda: self.load_matrix(self.sup_tree, "Suppliers_Matrix.xlsx"),
            lambda: self.clean_local_matrix("Suppliers_Matrix.xlsx", self.sup_tree),
            lambda: self.delete_all_entries("Suppliers_Matrix.xlsx", self.sup_tree)
        )
        
    def setup_buy_db_tab(self):
        self.buy_tree = self.create_database_tab_ui(
            self.tab_buy_db, 
            lambda: self.load_matrix(self.buy_tree, "Buyers_Matrix.xlsx"),
            lambda: self.clean_local_matrix("Buyers_Matrix.xlsx", self.buy_tree),
            lambda: self.delete_all_entries("Buyers_Matrix.xlsx", self.buy_tree),
            proposal_cmd=self.open_proposal_window
        )

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

        win = ctk.CTkToplevel(self)
        win.title(f"Trade Proposal - {company_name}")
        win.geometry("760x640")
        win.attributes("-topmost", True)
        win.focus_set()

        header_frame = ctk.CTkFrame(win, fg_color="#1f232a", corner_radius=8)
        header_frame.pack(fill="x", padx=15, pady=(15, 5))

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

        txt_proposal = ctk.CTkTextbox(win, wrap="word", font=("Arial", 12))
        txt_proposal.pack(fill="both", expand=True, padx=15, pady=10)

        btn_bar = ctk.CTkFrame(win, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(5, 15))

        def copy_proposal():
            self.clipboard_clear()
            self.clipboard_append(txt_proposal.get("0.0", "end").strip())
            btn_copy.configure(text="Copied! ✅")
            win.after(2000, lambda: btn_copy.configure(text="📋 Copy Proposal"))

        btn_copy = ctk.CTkButton(btn_bar, text="📋 Copy Proposal", command=copy_proposal, width=140, fg_color="#1f7a1f", hover_color="#145214")
        btn_copy.pack(side="left", padx=5)

        def start_generation():
            txt_proposal.delete("0.0", "end")
            txt_proposal.insert("0.0", "⏳ Generating personalized commercial proposal using Gemini AI...\nPlease wait a few seconds.")
            btn_regen.configure(state="disabled")

            def generate_worker():
                try:
                    from llm_fallback import generate_with_fallback
                    prompt = f"""You are an elite international trade and export business executive writing a formal B2B commercial export proposal.

Company Details:
- Exporter / Supplier: SinoMagan Indus Global Trade LLP
- Authorized Signatory: Fardin Mohammed, Partner
- Target Buyer / Client: {company_name}
- Industry: {industry}
- Products Demanded / Target Products: {target_products}
- Client Location: {locations}
- Client Website: {url}

Instructions:
1. Write a professional, highly compelling B2B export & supply proposal tailored specifically to {company_name} and their demand for {target_products}.
2. Present SinoMagan Indus Global Trade LLP as a trusted, end-to-end global trade partner with top-tier manufacturing connections, rigid quality control, and international logistics execution.
3. Highlight key advantages:
   - Direct factory sourcing & competitive wholesale pricing
   - Strict ISO/CE/RoHS quality inspection & compliance
   - Full container load (FCL) & less than container load (LCL) freight solutions
   - Flexible international trade terms (FOB, CIF, CFR) and reliable turnaround times
4. Keep the tone executive, persuasive, and partnership-focused.
5. End with a professional call-to-action to schedule a call or review sample specifications.
6. The sign-off MUST strictly be formatted as:

Warm regards,

Fardin Mohammed
Partner
SinoMagan Indus Global Trade LLP
"""
                    response = generate_with_fallback(prompt, logger=self.logger)
                    proposal_text = response.text.strip()
                    def on_done():
                        txt_proposal.delete("0.0", "end")
                        txt_proposal.insert("0.0", proposal_text)
                        btn_regen.configure(state="normal")
                    win.after(0, on_done)
                except Exception as e:
                    def on_err():
                        txt_proposal.delete("0.0", "end")
                        txt_proposal.insert("0.0", f"Error generating proposal: {e}")
                        btn_regen.configure(state="normal")
                    win.after(0, on_err)

            threading.Thread(target=generate_worker, daemon=True).start()

        btn_regen = ctk.CTkButton(btn_bar, text="🔄 Regenerate", command=start_generation, width=120, fg_color="#3a3a3a", hover_color="#2b2b2b")
        btn_regen.pack(side="left", padx=5)

        btn_close = ctk.CTkButton(btn_bar, text="Close", command=win.destroy, width=90, fg_color="#555555", hover_color="#444444")
        btn_close.pack(side="right", padx=5)

        start_generation()

    def open_url_proposal_window(self, initial_url=""):
        win = ctk.CTkToplevel(self)
        win.title("Instant B2B Trade Proposal Generator")
        win.geometry("820x690")
        win.attributes("-topmost", True)
        win.focus_set()

        # Top Header Banner
        header_frame = ctk.CTkFrame(win, fg_color="#1f232a", corner_radius=8)
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        lbl_title = ctk.CTkLabel(
            header_frame, 
            text="🌐 Instant B2B Proposal from Website URL", 
            font=("Arial", 16, "bold"),
            text_color="#ffffff"
        )
        lbl_title.pack(anchor="w", padx=15, pady=(10, 2))

        lbl_sub = ctk.CTkLabel(
            header_frame, 
            text="Enter any company website to scrape their products and generate a tailored proposal from SinoMagan Indus Global Trade LLP.", 
            font=("Arial", 11),
            text_color="#a0a0a0"
        )
        lbl_sub.pack(anchor="w", padx=15, pady=(0, 10))

        # URL Input Bar
        url_frame = ctk.CTkFrame(win, fg_color="transparent")
        url_frame.pack(fill="x", padx=15, pady=(0, 5))

        url_entry = ctk.CTkEntry(
            url_frame, 
            placeholder_text="Enter website URL (e.g. https://www.example.com)...", 
            font=("Arial", 12),
            height=38
        )
        url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        if initial_url:
            url_entry.insert(0, initial_url)

        btn_generate = ctk.CTkButton(
            url_frame, 
            text="⚡ Generate Proposal", 
            width=160, 
            height=38,
            fg_color="#1f7a1f", 
            hover_color="#145214",
            font=("Arial", 12, "bold")
        )
        btn_generate.pack(side="right")

        # Status Label
        lbl_status = ctk.CTkLabel(win, text="Status: Ready. Paste a URL and click Generate.", text_color="#a0a0a0", font=("Arial", 11))
        lbl_status.pack(anchor="w", padx=18, pady=(0, 5))

        # Proposal Textbox (Directly under the URL field)
        txt_proposal = ctk.CTkTextbox(win, wrap="word", font=("Arial", 12))
        txt_proposal.pack(fill="both", expand=True, padx=15, pady=5)
        txt_proposal.insert("0.0", "Your generated commercial proposal will appear here...")

        # Bottom Action Bar
        btn_bar = ctk.CTkFrame(win, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(10, 15))

        def copy_proposal():
            text = txt_proposal.get("0.0", "end").strip()
            if text and text != "Your generated commercial proposal will appear here...":
                self.clipboard_clear()
                self.clipboard_append(text)
                btn_copy.configure(text="Copied! ✅")
                win.after(2000, lambda: btn_copy.configure(text="📋 Copy Proposal"))

        btn_copy = ctk.CTkButton(btn_bar, text="📋 Copy Proposal", command=copy_proposal, width=140, fg_color="#1f7a1f", hover_color="#145214")
        btn_copy.pack(side="left", padx=5)

        def clear_fields():
            url_entry.delete(0, "end")
            txt_proposal.delete("0.0", "end")
            lbl_status.configure(text="Status: Ready.")

        btn_clear = ctk.CTkButton(btn_bar, text="Clear", command=clear_fields, width=90, fg_color="#3a3a3a", hover_color="#2b2b2b")
        btn_clear.pack(side="left", padx=5)

        btn_close = ctk.CTkButton(btn_bar, text="Close", command=win.destroy, width=90, fg_color="#555555", hover_color="#444444")
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
            txt_proposal.delete("0.0", "end")
            txt_proposal.insert("0.0", f"⏳ Step 1: Scraping website content from {target_url}...\n⏳ Step 2: Analyzing product portfolio with Gemini AI...\n\nPlease wait a moment.")

            def worker():
                try:
                    from scraper import scrape_url
                    scraped_text = scrape_url(target_url, self.logger)
                    
                    def update_status_ai():
                        lbl_status.configure(text="Status: Website scraped. Generating proposal with Gemini AI...")
                    win.after(0, update_status_ai)

                    from llm_fallback import generate_with_fallback
                    
                    if scraped_text and len(scraped_text.strip()) > 100:
                        content_block = f"Scraped Website Content of the Target Company:\n\"\"\"\n{scraped_text[:25000]}\n\"\"\""
                    else:
                        content_block = f"Note: Website text was minimal or protected. Tailor proposal to the company domain/URL: {target_url}."

                    prompt = f"""You are an elite international trade and export business executive writing a formal B2B commercial export proposal.

Company Details:
- Exporter / Supplier: SinoMagan Indus Global Trade LLP
- Authorized Signatory: Fardin Mohammed, Partner
- Target Buyer Website: {target_url}

{content_block}

Instructions:
1. Analyze the website text or domain name to identify:
   - The company's business name and industry
   - The specific products, parts, or equipment they produce, distribute, or utilize
2. Write a professional, highly compelling B2B commercial export proposal specifically offering products, components, or raw materials that match their exact business and product line.
3. Present SinoMagan Indus Global Trade LLP as a premier global sourcing and manufacturing supply partner with direct factory access, rigorous ISO/CE/RoHS quality control, and full container shipping solutions (FCL/LCL).
4. Highlight key advantages:
   - Direct factory sourcing & competitive wholesale pricing
   - Strict ISO/CE/RoHS quality inspection & compliance
   - Full container load (FCL) & less than container load (LCL) freight solutions
   - Flexible international trade terms (FOB, CIF, CFR) and reliable turnaround times
5. Keep the tone executive, persuasive, and partnership-focused.
6. End with a professional call-to-action to schedule a call or review catalog specifications.
7. The sign-off MUST strictly be formatted as:

Warm regards,

Fardin Mohammed
Partner
SinoMagan Indus Global Trade LLP
"""
                    response = generate_with_fallback(prompt, logger=self.logger)
                    proposal_text = response.text.strip()

                    def on_done():
                        txt_proposal.delete("0.0", "end")
                        txt_proposal.insert("0.0", proposal_text)
                        lbl_status.configure(text="Status: Proposal generated successfully! ✅")
                        btn_generate.configure(state="normal")
                    win.after(0, on_done)
                except Exception as e:
                    def on_err():
                        txt_proposal.delete("0.0", "end")
                        txt_proposal.insert("0.0", f"Error generating proposal: {e}")
                        lbl_status.configure(text="Status: Error during generation.")
                        btn_generate.configure(state="normal")
                    win.after(0, on_err)

            threading.Thread(target=worker, daemon=True).start()

        btn_generate.configure(command=start_url_generation)
        url_entry.bind("<Return>", lambda event: start_url_generation())

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
                
                is_buyers = (output_file == "Buyers_Matrix.xlsx")
                cols = list(df.columns)
                if is_buyers:
                    cols = ["Proposal"] + cols
                    
                tree["columns"] = cols
                for col in cols:
                    tree.heading(col, text=col)
                    if col == "Proposal":
                        tree.column(col, width=120, minwidth=100, anchor="center")
                    else:
                        tree.column(col, width=150, minwidth=100)
                        
                for _, row in df.iterrows():
                    values = list(row)
                    if is_buyers:
                        values = ["📝 Create"] + values
                    tree.insert("", "end", values=values)
                    
                self.logger.info(f"Successfully synced {output_file} with UI.")
            except Exception as e:
                self.logger.error(f"Failed to load matrix: {e}")
        else:
            self.logger.warning(f"No local matrix found to load: {output_file}")
            
    def clean_local_matrix(self, output_file, tree):
        clean_matrix(output_file, self.logger)
        self.load_matrix(tree, output_file)

    def setup_log_db_tab(self):
        self.log_tree = self.create_database_tab_ui(
            self.tab_log_db, 
            lambda: self.load_matrix(self.log_tree, "Logistics_Matrix.xlsx"),
            lambda: self.clean_local_matrix("Logistics_Matrix.xlsx", self.log_tree),
            lambda: self.delete_all_entries("Logistics_Matrix.xlsx", self.log_tree)
        )

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
        elif active_tab == "Logistics Scraper":
            self.lbl_log_status.configure(text=f"Status: {message[:50]}...")
        elif active_tab == "URL Discovery":
            self.lbl_disc_status.configure(text=f"Status: {message[:50]}...")

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
        
        self.lbl_log_status = ctk.CTkLabel(btn_frame, text="Status: Ready")
        self.lbl_log_status.pack(side="left", padx=20)
        
        self.log_output_textbox = ctk.CTkTextbox(self.tab_logistics)
        self.log_output_textbox.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")



if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()


