from flask import Flask, jsonify
from playwright.async_api import async_playwright
import asyncio
import time
import random
import json
import re

app = Flask(__name__)

async def run_playwright_task():
    async with async_playwright() as p:
        # Launch browser with proper settings for cloud hosting
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-gpu'
            ]
        )
        
        # Create context and page
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        # Track network requests
        requests_data = []
        
        async def handle_request(request):
            if 'trigger?' in request.url and request.method == 'POST':
                post_data = request.post_data
                headers = await request.all_headers()
                
                request_info = {
                    "url": request.url,
                    "method": request.method,
                    "headers": headers,
                    "data": post_data
                }
                requests_data.append(request_info)
        
        page.on('request', handle_request)
        
        try:
            # Navigate to the page
            await page.goto("https://workik.com/ai-code-generator", wait_until="networkidle")
            await page.wait_for_timeout(6000)  # Wait for page load
            
            # === Step 1: Select model ===
            try:
                model_selector = page.locator("//span[contains(text(),'GPT 4.1 Mini')]")
                if await model_selector.count() > 0:
                    await model_selector.click()
                    await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"Model selection error: {e}")
            
            # === Step 2: Type random message ===
            random_texts = [
                "Make a simple calculator in Python",
                "Generate a todo list app in React", 
                "Write HTML for a login form",
                "Give me CSS for a navbar",
                "Create a REST API with Flask",
                "Build a responsive navbar with CSS",
                "Make a password generator in JavaScript"
            ]
            
            message = random.choice(random_texts)
            
            # Find and fill the input box
            input_box = page.locator("div[contenteditable='true']")
            await input_box.wait_for(state="visible", timeout=10000)
            
            # Clear and type the message
            await input_box.fill(message)
            await page.wait_for_timeout(1000)
            
            # Click send button
            send_button = page.locator("button.MuiButtonBase-root.css-11uhnn1")
            if await send_button.count() == 0:
                # Fallback selectors
                send_button = page.locator("button[type='submit']")
                if await send_button.count() == 0:
                    send_button = page.locator("button:has-text('Send')")
            
            await send_button.click()
            await page.wait_for_timeout(10000)  # Wait for response
            
            # Extract tokens from captured requests
            tokens = {}
            curl_command = None
            
            for req_data in requests_data:
                if req_data["data"]:
                    try:
                        body = json.loads(req_data["data"])
                        for key, val in body.items():
                            if isinstance(val, str):
                                # Check for JWT-like tokens or long strings
                                if re.match(r"^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$", val) or len(val) > 20:
                                    tokens[key] = val
                        
                        curl_command = req_data
                        break
                    except json.JSONDecodeError:
                        pass
            
            await browser.close()
            
            return {
                "message_sent": message,
                "curl": curl_command,
                "tokens": tokens,
                "requests_captured": len(requests_data)
            }
            
        except Exception as e:
            await browser.close()
            return {"error": str(e)}

def run_async_task():
    """Wrapper to run async function in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(run_playwright_task())

# === Flask Routes ===
@app.route("/<task_id>", methods=["GET"])
def process(task_id):
    result = run_async_task()
    return jsonify({
        "task_id": task_id,
        "result": result,
        "timestamp": time.time()
    })

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "playwright-automation"})

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Playwright Automation Service",
        "usage": "GET /<task_id> to run automation task",
        "health": "GET /health for health check"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
