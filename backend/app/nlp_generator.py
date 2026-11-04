"""Natural Language Process Understanding & BPMN 2.0 XML Generation Engine.

Interprets natural language business process descriptions, extracts:
- Start and End Events
- Activities / Tasks with durations & resources
- Parallel Gateways (Split / Join)
- Exclusive Gateways (Decisions / Branches)
- Sequence Flows & Precedence Dependencies
- Complete BPMN 2.0 XML with full BPMNDI (Shapes, Bounds, Edges, Waypoints)

Prompt generation uses a configured OpenAI-compatible model endpoint.
"""

import re
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional


class ProcessNLPGenerator:
    """Understands natural language descriptions and synthesizes standard BPMN 2.0 XML."""

    @classmethod
    def generate_bpmn_xml(cls, text_prompt: str) -> str:
        """Generate and validate BPMN using the configured model."""
        prompt_clean = text_prompt.strip()
        if not prompt_clean:
            raise ValueError("Process prompt description cannot be empty.")

        api_key = os.environ.get("MAKEREND_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("MAKEREND_API_KEY is not configured.")
        xml = cls._generate_via_openai(prompt_clean, api_key)
        try:
            root = ET.fromstring(xml)
        except (ET.ParseError, TypeError) as exc:
            raise RuntimeError("The model returned invalid BPMN XML.") from exc
        if root.tag != "{http://www.omg.org/spec/BPMN/20100524/MODEL}definitions":
            raise RuntimeError("The model response is not a BPMN 2.0 definitions document.")
        return xml

    @classmethod
    def _generate_via_openai(cls, prompt: str, api_key: str) -> Optional[str]:
        """Call the configured OpenAI-compatible API to generate BPMN XML."""
        import urllib.request
        import urllib.error
        import json

        system_msg = (
            "You are an expert BPMN 2.0 architect. Generate valid, compliant BPMN 2.0 XML with "
            "complete BPMNDI diagram interchange (dc:Bounds, bpmndi:BPMNShape, bpmndi:BPMNEdge with di:waypoint). "
            "Preserve the described sequence, parallelism and decisions faithfully. Include start and end events, "
            "sequence flows, and task documentation specifying duration and resource when known. "
            "Do not invent process steps or assume tasks run in parallel. Return only raw XML, without markdown."
        )

        payload = {
            "model": os.environ.get("MAKEREND_MODEL", "gpt-6.1-terra"),
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Generate BPMN 2.0 XML for this business process:\n{prompt}"}
            ],
        }

        req = urllib.request.Request(
            os.environ.get("MAKEREND_BASE_URL", "https://makerend.com/v1").rstrip('/') + "/chat/completions",
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            raw_text = data['choices'][0]['message']['content'].strip()
            # Clean markdown code blocks if present
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
                raw_text = re.sub(r"\n?```$", "", raw_text)
            return raw_text.strip()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise RuntimeError("Makerend model is unavailable for this API key; check the model name and token channel settings.") from exc
            raise RuntimeError(f"Makerend request failed with HTTP {exc.code}; check the API configuration and provider availability.") from exc
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError, AttributeError) as exc:
            raise RuntimeError("Makerend BPMN generation failed; check the API configuration and provider availability.") from exc

    @classmethod
    def _synthesize_from_text(cls, text: str) -> str:
        """Deterministic Natural Language Process Synthesizer."""
        # 1. Break text into candidate steps/clauses
        # Split on sentence delimiters, semicolons, numbered lists or transitional adverbs
        normalized = text.replace("\r\n", "\n")
        lines = re.split(r'[\n;]|\.(?=\s+[A-Z0-9])|\b(?:then|after that|next|followed by|finally)\b', normalized, flags=re.IGNORECASE)

        raw_steps = [s.strip(" ,.-*\t") for s in lines if s.strip(" ,.-*\t")]

        extracted_tasks = []
        task_id_counter = 1

        # Check for global parallel indicators
        is_parallel_workflow = bool(re.search(r'\b(parallel|parallelly|simultaneous|simultaneously|concurrent|concurrently|at the same time|in parallel|both|all three)\b', text, re.IGNORECASE))
        has_decision = bool(re.search(r'\b(if|whether|check|decision|approved|rejected|condition)\b', text, re.IGNORECASE))

        for step in raw_steps:
            if len(step) < 4:
                continue

            # Extract duration if mentioned: e.g. "2 days", "3 hours", "duration: 4", "takes 3 units", "(2h)"
            dur = 2.0  # sensible default
            dur_match = re.search(r'(?:duration\s*[:=]?\s*|takes\s*|within\s*|for\s*)?([0-9]+(?:\.[0-9]+)?)\s*(?:days?|hours?|hrs?|units?|mins?|minutes?|secs?)?', step, re.IGNORECASE)
            if dur_match:
                try:
                    extracted_num = float(dur_match.group(1))
                    if 0.1 <= extracted_num <= 100:
                        dur = extracted_num
                except ValueError:
                    pass

            # Extract resource if mentioned: e.g. "by Worker 1", "assigned to Accountant", "Finance Team"
            res = f"Worker_{((task_id_counter - 1) % 2) + 1}"
            res_match = re.search(r'\b(?:by|assigned to|handled by|owner[:=]?)\s+([A-Za-z0-9_]+(?:\s+[A-Za-z0-9_]+)?)', step, re.IGNORECASE)
            if res_match:
                res = res_match.group(1).strip().replace(" ", "_")

            # Clean name of step
            clean_name = re.sub(r'^(?:step\s*\d+[:.]?|\d+[:.)]|\b(?:first|second|third|then|finally|next)\b)\s*', '', step, flags=re.IGNORECASE).strip()
            # Remove trailing duration expressions from task name
            clean_name = re.sub(r'\s*\([0-9.]+\s*[a-zA-Z]*\)', '', clean_name)
            clean_name = re.sub(r'\s*(?:takes|duration|within)\s*[0-9.]+\s*[a-zA-Z]*', '', clean_name, flags=re.IGNORECASE).strip()

            if not clean_name:
                clean_name = f"Activity {task_id_counter}"
            else:
                # Capitalize first letter, truncate if too long
                clean_name = clean_name[0].upper() + clean_name[1:]
                if len(clean_name) > 36:
                    clean_name = clean_name[:36] + "..."

            extracted_tasks.append({
                'id': f"Task_{task_id_counter}",
                'name': clean_name,
                'duration': dur,
                'resource': res
            })
            task_id_counter += 1

        # If only a single activity is found, preserve it and create a process
        # with one task rather than silently replacing the user's description.
        if len(extracted_tasks) < 2:
            extracted_tasks = extracted_tasks or [
                {'id': 'Task_1', 'name': 'Process Request', 'duration': 2.0, 'resource': 'Worker_1'}
            ]
            is_parallel_workflow = False

        # Limit to 5 tasks for clean, readable diagram layout
        if len(extracted_tasks) > 5:
            extracted_tasks = extracted_tasks[:5]

        # 2. Build standard BPMN 2.0 XML
        return cls._build_xml_document(extracted_tasks, is_parallel=is_parallel_workflow, has_decision=has_decision)

    @classmethod
    def _build_xml_document(cls, tasks: List[Dict[str, Any]], is_parallel: bool = True, has_decision: bool = False) -> str:
        """Constructs full BPMN 2.0 XML with compliant BPMNDI layout (Shapes & Edges with Waypoints)."""
        process_id = "Process_AutoGenerated"
        process_name = "Natural Language Generated Workflow"

        n_tasks = len(tasks)
        y_center = 200
        start_x = 160

        # Layout coordinates
        task_w = 120
        task_h = 80
        gw_w = 50
        gw_h = 50

        if is_parallel and n_tasks >= 2:
            # Parallel Fork-Join Pattern
            split_x = start_x + 90
            task_x = split_x + 110
            join_x = task_x + task_w + 100
            end_x = join_x + 100

            # Compute Y spread for tasks
            spacing = 100
            total_spread = (n_tasks - 1) * spacing
            top_y = y_center - (total_spread / 2)
            task_ys = [top_y + i * spacing for i in range(n_tasks)]

            # Construct Process elements
            xml_lines = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"',
                '                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"',
                '                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"',
                '                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"',
                '                  xmlns:camunda="http://camunda.org/schema/1.0/bpmn"',
                '                  id="Definitions_AutoGenerated"',
                '                  targetNamespace="http://example.com/bpmn">',
                f'  <bpmn:process id="{process_id}" name="{process_name}" isExecutable="true">',
                '    <bpmn:startEvent id="StartEvent_1" name="Process Start">',
                '      <bpmn:outgoing>Flow_Start_Split</bpmn:outgoing>',
                '    </bpmn:startEvent>',
                '    <bpmn:parallelGateway id="Gateway_Split" name="Parallel Split">',
                '      <bpmn:incoming>Flow_Start_Split</bpmn:incoming>',
            ]
            for t in tasks:
                xml_lines.append(f'      <bpmn:outgoing>Flow_Split_{t["id"]}</bpmn:outgoing>')
            xml_lines.append('    </bpmn:parallelGateway>')

            for t in tasks:
                xml_lines.extend([
                    f'    <bpmn:task id="{t["id"]}" name="{t["name"]}">',
                    f'      <bpmn:documentation>duration: {t["duration"]}; resource: {t["resource"]}</bpmn:documentation>',
                    '      <bpmn:extensionElements>',
                    '        <camunda:properties>',
                    f'          <camunda:property name="duration" value="{t["duration"]}" />',
                    f'          <camunda:property name="resource" value="{t["resource"]}" />',
                    '        </camunda:properties>',
                    '      </bpmn:extensionElements>',
                    f'      <bpmn:incoming>Flow_Split_{t["id"]}</bpmn:incoming>',
                    f'      <bpmn:outgoing>Flow_{t["id"]}_Join</bpmn:outgoing>',
                    '    </bpmn:task>'
                ])

            xml_lines.extend([
                '    <bpmn:parallelGateway id="Gateway_Join" name="Parallel Join">',
            ])
            for t in tasks:
                xml_lines.append(f'      <bpmn:incoming>Flow_{t["id"]}_Join</bpmn:incoming>')
            xml_lines.extend([
                '      <bpmn:outgoing>Flow_Join_End</bpmn:outgoing>',
                '    </bpmn:parallelGateway>',
                '    <bpmn:endEvent id="EndEvent_1" name="Process End">',
                '      <bpmn:incoming>Flow_Join_End</bpmn:incoming>',
                '    </bpmn:endEvent>',
                '    <!-- Sequence Flows -->',
                '    <bpmn:sequenceFlow id="Flow_Start_Split" sourceRef="StartEvent_1" targetRef="Gateway_Split"/>'
            ])
            for t in tasks:
                xml_lines.append(f'    <bpmn:sequenceFlow id="Flow_Split_{t["id"]}" sourceRef="Gateway_Split" targetRef="{t["id"]}"/>')
                xml_lines.append(f'    <bpmn:sequenceFlow id="Flow_{t["id"]}_Join" sourceRef="{t["id"]}" targetRef="Gateway_Join"/>')
            xml_lines.extend([
                '    <bpmn:sequenceFlow id="Flow_Join_End" sourceRef="Gateway_Join" targetRef="EndEvent_1"/>',
                '  </bpmn:process>',
                '  <bpmndi:BPMNDiagram id="BPMNDiagram_1">',
                f'    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{process_id}">',
                '      <!-- Shapes -->',
                f'      <bpmndi:BPMNShape id="Shape_Start" bpmnElement="StartEvent_1"><dc:Bounds x="{start_x}" y="{y_center - 18}" width="36" height="36"/></bpmndi:BPMNShape>',
                f'      <bpmndi:BPMNShape id="Shape_Split" bpmnElement="Gateway_Split"><dc:Bounds x="{split_x}" y="{y_center - 25}" width="{gw_w}" height="{gw_h}"/></bpmndi:BPMNShape>'
            ])
            for i, t in enumerate(tasks):
                xml_lines.append(f'      <bpmndi:BPMNShape id="Shape_{t["id"]}" bpmnElement="{t["id"]}"><dc:Bounds x="{task_x}" y="{task_ys[i] - 40}" width="{task_w}" height="{task_h}"/></bpmndi:BPMNShape>')
            xml_lines.extend([
                f'      <bpmndi:BPMNShape id="Shape_Join" bpmnElement="Gateway_Join"><dc:Bounds x="{join_x}" y="{y_center - 25}" width="{gw_w}" height="{gw_h}"/></bpmndi:BPMNShape>',
                f'      <bpmndi:BPMNShape id="Shape_End" bpmnElement="EndEvent_1"><dc:Bounds x="{end_x}" y="{y_center - 18}" width="36" height="36"/></bpmndi:BPMNShape>',
                '      <!-- Edges with Waypoints -->',
                '      <bpmndi:BPMNEdge id="Edge_Start_Split" bpmnElement="Flow_Start_Split">',
                f'        <di:waypoint x="{start_x + 36}" y="{y_center}"/>',
                f'        <di:waypoint x="{split_x}" y="{y_center}"/>',
                '      </bpmndi:BPMNEdge>'
            ])
            for i, t in enumerate(tasks):
                ty = task_ys[i]
                xml_lines.extend([
                    f'      <bpmndi:BPMNEdge id="Edge_Split_{t["id"]}" bpmnElement="Flow_Split_{t["id"]}">',
                    f'        <di:waypoint x="{split_x + gw_w / 2}" y="{y_center}"/>',
                    f'        <di:waypoint x="{split_x + gw_w / 2}" y="{ty}"/>',
                    f'        <di:waypoint x="{task_x}" y="{ty}"/>',
                    '      </bpmndi:BPMNEdge>',
                    f'      <bpmndi:BPMNEdge id="Edge_{t["id"]}_Join" bpmnElement="Flow_{t["id"]}_Join">',
                    f'        <di:waypoint x="{task_x + task_w}" y="{ty}"/>',
                    f'        <di:waypoint x="{join_x + gw_w / 2}" y="{ty}"/>',
                    f'        <di:waypoint x="{join_x + gw_w / 2}" y="{y_center}"/>',
                    '      </bpmndi:BPMNEdge>'
                ])
            xml_lines.extend([
                '      <bpmndi:BPMNEdge id="Edge_Join_End" bpmnElement="Flow_Join_End">',
                f'        <di:waypoint x="{join_x + gw_w}" y="{y_center}"/>',
                f'        <di:waypoint x="{end_x}" y="{y_center}"/>',
                '      </bpmndi:BPMNEdge>',
                '    </bpmndi:BPMNPlane>',
                '  </bpmndi:BPMNDiagram>',
                '</bpmn:definitions>'
            ])
            return "\n".join(xml_lines)

        else:
            # Sequential Workflow Pattern
            xml_lines = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"',
                '                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"',
                '                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"',
                '                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"',
                '                  xmlns:camunda="http://camunda.org/schema/1.0/bpmn"',
                '                  id="Definitions_AutoGenerated"',
                '                  targetNamespace="http://example.com/bpmn">',
                f'  <bpmn:process id="{process_id}" name="{process_name}" isExecutable="true">',
                '    <bpmn:startEvent id="StartEvent_1" name="Process Start">',
                '      <bpmn:outgoing>Flow_Start_Task1</bpmn:outgoing>',
                '    </bpmn:startEvent>',
            ]

            for i, t in enumerate(tasks):
                in_flow = "Flow_Start_Task1" if i == 0 else f"Flow_Task{i}_Task{i+1}"
                out_flow = f"Flow_Task{i+1}_Task{i+2}" if i < len(tasks) - 1 else f"Flow_Task{i+1}_End"
                xml_lines.extend([
                    f'    <bpmn:task id="{t["id"]}" name="{t["name"]}">',
                    f'      <bpmn:documentation>duration: {t["duration"]}; resource: {t["resource"]}</bpmn:documentation>',
                    '      <bpmn:extensionElements>',
                    '        <camunda:properties>',
                    f'          <camunda:property name="duration" value="{t["duration"]}" />',
                    f'          <camunda:property name="resource" value="{t["resource"]}" />',
                    '        </camunda:properties>',
                    '      </bpmn:extensionElements>',
                    f'      <bpmn:incoming>{in_flow}</bpmn:incoming>',
                    f'      <bpmn:outgoing>{out_flow}</bpmn:outgoing>',
                    '    </bpmn:task>'
                ])

            last_task = tasks[-1]["id"]
            xml_lines.extend([
                '    <bpmn:endEvent id="EndEvent_1" name="Process End">',
                f'      <bpmn:incoming>Flow_{last_task}_End</bpmn:incoming>',
                '    </bpmn:endEvent>',
                '    <!-- Sequence Flows -->',
                '    <bpmn:sequenceFlow id="Flow_Start_Task1" sourceRef="StartEvent_1" targetRef="Task_1"/>'
            ])
            for i in range(len(tasks) - 1):
                xml_lines.append(f'    <bpmn:sequenceFlow id="Flow_Task{i+1}_Task{i+2}" sourceRef="{tasks[i]["id"]}" targetRef="{tasks[i+1]["id"]}"/>')
            xml_lines.extend([
                f'    <bpmn:sequenceFlow id="Flow_{last_task}_End" sourceRef="{last_task}" targetRef="EndEvent_1"/>',
                '  </bpmn:process>',
                '  <bpmndi:BPMNDiagram id="BPMNDiagram_1">',
                f'    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{process_id}">',
                f'      <bpmndi:BPMNShape id="Shape_Start" bpmnElement="StartEvent_1"><dc:Bounds x="{start_x}" y="{y_center - 18}" width="36" height="36"/></bpmndi:BPMNShape>'
            ])
            cur_x = start_x + 90
            node_xs = [start_x]
            for i, t in enumerate(tasks):
                xml_lines.append(f'      <bpmndi:BPMNShape id="Shape_{t["id"]}" bpmnElement="{t["id"]}"><dc:Bounds x="{cur_x}" y="{y_center - 40}" width="{task_w}" height="{task_h}"/></bpmndi:BPMNShape>')
                node_xs.append(cur_x)
                cur_x += task_w + 60
            end_x = cur_x + 30
            node_xs.append(end_x)
            xml_lines.append(f'      <bpmndi:BPMNShape id="Shape_End" bpmnElement="EndEvent_1"><dc:Bounds x="{end_x}" y="{y_center - 18}" width="36" height="36"/></bpmndi:BPMNShape>')
            xml_lines.extend([
                '      <!-- Flow Edges -->',
                '      <bpmndi:BPMNEdge id="Edge_Start_Task1" bpmnElement="Flow_Start_Task1">',
                f'        <di:waypoint x="{start_x + 36}" y="{y_center}"/>',
                f'        <di:waypoint x="{node_xs[1]}" y="{y_center}"/>',
                '      </bpmndi:BPMNEdge>'
            ])
            for i in range(len(tasks) - 1):
                xml_lines.extend([
                    f'      <bpmndi:BPMNEdge id="Edge_Task{i+1}_Task{i+2}" bpmnElement="Flow_Task{i+1}_Task{i+2}">',
                    f'        <di:waypoint x="{node_xs[i+1] + task_w}" y="{y_center}"/>',
                    f'        <di:waypoint x="{node_xs[i+2]}" y="{y_center}"/>',
                    '      </bpmndi:BPMNEdge>'
                ])
            xml_lines.extend([
                f'      <bpmndi:BPMNEdge id="Edge_{last_task}_End" bpmnElement="Flow_{last_task}_End">',
                f'        <di:waypoint x="{node_xs[-2] + task_w}" y="{y_center}"/>',
                f'        <di:waypoint x="{end_x}" y="{y_center}"/>',
                '      </bpmndi:BPMNEdge>',
                '    </bpmndi:BPMNPlane>',
                '  </bpmndi:BPMNDiagram>',
                '</bpmn:definitions>'
            ])
            return "\n".join(xml_lines)
