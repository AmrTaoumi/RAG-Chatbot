import logging
import os
import sys
import time
import httpx

# OpenRouter client for the chat service.
# Reads OPENROUTER_API_KEY and OPENROUTER_MODEL from the environment (.env via docker compose).
OPENROUTER_URL =  "https://openrouter.ai/api/v1/chat/completions"



logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5         # 4 waits of 1+2+4+8 = 15s max, so a user never waits much longer than 15s plus request time
BASE_DELAY = 1         # seconds; doubles each retry (exponential backoff) to give rate limits time to reset
RETRYABLE_STATUS = {429, 500, 502, 503, 504} # temporary errors
MAX_TOKENS = 4000         # reasoning models used all 400 tokens on thinking and returned no answer. 4000 tokens is the max alloted by OPENROUTER
TIMEOUT_SECONDS = 30


def load_settings():
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL") or "nvidia/nemotron-3.5-super-vl:free"

    if not api_key:
        raise ValueError("API key is missing, set OPENROUTER_API_KEY")

    return api_key, model

def backoff_delay(attempt, response=None):
    # BASE_DELAY = 1: attempts 1 = 1s, 2 = 2s, 3 = 4s, 4 = 8s.
    return BASE_DELAY * 2 ** (attempt - 1) # we need to justify this number. it it fine to wait max 15 seconds total for a response before fail

# sends a question to the model and returns the answer.
def ask(messages, temperature=0.2):
    api_key, model = load_settings()
    headers = {
        "Authorization" : f"Bearer {api_key}",
    }

    body = {
        "model" : model,
        "max_tokens" : MAX_TOKENS,   #increase this number to allow for more tokens. i found that 1500 is able to get a response most of the time wile having 400 will stop at the thinking stage for some modles
        "temperature": temperature,
        "messages": messages,
    }

    logger.debug("OpenRouter request model=%s max_tokens=%d", model, body["max_tokens"])
    start = time.monotonic()

    for attempt in range(1, MAX_ATTEMPTS + 1):
        is_last_attempt = (attempt == MAX_ATTEMPTS)

        try:
            response = httpx.post(OPENROUTER_URL, headers=headers, json=body, timeout=TIMEOUT_SECONDS)
        
        except httpx.TransportError:
            if is_last_attempt:
                logger.error("OpenRouter timed out attempts=%d", attempt)
                raise RuntimeError(f"OpenRouter timed out after {attempt} attempts")
            delay = backoff_delay(attempt)
            logger.warning("OpenRouter timeout attempt=%d/%d retry_in=%ds", attempt, MAX_ATTEMPTS, delay)
            time.sleep(delay)
            continue


        if response.status_code == 200:
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
    
            # for debugging and understanding the json keys, etc
            # print(json.dumps(data, indent=2)) 
    
            if not content:
                reason = choice.get("finish_reason")
                logger.error("OpenRouter empty answer finish_reason=%s", reason)
                raise RuntimeError(f"Model returned no answer (finish_reason: {reason})")

            usage = data.get("usage", {})
            logger.info(
                "OpenRouter success model=%s attempt=%d elapsed=%.2fs prompt_tokens=%s completion_tokens=%s",
                model, attempt, time.monotonic() - start,
                usage.get("prompt_tokens"), usage.get("completion_tokens"),
            )
            return content

        

        if response.status_code in RETRYABLE_STATUS and not is_last_attempt:
            delay = backoff_delay(attempt, response)
            logger.warning("OpenRouter status=%d attempt=%d/%d retry_in=%ds",response.status_code, attempt, MAX_ATTEMPTS, delay)
            time.sleep(delay)
            continue
        # vlaue error check if it is a jsnon and key error to check the key
        try:
            message = response.json()["error"]["message"]
        except (ValueError, KeyError):
            message = response.text[:200]
        logger.error("OpenRouter failed status=%d message=%s", response.status_code, message)
        raise RuntimeError(f"OpenRouter error {response.status_code}: {message}")

  
if __name__ == "__main__":

    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
    )
    
    logging.getLogger("httpx").setLevel(logging.WARNING)
    result = ask([{"role": "user", "content": "What happens if I miss an exam?"}])

    print(result)
