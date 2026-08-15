from langgraph.types import Send
from langchain_core.messages import HumanMessage
from typing import Dict
from pr_review_agent.state import PRState
from pr_review_agent.llm import model

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
1. Correctness issues
2. Security concerns
3. Performance concerns
4. Missing tests
5. Style / readability

Be concise. Use bullet points. Say "LGTM" if no issues.
"""


def analyze_single_file(state: PRState) -> Dict:
    filename = state["_current_file"]
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
    return {
        "file_reviews": [{"file": filename, "review": response.content}],
        "observations": [f"Reviewed {filename}"],
    }


def fan_out_files(state: PRState) -> list[Send]:
    return [
        Send("analyze_single_file", {**state, "_current_file": f})
        for f in state.get("changed_files", [])
    ]
