from typing import Dict
from pr_review_agent.state import PRState
from pr_review_agent.github_client import get_repo_and_pr, get_repo, get_file_at_ref


def fetch_pr(state: PRState) -> Dict:
    repo, pr = get_repo_and_pr(state["pr_url"])

    changed_files, diff_by_file = [], {}
    for f in pr.get_files():
        changed_files.append(f.filename)
        diff_by_file[f.filename] = f.patch or ""

    return {
        "pr_metadata": {
            "title": pr.title,
            "author": pr.user.login,
            "base": pr.base.ref,
            "body": pr.body or "",
        },
        "changed_files": changed_files,
        "diff_by_file": diff_by_file,
    }


def expand_context(state: PRState) -> Dict:
    repo = get_repo(state["pr_url"])
    base = state["pr_metadata"]["base"]

    context_files = {
        filename: get_file_at_ref(repo, filename, base)
        for filename in state.get("changed_files", [])
    }
    return {"context_files": context_files}
