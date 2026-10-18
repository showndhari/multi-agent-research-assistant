import json
import os
import re
from groq import Groq, APIError


class ConfigError(RuntimeError):
    pass


class ServiceError(RuntimeError):
    pass


def complete(system, user, max_tokens=3000):
    key = os.getenv("GROQ_API_KEY")

    if not key:
        raise ConfigError("GROQ_API_KEY is not set")

    try:
        client = Groq(api_key=key, timeout=90, max_retries=2)

        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0,
        )

        result = response.choices[0].message.content

        if not result:
            raise ServiceError("Groq returned an empty response")

        return result

    except APIError as e:
        raise ServiceError(f"Groq API error: {e}") from e


def complete_json(system, user, max_tokens=3000):
    text = complete(
        system + "\nReturn ONLY a valid JSON object, no prose or code fences.",
        user,
        max_tokens,
    )

    # Extract a JSON object, including multiline objects.
    match = re.search(r"\{.*\}", text, re.S)

    if not match:
        raise ServiceError("LLM returned no JSON object")

    try:
        result = json.loads(match.group(0))

        if not isinstance(result, dict):
            raise ServiceError("LLM response must be a JSON object")

        return result

    except json.JSONDecodeError as e:
        raise ServiceError(f"LLM returned invalid JSON: {e}") from e