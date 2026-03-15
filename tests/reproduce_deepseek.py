import os

from dotenv import load_dotenv
from litellm import completion

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
print(f"API Key loaded: {api_key[:4]}...{api_key[-3:]}")

try:
    print("Sending request to DeepSeek via LiteLLM...")
    response = completion(
        model="deepseek/deepseek-chat",
        messages=[{"role": "user", "content": "Hello"}],
        api_key=api_key,
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
