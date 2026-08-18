import logging
import re
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "output.txt"

logger = logging.getLogger("pr_review_agent")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    handler = logging.FileHandler(OUTPUT_PATH)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def redact_secrets(value: str) -> str:
    if not isinstance(value, str):
        return value

    redacted = re.sub(r"(key=)([^&\s]+)", r"\1[REDACTED]", value, flags=re.IGNORECASE)
    redacted = re.sub(r"(token=)([^&\s]+)", r"\1[REDACTED]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(Authorization:\s*Bearer\s+)([^\s]+)", r"\1[REDACTED]", redacted, flags=re.IGNORECASE)
    return redacted


def reset_log():
    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        handle.write("")
    logger.info("node app - action: start")


def log_action(node_name: str, action: str, details: str = ""):
    message = f"node {node_name} - action: {action}"
    if details:
        message = f"{message}\n{redact_secrets(details)}"
    logger.info(redact_secrets(message))


def log_transition(from_node: str, to_node: str):
    logger.info(redact_secrets(f"node {from_node} - action: complete"))
    logger.info(redact_secrets(f"--create node {to_node}---"))
    logger.info(redact_secrets(f"--move to node {to_node} --"))


def log_final_review(review: str):
    logger.info("\n=== FINAL LLM REVIEW ===")
    logger.info(redact_secrets(review))
