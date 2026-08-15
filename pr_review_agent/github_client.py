import os
from github import Github


def get_github_client() -> Github:
    token = os.getenv("GITHUB_TOKEN")
    return Github(token)


def get_repo_and_pr(pr_url: str):
    g = get_github_client()
    parts = pr_url.rstrip("/").split("/")
    repo = g.get_repo(f"{parts[-4]}/{parts[-3]}")
    pr = repo.get_pull(int(parts[-1]))
    return repo, pr


def get_repo(pr_url: str):
    g = get_github_client()
    parts = pr_url.rstrip("/").split("/")
    return g.get_repo(f"{parts[-4]}/{parts[-3]}")


def get_file_at_ref(repo, filename: str, ref: str) -> str:
    try:
        content = repo.get_contents(filename, ref=ref)
        return content.decoded_content.decode("utf-8")
    except Exception:
        return ""
