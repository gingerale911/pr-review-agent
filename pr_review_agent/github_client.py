import os
import subprocess
from github import Github
from pr_review_agent.logging_utils import log_action


def get_github_client() -> Github:
    log_action("tool", "GitHub client init", "source=env_or_gh_cli")
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        try:
            token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
        except Exception:
            token = None
    if not token:
        raise RuntimeError(
            "No GitHub token available. Set GITHUB_TOKEN or run 'gh auth login' and ensure 'gh auth token' works."
        )
    return Github(token)


def get_repo_and_pr(pr_url: str):
    g = get_github_client()
    parts = pr_url.rstrip("/").split("/")
    target = f"{parts[-4]}/{parts[-3]}"
    log_action("tool", "GitHub API call", f"method=get_repo owner_repo={target}")
    repo = g.get_repo(target)
    pr_number = int(parts[-1])
    log_action("tool", "GitHub API call", f"method=get_pull number={pr_number}")
    pr = repo.get_pull(pr_number)
    return repo, pr


def get_repo(pr_url: str):
    g = get_github_client()
    parts = pr_url.rstrip("/").split("/")
    target = f"{parts[-4]}/{parts[-3]}"
    log_action("tool", "GitHub API call", f"method=get_repo owner_repo={target}")
    return g.get_repo(target)


def get_file_at_ref(repo, filename: str, ref: str) -> str:
    try:
        log_action("tool", "GitHub API call", f"method=get_contents repo={repo.full_name} ref={ref} path={filename}")
        content = repo.get_contents(filename, ref=ref)
        return content.decoded_content.decode("utf-8")
    except Exception:
        log_action("tool", "GitHub API call", f"method=get_contents failed repo={repo.full_name} ref={ref} path={filename}")
        return ""


def post_review_comment(pr_url: str, review_text: str) -> str:
    repo, pr = get_repo_and_pr(pr_url)
    body = f"## 🤖 Automated PR Review\n\n{review_text}"
    log_action("tool", "GitHub API call", f"method=create_issue_comment repo={repo.full_name} pr={pr.number}")
    comment = pr.create_issue_comment(body)
    return getattr(comment, "html_url", "") or getattr(comment, "url", "")
