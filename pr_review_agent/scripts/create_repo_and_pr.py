#!/usr/bin/env python3
"""Create a new GitHub repo and open a PR with intentionally faulty code.

Requires: GITHUB_TOKEN in environment with `repo` scope.
"""
import os
import time
from github import Github


def main():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN not set in environment")
        return 2

    g = Github(token)
    user = g.get_user()
    ts = int(time.time())
    repo_name = f"pr-review-agent-test-{ts}"

    print("Creating repo:", repo_name)
    repo = user.create_repo(repo_name, private=True, description="Test repo created by script")
    print("Repo created:", repo.html_url)

    # Create an initial README on main
    repo.create_file("README.md", "Initial commit", "# Test repo\n", branch="main")

    # Create a buggy branch from main
    main_ref = repo.get_git_ref("heads/main")
    branch_name = "buggy-branch"
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_ref.object.sha)
    print("Created branch:", branch_name)

    # Add a faulty file (syntax error) to the buggy branch
    buggy_content = "def broken_func(:\n    pass\n"
    repo.create_file("buggy.py", "Add buggy code", buggy_content, branch=branch_name)
    print("Added buggy file on branch:", branch_name)

    # Open a PR from buggy-branch into main
    pr = repo.create_pull(title="[TEST] Faulty code PR", body="This PR intentionally introduces faulty code for testing.", head=branch_name, base="main")
    print("Opened PR:", pr.html_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
