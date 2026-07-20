from typing import TypedDict, List

class AgentState(TypedDict):
    raw_documents: List[str]
    current_file: str
    current_loop_count: int
    compliance_errors: List[str]
    feedback_for_analyst: str
    executive_remedy_context: str
    final_report: str
    # New state channel to receive data back from the review panel subgraph
    panel_review_summary: dict