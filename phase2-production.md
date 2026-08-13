# PR Review Agent — Phase 2: Production

> **Goal:** Make the agent production-ready — checkpointing, human-in-the-loop approval, GitHub comment posting, streaming output, and a CLI.

**Builds on:** Phase 1 adaptive graph

---

## 1. What Changes

| Feature | Phase 1 | Phase 2 |
|---|---|---|
| Output | Final dict returned | Streamed live to terminal |
| State persistence | In-memory | Checkpointed (SQLite / Postgres) |
| Resume | Not supported | Interrupt + resume mid-graph |
| Human review | None | HITL pause before posting |
| GitHub output | None | Posts review as PR comment |
| Interface | Python script | CLI (`typer`) |

---

## 2. Checkpointing

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# Dev
checkpointer = SqliteSaver.from_conn_string("reviews.db")

# Prod
# from langgraph.checkpoint.postgres import PostgresSaver
# checkpointer = PostgresSaver.from_conn_string(os.environ["DATABASE_URL"])

graph = builder.compile(checkpointer=checkpointer)
```

Every invocation gets a stable `thread_id`:

```python
config = {"configurable": {"thread_id": "pr-42-run-1"}}
result = graph.invoke({"pr_url": "..."}, config=config)

# Resume after interrupt (no need to re-pass state)
graph.invoke(None, config=config)
```

---

## 3. Human-in-the-Loop (HITL)

Before posting to GitHub, the graph pauses and surfaces the draft for human review.

### 3.1 Interrupt node

```python
from langgraph.types import interrupt

def human_approval(state: PRState) -> dict:
    decision = interrupt({
        "draft_review": state["final_review"],
        "security_findings": state.get("security_findings", []),
        "message": "Review the draft. Edit if needed, then approve to post.",
    })

    if isinstance(decision, str):
        return {"final_review": decision}   # user edited the review
    return {}                               # no edit, post as-is
```

### 3.2 Graph additions

```python
builder.add_node("human_approval", human_approval)
builder.add_node("post_to_github", post_to_github)

# Append to Phase 1 graph after synthesize
builder.add_edge("synthesize", "human_approval")
builder.add_edge("human_approval", "post_to_github")
builder.add_edge("post_to_github", END)
```

### 3.3 Sequence

```
Graph          Human           GitHub
  │               │               │
  │─synthesize    │               │
  │─interrupt────►│               │
  │    (paused)   │               │
  │               │ [reads draft] │
  │               │ [edits / ok]  │
  │               │──resume()────►│
  │◄──────────────│               │
  │─post_to_github────────────────►│
  │◄──PR comment──────────────────│
```

---

## 4. `post_to_github`

```python
def post_to_github(state: PRState) -> dict:
    g = Github(os.environ["GITHUB_TOKEN"])
    parts = state["pr_url"].rstrip("/").split("/")
    repo = g.get_repo(f"{parts[-4]}/{parts[-3]}")
    pr = repo.get_pull(int(parts[-1]))

    body = f"## 🤖 Automated PR Review\n\n{state['final_review']}"

    if state.get("security_findings"):
        body += "\n\n### 🔐 Security Findings\n"
        for f in state["security_findings"]:
            body += f"- **[{f['severity']}]** `{f['file']}`: {f['issue']}\n"

    pr.create_issue_comment(body)
    return {"observations": ["Posted review to GitHub."]}
```

---

## 5. Streaming Output

```python
async def run_with_streaming(pr_url: str, config: dict):
    async for event in graph.astream_events(
        {"pr_url": pr_url, "question": ""},
        config=config,
        version="v2",
    ):
        kind = event["event"]
        name = event.get("name", "")

        if kind == "on_chain_start":
            print(f"\n▶ {name}")

        elif kind == "on_chain_end" and name == "synthesize":
            print("\n📋 Draft Review Ready")
            print(event["data"]["output"].get("final_review", ""))

        elif kind == "on_chain_end" and name == "human_approval":
            print("\n⏸  Paused — run `pr-review approve --thread <id>`")
```

**Live terminal output:**
```
▶ fetch_pr
▶ expand_context
▶ analyze_single_file (×4, parallel)
▶ decide_next_action
  → security_check triggered
▶ security_check
  → 2 findings
▶ decide_next_action
  → read_more: middleware/auth.py
▶ read_cross_ref
▶ decide_next_action
  → synthesize
▶ synthesize

📋 Draft Review Ready
## PR Review: "Add OAuth2 login flow"
Verdict: REQUEST CHANGES
...

⏸  Paused — run `pr-review approve --thread pr-42-1720000000`
```

---

## 6. CLI Interface

```python
import typer, asyncio, time

app = typer.Typer()

@app.command()
def review(
    pr_url: str = typer.Argument(..., help="GitHub PR URL"),
    thread_id: str = typer.Option(None, help="Resume existing thread"),
    focus: str = typer.Option("", help="e.g. 'check auth'"),
):
    """Start or resume a PR review."""
    tid = thread_id or f"pr-{pr_url.split('/')[-1]}-{int(time.time())}"
    typer.echo(f"Thread: {tid}")
    asyncio.run(run_with_streaming(pr_url, {"configurable": {"thread_id": tid}}))


@app.command()
def approve(
    thread_id: str = typer.Argument(...),
    edit: str = typer.Option(None, help="Paste edited review text"),
):
    """Approve draft and post to GitHub."""
    graph.invoke(edit, config={"configurable": {"thread_id": thread_id}})
    typer.echo("✅ Review posted to GitHub.")


@app.command()
def status(thread_id: str = typer.Argument(...)):
    """Show current state of a review thread."""
    state = graph.get_state({"configurable": {"thread_id": thread_id}})
    typer.echo(f"Next node:      {state.next}")
    typer.echo(f"Iterations:     {state.values.get('iteration', 0)}")
    typer.echo(f"Files reviewed: {len(state.values.get('file_reviews', []))}")

if __name__ == "__main__":
    app()
```

**Usage:**
```bash
# Start
pr-review review https://github.com/org/repo/pull/42 --focus "check auth"

# Approve and post
pr-review approve pr-42-1720000000

# Resume with edits
pr-review approve pr-42-1720000000 --edit "$(cat my_review.md)"

# Check status
pr-review status pr-42-1720000000
```

---

## 7. Full Graph (Phase 2)

```
START
  │
fetch_pr
  │
expand_context
  │
  ├─── fan_out (Send) ──► analyze_single_file (×N, parallel)
  │                               │
  └───────────────────────►───────┘
                                  │
                          decide_next_action
                             │         │         │
                        read_more  security  synthesize
                             │     subgraph      │
                             │         │    human_approval
                             └────►────┘         │ (HITL interrupt)
                           (loop, max 3)   post_to_github
                                                  │
                                                 END
```

---

## 8. Environment Variables

```bash
GITHUB_TOKEN=ghp_...
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=sqlite:///reviews.db   # or postgres://...
```

---

## 9. Deliverables for Phase 2

- [ ] SQLite checkpointer wired to graph
- [ ] `human_approval` interrupt node
- [ ] `post_to_github` posts formatted PR comment
- [ ] `astream_events` live streaming
- [ ] `typer` CLI: `review`, `approve`, `status`
- [ ] `thread_id` stable across resume
- [ ] README with setup and usage
- [ ] `.env.example`
