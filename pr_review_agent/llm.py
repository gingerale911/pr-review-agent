import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

# We use getenv with a fallback during initial import/tests so it doesn't crash if keys are missing
api_key = os.getenv("ANTHROPIC_API_KEY", "dummy-key-for-testing")
model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

# If they specified claude-sonnet-4-6 in the design docs, we can default to it or fall back
if os.getenv("ANTHROPIC_MODEL") is None:
    model_name = "claude-3-5-sonnet-20241022"  # or "claude-3-5-sonnet-latest"

model = ChatAnthropic(
    model=model_name,
    api_key=api_key,
)
