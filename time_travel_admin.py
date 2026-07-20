import json
from app import app

def run_production_pipeline():
    # Define a static thread context for the session
    filename = "tender_camden_it.txt"
    config = {"configurable": {"thread_id": f"session_{filename}"}}
    
    initial_inputs = {
        "raw_documents": [],
        "current_file": filename,
        "current_loop_count": 0,
        "compliance_errors": [],
        "feedback_for_analyst": "",
        "executive_remedy_context": "",
        "panel_review_summary": {},
        "final_report": ""
    }
    
    print("=== STEP 1: INITIAL PIPELINE RUN ===")
    # 1. Run the system forward. It will halt when it hits the HumanTriage node because Camden fails credentials.
    state_output = app.invoke(initial_inputs, config=config)
    
    print("\n=== STEP 2: INSPECTING TIME-TRAVEL HISTORICAL SNAPSHOTS ===")
    # 2. Programmatically fetch every single state checkpoint LangGraph recorded across time
    history = list(app.get_state_history(config))
    
    print(f"Recorded Timeline Length: {len(history)} snapshots.")
    for idx, checkpoint in enumerate(history):
        print(f"  [{idx}] Checkpoint ID: {checkpoint.config['configurable']['checkpoint_id']} | Next Planned Node: {checkpoint.next}")
    
    # 3. Simulate an administrative operational rewrite
    print("\n=== STEP 3: PROGRAMMATIC TIME-TRAVEL FORK ===")
    print("The supervisor decides to travel back in time, clear out errors, and inject qualification data.")
    
    # Choose the most recent checkpoint snapshot (the paused triage state)
    target_checkpoint = history[0].config
    
    # We programmatically update the memory state, overriding the errors and adding mitigation notes
    app.update_state(
        target_checkpoint, 
        {
            "compliance_errors": [],  # Clear the failures
            "executive_remedy_context": "ADMIN OVERRIDE: Corporate commits to providing cross-border insurance indemnity structures."
        },
        as_node="HumanTriage"  # Tell LangGraph we are writing this modification as the Triage Node
    )
    
    print(" -> State rewritten perfectly in memory history. Resuming workflow from checkpoint timeline...")
    
    # 4. Resume execution. Passing None tells LangGraph to pick up directly from the modified historical save state!
    final_forked_state = app.invoke(None, config=target_checkpoint)
    
    print("\n=== STEP 4: TIME-TRAVEL RESUMPTION COMPLETED ===")
    print("Forked Timeline Output Memo Preview:")
    print("-" * 60)
    print(final_forked_state.get("final_report"))
    print("-" * 60)

if __name__ == "__main__":
    run_production_pipeline()