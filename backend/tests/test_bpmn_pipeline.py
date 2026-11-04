import unittest
import tempfile
from pathlib import Path

from backend.app.optimizer import BPMNParser, WorkflowGraph, PetriNet, PetriNetAnalyzer, IterativeOptimizer
from backend.app.report_builder import _draw_actual_workflow_diagram
from backend.app.report_builder import build_comparative_pdf_report
from backend.app.report_diagrams import bpmn_graph, petri_graph, render_graph


ROOT = Path(__file__).resolve().parents[2]


class BPMNPetriNetTests(unittest.TestCase):
    def test_camunda_properties_are_read_and_parallel_net_is_bounded(self):
        xml = (ROOT / 'frontend' / '2.xml').read_text(encoding='utf-8')
        parsed = BPMNParser.parse(xml)
        self.assertEqual([task['duration'] for task in parsed['tasks']], [2.0, 3.0, 4.0])
        self.assertEqual(parsed['tasks'][0]['resource'], 'Worker_1')

        net = PetriNet.from_workflow(WorkflowGraph(parsed))
        analysis = PetriNetAnalyzer(net).explore_state_space()
        self.assertEqual(analysis['deadlock_states'], 0)
        self.assertTrue(analysis['is_sound'])
        self.assertEqual(len(net.places), 10)  # eight flows and source/sink places

    def test_default_namespace_is_supported(self):
        xml = '''<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">
          <process id="p"><startEvent id="s"/><task id="t" name="Work"/>
          <endEvent id="e"/><sequenceFlow id="a" sourceRef="s" targetRef="t"/>
          <sequenceFlow id="b" sourceRef="t" targetRef="e"/></process></definitions>'''
        parsed = BPMNParser.parse(xml)
        self.assertEqual(len(parsed['tasks']), 1)
        self.assertEqual(len(parsed['flows']), 2)

    def test_dangling_sequence_flow_fails_early(self):
        xml = '''<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">
          <process id="p"><task id="t"/><sequenceFlow id="f" sourceRef="t" targetRef="missing"/></process>
        </definitions>'''
        with self.assertRaisesRegex(ValueError, 'unknown BPMN element'):
            BPMNParser.parse(xml)

    def test_state_limit_reports_inconclusive_not_sound(self):
        xml = (ROOT / 'frontend' / '2.xml').read_text(encoding='utf-8')
        net = PetriNet.from_workflow(WorkflowGraph(BPMNParser.parse(xml)))
        result = PetriNetAnalyzer(net).explore_state_space(max_states=1)
        self.assertTrue(result['truncated'])
        self.assertFalse(result['is_sound'])
        self.assertEqual(result['total_reachable_states'], 1)

    def test_candidate_iteration_limit_preserves_durations_and_xml(self):
        xml = (ROOT / 'frontend' / '2.xml').read_text(encoding='utf-8')
        wf = WorkflowGraph(BPMNParser.parse(xml))
        for cap in (0, 1, 3):
            with self.subTest(cap=cap):
                result = IterativeOptimizer(wf, base_resources=2, max_iterations=cap).run()
                self.assertEqual(result['total_iterations'], cap + 1)  # baseline plus candidate runs
                self.assertEqual(len(result['iteration_history']) - 1, cap)
                self.assertEqual(result['optimized_bpmn_xml'], xml)
                self.assertEqual(
                    [item['duration'] for item in result['optimized_schedule']],
                    [item['duration'] for item in result['baseline_schedule']],
                )

    def test_report_diagram_uses_workflow_nodes_and_flows(self):
        xml = '''<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">
          <process id="p"><startEvent id="s"/><task id="custom" name="Custom Activity"/>
          <endEvent id="e"/><sequenceFlow id="a" sourceRef="s" targetRef="custom"/>
          <sequenceFlow id="b" sourceRef="custom" targetRef="e"/></process></definitions>'''
        parsed = BPMNParser.parse(xml)
        result = {'workflow': {'tasks': parsed['tasks'], 'events': parsed['events'],
                               'gateways': parsed['gateways'], 'sequence_flows': parsed['flows']}}
        diagram = _draw_actual_workflow_diagram(result)
        labels = [item.text for item in diagram.contents if getattr(item, 'text', None)]
        self.assertIn('Custom Activity', labels)
        self.assertFalse(any('AND Split' in label for label in labels))

    def test_graphviz_diagrams_match_converted_net_and_build_pdf(self):
        xml = (ROOT / 'frontend' / '2.xml').read_text(encoding='utf-8')
        parsed = BPMNParser.parse(xml)
        net = PetriNet.from_workflow(WorkflowGraph(parsed))
        bpmn = bpmn_graph(parsed)
        petri = petri_graph(parsed)
        for node in parsed['tasks'] + parsed['events'] + parsed['gateways']:
            self.assertIn(node['id'], bpmn.source)
        for place in net.places:
            self.assertIn(place, petri.source)
        for source, target in net.arcs:
            self.assertIn(f'{source} -> {target}', petri.source)
        self.assertIn('●', petri.source)
        self.assertGreater(render_graph(bpmn).width, 0)
        self.assertGreater(render_graph(petri).height, 0)
        result = IterativeOptimizer(WorkflowGraph(parsed), base_resources=2, max_iterations=1).run()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.pdf'
            build_comparative_pdf_report(result, str(output))
            self.assertTrue(output.read_bytes().startswith(b'%PDF'))


if __name__ == '__main__':
    unittest.main()
