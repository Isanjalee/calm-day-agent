import os
from groq import Groq

def ask_groq(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "GROQ_API_KEY missing."

    client = Groq(api_key=api_key)

    chat = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a calm, gentle daily planning assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
        max_tokens=600
    )
    return chat.choices[0].message.content.strip()
