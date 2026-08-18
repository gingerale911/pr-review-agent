from langchain_core.messages import HumanMessage
from typing import Dict
from pr_review_agent.state import PRState
from pr_review_agent.llm import model
from pr_review_agent.logging_utils import log_action, log_final_review

SYNTHESIS_PROMPT = """\
PR title: "{title}"

Per-file reviews:
{findings}

Security findings:
{security}

Write a final PR review:
- Overall verdict: APPROVE / REQUEST CHANGES / COMMENT
- Critical issues
- Concerns by severity
- Suggested next steps
"""


def synthesize(state: PRState) -> Dict:
    log_action("synthesize", "compose final PR review")
    findings = "\n\n".join(
        f"### {r['file']}\n{r['review']}" for r in state.get("file_reviews", [])
    )
    security = "\n".join(
        f"- [{f['severity']}] {f['file']}: {f['issue']}"
        for f in state.get("security_findings", [])
    ) or "None"

    response = model.invoke([HumanMessage(content=SYNTHESIS_PROMPT.format(
        title=state.get("pr_metadata", {}).get("title", ""),
        findings=findings,
        security=security,
    ))])
    log_final_review(response.content)
    log_action("synthesize", "completed", "final review generated")
    return {"final_review": response.content}
