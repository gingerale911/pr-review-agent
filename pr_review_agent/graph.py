from langgraph.graph import StateGraph, START, END
from pr_review_agent.state import PRState
from pr_review_agent.nodes import (
    fetch_pr, expand_context, analyze_single_file, fan_out_files,
    decide_next_action, read_cross_ref, synthesize,
)
from pr_review_agent.security import security_subgraph


def route_decision(state: PRState) -> str:
    return state.get("next_action", "synthesize")


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
