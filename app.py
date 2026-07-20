import os
import time
import json
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from pypdf import PdfReader

# Import base configuration and the new subgraph
from state import AgentState
from review_subgraph import review_panel_subgraph

load_dotenv()

llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.0)

# ==========================================
# PARENT NODES
# ==========================================

def ingestion_node(state: AgentState) -> dict:
    print("\n[Parent Node] Ingesting Document Source...")
    folder_path = "incoming_files"
    extracted_text = ""
    target_filename = state.get("current_file")
    target_file = os.path.join(folder_path, target_filename)
    
    if target_file.endswith(".txt"):
        try:
            # First try standard UTF-8
            with open(target_file, "r", encoding="utf-8") as f:
                extracted_text = f.read()
        except UnicodeDecodeError:
            # Fallback to Western European encoding if a raw £ sign is encountered
            with open(target_file, "r", encoding="cp1252") as f:
                extracted_text = f.read()
                
    elif target_file.endswith(".pdf"):
        reader = PdfReader(target_file)
        for page in reader.pages:
            text = page.extract_text()
            if text: extracted_text += text + "\n"
            
    return {"raw_documents": [extracted_text]}


# --- THE SUBGRAPH ADAPTER NODE ---
def board_review_panel_node(state: AgentState) -> dict:
    print("\n[Parent Node] Invoking Subgraph: Triggering Parallel Boardroom Review Panel...")
    
    with open("client_profile.json", "r") as f:
        profile = json.load(f)
        
    # Translate parent state inputs into the format required by the subgraph state map
    subgraph_inputs = {
        "raw_text": state["raw_documents"][0],
        "client_profile": profile,
        "discovered_requirements": [],
        "compliance_flags": []
    }
    
    # Execute the standalone compiled subgraph synchronously
    subgraph_outputs = review_panel_subgraph.invoke(subgraph_inputs)
    
    # Map the unified panel summary results back into the parent graph's layout
    review_data = subgraph_outputs.get("final_panel_review", {})
    
    return {
        "panel_review_summary": review_data,
        "compliance_errors": review_data.get("blockers", [])
    }


def triage_node(state: AgentState) -> dict:
    print("\n⚠️ [PARENT HUMAN TRIAGE NODE] ⚠️")
    print(f"Critical Blockers Found: {state.get('compliance_errors')}")
    print("The automation has suspended execution to protect compliance integrity.")
    print("A human administrator must intervene using the Time-Travel Engine script to fix this.")
    
    # We return an empty dict to pause the flow here in place
    return {}


def report_generator_node(state: AgentState) -> dict:
    print("\n[Parent Node] Compiling Final Memorandum...")
    summary = state.get("panel_review_summary", {})
    
    user_prompt = (
        f"Generate a procurement memorandum. Contract Assessment Summary Data:\n{summary}\n"
        f"Administrative Override / Remedial Strategy Applied: {state.get('executive_remedy_context', 'None')}"
    )
    response = llm.invoke([HumanMessage(content=user_prompt)])
    return {"final_report": response.content.strip()}


# ==========================================
# PARENT GRAPH ROUTING & TOPOLOGY
# ==========================================

def route_after_panel_review(state: AgentState) -> str:
    if len(state.get("compliance_errors", [])) > 0:
        print(" -> [Parent Router] Deficits detected. Routing to Human Triage Node.")
        return "triage"
    print(" -> [Parent Router] All criteria clean. Routing to Report Generation.")
    return "generate"


workflow = StateGraph(AgentState)

workflow.add_node("Ingest", ingestion_node)
workflow.add_node("ParallelPanelReview", board_review_panel_node)
workflow.add_node("HumanTriage", triage_node)
workflow.add_node("GenerateReport", report_generator_node)

workflow.set_entry_point("Ingest")
workflow.add_edge("Ingest", "ParallelPanelReview")

workflow.add_conditional_edges(
    "ParallelPanelReview",
    route_after_panel_review,
    {
        "triage": "HumanTriage",
        "generate": "GenerateReport"
    }
)

workflow.add_edge("HumanTriage", "GenerateReport")
workflow.add_edge("GenerateReport", END)

# Persistent Memory Saver Checkpointer is crucial for Time Travel
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)