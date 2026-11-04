"""BPMN-Based Workflow Analysis and Iterative Optimization Engine.

Implements all 10 stages:
1. XML Parsing (Tasks, Gateways, Events, Flows, Durations, Resources)
2. Workflow Graph Modeling (NetworkX)
3. Petri-Net Conversion (Places, Transitions, Arcs, Markings)
4. Initial Analysis (Bounded Deadlock and Reachability Checks, Concurrency)
5. Timed Discrete-Event Simulation (Task execution, Resource Allocation, Queuing)
6. Metric Calculation (Makespan, Throughput, Utilization, Waiting, Bottlenecks, etc.)
7. Problem Identification (Inefficiencies, Critical Path, Contention)
8. Candidate Scenario Evaluation (Scheduling and Worker-Pool Assumptions)
9. Re-simulation and Candidate Evaluation
10. Final Summary, Metrics Comparison & BPMN XML Generation
"""

import xml.etree.ElementTree as ET
import re
import networkx as nx
import copy
import math
from typing import Dict, List, Tuple, Any, Optional
from collections import deque, defaultdict


# ============================================================================
# STAGE 1: BPMN XML Parsing
# ============================================================================

class BPMNParser:
    """Parses standard BPMN 2.0 XML models."""
    
    NAMESPACES = {
        'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
        'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
        'dc': 'http://www.omg.org/spec/DD/20100524/DC',
        'di': 'http://www.omg.org/spec/DD/20100524/DI',
    }

    TASK_TAGS = ['task', 'userTask', 'serviceTask', 'scriptTask', 'manualTask', 'businessRuleTask']
    GATEWAY_TAGS = ['parallelGateway', 'exclusiveGateway', 'inclusiveGateway', 'eventBasedGateway', 'complexGateway']
    EVENT_TAGS = ['startEvent', 'endEvent', 'intermediateThrowEvent', 'intermediateCatchEvent']

    @classmethod
    def parse(cls, xml_content: str) -> Dict[str, Any]:
        try:
            root = ET.fromstring(xml_content)
        except Exception as e:
            raise ValueError(f"Malformed BPMN XML: {str(e)}")

        tasks = []
        for tag in cls.TASK_TAGS:
            for elem in root.findall(f'.//bpmn:{tag}', cls.NAMESPACES):
                elem_id = elem.attrib.get('id', '')
                if not elem_id:
                    raise ValueError(f"BPMN {tag} element is missing its required id.")
                elem_name = elem.attrib.get('name', elem_id)
                properties = elem.findall('.//{http://camunda.org/schema/1.0/bpmn}property')
                property_values = {item.attrib.get('name', '').lower(): item.attrib.get('value', '') for item in properties}
                # Duration: check attribute, child element or documentation
                duration = 1.0
                if 'duration' in elem.attrib:
                    try:
                        duration = float(elem.attrib['duration'])
                    except ValueError:
                        pass
                else:
                    # Camunda properties are commonly used to carry simulation metadata.
                    if property_values.get('duration'):
                        try:
                            duration = float(property_values['duration'])
                        except ValueError:
                            pass
                    # check for documentation or custom properties
                    doc = elem.find('bpmn:documentation', cls.NAMESPACES)
                    if duration == 1.0 and doc is not None and doc.text:
                        m = re.search(r'duration\s*[:=]\s*([0-9.]+)', doc.text, re.IGNORECASE)
                        if m:
                            duration = float(m.group(1))

                # Resource requirements
                resource = elem.attrib.get('resource', elem.attrib.get('candidateGroups', property_values.get('resource', 'Worker_Pool')))
                
                tasks.append({
                    'id': elem_id,
                    'name': elem_name if elem_name else elem_id,
                    'type': tag,
                    'duration': max(0.1, duration),
                    'resource': resource,
                    'incoming': [inc.text for inc in elem.findall('bpmn:incoming', cls.NAMESPACES) if inc.text],
                    'outgoing': [out.text for out in elem.findall('bpmn:outgoing', cls.NAMESPACES) if out.text]
                })

        gateways = []
        for tag in cls.GATEWAY_TAGS:
            for elem in root.findall(f'.//bpmn:{tag}', cls.NAMESPACES):
                elem_id = elem.attrib.get('id', '')
                gateways.append({
                    'id': elem_id,
                    'name': elem.attrib.get('name', elem_id),
                    'type': tag,
                    'incoming': [inc.text for inc in elem.findall('bpmn:incoming', cls.NAMESPACES) if inc.text],
                    'outgoing': [out.text for out in elem.findall('bpmn:outgoing', cls.NAMESPACES) if out.text]
                })

        events = []
        for tag in cls.EVENT_TAGS:
            for elem in root.findall(f'.//bpmn:{tag}', cls.NAMESPACES):
                elem_id = elem.attrib.get('id', '')
                events.append({
                    'id': elem_id,
                    'name': elem.attrib.get('name', elem_id),
                    'type': tag,
                    'incoming': [inc.text for inc in elem.findall('bpmn:incoming', cls.NAMESPACES) if inc.text],
                    'outgoing': [out.text for out in elem.findall('bpmn:outgoing', cls.NAMESPACES) if out.text]
                })

        flows = []
        for elem in root.findall('.//bpmn:sequenceFlow', cls.NAMESPACES):
            if not elem.attrib.get('id') or not elem.attrib.get('sourceRef') or not elem.attrib.get('targetRef'):
                raise ValueError("Every BPMN sequenceFlow must have id, sourceRef and targetRef attributes.")
            flows.append({
                'id': elem.attrib.get('id', ''),
                'name': elem.attrib.get('name', ''),
                'sourceRef': elem.attrib.get('sourceRef', ''),
                'targetRef': elem.attrib.get('targetRef', '')
            })

        known_ids = {item['id'] for item in tasks + gateways + events}
        for flow in flows:
            if flow['sourceRef'] not in known_ids or flow['targetRef'] not in known_ids:
                raise ValueError(f"Sequence flow {flow['id']} references an unknown BPMN element.")
        if not tasks:
            raise ValueError("No executable BPMN tasks were found.")

        return {
            'tasks': tasks,
            'gateways': gateways,
            'events': events,
            'flows': flows,
            'raw_xml': xml_content
        }


# ============================================================================
# STAGE 2: Workflow Graph Modeling
# ============================================================================

class WorkflowGraph:
    """Directed workflow graph model built on NetworkX."""

    def __init__(self, parsed_data: Dict[str, Any]):
        self.data = parsed_data
        self.graph = nx.DiGraph()
        self._build_graph()

    def _build_graph(self):
        all_nodes = self.data['tasks'] + self.data['gateways'] + self.data['events']
        for node in all_nodes:
            self.graph.add_node(
                node['id'],
                name=node['name'],
                category='task' if node in self.data['tasks'] else ('gateway' if node in self.data['gateways'] else 'event'),
                subtype=node['type'],
                duration=node.get('duration', 0.0),
                resource=node.get('resource', None)
            )

        for flow in self.data['flows']:
            src = flow['sourceRef']
            tgt = flow['targetRef']
            if src in self.graph and tgt in self.graph:
                self.graph.add_edge(src, tgt, flow_id=flow['id'], name=flow.get('name', ''))

    def get_start_nodes(self) -> List[str]:
        starts = [n for n, d in self.graph.nodes(data=True) if d.get('subtype') == 'startEvent']
        if not starts:
            starts = [n for n in self.graph.nodes if self.graph.in_degree(n) == 0]
        return starts

    def get_end_nodes(self) -> List[str]:
        ends = [n for n, d in self.graph.nodes(data=True) if d.get('subtype') == 'endEvent']
        if not ends:
            ends = [n for n in self.graph.nodes if self.graph.out_degree(n) == 0]
        return ends

    def get_parallel_splits(self) -> List[str]:
        return [n for n, d in self.graph.nodes(data=True) 
                if d.get('subtype') == 'parallelGateway' and self.graph.out_degree(n) > 1]

    def get_parallel_joins(self) -> List[str]:
        return [n for n, d in self.graph.nodes(data=True) 
                if d.get('subtype') == 'parallelGateway' and self.graph.in_degree(n) > 1]


# ============================================================================
# STAGE 3: BPMN-to-Petri-Net Conversion
# ============================================================================

class PetriNet:
    """Petri-Net structure (Places, Transitions, Arcs, Markings)."""

    def __init__(self):
        self.places: Dict[str, Dict[str, Any]] = {}
        self.transitions: Dict[str, Dict[str, Any]] = {}
        self.arcs: List[Tuple[str, str]] = []  # (source, target)
        self.initial_marking: Dict[str, int] = {}
        self.final_marking: Dict[str, int] = {}

    @classmethod
    def from_workflow(cls, wf: WorkflowGraph) -> 'PetriNet':
        net = cls()
        parsed = wf.data

        # Sequence flows become places
        for flow in parsed['flows']:
            p_id = f"p_{flow['id']}"
            net.places[p_id] = {
                'id': p_id,
                'flow_id': flow['id'],
                'label': f"Flow {flow['id']}"
            }
            net.initial_marking[p_id] = 0
            net.final_marking[p_id] = 0

        # Elements become transitions
        all_elements = parsed['tasks'] + parsed['gateways'] + parsed['events']
        for elem in all_elements:
            if elem['type'] in ('inclusiveGateway', 'eventBasedGateway', 'complexGateway'):
                raise ValueError(f"{elem['type']} '{elem['id']}' is not supported by the Petri-net converter.")
            if elem['type'] == 'exclusiveGateway':
                continue
            t_id = f"t_{elem['id']}"
            net.transitions[t_id] = {
                'id': t_id,
                'elem_id': elem['id'],
                'name': elem['name'],
                'type': elem['type'],
                'duration': elem.get('duration', 0.0),
                'resource': elem.get('resource', None),
                'incoming': elem.get('incoming', []),
                'outgoing': elem.get('outgoing', [])
            }

        # Connect places and transitions. Parallel gateways are AND transitions;
        # XOR gateways are expanded into a transition for each input/output pair.
        flow_ids = set()
        for flow in parsed['flows']:
            p_id = f"p_{flow['id']}"
            if p_id in flow_ids:
                raise ValueError(f"Duplicate BPMN sequence flow id: {flow['id']}")
            flow_ids.add(p_id)
            t_src = f"t_{flow['sourceRef']}"
            t_tgt = f"t_{flow['targetRef']}"
            source = next((g for g in parsed['gateways'] if g['id'] == flow['sourceRef']), None)
            target = next((g for g in parsed['gateways'] if g['id'] == flow['targetRef']), None)
            if source is None and t_src in net.transitions:
                net.arcs.append((t_src, p_id))
            if target is None and t_tgt in net.transitions:
                net.arcs.append((p_id, t_tgt))

        for gateway in parsed['gateways']:
            if gateway['type'] == 'parallelGateway':
                t_id = f"t_{gateway['id']}"
                for flow_id in gateway.get('incoming', []):
                    net.arcs.append((f"p_{flow_id}", t_id))
                for flow_id in gateway.get('outgoing', []):
                    net.arcs.append((t_id, f"p_{flow_id}"))
            elif gateway['type'] == 'exclusiveGateway':
                incoming = gateway.get('incoming', [])
                outgoing = gateway.get('outgoing', [])
                if not incoming or not outgoing:
                    raise ValueError(f"Exclusive gateway '{gateway['id']}' must have incoming and outgoing flows.")
                for in_index, in_flow in enumerate(incoming):
                    for out_index, out_flow in enumerate(outgoing):
                        t_id = f"t_{gateway['id']}_{in_index + 1}_{out_index + 1}"
                        net.transitions[t_id] = {
                            'id': t_id, 'elem_id': gateway['id'], 'name': gateway['name'],
                            'type': gateway['type'], 'duration': 0.0, 'resource': None,
                        }
                        net.arcs.extend([(f"p_{in_flow}", t_id), (t_id, f"p_{out_flow}")])

        # Give every BPMN element a transition. The synthetic source/sink places
        # make event transitions consume/produce tokens just like other nodes.
        # Add explicit initial and final places.
        start_nodes = wf.get_start_nodes()
        if start_nodes:
            p_start = "p_start_source"
            net.places[p_start] = {'id': p_start, 'label': 'Start Place'}
            net.initial_marking[p_start] = 1
            for s in start_nodes:
                net.arcs.append((p_start, f"t_{s}"))
        else:
            # Fallback: token in first place
            if net.places:
                first_place = list(net.places.keys())[0]
                net.initial_marking[first_place] = 1

        end_nodes = wf.get_end_nodes()
        if end_nodes:
            p_sink = "p_sink_end"
            net.places[p_sink] = {'id': p_sink, 'label': 'Sink Place'}
            net.final_marking[p_sink] = 1
            for e in end_nodes:
                net.arcs.append((f"t_{e}", p_sink))

        return net

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation of this ordinary Petri net."""
        return {
            'places': list(self.places.values()),
            'transitions': list(self.transitions.values()),
            'arcs': [{'source': source, 'target': target} for source, target in self.arcs],
            'initial_marking': self.initial_marking,
            'final_marking': self.final_marking,
        }


# ============================================================================
# STAGE 4: Initial Formal Verification & State-Space Exploration
# ============================================================================

class PetriNetAnalyzer:
    """Formal analysis: Reachability, Deadlocks, Soundness, Concurrency."""

    def __init__(self, net: PetriNet):
        self.net = net

    def explore_state_space(self, max_states: int = 5000) -> Dict[str, Any]:
        """BFS state space exploration over discrete Petri-net markings."""
        if max_states < 1:
            raise ValueError("max_states must be at least 1.")
        # Precompute transition input/output places
        trans_inputs = defaultdict(list)
        trans_outputs = defaultdict(list)
        for src, tgt in self.net.arcs:
            if src in self.net.places and tgt in self.net.transitions:
                trans_inputs[tgt].append(src)
            elif src in self.net.transitions and tgt in self.net.places:
                trans_outputs[src].append(tgt)

        initial_tuple = tuple(sorted((p, self.net.initial_marking.get(p, 0)) for p in self.net.places))
        visited = set()
        queue = deque([initial_tuple])
        visited.add(initial_tuple)

        reachable_markings = []
        deadlock_markings = []
        sink_place = "p_sink_end"

        truncated = False
        while queue:
            current = queue.popleft()
            curr_dict = dict(current)
            reachable_markings.append(curr_dict)

            # Check which transitions can fire
            enabled_trans = []
            for t, in_places in trans_inputs.items():
                # A transition is enabled if each input place has >= 1 token
                if in_places and all(curr_dict.get(p, 0) >= 1 for p in in_places):
                    enabled_trans.append(t)

            if not enabled_trans:
                # If no transitions enabled and process not at final state -> Deadlock!
                is_final = (sink_place in curr_dict and curr_dict[sink_place] >= 1)
                # Also check if any tokens left in non-sink places
                non_sink_tokens = sum(cnt for p, cnt in curr_dict.items() if p != sink_place)
                if not is_final or non_sink_tokens > 0:
                    deadlock_markings.append(curr_dict)
            else:
                for t in enabled_trans:
                    new_dict = curr_dict.copy()
                    for p in trans_inputs[t]:
                        new_dict[p] -= 1
                    for p in trans_outputs[t]:
                        new_dict[p] = new_dict.get(p, 0) + 1
                    new_tuple = tuple(sorted(new_dict.items()))
                    if new_tuple not in visited:
                        if len(visited) >= max_states:
                            truncated = True
                            queue.clear()
                            break
                        visited.add(new_tuple)
                        queue.append(new_tuple)

        # Soundness: Can always reach end, and at final state no tokens left behind
        has_proper_final_marking = any(
            marking.get(sink_place, 0) == 1 and
            sum(tokens for place, tokens in marking.items() if place != sink_place) == 0
            for marking in reachable_markings
        )
        is_sound = (not truncated and len(queue) == 0 and len(deadlock_markings) == 0 and
                    len(reachable_markings) > 0 and has_proper_final_marking)

        return {
            'total_reachable_states': len(visited),
            'deadlock_states': len(deadlock_markings),
            'is_sound': is_sound,
            'deadlocks': deadlock_markings[:5],  # first few samples
            'truncated': truncated,
        }

    def compute_concurrency_degree(self, wf: WorkflowGraph) -> int:
        """Find max number of independent activities that can execute simultaneously."""
        task_nodes = [n for n, d in wf.graph.nodes(data=True) if d.get('category') == 'task']
        if not task_nodes:
            return 1
        
        # Two tasks are concurrent if there is no directed path between them
        concurrent_pairs = set()
        for i, t1 in enumerate(task_nodes):
            for t2 in task_nodes[i+1:]:
                has_path_1_2 = nx.has_path(wf.graph, t1, t2)
                has_path_2_1 = nx.has_path(wf.graph, t2, t1)
                if not has_path_1_2 and not has_path_2_1:
                    concurrent_pairs.add((t1, t2))

        # Build concurrency graph and find max clique size
        cg = nx.Graph()
        cg.add_nodes_from(task_nodes)
        cg.add_edges_from(concurrent_pairs)
        
        cliques = list(nx.find_cliques(cg))
        max_clique = max(len(c) for c in cliques) if cliques else 1
        return max(1, max_clique)


# ============================================================================
# STAGE 5: Timed Discrete-Event Simulation
# ============================================================================

class DiscreteEventSimulator:
    """Discrete-event simulation modeling task durations, precedence, and resource limits."""

    def __init__(self, wf: WorkflowGraph, num_resources: int = 2):
        self.wf = wf
        self.num_resources = max(1, num_resources)

    def simulate(self, task_priorities: Optional[Dict[str, float]] = None,
                 duration_overrides: Optional[Dict[str, float]] = None,
                 resource_allocations: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        """Executes timed simulation with task queuing on shared resources."""
        g = self.wf.graph
        durations = {}
        for n, d in g.nodes(data=True):
            dur = d.get('duration', 0.0)
            if duration_overrides and n in duration_overrides:
                dur = duration_overrides[n]
            durations[n] = max(0.0, dur)

        # Predecessor mapping
        preds = {n: list(g.predecessors(n)) for n in g.nodes}
        succs = {n: list(g.successors(n)) for n in g.nodes}

        # Track execution state
        ready_time = {}
        start_time = {}
        finish_time = {}
        assigned_resource = {}
        waiting_time = {}

        # Resource management: workers available at times
        # List of worker available times: [avail_time_worker_0, avail_time_worker_1, ...]
        total_workers = self.num_resources
        worker_busy_until = [0.0] * total_workers
        worker_task_history = defaultdict(list)

        # Topological traversal respecting dependencies
        in_degrees = {n: len(preds[n]) for n in g.nodes}
        ready_queue = [n for n in g.nodes if in_degrees[n] == 0]
        for n in ready_queue:
            ready_time[n] = 0.0

        clock = 0.0
        completed = set()
        resource_conflicts_count = 0
        total_synchronization_overhead = 0.0

        # Event loop
        while ready_queue:
            # Sort ready tasks: prioritize by priority map (higher is higher priority)
            if task_priorities:
                ready_queue.sort(key=lambda x: task_priorities.get(x, 0.0), reverse=True)

            current_node = ready_queue.pop(0)
            node_data = g.nodes[current_node]
            is_task = (node_data.get('category') == 'task')
            dur = durations[current_node]
            earliest_start = ready_time.get(current_node, 0.0)

            # Check if this node is a join gateway -> measure sync overhead
            if node_data.get('subtype') == 'parallelGateway' and len(preds[current_node]) > 1:
                pred_finishes = [finish_time[p] for p in preds[current_node] if p in finish_time]
                if pred_finishes:
                    sync_delay = max(pred_finishes) - min(pred_finishes)
                    total_synchronization_overhead += sync_delay

            if is_task and dur > 0.0:
                # Needs a worker from the resource pool
                # Find the worker that becomes free earliest
                earliest_worker_idx = min(range(total_workers), key=lambda idx: worker_busy_until[idx])
                worker_avail = worker_busy_until[earliest_worker_idx]

                actual_start = max(earliest_start, worker_avail)
                if worker_avail > earliest_start:
                    resource_conflicts_count += 1

                actual_finish = actual_start + dur
                wait = actual_start - earliest_start

                worker_busy_until[earliest_worker_idx] = actual_finish
                worker_task_history[earliest_worker_idx].append({
                    'task': current_node,
                    'name': node_data.get('name', current_node),
                    'start': actual_start,
                    'finish': actual_finish,
                    'duration': dur
                })
                assigned_resource[current_node] = f"Worker_{earliest_worker_idx + 1}"
            else:
                # Instantaneous events or gateways
                actual_start = earliest_start
                actual_finish = actual_start + dur
                wait = 0.0
                assigned_resource[current_node] = "Control_Engine"

            start_time[current_node] = actual_start
            finish_time[current_node] = actual_finish
            waiting_time[current_node] = wait
            completed.add(current_node)

            # Release successors
            for s in succs[current_node]:
                in_degrees[s] -= 1
                if s not in ready_time:
                    ready_time[s] = actual_finish
                else:
                    # Parallel join requires max of all incoming; XOR would take min
                    if g.nodes[s].get('subtype') == 'parallelGateway':
                        ready_time[s] = max(ready_time[s], actual_finish)
                    else:
                        ready_time[s] = max(ready_time[s], actual_finish)

                if in_degrees[s] == 0:
                    ready_queue.append(s)

        makespan = max(finish_time.values()) if finish_time else 0.0

        # Detailed schedule records
        schedule = []
        for n in g.nodes:
            d = g.nodes[n]
            if d.get('category') == 'task':
                schedule.append({
                    'id': n,
                    'name': d.get('name', n),
                    'duration': durations[n],
                    'ready_time': round(ready_time.get(n, 0.0), 2),
                    'start_time': round(start_time.get(n, 0.0), 2),
                    'finish_time': round(finish_time.get(n, 0.0), 2),
                    'waiting_time': round(waiting_time.get(n, 0.0), 2),
                    'resource': assigned_resource.get(n, 'Worker_1')
                })

        # Calculate worker busy time
        worker_busy_sum = 0.0
        for widx in range(total_workers):
            busy = sum(item['duration'] for item in worker_task_history[widx])
            worker_busy_sum += busy

        total_capacity = makespan * total_workers
        utilization = (worker_busy_sum / total_capacity * 100.0) if total_capacity > 0 else 0.0
        idle_time = max(0.0, total_capacity - worker_busy_sum)

        return {
            'makespan': round(makespan, 2),
            'schedule': schedule,
            'start_time': start_time,
            'finish_time': finish_time,
            'waiting_time': waiting_time,
            'total_synchronization_overhead': round(total_synchronization_overhead, 2),
            'resource_conflicts': resource_conflicts_count,
            'resource_utilization': round(utilization, 1),
            'total_idle_time': round(idle_time, 2),
            'worker_history': dict(worker_task_history),
            'num_resources': total_workers
        }


# ============================================================================
# STAGE 6 & 7: Metric Calculation & Problem Identification
# ============================================================================

class MetricsCalculator:
    """Calculates all 11 core performance and correctness metrics."""

    @staticmethod
    def calculate(wf: WorkflowGraph, net_analysis: Dict[str, Any], sim_result: Dict[str, Any], max_concurrency: int) -> Dict[str, Any]:
        makespan = sim_result['makespan']
        schedule = sim_result['schedule']
        
        task_count = len(schedule)
        avg_wait = (sum(s['waiting_time'] for s in schedule) / task_count) if task_count > 0 else 0.0
        throughput = round(1.0 / makespan, 4) if makespan > 0 else 0.0
        time_wasted = round(sim_result['total_idle_time'] + sum(s['waiting_time'] for s in schedule), 2)

        # Identify bottleneck tasks (tasks on critical path with largest duration or wait)
        bottleneck = "None"
        if schedule:
            # Task that ends closest to makespan with longest duration
            candidates = sorted(schedule, key=lambda x: (x['finish_time'], x['duration']), reverse=True)
            bottleneck = f"{candidates[0]['name']} (id: {candidates[0]['id']})"

        return {
            'makespan': makespan,
            'throughput': throughput,
            'resource_utilization': sim_result['resource_utilization'],
            'average_waiting_time': round(avg_wait, 2),
            'time_wasted': time_wasted,
            'maximum_concurrency': max_concurrency,
            'reachable_states': net_analysis['total_reachable_states'],
            'deadlocks': net_analysis['deadlock_states'],
            'bottlenecks': bottleneck,
            'synchronization_overhead': sim_result['total_synchronization_overhead'],
            'resource_conflicts': sim_result['resource_conflicts']
        }


class ProblemIdentifier:
    """Examines metrics and pinpoints exact inefficiencies."""

    @staticmethod
    def diagnose(metrics: Dict[str, Any], sim_result: Dict[str, Any]) -> List[str]:
        problems = []
        if metrics['deadlocks'] > 0:
            problems.append(f"Critical: Workflow has {metrics['deadlocks']} deadlock states where execution halts prematurely.")
        if metrics['synchronization_overhead'] > 0:
            problems.append(f"Synchronization Delay: Parallel branches have duration skew causing {metrics['synchronization_overhead']} time units of waiting at join gateways.")
        if metrics['resource_conflicts'] > 0:
            problems.append(f"Resource Contention: {metrics['resource_conflicts']} tasks experienced delays waiting for available workers in the resource pool.")
        if metrics['average_waiting_time'] > 0.5:
            problems.append(f"High Task Latency: Tasks spend an average of {metrics['average_waiting_time']} time units idling before execution begins.")
        if metrics['resource_utilization'] < 60.0:
            problems.append(f"Low Capacity Efficiency: Resource utilization is only {metrics['resource_utilization']}%, indicating excessive idle capacity.")
        if not problems:
            problems.append("Workflow structure is sound, but execution time can be further accelerated via critical-path optimization.")
        return problems


# ============================================================================
# STAGE 8 & 9: Iterative Optimization Engine & Re-simulation
# ============================================================================

class IterativeOptimizer:
    """Iteratively explores candidate improvements: scheduling, resource balancing, and leveling."""

    def __init__(self, wf: WorkflowGraph, base_resources: int = 2, max_iterations: int = 6):
        self.wf = wf
        self.base_resources = base_resources
        self.max_iterations = max_iterations

    def run(self) -> Dict[str, Any]:
        if self.base_resources < 1:
            raise ValueError("The worker count must be at least 1.")
        if self.max_iterations < 0:
            raise ValueError("max_iterations cannot be negative.")
        if not nx.is_directed_acyclic_graph(self.wf.graph):
            raise ValueError("Timed simulation does not support BPMN loops; use an acyclic process model.")
        for node, data in self.wf.graph.nodes(data=True):
            if data.get('subtype') == 'exclusiveGateway' and (
                self.wf.graph.in_degree(node) > 1 or self.wf.graph.out_degree(node) > 1
            ):
                raise ValueError(
                    "Optimization simulation does not model exclusive-gateway conditions. "
                    "The BPMN can still be converted with /convert-to-petri-net."
                )
        # Baseline analysis
        net = PetriNet.from_workflow(self.wf)
        analyzer = PetriNetAnalyzer(net)
        net_analysis = analyzer.explore_state_space()
        max_conc = analyzer.compute_concurrency_degree(self.wf)

        sim = DiscreteEventSimulator(self.wf, num_resources=self.base_resources)
        baseline_sim = sim.simulate()
        baseline_metrics = MetricsCalculator.calculate(self.wf, net_analysis, baseline_sim, max_conc)
        baseline_problems = ProblemIdentifier.diagnose(baseline_metrics, baseline_sim)

        iteration_history = []
        # Iteration 0: Baseline
        iteration_history.append({
            'iteration': 0,
            'strategy': 'Baseline Workflow',
            'description': 'Initial unoptimized workflow schedule and allocation',
            'makespan': baseline_metrics['makespan'],
            'waiting_time': baseline_metrics['average_waiting_time'],
            'utilization': baseline_metrics['resource_utilization'],
            'improvement_pct': 0.0,
            'status': 'Baseline Accepted'
        })

        best_metrics = copy.deepcopy(baseline_metrics)
        best_sim = copy.deepcopy(baseline_sim)
        best_iteration = 0
        best_strategy = "Baseline"
        current_priorities = {}
        current_resources = self.base_resources
        current_durations = {}

        # Preserve original task durations in every scheduling/capacity scenario.
        for s in baseline_sim['schedule']:
            current_durations[s['id']] = s['duration']

        def finalize() -> Dict[str, Any]:
            overall_improvement = round(((baseline_metrics['makespan'] - best_metrics['makespan']) /
                                         baseline_metrics['makespan'] * 100), 2) if baseline_metrics['makespan'] > 0 else 0.0
            return {
                'baseline_metrics': baseline_metrics,
                'optimized_metrics': best_metrics,
                'baseline_schedule': baseline_sim['schedule'],
                'optimized_schedule': best_sim['schedule'],
                'iteration_history': iteration_history,
                'total_iterations': len(iteration_history),
                'best_iteration': best_iteration,
                'best_strategy': best_strategy,
                'overall_improvement_pct': overall_improvement,
                'problems_identified': baseline_problems,
                # The candidates change simulated scheduling/capacity assumptions, not BPMN
                # task semantics. Export the submitted model without invented duration edits.
                'optimized_bpmn_xml': self.wf.data.get('raw_xml', ''),
                'net_analysis': net_analysis,
                'workflow': {key: value for key, value in self.wf.data.items() if key != 'raw_xml'},
            }

        priorities = {task_id: duration * 10.0 for task_id, duration in current_durations.items()}
        for iteration in range(1, self.max_iterations + 1):
            # First candidate changes only the scheduling tie-break. Subsequent candidates
            # model progressively larger worker pools, up to the API's 100-worker limit.
            resources = self.base_resources if iteration == 1 else min(100, self.base_resources + iteration - 1)
            candidate_simulator = DiscreteEventSimulator(self.wf, num_resources=resources)
            candidate_sim = candidate_simulator.simulate(
                task_priorities=priorities,
                duration_overrides=current_durations,
            )
            candidate_metrics = MetricsCalculator.calculate(self.wf, net_analysis, candidate_sim, max_conc)
            improvement = round(
                ((baseline_metrics['makespan'] - candidate_metrics['makespan']) /
                 baseline_metrics['makespan'] * 100), 2
            ) if baseline_metrics['makespan'] > 0 else 0.0
            strategy = ('Longest-task-first scheduling' if iteration == 1 else
                        f'Hypothetical capacity scenario ({resources} workers)')
            accepted = (
                candidate_metrics['makespan'] < best_metrics['makespan'] or
                (candidate_metrics['makespan'] == best_metrics['makespan'] and
                 candidate_metrics['average_waiting_time'] < best_metrics['average_waiting_time'])
            )
            iteration_history.append({
                'iteration': iteration,
                'strategy': strategy,
                'description': ('Tested a longest-task-first scheduling priority without changing task durations.'
                                if iteration == 1 else
                                f'Simulated a worker pool of {resources}; this is a capacity scenario, not an applied deployment change.'),
                'makespan': candidate_metrics['makespan'],
                'waiting_time': candidate_metrics['average_waiting_time'],
                'utilization': candidate_metrics['resource_utilization'],
                'improvement_pct': improvement,
                'status': 'Best candidate' if accepted else 'Not better than current best',
            })
            if accepted:
                best_metrics = candidate_metrics
                best_sim = candidate_sim
                best_iteration = iteration
                best_strategy = strategy
                current_resources = resources

            # Further iterations would repeat the same maximum-capacity simulation.
            if resources == 100:
                break

        return finalize()

    def _generate_optimized_xml(self, durations: Dict[str, float], resources: int) -> str:
        """Injects optimized durations and resource annotations into the BPMN XML adhering strictly to standard BPMN 2.0 schema."""
        raw_xml = self.wf.data.get('raw_xml', '')
        if not raw_xml:
            return ""
        try:
            root = ET.fromstring(raw_xml)
            ns = BPMNParser.NAMESPACES

            # Register standard namespaces to avoid ns0: prefixes
            ET.register_namespace('bpmn', 'http://www.omg.org/spec/BPMN/20100524/MODEL')
            ET.register_namespace('bpmndi', 'http://www.omg.org/spec/BPMN/20100524/DI')
            ET.register_namespace('dc', 'http://www.omg.org/spec/DD/20100524/DC')
            ET.register_namespace('di', 'http://www.omg.org/spec/DD/20100524/DI')
            ET.register_namespace('camunda', 'http://camunda.org/schema/1.0/bpmn')

            # 1. Clean non-standard attributes and annotate standard documentation
            for tag in BPMNParser.TASK_TAGS:
                for elem in root.findall(f'.//bpmn:{tag}', ns):
                    elem_id = elem.attrib.get('id', '')
                    # Remove non-standard attributes to eliminate validator warnings in Camunda/bpmn.io
                    elem.attrib.pop('duration', None)
                    elem.attrib.pop('resource', None)

                    if elem_id in durations:
                        dur_val = durations[elem_id]
                        # Standard BPMN 2.0 documentation element
                        doc = elem.find('bpmn:documentation', ns)
                        if doc is None:
                            doc = ET.SubElement(elem, '{http://www.omg.org/spec/BPMN/20100524/MODEL}documentation')
                        doc.text = f"Optimized Duration: {dur_val} time units; Assigned Resource: Worker_Pool_{resources}."

                        # Standard ExtensionElements with properties for engine automation
                        ext = elem.find('bpmn:extensionElements', ns)
                        if ext is None:
                            ext = ET.SubElement(elem, '{http://www.omg.org/spec/BPMN/20100524/MODEL}extensionElements')
                        # Camunda / BPMN properties
                        props = ext.find('{http://camunda.org/schema/1.0/bpmn}properties')
                        if props is None:
                            props = ET.SubElement(ext, '{http://camunda.org/schema/1.0/bpmn}properties')
                        else:
                            props.clear()
                        p1 = ET.SubElement(props, '{http://camunda.org/schema/1.0/bpmn}property')
                        p1.attrib['name'] = 'duration'
                        p1.attrib['value'] = str(dur_val)
                        p2 = ET.SubElement(props, '{http://camunda.org/schema/1.0/bpmn}property')
                        p2.attrib['name'] = 'resource'
                        p2.attrib['value'] = f"Worker_Pool_{resources}"

            # 2. Ensure BPMNDI Plane exists and has Shapes & Edges for arrows
            plane = root.find('.//bpmndi:BPMNPlane', ns)
            if plane is not None:
                # Find all existing shape bounds
                shape_bounds = {}
                for shape in plane.findall('bpmndi:BPMNShape', ns):
                    b_elem = shape.find('dc:Bounds', ns)
                    elem_ref = shape.attrib.get('bpmnElement')
                    if b_elem is not None and elem_ref:
                        try:
                            shape_bounds[elem_ref] = {
                                'x': float(b_elem.attrib.get('x', 0)),
                                'y': float(b_elem.attrib.get('y', 0)),
                                'width': float(b_elem.attrib.get('width', 100)),
                                'height': float(b_elem.attrib.get('height', 80))
                            }
                        except ValueError:
                            pass

                # Check which sequence flows are missing BPMNEdge
                existing_edges = set()
                for edge in plane.findall('bpmndi:BPMNEdge', ns):
                    flow_ref = edge.attrib.get('bpmnElement')
                    if flow_ref:
                        existing_edges.add(flow_ref)

                # For any sequenceFlow without an edge, generate one using connected shape bounds
                for flow in self.wf.data['flows']:
                    f_id = flow['id']
                    if f_id not in existing_edges:
                        src_id = flow['sourceRef']
                        tgt_id = flow['targetRef']
                        if src_id in shape_bounds and tgt_id in shape_bounds:
                            s = shape_bounds[src_id]
                            t = shape_bounds[tgt_id]
                            
                            # Start waypoint: right center of source
                            start_x = s['x'] + s['width']
                            start_y = s['y'] + (s['height'] / 2.0)
                            # End waypoint: left center of target
                            end_x = t['x']
                            end_y = t['y'] + (t['height'] / 2.0)

                            edge_elem = ET.SubElement(plane, '{http://www.omg.org/spec/BPMN/20100524/DI}BPMNEdge')
                            edge_elem.attrib['id'] = f"BPMNEdge_{f_id}"
                            edge_elem.attrib['bpmnElement'] = f_id

                            # If not a straight horizontal line, add an intermediate bend
                            if abs(start_y - end_y) > 10 and (end_x - start_x) > 20:
                                mid_x = start_x + (end_x - start_x) / 2.0
                                wp1 = ET.SubElement(edge_elem, '{http://www.omg.org/spec/DD/20100524/DI}waypoint')
                                wp1.attrib['x'] = f"{start_x:.0f}"
                                wp1.attrib['y'] = f"{start_y:.0f}"
                                wp2 = ET.SubElement(edge_elem, '{http://www.omg.org/spec/DD/20100524/DI}waypoint')
                                wp2.attrib['x'] = f"{mid_x:.0f}"
                                wp2.attrib['y'] = f"{start_y:.0f}"
                                wp3 = ET.SubElement(edge_elem, '{http://www.omg.org/spec/DD/20100524/DI}waypoint')
                                wp3.attrib['x'] = f"{mid_x:.0f}"
                                wp3.attrib['y'] = f"{end_y:.0f}"
                                wp4 = ET.SubElement(edge_elem, '{http://www.omg.org/spec/DD/20100524/DI}waypoint')
                                wp4.attrib['x'] = f"{end_x:.0f}"
                                wp4.attrib['y'] = f"{end_y:.0f}"
                            else:
                                wp1 = ET.SubElement(edge_elem, '{http://www.omg.org/spec/DD/20100524/DI}waypoint')
                                wp1.attrib['x'] = f"{start_x:.0f}"
                                wp1.attrib['y'] = f"{start_y:.0f}"
                                wp2 = ET.SubElement(edge_elem, '{http://www.omg.org/spec/DD/20100524/DI}waypoint')
                                wp2.attrib['x'] = f"{end_x:.0f}"
                                wp2.attrib['y'] = f"{end_y:.0f}"

            return ET.tostring(root, encoding='utf-8').decode('utf-8')
        except Exception as ex:
            return raw_xml
