"""Legacy bridge to new optimization engine."""

from .optimizer import (
    BPMNParser, WorkflowGraph, PetriNet, PetriNetAnalyzer,
    DiscreteEventSimulator, MetricsCalculator, ProblemIdentifier,
    IterativeOptimizer
)
from .report_builder import build_comparative_pdf_report

def parse_bpmn(xml_content: str):
    return BPMNParser.parse(xml_content)

def bpmn_to_petri(parsed: dict):
    wf = WorkflowGraph(parsed)
    return PetriNet.from_workflow(wf)


def analyze_bpmn(xml_content: str, max_states: int = 5000):
    """Parse BPMN and return the Petri net plus reachability diagnostics."""
    parsed = parse_bpmn(xml_content)
    workflow = WorkflowGraph(parsed)
    net = PetriNet.from_workflow(workflow)
    verification = PetriNetAnalyzer(net).explore_state_space(max_states=max_states)
    return {
        'workflow': parsed,
        'petri_net': net.to_dict(),
        'verification': verification,
    }
