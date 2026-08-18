import json
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from typing import Dict
from pr_review_agent.state import PRState
from pr_review_agent.llm import model
from pr_review_agent.logging_utils import log_action

SECURITY_CHECKS = [
    "SQL injection", "XSS / template injection",
    "Broken authentication", "Insecure direct object reference",
    "Sensitive data in logs or cookies", "Missing authorization checks",
]


def security_scan(state: PRState) -> Dict:
    log_action("security_scan", "run security checks")
    findings = []
    for filename, diff in state.get("diff_by_file", {}).items():
        response = model.invoke([HumanMessage(content=f"""\
Security review of this diff.

File: {filename}
{diff[:4000]}

Check for: {checks}

Return JSON: [{{"issue":"...","severity":"HIGH|MEDIUM|LOW","line_hint":"..."}}]
Return [] if none.
""".format(filename=filename, diff=diff, checks=", ".join(SECURITY_CHECKS)))])
        try:
            parsed = json.loads(response.content)
            for f in parsed:
                f["file"] = filename
                findings.append(f)
        except Exception:
            # ignore parse errors
            continue

    result = {
        "security_findings": findings,
        "observations": [f"Security scan: {len(findings)} issues found."],
    }
    log_action("security_scan", "completed", f"issues={len(findings)}")
    return result


sec_builder = StateGraph(PRState)
sec_builder.add_node("security_scan", security_scan)
sec_builder.add_edge(START, "security_scan")
sec_builder.add_edge("security_scan", END)
security_subgraph = sec_builder.compile()
