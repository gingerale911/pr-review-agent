import json
from langchain_core.messages import HumanMessage
from typing import Dict
from pr_review_agent.state import PRState
from pr_review_agent.llm import model
from pr_review_agent.logging_utils import log_action

DECISION_PROMPT = """\
You are orchestrating a PR review.

Changed files: {changed_files}
Files already read: {files_read}
Observations:
{observations}

Decide the next action:
- "read_more": need more context (list which files)
- "security_check": diff touches auth/crypto/sessions/permissions
- "synthesize": enough info for final review

Respond ONLY in JSON:
{{"action": "read_more"|"security_check"|"synthesize",
  "files_to_read": [],
  "reason": "..."}}
"""


def decide_next_action(state: PRState) -> Dict:
    log_action("decide_next_action", "evaluate next action")
    if state.get("iteration", 0) >= 3:
        log_action("decide_next_action", "iteration limit reached", "next_action=synthesize")
        return {"next_action": "synthesize"}

    files_read = (
        list(state.get("context_files", {}).keys())
        + list(state.get("cross_ref_contents", {}).keys())
    )

    response = model.invoke([
        HumanMessage(content=DECISION_PROMPT.format(
            changed_files=state.get("changed_files", []),
            files_read=files_read,
            observations="\n".join(state.get("observations", [])),
        ))
    ])

    try:
        result = json.loads(response.content)
    except Exception:
        log_action("decide_next_action", "fallback decision", "next_action=synthesize")
        return {"next_action": "synthesize", "iteration": state.get("iteration", 0) + 1}

    chosen = result["action"]
    log_action("decide_next_action", "decision made", f"action={chosen}; reason={result.get('reason', '')}")
    return {
        "next_action": chosen,
        "cross_ref_files": result.get("files_to_read", []),
        "iteration": state.get("iteration", 0) + 1,
        "observations": [f"Decision: {result.get('reason', '')}"],
    }
