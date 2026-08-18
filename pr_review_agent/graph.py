from langgraph.graph import StateGraph, START, END
from pr_review_agent.state import PRState
from pr_review_agent.nodes import (
    fetch_pr, expand_context, analyze_single_file, fan_out_files,
    decide_next_action, read_cross_ref, synthesize,
)
from pr_review_agent.security import security_subgraph
from pr_review_agent.github_client import post_review_comment
from pr_review_agent.logging_utils import log_action, log_transition, reset_log


def route_decision(state: PRState) -> str:
    decision = state.get("next_action", "synthesize")
    log_action("decide_next_action", f"route_decision -> {decision}")
    return decision


def post_to_github(state: PRState) -> dict:
    review = state.get("final_review", "")
    if not review:
        return {"observations": ["No final review to post to GitHub."]}

    url = post_review_comment(state["pr_url"], review)
    log_action("post_to_github", "posted", f"url={url}")
    return {"observations": [f"Posted PR review to GitHub: {url}"]}


reset_log()
log_action("graph", "initialize workflow")

builder = StateGraph(PRState)

builder.add_node("fetch_pr", fetch_pr)
builder.add_node("expand_context", expand_context)
builder.add_node("analyze_single_file", analyze_single_file)
builder.add_node("decide_next_action", decide_next_action)
builder.add_node("read_cross_ref", read_cross_ref)
builder.add_node("security_check", security_subgraph)
builder.add_node("synthesize", synthesize)
builder.add_node("post_to_github", post_to_github)

builder.add_edge(START, "fetch_pr")
log_transition("START", "fetch_pr")
builder.add_edge("fetch_pr", "expand_context")
log_transition("fetch_pr", "expand_context")

# Fan out parallel file analysis
builder.add_conditional_edges("expand_context", fan_out_files, ["analyze_single_file"]) 
log_transition("expand_context", "analyze_single_file")
builder.add_edge("analyze_single_file", "decide_next_action")
log_transition("analyze_single_file", "decide_next_action")

# Decision routing (with cycles)
builder.add_conditional_edges("decide_next_action", route_decision, {
    "read_more": "read_cross_ref",
    "security_check": "security_check",
    "synthesize": "synthesize",
})
log_transition("decide_next_action", "read_cross_ref")
log_transition("decide_next_action", "security_check")
log_transition("decide_next_action", "synthesize")
builder.add_edge("read_cross_ref", "decide_next_action")
log_transition("read_cross_ref", "decide_next_action")
builder.add_edge("security_check", "decide_next_action")
log_transition("security_check", "decide_next_action")
builder.add_edge("synthesize", "post_to_github")
log_transition("synthesize", "post_to_github")
builder.add_edge("post_to_github", END)
log_transition("post_to_github", "END")

graph = builder.compile()
