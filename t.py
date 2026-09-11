import json
import os
import sys
import urllib.error
import urllib.request

# -------------------------------------------------------------
# Fix Windows Console Encoding (Supports Python 3.6+ & cp1252)
# -------------------------------------------------------------
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        import codecs
        try:
            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach(), errors="replace")
        except Exception:
            pass

def safe_print(text=""):
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            enc = sys.stdout.encoding or "ascii"
            print(text.encode(enc, errors="replace").decode(enc))
        except Exception:
            print(text.encode("ascii", errors="replace").decode("ascii"))

# -------------------------------------------------------------
# 1. Load .env File (Zero Dependencies / Built-in Python)
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

def load_env():
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip("'\"")
        except Exception:
            pass

def clean_key(k):
    k = (k or "").strip().strip("'\"")
    while "GEMINI_API_KEY=" in k:
        k = k.replace("GEMINI_API_KEY=", "").strip().strip("'\"")
    return k

load_env()
api_key = clean_key(os.getenv("GEMINI_API_KEY", ""))

def prompt_for_api_key():
    global api_key
    safe_print("\n" + "="*55)
    safe_print("[!] Valid Gemini API Key nahi mili.")
    safe_print("[*] Free API Key yahan se banayein: https://aistudio.google.com/apikey")
    safe_print("="*55)
    try:
        new_key = input("[*] Apni Gemini API Key yahan paste karein: ").strip()
    except Exception:
        new_key = ""
    new_key = clean_key(new_key)
    if new_key:
        api_key = new_key
        try:
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write(f"GEMINI_API_KEY={new_key}\n")
            safe_print("[+] API Key .env file mein save ho gayi hai!\n")
        except Exception as e:
            safe_print(f"[!] .env file save karne mein error: {e}")
    else:
        safe_print("[X] Bina API Key ke bot nahi chal sakta.")
        sys.exit(1)

if not api_key or api_key == "your_gemini_api_key_here":
    prompt_for_api_key()

# -------------------------------------------------------------
# 2. Gemini API Call Function (Built-in urllib - No Pip Needed!)
# -------------------------------------------------------------
MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

def call_gemini(conversation_history, model_name=None):
    models_to_try = [model_name] if model_name else MODELS
    last_err = None
    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        payload = json.dumps({"contents": conversation_history}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                try:
                    return result["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    return "Maaf kijiye, response format samajh nahi aaya."
        except urllib.error.HTTPError as err:
            last_err = err
            if err.code == 404:
                continue
            raise err
    if last_err:
        raise last_err
    return "Maaf kijiye, response format samajh nahi aaya."

# -------------------------------------------------------------
# 3. Interactive Chatbot Loop
# -------------------------------------------------------------
safe_print("\n" + "="*55)
safe_print("[AI Chatbot Ready Hai! Bahar nikalne ke liye 'exit' likhein]")
safe_print("="*55)

history = []

while True:
    try:
        user_input = input("\n[Aap]: ")
    except (KeyboardInterrupt, EOFError):
        safe_print("\n[AI]: Alvida!")
        break

    cleaned = user_input.strip()
    if cleaned.lower() in ["exit", "quit", "bye"]:
        safe_print("[AI]: Alvida! Phir milenge.")
        break

    if not cleaned:
        continue

    # Conversation history maintain karein
    history.append({"role": "user", "parts": [{"text": cleaned}]})

    try:
        reply = call_gemini(history)
        history.append({"role": "model", "parts": [{"text": reply}]})
        safe_print(f"\n[AI]: {reply}")

    except urllib.error.HTTPError as err:
        try:
            error_data = json.loads(err.read().decode("utf-8"))
            error_message = error_data.get("error", {}).get("message", str(err))
        except Exception:
            error_message = str(err)

        safe_print(f"\n[X] API Error ({err.code}): {error_message}")

        # Agar API key invalid ho
        if err.code in [400, 401, 403]:
            safe_print("\n[!] Lagta hai aapki API Key galat ya expire ho gayi hai.")
            prompt_for_api_key()
            try:
                reply = call_gemini(history)
                history.append({"role": "model", "parts": [{"text": reply}]})
            except Exception as retry_err:
                if hasattr(retry_err, "read"):
                    try:
                        err_body = json.loads(retry_err.read().decode("utf-8"))
                        msg = err_body.get("error", {}).get("message", str(retry_err))
                        safe_print(f"[X] Retry error: {msg}")
                    except Exception:
                        safe_print(f"[X] Retry error: {retry_err}")
                else:
                    safe_print(f"[X] Retry error: {retry_err}")
                history.pop()
        else:
            try:
                safe_print("[*] Alternate model se try kar rahe hain...")
                reply = call_gemini(history, model_name=MODELS[1])
                history.append({"role": "model", "parts": [{"text": reply}]})
                safe_print(f"\n[AI]: {reply}")
            except Exception as retry_err:
                safe_print(f"[X] Alternate model fail: {retry_err}")
                history.pop()

    except Exception as e:
        safe_print(f"\n[X] Network / Connection Error: {e}")
        history.pop()
