"""Compiled LangGraph StateGraph orchestration for SANGYAN investigations."""
from __future__ import annotations

from typing import Any, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from sangyan.workflow.nodes import WorkflowNodeSuite
from sangyan.workflow.state import InvestigationWorkflowState


class InvestigationWorkflow:
    """Orchestrates multi-content investigations across deterministic domain engines using LangGraph."""

    def __init__(
        self,
        node_suite: Optional[WorkflowNodeSuite] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ) -> None:
        self.node_suite = node_suite or WorkflowNodeSuite()
        self.checkpointer = checkpointer
        self._compiled_graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(InvestigationWorkflowState)

        # Register nodes
        builder.add_node("intake_node", self.node_suite.intake_node)
        builder.add_node("intelligence_node", self.node_suite.intelligence_node)
        builder.add_node("verification_node", self.node_suite.verification_node)
        builder.add_node("correlation_node", self.node_suite.correlation_node)
        builder.add_node("scam_chain_node", self.node_suite.scam_chain_node)
        builder.add_node("guidance_node", self.node_suite.guidance_node)
        builder.add_node("explanation_node", self.node_suite.explanation_node)
        builder.add_node("review_gate_node", self.node_suite.review_gate_node)
        builder.add_node("trust_finalization_node", self.node_suite.trust_finalization_node)
        builder.add_node("completion_node", self.node_suite.completion_node)
        builder.add_node("failure_node", self.node_suite.failure_node)

        # Wire pipeline flow
        builder.add_edge(START, "intake_node")
        builder.add_edge("intake_node", "intelligence_node")
        builder.add_edge("intelligence_node", "verification_node")
        builder.add_edge("verification_node", "correlation_node")
        builder.add_edge("correlation_node", "scam_chain_node")
        builder.add_edge("scam_chain_node", "guidance_node")
        builder.add_edge("guidance_node", "explanation_node")

        # Conditional route: human review gate or trust finalization
        builder.add_conditional_edges(
            "explanation_node",
            self.node_suite.should_review_condition,
            {
                "review_gate_node": "review_gate_node",
                "trust_finalization_node": "trust_finalization_node",
            },
        )

        builder.add_edge("review_gate_node", "trust_finalization_node")
        builder.add_edge("trust_finalization_node", "completion_node")
        builder.add_edge("completion_node", END)
        builder.add_edge("failure_node", END)

        return builder.compile(checkpointer=self.checkpointer)

    @property
    def compiled_graph(self):
        return self._compiled_graph

    def invoke(self, state_or_command: Any, thread_id: str) -> dict[str, Any]:
        """Execute or resume the graph for a specific thread identity."""
        config = {"configurable": {"thread_id": thread_id}}
        return self._compiled_graph.invoke(state_or_command, config=config)

    def get_state(self, thread_id: str) -> Any:
        """Retrieve current snapshot state for a specific thread identity."""
        config = {"configurable": {"thread_id": thread_id}}
        return self._compiled_graph.get_state(config)
