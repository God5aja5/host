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

def extract_tokens_from_text(text):
    tokens = {}
    # try parse as json first
    try:
        body = json.loads(text)
        if isinstance(body, dict):
            for k, v in body.items():
                if isinstance(v, str):
                    if re.match(r"^[A-Za-z0-9-]+\.[A-Za-z0-9-]+\.[A-Za-z0-9-]+$", v) or len(v) > 20:
                        tokens[k] = v
    except Exception:
        # fallback: regex find jwt-like or long alphanumeric sequences
        matches = re.findall(r"[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+", text)
        for i, m in enumerate(matches):
            tokens[f"match_{i}"] = m
        if not matches:
            long_matches = re.findall(r"[A-Za-z0-9\-_]{30,}", text)
            for i, m in enumerate(long_matches):
                tokens[f"longmatch_{i}"] = m
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
        browser = pw.chromium.launch(headless=True, args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ])
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            # give extra time for full page load if needed
            time.sleep(4)

            # Step 1: click model if present
            try:
                # locate element by text and click (first match)
                model_locator = page.locator("text=GPT 4.1 Mini").first
                if model_locator.count() > 0:
                    model_locator.click(timeout=5000)
                    time.sleep(1)
            except Exception:
                # ignore if not found
                pass

            # Step 2: fill contenteditable with our message
            try:
                input_box = page.locator("div[contenteditable='true']").first
                input_box.evaluate("(el, text) => { el.innerText = text; el.dispatchEvent(new InputEvent('input', { bubbles: true })); }", message)
                time.sleep(0.5)
            except Exception as e:
                return {"error": f"Could not find or fill input box: {str(e)}"}

            # prepare to capture the trigger request
            req_info = None
            try:
                # Use expect_request as context manager to capture the POST request containing 'trigger?'
                with page.expect_request(lambda req: ("trigger?" in req.url or "trigger?" in req.url.split("?")[0]) and req.method == "POST", timeout=15000) as ex_req:
                    # Click send button
                    try:
                        send_btn = page.locator("button.MuiButtonBase-root.css-11uhnn1").first
                        send_btn.click()
                    except Exception:
                        # fallback: press Enter in input_box
                        try:
                            input_box.press("Enter")
                        except Exception:
                            pass
                    # wait for the expected request
                    req = ex_req.value
                    req_info = {
                        "url": req.url,
                        "method": req.method,
                        "headers": dict(req.headers),
                        "post_data": req.post_data or ""
                    }
            except PlaywrightTimeoutError:
                # timed out waiting for request
                # Collect any recent requests that contain 'trigger?' as fallback
                recent = []
                for r in context.request._requests:  # private API fallback; best-effort
                    try:
                        if "trigger?" in r.url and r.method == "POST":
                            recent.append(r)
                    except Exception:
                        pass
                if recent:
                    r = recent[-1]
                    req_info = {
                        "url": getattr(r, "url", ""),
                        "method": getattr(r, "method", ""),
                        "headers": dict(getattr(r, "headers", {})),
                        "post_data": getattr(r, "post_data", "") or ""
                    }
                else:
                    req_info = None
            except Exception as e:
                return {"error": f"Error while capturing request: {str(e)}"}

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
