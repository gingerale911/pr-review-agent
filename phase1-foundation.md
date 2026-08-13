# PR Review Agent — Phase 1: Foundation + Intelligence

> **Goal:** A fully working PR reviewer — fetches GitHub PR, reads context beyond the diff, runs adaptive routing with a security subgraph, and produces a structured review.

---

## 1. Architecture Overview

```
START
  │
fetch_pr
  │
expand_context
  │
  ├─── fan_out (Send, parallel) ──► analyze_single_file (×N)
  │                                        │
  └─────────────────────────────────►──────┘
                                           │
                                   decide_next_action
                                      │         │         │
                                 read_more  security  synthesize
                                      │     subgraph      │
                                      │         │         │
                                      └────►────┘         │
                                    (loop, max 3)         │
                                                         END
```

**Stack:**
- LangGraph (Graph API)
- LangChain + Claude Sonnet 4.6
- PyGithub (GitHub REST API)

---

## 2. State Schema

```python
from typing import TypedDict, Annotated, Literal
import operator

class PRState(TypedDict):
    # Input
    pr_url: str
    question: str                          # optional focus e.g. "check auth"

    # Fetched
    pr_metadata: dict                      # title, author, base branch
    changed_files: list[str]
    diff_by_file: dict[str, str]           # file → raw diff

    # Context
    context_files: dict[str, str]          # base-branch file contents
    cross_ref_files: list[str]             # extra files agent requests
    cross_ref_contents: dict[str, str]

    # Analysis
    file_reviews: Annotated[list[dict], operator.add]
    observations: Annotated[list[str], operator.add]
    security_findings: list[dict]

    # Routing
    next_action: Literal["read_more", "security_check", "synthesize"]
    iteration: int

    # Output
    final_review: str
```

---

## 3. Node Definitions

### 3.1 `fetch_pr`

```python
from github import Github

def fetch_pr(state: PRState) -> dict:
    g = Github(os.environ["GITHUB_TOKEN"])
    parts = state["pr_url"].rstrip("/").split("/")
    repo = g.get_repo(f"{parts[-4]}/{parts[-3]}")
    pr = repo.get_pull(int(parts[-1]))

    changed_files, diff_by_file = [], {}
    for f in pr.get_files():
        changed_files.append(f.filename)
        diff_by_file[f.filename] = f.patch or ""

    return {
        "pr_metadata": {"title": pr.title, "author": pr.user.login,
                        "base": pr.base.ref, "body": pr.body or ""},
        "changed_files": changed_files,
        "diff_by_file": diff_by_file,
    }
```

---

### 3.2 `expand_context`

Reads full base-branch content for each changed file.

```python
def expand_context(state: PRState) -> dict:
    g = Github(os.environ["GITHUB_TOKEN"])
    parts = state["pr_url"].rstrip("/").split("/")
    repo = g.get_repo(f"{parts[-4]}/{parts[-3]}")

    context_files = {}
    for filename in state["changed_files"]:
        try:
            content = repo.get_contents(filename, ref=state["pr_metadata"]["base"])
            context_files[filename] = content.decoded_content.decode("utf-8")
        except Exception:
            context_files[filename] = ""   # new file, no base content

    return {"context_files": context_files}
```

---

### 3.3 `analyze_single_file` (parallel via `Send`)

```python
from langgraph.types import Send

REVIEW_PROMPT = """\
You are a senior engineer reviewing a pull request.

File: {filename}

--- DIFF ---
{diff}

--- FULL FILE (base branch) ---
{context}

--- RELATED FILES ---
{cross_ref}

Review this change. Report:
1. Correctness issues
2. Security concerns
3. Performance concerns
4. Missing tests
5. Style / readability

Be concise. Use bullet points. Say "LGTM" if no issues.
"""

def analyze_single_file(state: PRState) -> dict:
    filename = state["_current_file"]
    cross_ref = "\n\n".join(
        f"// {f}\n{c[:2000]}"
        for f, c in state.get("cross_ref_contents", {}).items()
    )
    response = model.invoke([
        HumanMessage(content=REVIEW_PROMPT.format(
            filename=filename,
            diff=state["diff_by_file"].get(filename, "")[:4000],
            context=state["context_files"].get(filename, "")[:4000],
            cross_ref=cross_ref[:3000],
        ))
    ])
    return {
        "file_reviews": [{"file": filename, "review": response.content}],
        "observations": [f"Reviewed {filename}"],
    }

def fan_out_files(state: PRState) -> list[Send]:
    return [
        Send("analyze_single_file", {**state, "_current_file": f})
        for f in state["changed_files"]
    ]
```

---

### 3.4 `decide_next_action`

The core routing node — reads observations and decides what to do next.

```python
import json

DECISION_PROMPT = """\
You are orchestrating a PR review.

Changed files: {changed_files}
Files already read: {files_read}
Observations:
{observations}

Decide the next action:
- "read_more": need more context (list which files)
- "security_check": diff touches auth/crypto/sessions/permissions
- "synthesize": enough info for final review

Respond ONLY in JSON:
{{"action": "read_more"|"security_check"|"synthesize",
  "files_to_read": [],
  "reason": "..."}}
"""

def decide_next_action(state: PRState) -> dict:
    if state.get("iteration", 0) >= 3:
        return {"next_action": "synthesize"}

    files_read = (list(state.get("context_files", {}).keys()) +
                  list(state.get("cross_ref_contents", {}).keys()))

    response = model.invoke([
        HumanMessage(content=DECISION_PROMPT.format(
            changed_files=state["changed_files"],
            files_read=files_read,
            observations="\n".join(state.get("observations", [])),
        ))
    ])

    result = json.loads(response.content)
    return {
        "next_action": result["action"],
        "cross_ref_files": result.get("files_to_read", []),
        "iteration": state.get("iteration", 0) + 1,
        "observations": [f"Decision: {result['reason']}"],
    }
```

---

### 3.5 `read_cross_ref`

```python
def read_cross_ref(state: PRState) -> dict:
    g = Github(os.environ["GITHUB_TOKEN"])
    parts = state["pr_url"].rstrip("/").split("/")
    repo = g.get_repo(f"{parts[-4]}/{parts[-3]}")

    new_contents = {}
    already_read = state.get("cross_ref_contents", {})
    for filename in state.get("cross_ref_files", []):
        if filename in already_read:
            continue
        try:
            content = repo.get_contents(filename, ref=state["pr_metadata"]["base"])
            new_contents[filename] = content.decoded_content.decode("utf-8")
        except Exception:
            new_contents[filename] = ""

    return {
        "cross_ref_contents": {**already_read, **new_contents},
        "observations": [f"Read cross-ref: {list(new_contents.keys())}"],
    }
```

---

### 3.6 Security Subgraph

Runs only when `decide_next_action` routes to `security_check`.

```python
from langgraph.graph import StateGraph, START, END

SECURITY_CHECKS = [
    "SQL injection", "XSS / template injection",
    "Broken authentication", "Insecure direct object reference",
    "Sensitive data in logs or cookies", "Missing authorization checks",
]

def security_scan(state: PRState) -> dict:
    findings = []
    for filename, diff in state["diff_by_file"].items():
        response = model.invoke([HumanMessage(content=f"""\
Security review of this diff.

File: {filename}
{diff[:4000]}

Check for: {", ".join(SECURITY_CHECKS)}

Return JSON: [{{"issue":"...","severity":"HIGH|MEDIUM|LOW","line_hint":"..."}}]
Return [] if none.
""")])
        try:
            for f in json.loads(response.content):
                f["file"] = filename
                findings.append(f)
        except Exception:
            pass

    return {
        "security_findings": findings,
        "observations": [f"Security scan: {len(findings)} issues found."],
    }

# Subgraph
sec_builder = StateGraph(PRState)
sec_builder.add_node("security_scan", security_scan)
sec_builder.add_edge(START, "security_scan")
sec_builder.add_edge("security_scan", END)
security_subgraph = sec_builder.compile()
```

---

### 3.7 `synthesize`

```python
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

def synthesize(state: PRState) -> dict:
    findings = "\n\n".join(f"### {r['file']}\n{r['review']}"
                           for r in state["file_reviews"])
    security = "\n".join(
        f"- [{f['severity']}] {f['file']}: {f['issue']}"
        for f in state.get("security_findings", [])
    ) or "None"

    response = model.invoke([HumanMessage(content=SYNTHESIS_PROMPT.format(
        title=state["pr_metadata"]["title"],
        findings=findings,
        security=security,
    ))])
    return {"final_review": response.content}
```

---

## 4. Graph Assembly

```python
from langgraph.graph import StateGraph, START, END

def route_decision(state: PRState) -> str:
    return state["next_action"]

builder = StateGraph(PRState)

builder.add_node("fetch_pr", fetch_pr)
builder.add_node("expand_context", expand_context)
builder.add_node("analyze_single_file", analyze_single_file)
builder.add_node("decide_next_action", decide_next_action)
builder.add_node("read_cross_ref", read_cross_ref)
builder.add_node("security_check", security_subgraph)
builder.add_node("synthesize", synthesize)

builder.add_edge(START, "fetch_pr")
builder.add_edge("fetch_pr", "expand_context")

# Fan out parallel file analysis
builder.add_conditional_edges("expand_context", fan_out_files, ["analyze_single_file"])
builder.add_edge("analyze_single_file", "decide_next_action")

# Decision routing (with cycles)
builder.add_conditional_edges("decide_next_action", route_decision, {
    "read_more": "read_cross_ref",
    "security_check": "security_check",
    "synthesize": "synthesize",
})
builder.add_edge("read_cross_ref", "decide_next_action")
builder.add_edge("security_check", "decide_next_action")
builder.add_edge("synthesize", END)

graph = builder.compile()
```

---

## 5. Sequence Diagram

```
User     Graph      GitHub     LLM     SecuritySubgraph
 │         │           │         │            │
 │─invoke─►│           │         │            │
 │         │─fetch────►│         │            │
 │         │◄─diff─────│         │            │
 │         │─expand───►│         │            │
 │         │◄─files────│         │            │
 │         │                     │            │
 │         │─[parallel analyze]─►│            │
 │         │◄─[file reviews]─────│            │
 │         │                     │            │
 │         │─decide─────────────►│            │
 │         │◄─"security_check"───│            │
 │         │──────────────────────────────────►│
 │         │◄─findings────────────────────────│
 │         │                     │            │
 │         │─decide─────────────►│            │
 │         │◄─"read_more"────────│            │
 │         │─read_cross_ref────►│             │
 │         │◄─contents──────────│             │
 │         │                     │            │
 │         │─decide─────────────►│            │
 │         │◄─"synthesize"───────│            │
 │         │─synthesize─────────►│            │
 │         │◄─final review───────│            │
 │◄─result─│                                  │
```

---

## 6. Running It

```python
result = graph.invoke({
    "pr_url": "https://github.com/org/repo/pull/42",
    "question": "",
})
print(result["final_review"])
```

---

## 7. Deliverables for Phase 1

- [ ] All nodes implemented and graph compiles
- [ ] Parallel file analysis via `Send`
- [ ] `decide_next_action` routing with 3-iteration guard
- [ ] Security subgraph on sensitive diffs
- [ ] `read_cross_ref` for dynamic file expansion
- [ ] End-to-end test on a real PR
- [ ] `.env`: `GITHUB_TOKEN`, `ANTHROPIC_API_KEY`
