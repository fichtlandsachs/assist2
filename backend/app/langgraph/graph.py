"""LangGraph State Machine Definition for Conversation Engine."""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from app.langgraph.state import ConversationState
from app.langgraph.nodes import (
    load_context_node,
    detect_initial_context_node,
    detect_intent_node,
    detect_mode_switch_node,
    extract_facts_node,
    map_protocol_node,
    calculate_story_sizing_node,
    evaluate_readiness_node,
    decide_structure_proposal_node,
    generate_structure_proposal_node,
    plan_questions_node,
    generate_response_node,
    save_results_node,
    observer_hook_node,
    audit_node,
)


def create_conversation_graph() -> StateGraph:
    """Create the conversation engine state graph."""
    
    # Initialize graph
    workflow = StateGraph(ConversationState)
    
    # Add all nodes
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("detect_initial_context", detect_initial_context_node)
    workflow.add_node("detect_intent", detect_intent_node)
    workflow.add_node("detect_mode_switch", detect_mode_switch_node)
    workflow.add_node("extract_facts", extract_facts_node)
    workflow.add_node("map_protocol", map_protocol_node)
    workflow.add_node("calculate_story_sizing", calculate_story_sizing_node)
    workflow.add_node("evaluate_readiness", evaluate_readiness_node)
    workflow.add_node("decide_structure_proposal", decide_structure_proposal_node)
    workflow.add_node("generate_structure_proposal", generate_structure_proposal_node)
    workflow.add_node("plan_questions", plan_questions_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("save_results", save_results_node)
    workflow.add_node("observer_hook", observer_hook_node)
    workflow.add_node("audit", audit_node)
    
    # Set entry point
    workflow.set_entry_point("load_context")
    
    # Linear flow edges
    workflow.add_edge("load_context", "detect_initial_context")
    workflow.add_edge("detect_initial_context", "detect_intent")
    workflow.add_edge("detect_intent", "detect_mode_switch")
    workflow.add_edge("detect_mode_switch", "extract_facts")
    workflow.add_edge("extract_facts", "map_protocol")
    workflow.add_edge("map_protocol", "calculate_story_sizing")
    workflow.add_edge("calculate_story_sizing", "evaluate_readiness")
    workflow.add_edge("evaluate_readiness", "decide_structure_proposal")
    
    # Conditional edge for structure proposal
    def should_generate_proposal(state: ConversationState) -> str:
        """Determine if structure proposal should be generated."""
        if state.get("structure_proposal_required", False):
            return "generate_structure_proposal"
        return "plan_questions"
    
    workflow.add_conditional_edges(
        "decide_structure_proposal",
        should_generate_proposal,
        {
            "generate_structure_proposal": "generate_structure_proposal",
            "plan_questions": "plan_questions",
        }
    )
    
    # Continue after structure proposal or question planning
    workflow.add_edge("generate_structure_proposal", "generate_response")
    workflow.add_edge("plan_questions", "generate_response")
    
    # Final edges
    workflow.add_edge("generate_response", "save_results")
    workflow.add_edge("save_results", "observer_hook")
    workflow.add_edge("observer_hook", "audit")
    workflow.add_edge("audit", END)
    
    return workflow


def get_conversation_workflow():
    """Get the compiled conversation workflow."""
    graph = create_conversation_graph()
    return graph.compile()
