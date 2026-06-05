from openai import AsyncOpenAI
import asyncio
from backend.core.config import GROQ_API_KEY

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

MODEL_NAME = "llama-3.1-8b-instant"
print("MODEL =", MODEL_NAME)
print("KEY EXISTS =", GROQ_API_KEY is not None)


async def call_llm(
    prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 800,
) -> str:
    print("PROMPT LEN =", len(prompt))
    retries = 3

    for attempt in range(retries):

        try:
            print("CALLING GROQ...")

            response = await asyncio.wait_for(

                client.chat.completions.create(

                    model=MODEL_NAME,

                    temperature=temperature,

                    max_tokens=max_tokens,

                    messages=[

                        {
                            "role": "system",
                            "content":
                                "You are a precise technical AI interviewer."
                        },

                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                ),

                timeout=45,
            )

            return (
                response
                .choices[0]
                .message.content
                .strip()
            )

        except Exception as e:

            print(
                f"[LLM] attempt {attempt+1} failed: {e}"
            )

            if attempt == retries - 1:
                raise

            await asyncio.sleep(1.5)

async def call_llm_json(
    prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 800,
) -> dict:

    import json
    import re

    raw = await call_llm(prompt, temperature, max_tokens)

    cleaned = re.sub(r"```(?:json)?", "", raw)
    cleaned = re.sub(r"```", "", cleaned).strip()

    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)

    if match:
        cleaned = match.group(1)

    try:
        return json.loads(cleaned)

    except Exception:
        return {}


async def call_llm_streaming(
    prompt: str,
    temperature: float = 0.0
):

    stream = await client.chat.completions.create(
        model=MODEL_NAME,
        temperature=temperature,
        stream=True,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    async for chunk in stream:

        delta = chunk.choices[0].delta.content

        if delta:
            yield delta
























# import json
# import re
# import httpx
# from backend.core.config import OLLAMA_BASE_URL, LLM_MODEL


# async def call_llm(prompt: str, temperature: float = 0.0) -> str:
#     """Non-streaming LLM call via Ollama /api/generate."""
#     async with httpx.AsyncClient(timeout=120.0) as client:
#         resp = await client.post(
#             f"{OLLAMA_BASE_URL}/api/generate",
#             json={
#                 "model": LLM_MODEL,
#                 "prompt": prompt,
#                 "stream": False,
#                 "options": {"temperature": temperature},
#             },
#         )
#         resp.raise_for_status()
#         return resp.json().get("response", "").strip()


# async def call_llm_json(prompt: str, temperature: float = 0.0) -> dict:
#     """
#     Call LLM and parse JSON response.
#     Strips markdown fences if present.
#     Returns {} on parse failure.
#     """
#     raw = await call_llm(prompt, temperature)

#     # Strip ```json ... ``` fences
#     cleaned = re.sub(r"```(?:json)?\s*", "", raw)
#     cleaned = re.sub(r"```", "", cleaned).strip()

#     # Extract first {...} or [...] block
#     match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
#     if match:
#         cleaned = match.group(1)

#     try:
#         return json.loads(cleaned)
#     except json.JSONDecodeError:
#         return {}


# async def call_llm_streaming(prompt: str, temperature: float = 0.0):
#     """
#     Async generator — yields text tokens for SSE streaming.
#     Usage:
#         async for token in call_llm_streaming(prompt):
#             yield token
#     """
#     async with httpx.AsyncClient(timeout=120.0) as client:
#         async with client.stream(
#             "POST",
#             f"{OLLAMA_BASE_URL}/api/generate",
#             json={
#                 "model": LLM_MODEL,
#                 "prompt": prompt,
#                 "stream": True,
#                 "options": {"temperature": temperature},
#             },
#         ) as resp:
#             resp.raise_for_status()
#             async for line in resp.aiter_lines():
#                 if not line:
#                     continue
#                 try:
#                     data = json.loads(line)
#                     token = data.get("response", "")
#                     if token:
#                         yield token
#                     if data.get("done"):
#                         break
#                 except json.JSONDecodeError:
#                     continue
