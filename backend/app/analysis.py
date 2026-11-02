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
