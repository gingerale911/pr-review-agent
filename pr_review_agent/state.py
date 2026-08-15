from typing import TypedDict, Annotated, Literal, Optional, List, Dict
import operator


class PRState(TypedDict, total=False):
    # Input
    pr_url: str
    question: str

    # Fetched
    pr_metadata: dict
    changed_files: List[str]
    diff_by_file: Dict[str, str]

    # Context
    context_files: Dict[str, str]
    cross_ref_files: List[str]
    cross_ref_contents: Dict[str, str]

    # Analysis
    file_reviews: Annotated[List[dict], operator.add]
    observations: Annotated[List[str], operator.add]
    security_findings: List[dict]

    # Routing
    next_action: Literal["read_more", "security_check", "synthesize"]
    iteration: int

    # Output
    final_review: str

    # Node-specific (used during parallel fan-out)
    _current_file: str
