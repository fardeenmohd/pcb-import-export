import re

with open('main.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace suggest_query
target_suggest = re.compile(r'    def suggest_query\(self\):.*?    def start_discovery\(self\):', re.DOTALL)
replacement_suggest = """    def suggest_query(self):
        strategy = self.strategy_var.get()
        region = self.region_var.get()
        self.btn_suggest.configure(state="disabled")
        self.query_entry.delete(0, "end")
        self.query_entry.insert(0, "Generating AI suggestion...")
        threading.Thread(target=self.suggest_query_thread, args=(strategy, region), daemon=True).start()

    def suggest_query_thread(self, strategy, region):
        try:
            from google import genai
            client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
            
            if strategy == "Suppliers":
                target = "Indian PCB manufacturers and suppliers of electronic components, chips, or microcontrollers."
            else:
                region_name = region.split(" (")[0]
                target = f"hardware OEMs, IoT startups, or medical/automotive electronic brands in {region_name} that BUILD physical products."
                
            prompt = f\"\"\"
            You are a B2B sourcing expert.
            The user wants to find: {target}
            
            Generate a single, highly specific DuckDuckGo search query to find their actual company websites.
            Do not include any quotes or explanations. Just return the raw query string.
            Example for Buyers: "Industrial IoT sensor OEMs Australia" or "EV charging station manufacturers"
            Example for Suppliers: "Rigid-flex PCB manufacturers India"
            \"\"\"
            
            response = client.models.generate_content(
                model='gemini-flash-lite-latest',
                contents=prompt
            )
            query = response.text.strip().replace('"', '').replace('\\n', '')
            self.ui_queue.put((self.on_suggest_complete, (query,)))
        except Exception as e:
            self.logger.error(f"Suggest failed: {e}")
            self.ui_queue.put((self.on_suggest_complete, ("Error generating query",)))
            
    def on_suggest_complete(self, query):
        self.query_entry.delete(0, "end")
        self.query_entry.insert(0, query)
        self.btn_suggest.configure(state="normal")

    def start_discovery(self):"""

code = target_suggest.sub(replacement_suggest, code)


# Replace discover_urls_thread
target_discover = re.compile(r'    def discover_urls_thread\(self, query, max_results, region_code\):.*?    def on_discovery_complete\(self, urls, error\):', re.DOTALL)
replacement_discover = """    def discover_urls_thread(self, query, max_results, region_code):
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
                
            client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
            
            if strategy == "Suppliers":
                filter_goal = "Indian PCB manufacturers, electronic component suppliers, or microcontrollers distributors. KEEP directories like IndiaMart or TradeIndia if they lead to suppliers."
            else:
                filter_goal = "Actual company websites for Hardware OEMs, startups, or brands that build physical products. REMOVE news articles, Wikipedia, Amazon, PDFs, and generic directories."
                
            prompt = f\"\"\"
            You are an expert lead generation AI.
            The user is searching for: {filter_goal}
            
            Here are the raw search results from DuckDuckGo:
            {search_context}
            
            Filter the list based on the goal. Return ONLY the URLs that strongly match.
            \"\"\"
            
            response = client.models.generate_content(
                model='gemini-flash-lite-latest',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FilteredURLs,
                ),
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

    def on_discovery_complete(self, urls, error):"""

code = target_discover.sub(replacement_discover, code)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("AI Discovery features injected.")
