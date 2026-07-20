import operator
from typing import Annotated, TypedDict, List, Dict

class SubgraphState(TypedDict):
    # Inputs passed from the parent graph
    raw_text: str
    client_profile: dict
    
    # Reducer channels: Parallel nodes can append to these safely without overwriting
    discovered_requirements: Annotated[list, operator.add]
    compliance_flags: Annotated[list, operator.add]
    
    # Final consolidated output map
    final_panel_review: dict