# PR Review Agent Operating Manual

This project reviews a GitHub pull request using a configured Gemini / Google AI Studio model and a GitHub token.

## 1. Set up environment variables

Create a local file named `.env` in the project root or in `pr_review_agent/.env` if that is how your shell is configured.

Use this format:

```env
GITHUB_TOKEN=your_github_token_here
AI_STUDIO_API_KEY=your_google_ai_studio_key_here
AI_STUDIO_MODEL=models/gemini-3.1-flash-lite
```

Notes:
- `GITHUB_TOKEN` is used for GitHub API access.
- `AI_STUDIO_API_KEY` is the Google AI Studio / Gemini API key.
- `AI_STUDIO_MODEL` should be a valid model name. The verified working light model is:
  - `models/gemini-3.1-flash-lite`

The repo also includes a sample file at `pr_review_agent/.env.example` with the expected keys.

## 2. Install dependencies

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r pr_review_agent/requirements.txt
```

## 3. Set the PR URL

The agent expects a GitHub PR URL in the format:

```text
https://github.com/OWNER/REPO/pull/NUMBER
```

Example:

```text
https://github.com/gingerale911/pr-review-agent-test-1786830433/pull/1
```

You can set this directly in code or pass it in when invoking the graph from Python.

## 4. Run the agent

### Option A: use the built-in runner

```bash
export $(grep -v '^#' pr_review_agent/.env | xargs)
.venv/bin/python pr_review_agent/main.py
```

This runner currently calls the graph with a PR URL defined in code. If you want a different PR, edit the URL in `pr_review_agent/main.py` before running it.

### Option B: run the graph directly in Python

```bash
export $(grep -v '^#' pr_review_agent/.env | xargs)
.venv/bin/python - <<'PY'
from pr_review_agent.graph import graph

pr_url = 'https://github.com/OWNER/REPO/pull/NUMBER'
result = graph.invoke({
    'pr_url': pr_url,
    'question': 'Review this PR.'
})
print(result.get('final_review'))
PY
```

## 5. Check the action log

The agent writes node transitions and decisions to a file named `output.txt` in the project root.

To view it:

```bash
cat output.txt
```

This file records entries like:

```text
node fetch_pr - action: fetch PR metadata and diffs
--create node expand_context---
--move to node expand_context --
node decide_next_action - action: decision made
```

## 6. Common troubleshooting

### Missing API key errors

Check that `.env` exists and contains the keys exactly:

```bash
grep -E 'GITHUB_TOKEN|AI_STUDIO_API_KEY|AI_STUDIO_MODEL' pr_review_agent/.env
```

### 404 when fetching the PR

Verify the GitHub PR URL is valid and the repo is public or accessible with the configured token.

### Model rejected or unavailable

Use a valid Google AI Studio model. The current confirmed model is:

```text
models/gemini-3.1-flash-lite
```

## 7. Typical developer flow

```bash
source .venv/bin/activate
export $(grep -v '^#' pr_review_agent/.env | xargs)
.venv/bin/python pr_review_agent/main.py
cat output.txt
```

This is the usual flow for running the PR review agent locally.
