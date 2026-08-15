from langchain_core.messages import HumanMessage
from typing import Dict
from pr_review_agent.state import PRState
from pr_review_agent.llm import model

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
    return {"final_review": response.content}
