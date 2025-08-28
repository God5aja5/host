# Add these imports at top of your app.py
import requests
import datetime
import traceback
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Replace your existing run_playwright_task with this function
def run_playwright_task():
    URL = "https://workik.com/ai-code-generator"
    random_texts = [
        "Make a simple calculator in Python",
        "Generate a todo list app in React",
        "Write HTML for a login form",
        "Give me CSS for a navbar"
    ]
    message = random.choice(random_texts)

    # Quick HTTP reachability check from container (before launching browser)
    try:
        resp = requests.get(URL, timeout=8)
        # Accept any 2xx/3xx/4xx but if DNS fails or connection error it will raise
        reachable = True
    except Exception as e:
        return {
            "message_sent": message,
            "error": "Preflight HTTP check failed",
            "preflight_exception": repr(e),
            "hint": "Check outbound network/DNS from the host/container, or that the site doesn't block container IPs."
        }

    # Launch playwright and attempt navigation with retries and diagnostics
    diagnostics = {}
    with sync_playwright() as pw:
        # Add common container-friendly flags
        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-networking"
        ]
        browser = None
        try:
            browser = pw.chromium.launch(headless=True, args=launch_args)
        except Exception as e:
            return {"error": "Browser launch failed", "exception": repr(e), "trace": traceback.format_exc()}

        context = browser.new_context(viewport={"width": 1280, "height": 800},
                                      user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118 Safari/537.36")
        page = context.new_page()

        # Quick connectivity sanity test: example.com
        try:
            page.goto("https://example.com", timeout=10000, wait_until="domcontentloaded")
            diagnostics["example_ok"] = True
        except Exception as e:
            diagnostics["example_ok"] = False
            diagnostics["example_exc"] = repr(e)

        # Try navigating to target with retries
        last_exc = None
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                nav_timeout = 30000 + (attempt - 1) * 30000  # 30s, 60s, 90s
                page.goto(URL, timeout=nav_timeout, wait_until="domcontentloaded")
                # small wait for SPA resources
                page.wait_for_timeout(1500)
                # success
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                diagnostics.setdefault("attempts", []).append({
                    "attempt": attempt,
                    "timeout_ms": nav_timeout,
                    "exception": repr(exc)
                })
                # on failure, try to capture some debug artifacts
                try:
                    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                    screenshot_path = f"/tmp/fail_nav_{ts}_att{attempt}.png"
                    page.screenshot(path=screenshot_path, full_page=False)
                    diagnostics[f"screenshot_attempt_{attempt}"] = screenshot_path
                except Exception as ss_e:
                    diagnostics[f"screenshot_err_{attempt}"] = repr(ss_e)
                # collect page content (trimmed)
                try:
                    content = page.content()[:8000]
                    diagnostics[f"page_content_attempt_{attempt}"] = content
                except Exception as c_e:
                    diagnostics[f"page_content_err_{attempt}"] = repr(c_e)
                # small backoff before next attempt
                page.wait_for_timeout(1000 * attempt)

        # If navigation never succeeded, return diagnostics
        if last_exc is not None:
            # Close resources
            try:
                context.close()
            except:
                pass
            try:
                browser.close()
            except:
                pass
            return {
                "message_sent": message,
                "error": "Navigation failed after retries",
                "last_exception": repr(last_exc),
                "diagnostics": diagnostics,
                "hint": "If example.com also failed, container likely has no outbound network or DNS. If example succeeded but target failed, site may block Render IPs or require extra headers."
            }

        # From here, page is loaded. Continue the rest of your logic:
        try:
            # click the GPT model if present
            try:
                model_locator = page.locator("text=GPT 4.1 Mini").first
                if model_locator.count() > 0:
                    model_locator.click(timeout=3000)
                    page.wait_for_timeout(500)
            except Exception:
                pass

            # fill contenteditable
            try:
                input_box = page.locator("div[contenteditable='true']").first
                if input_box.count() == 0:
                    raise RuntimeError("input box not found")
                input_box.evaluate("(el, text) => { el.innerText = text; el.dispatchEvent(new InputEvent('input', { bubbles: true })); }", message)
                page.wait_for_timeout(300)
            except Exception as e:
                # close and return
                context.close()
                browser.close()
                return {"message_sent": message, "error": "failed to fill input", "exception": repr(e)}

            # capture request
            req_info = None
            try:
                predicate = lambda req: ("trigger?" in req.url or "trigger?" in req.url.split("?")[0]) and req.method == "POST"
                with page.expect_request(predicate, timeout=15000) as req_ctx:
                    # send
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
                    post_data = getattr(req, "post_data", "") or ""
                    req_info = {"url": req.url, "method": req.method, "headers": dict(req.headers), "post_data": post_data}
            except PlaywrightTimeoutError:
                req_info = None
            except Exception as e:
                req_info = {"capture_error": repr(e)}

            # final cleanup
            try:
                context.close()
            except:
                pass
            try:
                browser.close()
            except:
                pass

            # return successful result
            return {"message_sent": message, "request": req_info, "tokens": {}, "diagnostics": diagnostics}

        except Exception as e:
            try:
                context.close()
            except:
                pass
            try:
                browser.close()
            except:
                pass
            return {"message_sent": message, "error": "unexpected failure", "exception": repr(e), "trace": traceback.format_exc(), "diagnostics": diagnostics}
