from typing import Dict
from pr_review_agent.state import PRState
from pr_review_agent.github_client import get_repo, get_file_at_ref


def read_cross_ref(state: PRState) -> Dict:
    repo = get_repo(state["pr_url"])
    base = state["pr_metadata"]["base"]

    already_read = state.get("cross_ref_contents", {})
    new_contents = {}
    for filename in state.get("cross_ref_files", []):
        if filename in already_read:
            continue
        new_contents[filename] = get_file_at_ref(repo, filename, base)

    return {
        "cross_ref_contents": {**already_read, **new_contents},
        "observations": [f"Read cross-ref: {list(new_contents.keys())}"],
    }
