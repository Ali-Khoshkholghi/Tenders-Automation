import os
import json
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from review_state import SubgraphState
from dotenv import load_dotenv

load_dotenv()

# Initialize LLM layer
llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.0)

# ==========================================
# 1. PARALLEL EXPERT NODES (FAN-OUT)
# ==========================================

def financial_expert_node(state: SubgraphState) -> dict:
    print("[Parallel Expert] Running Financial Analyst...")
    text = state["raw_text"]
    profile = state["client_profile"]
    
    prompt = (
        "You are a Financial Procurement Expert. Scan the text and extract the minimum annual turnover "
        "and public liability insurance requirements. Return a list containing ONE dictionary, for example:\n"
        "[{{'type': 'financial', 'turnover_req': 1000000, 'insurance_req': 2000000}}]"
    )
    
    response = llm.invoke([SystemMessage(content=prompt), HumanMessage(content=text[:8000])])
    try:
        data = eval(response.content.strip())
    except:
        data = []
        
    # Check if client fails financials
    flags = []
    if data:
        metrics = data[0]
        if profile["actual_turnover"] < metrics.get("turnover_req", 0):
            flags.append("FAIL_TURNOVER")
        if profile["actual_insurance"] < metrics.get("insurance_req", 0):
            flags.append("FAIL_INSURANCE")
            
    return {"discovered_requirements": data, "compliance_flags": flags}


def security_expert_node(state: SubgraphState) -> dict:
    print("[Parallel Expert] Running Security Auditor...")
    text = state["raw_text"]
    profile = state["client_profile"]
    
    prompt = (
        "You are a Cybersecurity Compliance Expert. Scan the text to check if 'Cyber Essentials' "
        "or 'Cyber Essentials Plus' is strictly mandatory. Return a list containing ONE dictionary, for example:\n"
        "[{{'type': 'security', 'cyber_essentials_mandatory': True}}]"
    )
    
    response = llm.invoke([SystemMessage(content=prompt), HumanMessage(content=text[:8000])])
    try:
        data = eval(response.content.strip())
    except:
        data = []
        
    flags = []
    if data:
        req = data[0]
        if req.get("cyber_essentials_mandatory") and not profile.get("cyber_essentials_plus"):
            flags.append("FAIL_CYBER_ESSENTIALS")
            
    return {"discovered_requirements": data, "compliance_flags": flags}


def legal_expert_node(state: SubgraphState) -> dict:
    print("[Parallel Expert] Running Legal Compliance Officer...")
    text = state["raw_text"]
    profile = state["client_profile"]
    
    prompt = (
        "You are a Corporate Legal Procurement Officer. Scan the text to check if the bidding entity "
        "must be registered in the United Kingdom. Return a list containing ONE dictionary, for example:\n"
        "[{{'type': 'legal', 'uk_registration_mandatory': True}}]"
    )
    
    response = llm.invoke([SystemMessage(content=prompt), HumanMessage(content=text[:8000])])
    try:
        data = eval(response.content.strip())
    except:
        data = []
        
    flags = []
    if data:
        req = data[0]
        if req.get("uk_registration_mandatory") and not profile.get("uk_registered"):
            flags.append("FAIL_UK_REGISTRATION")
            
    return {"discovered_requirements": data, "compliance_flags": flags}


# ==========================================
# 2. CONSOLIDATION NODE (FAN-IN)
# ==========================================

def consolidation_node(state: SubgraphState) -> dict:
    print("\n[Consolidation Node] Gathering and merging expert results...")
    
    # Because of our Reducer, these lists combined the outputs of all 3 parallel runs flawlessly
    all_requirements = state.get("discovered_requirements", [])
    all_flags = state.get("compliance_flags", [])
    
    print(f" -> Consolidated Flags: {all_flags}")
    print(f" -> Consolidated Requirements List: {all_requirements}")
    
    summary = {
        "status": "PASSED" if len(all_flags) == 0 else "FAILED",
        "blockers": all_flags,
        "metrics_map": all_requirements
    }
    
    return {"final_panel_review": summary}


# ==========================================
# 3. SUBGRAPH ASSEMBLY & COMPILATION
# ==========================================

sub_workflow = StateGraph(SubgraphState)

# Register nodes
sub_workflow.add_node("FinancialExpert", financial_expert_node)
sub_workflow.add_node("SecurityExpert", security_expert_node)
sub_workflow.add_node("LegalExpert", legal_expert_node)
sub_workflow.add_node("Consolidator", consolidation_node)

# Wire the Parallel Fan-Out
# Setting the entry point to multiple nodes causes them to run concurrently!
sub_workflow.set_conditional_entry_point(
    lambda state: ["FinancialExpert", "SecurityExpert", "LegalExpert"]
)

# Wire the Fan-In (All parallel nodes merge into the Consolidator)
sub_workflow.add_edge("FinancialExpert", "Consolidator")
sub_workflow.add_edge("SecurityExpert", "Consolidator")
sub_workflow.add_edge("LegalExpert", "Consolidator")

sub_workflow.add_edge("Consolidator", END)

# Compile the subgraph independently
review_panel_subgraph = sub_workflow.compile()