from pr_review_agent.graph import graph


if __name__ == "__main__":
    result = graph.invoke({
        "pr_url": "https://github.com/org/repo/pull/42",
        "question": "",
    })
    print(result.get("final_review", "(no review generated)"))
