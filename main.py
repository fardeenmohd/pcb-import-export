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
        self.tab_logs = self.tabview.add("Agent Logs")
        
        self.setup_discovery_tab()
        self.setup_suppliers_tab()
        self.setup_sup_db_tab()
        self.setup_buyers_tab()
        self.setup_buy_db_tab()
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
        self.tab_discovery.grid_rowconfigure(2, weight=1)
        
        control_frame = ctk.CTkFrame(self.tab_discovery)
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.strategy_var = ctk.StringVar(value="Buyers")
        self.strategy_dropdown = ctk.CTkOptionMenu(
            control_frame, 
            values=["Suppliers", "Buyers"],
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
        
        self.query_entry = ctk.CTkEntry(control_frame, placeholder_text="Enter base query", width=250)
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
        
        lbl = ctk.CTkLabel(self.tab_discovery, text="Discovered URLs will appear below. Copy them into the respective Scraper tab.", text_color="gray")
        lbl.grid(row=1, column=0, padx=10, sticky="w")
        
        self.discovery_textbox = ctk.CTkTextbox(self.tab_discovery, wrap="none")
        self.discovery_textbox.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

    def on_strategy_change(self, choice):
        if choice == "Suppliers":
            self.region_dropdown.configure(state="disabled")
        else:
            self.region_dropdown.configure(state="normal")

    def suggest_query(self):
        strategy = self.strategy_var.get()
        region = self.region_var.get()
        self.btn_suggest.configure(state="disabled")
        self.query_entry.delete(0, "end")
        self.query_entry.insert(0, "Generating AI suggestion...")
        threading.Thread(target=self.suggest_query_thread, args=(strategy, region), daemon=True).start()

    def suggest_query_thread(self, strategy, region):
        try:
            import random
            if strategy == "Suppliers":
                try:
                    with open("vision_context_suppliers.md", "r", encoding="utf-8") as f:
                        vision_text = f.read()
                except:
                    vision_text = "Target: Electrical Components, Cables, Switchgear, HVAC Parts, Batteries, Generators, LED Lighting, Appliances, and Testing Equipment."
                
                prompt = f"""You are an elite B2B sourcing expert.
Below is our Business Vision Context detailing the exact products and niches we are targeting.

{vision_text}

Your task:
1. Randomly pick ONE highly specific product, component, or technical keyword from the context above (e.g., 'LiFePO4 battery pack', 'Corax Poultry LED', 'double-compression brass cable gland', 'Phoenix Contact UT-4', 'VFDs', etc.). Pick a different one each time you are called to ensure diversity!
2. Generate a single, highly specific DuckDuckGo search query to find MANUFACTURERS and SUPPLIERS of that exact product.
3. The query MUST target ALL of India (e.g. include terms like "manufacturer India", and avoid strictly locking into Delhi NCR).

Do not include any quotes, markdown, or explanations. Return ONLY the raw query string.
Example: LiFePO4 battery pack OEM manufacturers India
"""
            else:
                region_name = region.split(" (")[0]
                if "Worldwide" in region_name or "Global" in region_name:
                    region_target = "globally or in major industrial hubs"
                else:
                    region_target = f"in {region_name}"
                    
                try:
                    with open("vision_context_v2.md", "r", encoding="utf-8") as f:
                        vision_text = f.read()
                except:
                    vision_text = "Target: Electrical Components, Cables, Switchgear, HVAC Parts, Batteries, Generators, LED Lighting, Appliances, or Testing Equipment."

                prompt = f"""You are an elite B2B sourcing expert.
Below is our Business Vision Context detailing the exact products and niches we are targeting.

{vision_text}

Your task:
1. Randomly pick ONE highly specific product, component, or technical keyword from the context above (e.g., 'LiFePO4 battery pack', 'Corax Poultry LED', 'double-compression brass cable gland', 'Phoenix Contact UT-4', 'VFDs', etc.). Pick a different one each time you are called to ensure diversity!
2. Generate a single, highly specific DuckDuckGo search query to find actual B2B BUYERS, DISTRIBUTORS, or OEMs for that exact product {region_target}.
3. The query should look for companies that buy or distribute this, not companies that manufacture it (unless they are OEMs using it as parts).

Do not include any quotes, markdown, or explanations. Return ONLY the raw query string.
Example: Variable Frequency Drives industrial distributors {region_name}
"""
            
            from llm_fallback import generate_with_fallback
            
            # Use temperature=0.9 to ensure we get different niches each time the user clicks suggest!
            # Since generate_with_fallback might not support kwargs perfectly depending on implementation, 
            # we will just add a random seed text to the prompt to force variety.
            prompt += "\n\nRandom Seed to ensure variety: " + str(random.randint(1, 100000))
            
            response = generate_with_fallback(prompt, logger=self.logger)
            query = response.text.strip().replace('"', '').replace('\n', '')
            self.ui_queue.put((self.on_suggest_complete, (query,)))
        except Exception as e:
            self.logger.error(f"Suggest failed: {e}")
            self.ui_queue.put((self.on_suggest_complete, ("Error generating query",)))
            
    def on_suggest_complete(self, query):
        self.query_entry.delete(0, "end")
        self.query_entry.insert(0, query)
        self.btn_suggest.configure(state="normal")

    def start_discovery(self):
        query = self.query_entry.get().strip()
        if not query:
            return
            
        strategy = self.strategy_var.get()
        if strategy == "Suppliers":
            query += " (site:indiamart.com OR site:tradeindia.com OR site:justdial.com OR site:exportersindia.com)"
            region_code = "in-en"
        else:
            query += " -\"PCB manufacturer\" -\"PCB assembly\" -\"printed circuit board\""
            region_code = self.region_var.get().split(" (")[1].replace(")", "")
            
        max_results = int(self.results_slider.get())
        
        self.btn_search.configure(state="disabled")
        self.lbl_disc_status.configure(text="Status: Searching...")
        self.discovery_textbox.delete("0.0", "end")
        
        threading.Thread(target=self.discover_urls_thread, args=(query, max_results, region_code), daemon=True).start()

    def discover_urls_thread(self, query, max_results, region_code):
        try:
            self.logger.info(f"Searching DuckDuckGo for: {query} [Region: {region_code}]")
            with DDGS() as ddgs:
                results = list(ddgs.text(query, region=region_code, max_results=max_results))
            
            if not results:
                self.ui_queue.put((self.on_discovery_complete, ([], None)))
                return
                
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
                
            if strategy == "Suppliers":
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
            self.ui_queue.put((self.on_discovery_complete, (urls, None)))
        except Exception as e:
            self.logger.error(f"Search/Filter failed: {e}")
            self.ui_queue.put((self.on_discovery_complete, ([], str(e))))
            
    def update_discovery_status(self, text):
        self.lbl_disc_status.configure(text=text)

    def on_discovery_complete(self, urls, error):
        self.btn_search.configure(state="normal")
        if error:
            self.lbl_disc_status.configure(text="Status: Error")
            self.discovery_textbox.insert("end", f"Error: {error}")
        else:
            self.lbl_disc_status.configure(text=f"Status: Found {len(urls)} URLs")
            self.discovery_textbox.insert("end", "\n".join(urls) + "\n")

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
        
        self.lbl_buy_status = ctk.CTkLabel(control_frame, text="Status: Idle", text_color="gray")
        self.lbl_buy_status.pack(side="left", padx=10)
        
        self.buy_output_textbox = ctk.CTkTextbox(self.tab_buyers, wrap="none")
        self.buy_output_textbox.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")

    def start_scraping(self, pipeline_type):
        if pipeline_type == "supplier":
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
        if pipeline_type == "supplier":
            output_file = "Suppliers_Matrix.xlsx"
            run_pipeline(urls, self.logger, output_file=output_file)
        else:
            output_file = "Buyers_Matrix.xlsx"
            run_buyer_pipeline(urls, self.logger, output_file=output_file)
            
        self.ui_queue.put((self.on_pipeline_complete, (output_file, pipeline_type)))
        
    def on_pipeline_complete(self, output_file, pipeline_type):
        if pipeline_type == "supplier":
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

    def create_database_tab_ui(self, tab, sync_cmd, clean_cmd, delete_all_cmd):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=0, column=0, pady=10, padx=10, sticky="w")
        
        btn_sync = ctk.CTkButton(btn_frame, text="Sync / Load Matrix", command=sync_cmd)
        btn_sync.pack(side="left", padx=(0, 10))
        
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
            lambda: self.delete_all_entries("Buyers_Matrix.xlsx", self.buy_tree)
        )

    def delete_all_entries(self, output_file, tree):
        import tkinter.messagebox as messagebox
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to completely delete {output_file}?\nThis action cannot be undone."):
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
                tree["columns"] = list(df.columns)
                for col in df.columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=150, minwidth=100)
                for _, row in df.iterrows():
                    tree.insert("", "end", values=list(row))
                self.logger.info(f"Successfully synced {output_file} with UI.")
            except Exception as e:
                self.logger.error(f"Failed to load matrix: {e}")
        else:
            self.logger.warning(f"No local matrix found to load: {output_file}")
            
    def clean_local_matrix(self, output_file, tree):
        clean_matrix(output_file, self.logger)
        self.load_matrix(tree, output_file)

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
        elif active_tab == "URL Discovery":
            self.lbl_disc_status.configure(text=f"Status: {message[:50]}...")

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()
