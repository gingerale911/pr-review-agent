from langgraph.types import Send
from langchain_core.messages import HumanMessage
from typing import Dict
from pr_review_agent.state import PRState
from pr_review_agent.llm import model
from pr_review_agent.logging_utils import log_action

REVIEW_PROMPT = """\
You are a senior engineer reviewing a pull request.

File: {filename}

--- DIFF ---
{diff}

--- FULL FILE (base branch) ---
{context}

--- RELATED FILES ---
{cross_ref}

Review this change. Report:
* Runtime errors and exceptions
* Undefined variables / scope issues
* Python evaluation-order problems
* String interpolation and .format() mistakes
* Incorrect control flow
* Type mismatches and malformed data
* API/integration failures
* Security and performance bugs
* Concrete impact and fixes
* Distinguishing actionable defects from speculative concerns

Be concise. Use bullet points. Say "LGTM" if no issues.
"""


def analyze_single_file(state: PRState) -> Dict:
    filename = state["_current_file"]
    log_action("analyze_single_file", f"review file {filename}")
    cross_ref = "\n\n".join(
        f"// {f}\n{c[:2000]}"
        for f, c in state.get("cross_ref_contents", {}).items()
    )
    response = model.invoke([
        HumanMessage(content=REVIEW_PROMPT.format(
            filename=filename,
            diff=state["diff_by_file"].get(filename, "")[:4000],
            context=state["context_files"].get(filename, "")[:4000],
            cross_ref=cross_ref[:3000],
        ))
    ])
    result = {
        "file_reviews": [{"file": filename, "review": response.content}],
        "observations": [f"Reviewed {filename}"],
    }
    log_action("analyze_single_file", "completed", f"file={filename}")
    return result


def fan_out_files(state: PRState) -> list[Send]:
    files = state.get("changed_files", [])
    log_action("fan_out_files", "dispatch file analysis", f"files={files}")
    return [
        Send("analyze_single_file", {**state, "_current_file": f})
        for f in files
    ]
