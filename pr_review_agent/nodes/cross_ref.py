from typing import Dict
from pr_review_agent.state import PRState
from pr_review_agent.github_client import get_repo, get_file_at_ref
from pr_review_agent.logging_utils import log_action


def read_cross_ref(state: PRState) -> Dict:
    log_action("read_cross_ref", "read related files", f"files={state.get('cross_ref_files', [])}")
    repo = get_repo(state["pr_url"])
    base = state["pr_metadata"]["base"]

    already_read = state.get("cross_ref_contents", {})
    new_contents = {}
    for filename in state.get("cross_ref_files", []):
        if filename in already_read:
            continue
        new_contents[filename] = get_file_at_ref(repo, filename, base)

    result = {
        "cross_ref_contents": {**already_read, **new_contents},
        "observations": [f"Read cross-ref: {list(new_contents.keys())}"],
    }
    log_action("read_cross_ref", "completed", f"loaded={list(new_contents.keys())}")
    return result
