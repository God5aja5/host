from fastapi import FastAPI
from fastapi.responses import JSONResponse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import random
import json
import re
import os

app = FastAPI()

URL = "https://workik.com/ai-code-generator"

def extract_tokens_from_text(text: str):
    tokens = {}
    if not text:
        return tokens
    # Try parse JSON
    try:
        body = json.loads(text)
        if isinstance(body, dict):
            for k, v in body.items():
                if isinstance(v, str):
                    if re.match(r"^[A-Za-z0-9-]+\.[A-Za-z0-9-]+\.[A-Za-z0-9-]+$", v) or len(v) > 20:
                        tokens[k] = v
        return tokens
    except Exception:
        pass

    # Look for JWT-like or long alphanumeric sequences
    matches = re.findall(r"[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+", text)
    for i, m in enumerate(matches):
        tokens[f"jwt_{i}"] = m
    if not matches:
        long_matches = re.findall(r"[A-Za-z0-9\-_]{30,}", text)
        for i, m in enumerate(long_matches):
            tokens[f"long_{i}"] = m
    return tokens

def run_playwright_task():
    random_texts = [
        "Make a simple calculator in Python",
        "Generate a todo list app in React",
        "Write HTML for a login form",
        "Give me CSS for a navbar"
    ]
    message = random.choice(random_texts)

    with sync_playwright() as pw:
        # Launch Chromium (official image already contains browsers)
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)  # let SPA resources load a bit

            # Optional: click model selector if present
            try:
                model_locator = page.locator("text=GPT 4.1 Mini").first
                if model_locator.count() > 0:
                    model_locator.click(timeout=3000)
                    time.sleep(1)
            except Exception:
                pass

            # Fill the contenteditable input
            try:
                input_box = page.locator("div[contenteditable='true']").first
                if input_box.count() == 0:
                    return {"error": "input box not found"}
                input_box.evaluate("(el, text) => { el.innerText = text; el.dispatchEvent(new InputEvent('input', { bubbles: true })); }", message)
                time.sleep(0.3)
            except Exception as e:
                return {"error": f"failed to fill input: {str(e)}"}

            # Capture POST request containing "trigger?"
            req_info = None
            try:
                predicate = lambda req: ("trigger?" in req.url or "trigger?" in req.url.split("?")[0]) and req.method == "POST"
                with page.expect_request(predicate, timeout=15000) as req_ctx:
                    # Click send button; fallback to pressing Enter if not found
                    try:
                        send_btn = page.locator("button.MuiButtonBase-root.css-11uhnn1").first
                        if send_btn.count() > 0:
                            send_btn.click()
                        else:
                            input_box.press("Enter")
                    except Exception:
                        try:
                            input_box.press("Enter")
                        except Exception:
                            pass

                    req = req_ctx.value
                    # Extract data safely (some Request APIs are methods in different versions)
                    try:
                        post_data = req.post_data
                    except Exception:
                        try:
                            post_data = req.post_data()
                        except Exception:
                            post_data = ""
                    req_info = {
                        "url": req.url,
                        "method": req.method,
                        "headers": dict(req.headers),
                        "post_data": post_data or ""
                    }
            except PlaywrightTimeoutError:
                # timed out waiting for the request
                req_info = None
            except Exception as e:
                return {"error": f"error capturing request: {str(e)}"}

            tokens = {}
            if req_info and req_info.get("post_data"):
                tokens = extract_tokens_from_text(req_info["post_data"])

            return {
                "message_sent": message,
                "request": req_info,
                "tokens": tokens
            }
        finally:
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

@app.get("/{task_id}")
def process(task_id: str):
    try:
        result = run_playwright_task()
        return JSONResponse({"task_id": task_id, "result": result})
    except Exception as e:
        return JSONResponse({"task_id": task_id, "error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), log_level="info")
