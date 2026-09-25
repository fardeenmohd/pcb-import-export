import customtkinter as ctk
import threading
import pandas as pd
import os
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from tkinter import ttk

from logger_util import setup_logger
from processor import run_pipeline

# Load environment variables
load_dotenv()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("NCR PCB Supplier Discovery Agent")
        self.geometry("1000x700")
        
        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Setup Logger with GUI callback
        self.logger = setup_logger(self.log_callback)
        
        # Create Tabs
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        self.tab_discovery = self.tabview.add("URL Discovery")
        self.tab_suppliers = self.tabview.add("Inventory & Suppliers")
        self.tab_database = self.tabview.add("Suppliers Database")
        self.tab_buyers = self.tabview.add("Buyers")
        self.tab_logs = self.tabview.add("Agent Logs")
        
        self.setup_discovery_tab()
        self.setup_suppliers_tab()
        self.setup_database_tab()
        self.setup_buyers_tab()
        self.setup_logs_tab()

    def setup_discovery_tab(self):
        self.tab_discovery.grid_columnconfigure(0, weight=1)
        self.tab_discovery.grid_rowconfigure(2, weight=1)
        
        # Search controls
        control_frame = ctk.CTkFrame(self.tab_discovery)
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.query_entry = ctk.CTkEntry(control_frame, placeholder_text="Enter search query", width=300)
        self.query_entry.pack(side="left", padx=10, pady=10)
        self.query_entry.insert(0, "PCB manufacturers Delhi NCR")
        
        self.chk_yellow_pages = ctk.CTkCheckBox(control_frame, text="Target IndiaMart/TradeIndia")
        self.chk_yellow_pages.pack(side="left", padx=5)
        self.chk_yellow_pages.select()
        
        self.results_slider = ctk.CTkSlider(control_frame, from_=5, to=50, number_of_steps=9, width=100)
        self.results_slider.set(10)
        self.results_slider.pack(side="left", padx=10)
        
        self.btn_search = ctk.CTkButton(control_frame, text="Discover URLs", command=self.start_discovery)
        self.btn_search.pack(side="left", padx=10)
        
        self.lbl_disc_status = ctk.CTkLabel(control_frame, text="Status: Idle", text_color="gray")
        self.lbl_disc_status.pack(side="left", padx=10)
        
        # Helper text
        lbl = ctk.CTkLabel(self.tab_discovery, text="Discovered URLs will appear below. Copy them into the Inventory & Suppliers tab.", text_color="gray")
        lbl.grid(row=1, column=0, padx=10, sticky="w")
        
        # Results box
        self.discovery_textbox = ctk.CTkTextbox(self.tab_discovery, wrap="none")
        self.discovery_textbox.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

    def start_discovery(self):
        query = self.query_entry.get().strip()
        if not query:
            return
            
        if self.chk_yellow_pages.get() == 1:
            query += " (site:indiamart.com OR site:tradeindia.com OR site:justdial.com)"
            
        max_results = int(self.results_slider.get())
        self.btn_search.configure(state="disabled")
        self.lbl_disc_status.configure(text="Status: Searching DuckDuckGo...")
        self.discovery_textbox.delete("0.0", "end")
        
        threading.Thread(target=self.discover_urls_thread, args=(query, max_results), daemon=True).start()
        
    def discover_urls_thread(self, query, max_results):
        try:
            self.logger.info(f"Searching DuckDuckGo for: {query} (max: {max_results})")
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            
            urls = [r.get('href') for r in results if r.get('href')]
            self.after(0, self.on_discovery_complete, urls, None)
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            self.after(0, self.on_discovery_complete, [], str(e))
            
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
        
        # Context Label
        criteria_text = (
            "Context: Scraping PCB Manufacturers in Delhi-NCR.\n"
            "Extracting: Services, Materials, Layers, Finishes, Certifications, Advanced Capabilities."
        )
        self.lbl_criteria = ctk.CTkLabel(self.tab_suppliers, text=criteria_text, justify="left", font=("Arial", 12, "bold"))
        self.lbl_criteria.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        # URLs input
        self.urls_textbox = ctk.CTkTextbox(self.tab_suppliers, height=80)
        self.urls_textbox.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.urls_textbox.insert("0.0", "https://www.sahasraelectronics.com\n") # Default test URL
        
        # Controls
        self.control_frame = ctk.CTkFrame(self.tab_suppliers)
        self.control_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        self.btn_start = ctk.CTkButton(self.control_frame, text="Start Scraping", command=self.start_scraping)
        self.btn_start.pack(side="left", padx=10)
        
        self.lbl_status = ctk.CTkLabel(self.control_frame, text="Status: Idle", text_color="gray")
        self.lbl_status.pack(side="left", padx=10)
        
        # Output Grid (Text representation)
        self.output_textbox = ctk.CTkTextbox(self.tab_suppliers, wrap="none")
        self.output_textbox.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")

    def setup_database_tab(self):
        self.tab_database.grid_columnconfigure(0, weight=1)
        self.tab_database.grid_rowconfigure(1, weight=1)
        
        btn_sync = ctk.CTkButton(self.tab_database, text="Sync / Load Local Matrix", command=self.load_local_matrix)
        btn_sync.grid(row=0, column=0, pady=10, padx=10, sticky="w")
        
        frame = ctk.CTkFrame(self.tab_database)
        frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        # Customizing ttk treeview for dark mode to match CustomTkinter
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.map('Treeview', background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#343638')])
        
        self.tree = ttk.Treeview(frame, show='headings')
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
    def load_local_matrix(self):
        output_file = "Suppliers_Matrix.xlsx"
        if os.path.exists(output_file):
            try:
                df = pd.read_excel(output_file)
                
                # Clear existing rows
                self.tree.delete(*self.tree.get_children())
                
                # Setup columns
                self.tree["columns"] = list(df.columns)
                for col in df.columns:
                    self.tree.heading(col, text=col)
                    self.tree.column(col, width=150, minwidth=100)
                    
                # Insert data
                for _, row in df.iterrows():
                    self.tree.insert("", "end", values=list(row))
                
                self.logger.info("Successfully synced Suppliers Database tab with local matrix.")
            except Exception as e:
                self.logger.error(f"Failed to load matrix: {e}")
        else:
            self.logger.warning("No local matrix found to load.")
            
    def setup_buyers_tab(self):
        self.tab_buyers.grid_columnconfigure(0, weight=1)
        self.tab_buyers.grid_rowconfigure(1, weight=1)
        
        lbl = ctk.CTkLabel(self.tab_buyers, text="Buyer Discovery (In Development)", font=("Arial", 16))
        lbl.grid(row=0, column=0, pady=20)
        
        self.buyer_textbox = ctk.CTkTextbox(self.tab_buyers)
        self.buyer_textbox.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.buyer_textbox.insert("0.0", "This module will be developed later.")
        
    def setup_logs_tab(self):
        self.tab_logs.grid_columnconfigure(0, weight=1)
        self.tab_logs.grid_rowconfigure(0, weight=1)
        
        self.log_textbox = ctk.CTkTextbox(self.tab_logs, wrap="word")
        self.log_textbox.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Load existing logs if any
        if os.path.exists("workflow_logs.txt"):
            with open("workflow_logs.txt", "r", encoding='utf-8') as f:
                self.log_textbox.insert("0.0", f.read())
                
    def log_callback(self, message):
        # Update log textbox safely from thread
        self.after(0, self._append_log, message)
        
    def _append_log(self, message):
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.lbl_status.configure(text=f"Status: {message[:50]}...")

    def start_scraping(self):
        urls_text = self.urls_textbox.get("0.0", "end").strip()
        if not urls_text:
            self.lbl_status.configure(text="Status: Please enter URLs.")
            return
            
        urls = [url.strip() for url in urls_text.split("\n") if url.strip()]
        
        self.btn_start.configure(state="disabled")
        self.lbl_status.configure(text="Status: Starting pipeline...")
        self.output_textbox.delete("0.0", "end")
        
        # Run in background thread
        threading.Thread(target=self.run_pipeline_thread, args=(urls,), daemon=True).start()

    def run_pipeline_thread(self, urls):
        output_file = "Suppliers_Matrix.xlsx"
        run_pipeline(urls, self.logger, output_file=output_file)
        self.after(0, self.on_pipeline_complete, output_file)
        
    def on_pipeline_complete(self, output_file):
        self.btn_start.configure(state="normal")
        self.lbl_status.configure(text="Status: Completed.")
        self.load_local_matrix()
        
        if os.path.exists(output_file):
            try:
                df = pd.read_excel(output_file)
                # Convert DataFrame to string for display
                df_string = df.to_string()
                self.output_textbox.insert("0.0", df_string)
            except Exception as e:
                self.output_textbox.insert("0.0", f"Error loading Excel file: {e}")
        else:
            self.output_textbox.insert("0.0", "Output file not found. Scraper may have failed.")

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()
