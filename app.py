from flask import Flask, jsonify
import subprocess
import json
import random
import time
import os

app = Flask(__name__)

def run_playwright_script():
    """Run playwright automation using subprocess"""
    
    # Random messages to send
    messages = [
        "Make a simple calculator in Python",
        "Generate a todo list app in React", 
        "Write HTML for a login form",
        "Give me CSS for a navbar",
        "Create a REST API with Flask",
        "Build a responsive navbar with CSS"
    ]
    
    selected_message = random.choice(messages)
    
    # Create a temporary playwright script
    script_content = f'''
import asyncio
from playwright.async_api import async_playwright
import json
import re

async def main():
    async with async_playwright() as p:
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
                '--disable-gpu',
                '--disable-extensions'
            ]
        )
        
        context = await browser.new_context(
            viewport={{'width': 1920, 'height': 1080}},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        )
        
        page = await context.new_page()
        
        requests_data = []
        
        async def handle_request(request):
            if 'trigger?' in request.url and request.method == 'POST':
                post_data = request.post_data
                headers = await request.all_headers()
                
                request_info = {{
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(headers),
                    "data": post_data
                }}
                requests_data.append(request_info)
        
        page.on('request', handle_request)
        
        try:
            await page.goto("https://workik.com/ai-code-generator", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)
            
            # Try to select model
            try:
                model_btn = page.locator("//span[contains(text(),'GPT 4.1 Mini')]").first
                if await model_btn.count() > 0:
                    await model_btn.click()
                    await page.wait_for_timeout(2000)
            except:
                pass
            
            # Find input and type message
            input_box = page.locator("div[contenteditable='true']").first
            await input_box.wait_for(state="visible", timeout=15000)
            await input_box.fill("{selected_message}")
            await page.wait_for_timeout(1000)
            
            # Click send button
            send_btn = page.locator("button.MuiButtonBase-root").first
            if await send_btn.count() == 0:
                send_btn = page.locator("button[type='submit']").first
            
            await send_btn.click()
            await page.wait_for_timeout(10000)
            
            # Extract tokens
            tokens = {{}}
            curl_command = None
            
            for req in requests_data:
                if req["data"]:
                    try:
                        body = json.loads(req["data"])
                        for key, val in body.items():
                            if isinstance(val, str) and (len(val) > 20 or "." in val):
                                tokens[key] = val
                        curl_command = req
                        break
                    except:
                        pass
            
            result = {{
                "message_sent": "{selected_message}",
                "curl": curl_command,
                "tokens": tokens,
                "requests_captured": len(requests_data)
            }}
            
            print(json.dumps(result))
            
        except Exception as e:
            print(json.dumps({{"error": str(e)}}))
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    # Write script to temporary file
    script_path = "/tmp/playwright_script.py"
    with open(script_path, "w") as f:
        f.write(script_content)
    
    try:
        # Run the playwright script
        result = subprocess.run(
            ["python", script_path], 
            capture_output=True, 
            text=True, 
            timeout=120
        )
        
        if result.returncode == 0:
            return json.loads(result.stdout.strip())
        else:
            return {"error": f"Script failed: {result.stderr}"}
            
    except subprocess.TimeoutExpired:
        return {"error": "Script timed out after 120 seconds"}
    except Exception as e:
        return {"error": f"Execution error: {str(e)}"}
    finally:
        # Clean up
        if os.path.exists(script_path):
            os.remove(script_path)

# === Flask Routes ===
@app.route("/<task_id>", methods=["GET"])
def process(task_id):
    result = run_playwright_script()
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
