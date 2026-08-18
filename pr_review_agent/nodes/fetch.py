from typing import Dict
from pr_review_agent.state import PRState
from pr_review_agent.github_client import get_repo_and_pr, get_repo, get_file_at_ref
from pr_review_agent.logging_utils import log_action


def fetch_pr(state: PRState) -> Dict:
    log_action("fetch_pr", "fetch PR metadata and diffs")
    repo, pr = get_repo_and_pr(state["pr_url"])

    changed_files, diff_by_file = [], {}
    for f in pr.get_files():
        changed_files.append(f.filename)
        diff_by_file[f.filename] = f.patch or ""

    result = {
        "pr_metadata": {
            "title": pr.title,
            "author": pr.user.login,
            "base": pr.base.ref,
            "body": pr.body or "",
        },
        "changed_files": changed_files,
        "diff_by_file": diff_by_file,
    }
    log_action("fetch_pr", "completed", f"files={changed_files}")
    return result


def expand_context(state: PRState) -> Dict:
    log_action("expand_context", "load base-file context")
    repo = get_repo(state["pr_url"])
    base = state["pr_metadata"]["base"]

    context_files = {
        filename: get_file_at_ref(repo, filename, base)
        for filename in state.get("changed_files", [])
    }
    log_action("expand_context", "completed", f"context_files={list(context_files.keys())}")
    return {"context_files": context_files}
