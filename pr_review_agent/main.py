import argparse
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from pr_review_agent.graph import graph


def parse_args():
    parser = argparse.ArgumentParser(description="Run the PR review agent on a GitHub pull request.")
    parser.add_argument("--pr-url", default=os.getenv("PR_URL"), help="GitHub PR URL, e.g. https://github.com/OWNER/REPO/pull/123")
    parser.add_argument("--question", default="Review this PR.", help="Optional question for the reviewer")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    pr_url = args.pr_url or "https://github.com/OWNER/REPO/pull/NUMBER"
    result = graph.invoke({
        "pr_url": pr_url,
        "question": args.question,
    })
    print(result.get("final_review", "(no review generated)"))
