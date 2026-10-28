import os
import httpx
import json
#  TO USE THIS YOU MUST FIRST TYPE : export OPENROUTER_API_KEY="ADD YOUR OWN KEY HERE"
#  THIS IS THE WAY IM TESTING THE API KEY IT SAVES IT ON YOUR TERMINAL 
#  MUST DOWNLOAD HTTPX ON YOUR VENV BEFORE TESTING 
OPENROUTER_URL =  "https://openrouter.ai/api/v1/chat/completions"

# read config from environment variables. Fail early if the key is missing.
# TODO add the env variables right now its hard coded 

def load_settings():
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3.5-super-vl:free")

    if not api_key:
        raise ValueError("API key is missing, set OPENROUTER_API_KEY")

    return api_key, model

# sends a question to the model and returns the answer.
def ask(question: str) -> str:
    api_key, model = load_settings()
    headers = {
        "Authorization" : f"Bearer {api_key}",
    }

    body = {
        "model" : model,
        "max_tokens" : 1500,   #increase this number to allow for more tokens. i found that 1500 is able to get a response most of the time wile having 400 will stop at the thinking stage for some modles
        "messages": [
            {"role" : "user", "content" : question}
        ],
    }

    response = httpx.post(OPENROUTER_URL, headers=headers, json=body, timeout=30 ) 

    if response.status_code == 200:
        data = response.json()
        choice = data["choices"][0]
        content = choice["message"]["content"]

        # for debugging and understanding the json keys, etc
        # print(json.dumps(data, indent=2)) 

        if not content:
            reason = choice.get("finish_reason")
            raise RuntimeError(f"Model returned no answer(finish_reason: {reason})")
        
        return content

        
    else:
        data = response.json()
        message = data["error"]["message"]
        raise RuntimeError((f"OpenRouter error {response.status_code}: {message}"))


    
if __name__ == "__main__":

    result = ask("what is the meaning of life?") # ADD YOUR QUESTION HERE TO TEST IT. WIP
    # TODO add logs for usage(total_tokens reasoning_tokens etc)

    print(result)