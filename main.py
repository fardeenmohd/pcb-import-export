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
            variable=self.region_var, width=120,
            command=self.on_region_change
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
        
        def get_disc_mode():
            s = self.strategy_var.get()
            if s == "Suppliers":
                return "supplier"
            elif s == "Logistics":
                return "logistics"
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

        # Initial starter queries (covering all 11 product niches including PCBs & Electric Vehicles)
        starter_queries = [
            "switchgear panel distributors USA",
            "commercial lighting importers UAE",
            "industrial wire cable wholesalers Germany",
            "lithium battery pack distributors UK",
            "HVAC equipment wholesalers Australia",
            "solar inverter distributors Canada",
            "diesel generator dealers Saudi Arabia",
            "cable gland terminal block importers Oman",
            "floor scrubber cleaning equipment distributors Qatar",
            "PIR sensor testing equipment wholesalers Singapore",
            "industrial fan pump suppliers Kuwait",
            "home energy storage importers Poland",
            "EV charging station distributors USA",
            "electric vehicle charger importers UAE",
            "PCB assembly PCBA turnkey services Germany",
            "printed circuit board distributors USA",
            "rigid multi layer FR4 PCB board importers UK",
            "flexible PCB FPC distributors Canada"
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
            
            # Action button: 📝 Sourcing RFQ / 📝 Freight RFQ / 📝 Create Proposal
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
        elif strategy == "Logistics":
            self.log_urls_textbox.delete("0.0", "end")
            self.log_urls_textbox.insert("0.0", urls_joined)
            self.tabview.set("Logistics Scraper")
            self.lbl_log_status.configure(text=f"Loaded {len(self.current_hq_urls)} URLs from Discovery")
        else:
            self.buy_urls_textbox.delete("0.0", "end")
            self.buy_urls_textbox.insert("0.0", urls_joined)
            self.tabview.set("Buyers Scraper")
            self.lbl_buy_status.configure(text=f"Loaded {len(self.current_hq_urls)} URLs from Discovery")

    def on_region_change(self, choice):
        strategy = self.strategy_var.get()
        if strategy == "Suppliers":
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
                f"commercial lighting importers {dest}",
                f"industrial wire cable wholesalers {dest}",
                f"lithium battery pack distributors {dest}",
                f"HVAC equipment wholesalers {dest}",
                f"solar inverter distributors {dest}",
                f"diesel generator dealers {dest}",
                f"cable gland terminal block importers {dest}",
                f"floor scrubber cleaning equipment distributors {dest}",
                f"PIR sensor testing equipment wholesalers {dest}",
                f"industrial fan pump suppliers {dest}",
                f"home energy storage importers {dest}",
                f"EV charging station distributors {dest}",
                f"electric vehicle charger importers {dest}",
                f"PCB assembly PCBA turnkey services {dest}",
                f"printed circuit board distributors {dest}",
                f"rigid multi layer FR4 PCB importers {dest}",
                f"flexible PCB FPC manufacturers {dest}"
            ]
        self.populate_suggested_queries(queries)
        self.select_suggested_query(queries[0])

    def on_strategy_change(self, choice):
        if choice == "Suppliers":
            self.btn_disc_prop.configure(text="🌐 Quick URL Inquiry")
            self.region_dropdown.configure(state="disabled")
            self.btn_suggest.configure(state="normal")
            queries = [
                "distribution transformer manufacturers India",
                "switchgear panel factories Gujarat",
                "copper wire cable manufacturers India",
                "lithium battery pack makers Bangalore",
                "HVAC components suppliers Maharashtra",
                "circuit breaker factories India",
                "diesel generator manufacturers Pune",
                "brass cable glands manufacturers Jamnagar",
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
            self.populate_suggested_queries(queries)
            self.select_suggested_query(queries[0])
        elif choice == "Logistics":
            self.btn_disc_prop.configure(text="🌐 Quick Freight RFQ")
            self.region_dropdown.configure(state="normal")
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
        else:
            self.btn_disc_prop.configure(text="🌐 Quick URL Proposal")
            self.region_dropdown.configure(state="normal")
            self.btn_suggest.configure(state="normal")
            dest = self.region_var.get().split(" (")[0]
            if "Worldwide" in dest or "Global" in dest:
                dest = "worldwide"
            queries = [
                f"switchgear panel distributors {dest}",
                f"commercial lighting importers {dest}",
                f"industrial wire cable wholesalers {dest}",
                f"lithium battery pack distributors {dest}",
                f"HVAC equipment wholesalers {dest}",
                f"solar inverter distributors {dest}",
                f"diesel generator dealers {dest}",
                f"cable gland terminal block importers {dest}",
                f"floor scrubber cleaning equipment distributors {dest}",
                f"PIR sensor testing equipment wholesalers {dest}",
                f"industrial fan pump suppliers {dest}",
                f"home energy storage importers {dest}",
                f"EV charging station distributors {dest}",
                f"electric vehicle charger importers {dest}",
                f"PCB assembly PCBA turnkey services {dest}",
                f"printed circuit board distributors {dest}",
                f"rigid multi layer FR4 PCB importers {dest}",
                f"flexible PCB FPC manufacturers {dest}"
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
                prompt = """You are an elite B2B sourcing expert for Indian export-import trade.
Our company sources from Indian manufacturers across these 11 core industrial niches:

NICHE 1 - Electrical Components: Cable glands, crimping lugs, terminal blocks, rocker switches, push buttons, EV plugs, wiring sockets
NICHE 2 - Wires & Cables: LV/MV/HV power cables, armored XLPE cables, submersible cables, binding wires, hose reels
NICHE 3 - Switchgear & Panels: ACB, MCCB, MCB, VCB, relays, contactors, PCC/MCC panels, distribution boards
NICHE 4 - HVAC, Fans & Pumps: Axial/centrifugal fans, scroll/screw compressors, submersible pumps, refrigeration parts
NICHE 5 - Batteries & Energy Storage: LiFePO4 battery packs, home energy storage, marine batteries, GaN chargers, solar inverters
NICHE 6 - Industrial Generators: Cummins diesel gensets, gas generators, silent generators, wind turbines
NICHE 7 - LED Lighting: Streetlights, high-bay LED, poultry lighting systems, smart WiFi sockets, luminaires
NICHE 8 - Commercial Appliances: Industrial dehumidifiers, floor scrubbers, commercial laundry machines, kitchen equipment
NICHE 9 - Sensors & Testing: PIR sensors, float switches, transformer test benches, multimeters, data loggers
NICHE 10 - Electric Vehicles & EV Infrastructure: EV chargers (AC wallbox, DC fast chargers), EV charging cables, Type 2 & CCS2 connectors, EV battery packs (2W/3W/4W LiFePO4), BMS controllers, EV charging stations
NICHE 11 - Printed Circuit Boards (PCB) & PCBA: Multi-layer rigid FR4 PCBs, flexible FPC, aluminum MCPCB, turn-key SMT PCBA assembly, electronic EMS manufacturing, copper clad laminates (CCL)

Generate 14 to 18 short, simple, natural DuckDuckGo search queries to find Indian MANUFACTURERS and FACTORIES across India (e.g. Gujarat, Maharashtra, Delhi NCR, Bangalore, Tamil Nadu, Coimbatore, Pune, Jamnagar).

RULES:
1. Each query must be short and clean (3 to 6 words only).
   Examples of good queries:
   - "distribution transformer manufacturers India"
   - "switchgear panel factories Gujarat"
   - "brass cable glands manufacturers Jamnagar"
   - "diesel generator manufacturers Pune"
   - "LED streetlight factories India"
   - "floor scrubber machine suppliers India"
   - "PIR sensor manufacturers Delhi NCR"
   - "EV charging station manufacturers India"
   - "electric vehicle battery pack makers Pune"
   - "multi layer FR4 PCB manufacturers India"
   - "PCB assembly SMT PCBA factories Bangalore"
   - "copper clad laminate CCL suppliers India"
2. CRITICAL: You MUST cover ALL 11 niches above. Pick a DIFFERENT specific sub-product from each niche. Do NOT repeat the same niche twice until all 11 are covered.
3. Rotate between different Indian industrial hubs (Gujarat, Maharashtra, Tamil Nadu, Karnataka, Delhi NCR, etc.).
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
            else:
                region_name = region.split(" (")[0]
                if "Worldwide" in region_name or "Global" in region_name:
                    region_target = "global / worldwide"
                    region_kw = "worldwide"
                else:
                    region_target = region_name
                    region_kw = region_name

                prompt = f"""You are an elite B2B export sales director.
We are an Indian manufacturer and exporter supplying international buyers across these 11 core industrial niches:

NICHE 1 - Electrical Components: Cable glands, crimping lugs, terminal blocks, rocker switches, push buttons, EV plugs, wiring sockets
NICHE 2 - Wires & Cables: LV/MV/HV power cables, armored XLPE cables, submersible cables, binding wires, hose reels
NICHE 3 - Switchgear & Panels: ACB, MCCB, MCB, VCB, relays, contactors, PCC/MCC panels, distribution boards
NICHE 4 - HVAC, Fans & Pumps: Axial/centrifugal fans, scroll/screw compressors, submersible pumps, refrigeration parts
NICHE 5 - Batteries & Energy Storage: LiFePO4 battery packs, home energy storage, marine batteries, GaN chargers, solar inverters
NICHE 6 - Industrial Generators: Cummins diesel gensets, gas generators, silent generators, wind turbines
NICHE 7 - LED Lighting: Streetlights, high-bay LED, poultry lighting systems, smart WiFi sockets, luminaires
NICHE 8 - Commercial Appliances: Industrial dehumidifiers, floor scrubbers, commercial laundry machines, kitchen equipment
NICHE 9 - Sensors & Testing: PIR sensors, float switches, transformer test benches, multimeters, data loggers
NICHE 10 - Electric Vehicles & EV Infrastructure: EV chargers (AC wallbox, DC fast chargers), EV charging cables, Type 2 & CCS2 connectors, EV battery packs (2W/3W/4W LiFePO4), BMS controllers, EV charging stations
NICHE 11 - Printed Circuit Boards (PCB) & PCBA: Multi-layer rigid FR4 PCBs, flexible FPC, aluminum MCPCB, turn-key SMT PCBA assembly, electronic EMS manufacturing, copper clad laminates (CCL)

Generate 14 to 18 short, simple, natural DuckDuckGo search queries to find real B2B BUYERS, DISTRIBUTORS, IMPORTERS, WHOLESALERS, or CONTRACTORS in {region_target}.

RULES:
1. Each query must be short and clean (3 to 6 words only).
   Examples of good queries:
   - "switchgear panel distributors {region_kw}"
   - "commercial lighting importers {region_kw}"
   - "diesel generator dealers {region_kw}"
   - "cable gland terminal block importers {region_kw}"
   - "floor scrubber equipment distributors {region_kw}"
   - "PIR sensor wholesalers {region_kw}"
   - "home energy storage importers {region_kw}"
   - "EV charging station distributors {region_kw}"
   - "electric vehicle charger importers {region_kw}"
   - "PCB assembly PCBA turnkey services {region_kw}"
   - "printed circuit board distributors {region_kw}"
   - "rigid multi layer FR4 PCB importers {region_kw}"
   - "flexible PCB FPC manufacturers {region_kw}"
2. CRITICAL: You MUST cover ALL 11 niches above. Pick a DIFFERENT specific sub-product from each niche. Do NOT repeat the same niche twice until all 11 are covered.
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
                    queries = [
                        "distribution transformer manufacturers India",
                        "switchgear panel factories Gujarat",
                        "copper wire cable manufacturers India",
                        "lithium battery pack makers Bangalore",
                        "HVAC components suppliers Maharashtra",
                        "circuit breaker factories India",
                        "diesel generator manufacturers Pune",
                        "brass cable glands manufacturers Jamnagar",
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
                    dest_term = region.split(" (")[0]
                    queries = [
                        f"freight forwarders India to {dest_term} container shipping",
                        f"sea cargo forwarders Mumbai to {dest_term}",
                        f"container logistics agents India {dest_term}",
                        f"FCL shipping lines India {dest_term}"
                    ]
                else:
                    dest_term = region.split(" (")[0]
                    queries = [
                        f"switchgear panel distributors {dest_term}",
                        f"commercial lighting importers {dest_term}",
                        f"industrial wire cable wholesalers {dest_term}",
                        f"lithium battery pack distributors {dest_term}",
                        f"HVAC equipment wholesalers {dest_term}",
                        f"solar inverter distributors {dest_term}",
                        f"diesel generator dealers {dest_term}",
                        f"cable gland terminal block importers {dest_term}",
                        f"floor scrubber cleaning equipment distributors {dest_term}",
                        f"PIR sensor testing equipment wholesalers {dest_term}",
                        f"industrial fan pump suppliers {dest_term}",
                        f"home energy storage importers {dest_term}",
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
                    "switchgear panel factories Gujarat",
                    "copper wire cable manufacturers India",
                    "lithium battery pack makers Bangalore",
                    "HVAC components suppliers Maharashtra",
                    "circuit breaker factories India",
                    "diesel generator manufacturers Pune",
                    "brass cable glands manufacturers Jamnagar",
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
            else:
                fallback_queries = [
                    f"switchgear panel distributors {fallback_dest}",
                    f"commercial lighting importers {fallback_dest}",
                    f"industrial wire cable wholesalers {fallback_dest}",
                    f"lithium battery pack distributors {fallback_dest}",
                    f"HVAC equipment wholesalers {fallback_dest}",
                    f"solar inverter distributors {fallback_dest}",
                    f"diesel generator dealers {fallback_dest}",
                    f"cable gland terminal block importers {fallback_dest}",
                    f"floor scrubber cleaning equipment distributors {fallback_dest}",
                    f"PIR sensor testing equipment wholesalers {fallback_dest}",
                    f"industrial fan pump suppliers {fallback_dest}",
                    f"home energy storage importers {fallback_dest}",
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
        if strategy == "Suppliers":
            query += " (site:indiamart.com OR site:tradeindia.com OR site:justdial.com OR site:exportersindia.com)"
            region_code = "in-en"
        elif strategy == "Logistics":
            region_code = "in-en"
        else:
            query_lower = query.lower()
            if not any(term in query_lower for term in ["pcb", "circuit board", "circuit boards", "pcba", "smt"]):
                query += " -\"PCB manufacturer\" -\"PCB assembly\" -\"printed circuit board\""
            region_code = self.region_var.get().split(" (")[1].replace(")", "")
            
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
        
        criteria_text = "Supplier Context: Extracting Manufacturers, Factories, Capabilities, MOQs, & Certifications across all 11 Industrial Niches (PCBs, PCBA, Electrical, Cables, Switchgear, Batteries, HVAC, Electric Vehicles, etc.)."
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

    def create_database_tab_ui(self, tab, sync_cmd, clean_cmd, delete_all_cmd, proposal_cmd=None, is_supplier=False, mode=None):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        if mode is None:
            mode = "supplier" if is_supplier else "buyer"

        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=0, column=0, pady=10, padx=10, sticky="w")
        
        btn_sync = ctk.CTkButton(btn_frame, text="Sync / Load Matrix", command=sync_cmd)
        btn_sync.pack(side="left", padx=(0, 10))
        
        if proposal_cmd:
            if mode == "logistics":
                btn_prop_text = "📝 Create Freight RFQ"
                btn_url_prop_text = "🌐 Freight RFQ from URL"
                url_cmd = lambda: self.open_url_proposal_window(mode="logistics")
            elif mode == "supplier":
                btn_prop_text = "📝 Create Sourcing Inquiry"
                btn_url_prop_text = "🌐 Inquiry from URL"
                url_cmd = lambda: self.open_url_proposal_window(mode="supplier")
            else:
                btn_prop_text = "📝 Create Proposal"
                btn_url_prop_text = "🌐 Proposal from URL"
                url_cmd = lambda: self.open_url_proposal_window(mode="buyer")

            btn_prop = ctk.CTkButton(btn_frame, text=btn_prop_text, command=proposal_cmd, fg_color="#1f7a1f", hover_color="#145214")
            btn_prop.pack(side="left", padx=(0, 10))

            btn_url_prop = ctk.CTkButton(btn_frame, text=btn_url_prop_text, command=url_cmd, fg_color="#005b96", hover_color="#003f66")
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
            lambda: self.delete_all_entries("Suppliers_Matrix.xlsx", self.sup_tree),
            proposal_cmd=self.open_supplier_inquiry_window,
            is_supplier=True
        )
        
    def setup_buy_db_tab(self):
        self.buy_tree = self.create_database_tab_ui(
            self.tab_buy_db, 
            lambda: self.load_matrix(self.buy_tree, "Buyers_Matrix.xlsx"),
            lambda: self.clean_local_matrix("Buyers_Matrix.xlsx", self.buy_tree),
            lambda: self.delete_all_entries("Buyers_Matrix.xlsx", self.buy_tree),
            proposal_cmd=self.open_proposal_window,
            is_supplier=False
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
- SinoMagan Indus Global Trade LLP (Global sourcing, contract manufacturing, export & logistics management)
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
- SinoMagan Indus Global Trade LLP (Global sourcing, contract manufacturing, export & logistics management)
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
SinoMagan Indus Global Trade LLP regularly moves commercial export containerized freight (such as electrical switchgear, cables, battery storage systems, HVAC equipment, and industrial hardware) from major Indian ports (e.g. Nhava Sheva / JNPT, Mundra, Chennai) to international destinations (including GCC / Middle East, Europe, North America, Southeast Asia, and Africa).
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
        else:
            win.title("Instant B2B Trade Proposal Generator")
        win.geometry("820x760")
        win.attributes("-topmost", True)
        win.focus_set()

        # Top Header Banner
        header_frame = ctk.CTkFrame(win, fg_color="#1f232a", corner_radius=8)
        header_frame.pack(fill="x", padx=15, pady=(15, 8))

        if mode == "logistics":
            lbl_title_text = "🚢 Instant Freight Inquiry from Logistics Website"
            lbl_sub_text = "Enter logistics or freight forwarder website to analyze shipping routes, container services, and generate an official Freight Cargo RFQ from SinoMagan Indus Global Trade LLP."
            btn_gen_text = "⚡ Generate Freight RFQ"
            default_placeholder = "Your generated freight cargo inquiry will appear here..."
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
            width=175 if mode in ["supplier", "logistics"] else 160, 
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
                "Your generated freight cargo inquiry will appear here..."
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
                "Your generated freight cargo inquiry will appear here..."
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
SinoMagan Indus Global Trade LLP regularly moves commercial export containerized freight (such as electrical switchgear, cables, battery storage systems, HVAC equipment, and industrial hardware) from major Indian ports (e.g. Nhava Sheva / JNPT, Mundra, Chennai) to international destinations (including GCC / Middle East, Europe, North America, Southeast Asia, and Africa).
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
                    elif mode == "supplier":
                        prompt = f"""You are Fardin Mohammed, Partner at SinoMagan Indus Global Trade LLP, writing an official B2B Sourcing RFQ / vendor partnership inquiry to an industrial manufacturer / supplier.

Target Supplier Website: {target_url}
Known Scraped Email: {scraped_email}

{content_block}

Your Company:
- SinoMagan Indus Global Trade LLP (Global sourcing, contract manufacturing, export & logistics management)
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
- SinoMagan Indus Global Trade LLP (Global sourcing, contract manufacturing, export & logistics management)
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
                
                has_action_col = (output_file in ["Buyers_Matrix.xlsx", "Suppliers_Matrix.xlsx", "Logistics_Matrix.xlsx"])
                if output_file == "Suppliers_Matrix.xlsx":
                    action_col_name = "Inquiry"
                elif output_file == "Logistics_Matrix.xlsx":
                    action_col_name = "Inquiry"
                else:
                    action_col_name = "Proposal"
                cols = list(df.columns)
                if has_action_col:
                    cols = [action_col_name] + cols
                    
                tree["columns"] = cols
                for col in cols:
                    tree.heading(col, text=col)
                    if col in ["Proposal", "Inquiry"]:
                        tree.column(col, width=120, minwidth=100, anchor="center")
                    else:
                        tree.column(col, width=150, minwidth=100)
                        
                for _, row in df.iterrows():
                    values = list(row)
                    if has_action_col:
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
            lambda: self.delete_all_entries("Logistics_Matrix.xlsx", self.log_tree),
            proposal_cmd=self.open_logistics_inquiry_window,
            mode="logistics"
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


