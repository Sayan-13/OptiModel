"""Vector diagrams of the analyzed BPMN topology and converted Petri net."""

from io import BytesIO
import textwrap

from graphviz import Digraph, escape
from svglib.svglib import svg2rlg

from .optimizer import PetriNet, WorkflowGraph


def _label(value):
    # Wrap rather than truncate labels; escape DOT's special backslash sequences.
    return escape('\n'.join(textwrap.wrap(str(value), width=22, break_long_words=True)))


def _graph():
    graph = Digraph(engine='dot', format='svg')
    graph.attr(rankdir='LR', bgcolor='transparent', nodesep='0.35', ranksep='0.55', pad='0.15')
    graph.attr('node', fontname='Helvetica', fontsize='10', color='#334155', fontcolor='#0f172a')
    graph.attr('edge', color='#64748b', arrowsize='0.7')
    return graph


def bpmn_graph(workflow):
    graph = _graph()
    for node in workflow['events'] + workflow['gateways'] + workflow['tasks']:
        kind = node.get('type', '')
        label = _label(node.get('name') or node['id'])
        if kind.endswith('Event'):
            graph.node(node['id'], label, shape='circle', style='filled', fillcolor='#dcfce7',
                       peripheries='2' if kind == 'endEvent' else '1')
        elif kind.endswith('Gateway'):
            marker = '+' if kind == 'parallelGateway' else 'X' if kind == 'exclusiveGateway' else '?'
            graph.node(node['id'], _label(marker + '\n' + str(node.get('name') or node['id'])),
                       shape='diamond', style='filled', fillcolor='#fef3c7')
        else:
            graph.node(node['id'], label, shape='box', style='rounded,filled', fillcolor='#eff6ff')
    for flow in workflow.get('flows', workflow.get('sequence_flows', [])):
        graph.edge(flow['sourceRef'], flow['targetRef'], label=_label(flow.get('name', '')))
    return graph


def petri_graph(workflow):
    net = PetriNet.from_workflow(WorkflowGraph(workflow))
    graph = _graph()
    for place_id in net.places:
        tokens = net.initial_marking.get(place_id, 0)
        graph.node(place_id, '●' if tokens == 1 else str(tokens) if tokens else '',
                   shape='circle', fixedsize='true', width='0.3', style='filled', fillcolor='white')
    for transition_id, transition in net.transitions.items():
        graph.node(transition_id, _label(transition.get('name') or transition_id),
                   shape='box', style='filled', fillcolor='#e0e7ff')
    for source, target in net.arcs:
        graph.edge(source, target)
    return graph


def render_graph(graph, max_width=480, max_height=550):
    """Render Graphviz SVG to a scaled ReportLab vector drawing."""
    try:
        svg = graph.pipe()
    except Exception as exc:
        raise RuntimeError('Diagram rendering failed. Install Graphviz and ensure dot is on PATH.') from exc
    drawing = svg2rlg(BytesIO(svg))
    if drawing is None or not drawing.width or not drawing.height:
        raise RuntimeError('Graphviz produced an invalid diagram.')
    scale = min(1, max_width / drawing.width, max_height / drawing.height)
    drawing.scale(scale, scale)
    drawing.width *= scale
    drawing.height *= scale
    return drawing
