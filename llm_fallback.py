import os
import logging
from google import genai

def generate_with_fallback(prompt, config=None, logger=None):
    if logger is None:
        logger = logging.getLogger("ScraperAgent")
        
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from environment variables.")
        
    client = genai.Client(api_key=api_key)
    
    # Priority list of models to try
    fallback_models = [
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-3.5-flash",
        "gemini-flash-lite-latest",
        "gemini-pro-latest"
    ]
    
    last_error = None
    for model_name in fallback_models:
        try:
            logger.info(f"Attempting AI task with model: {model_name}")
            if config:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
            else:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
            logger.info(f"Success! Model {model_name} generated the response.")
            return response
        except Exception as e:
            error_str = str(e).lower()
            last_error = e
            # Fallback for server overloads, rate limits, or missing models
            if "503" in error_str or "unavailable" in error_str or "not found" in error_str or "404" in error_str or "429" in error_str or "quota" in error_str:
                logger.warning(f"Model {model_name} failed ({str(e)[:100]}...). Falling back to next model...")
                continue
            else:
                # If it's an internal schema error or bad request, don't loop
                raise e
                
    logger.error("All fallback models exhausted. The AI service is currently unavailable.")
    raise last_error
