"""Publication-Quality PDF Report Generator for BPMN Workflow Analysis and Iterative Optimization.

Generates comprehensive reports with:
- Initial vs Final Metrics Comparison Table
- Visual BPMN Workflow & Execution Topology Diagram
- Petri-Net Verification & State-Space Exploration Details
- Iteration History & Optimization Operations Summary
- Simulation Timeline & Resource Allocation Schedules
- Problem Diagnostics & Technical Conclusion
"""

import math
import os
from typing import Dict, Any, List
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Rect, Circle, Line, String, Polygon, Group
from .report_diagrams import bpmn_graph, petri_graph, render_graph


def _draw_workflow_bpmn_diagram(analysis_result: Dict[str, Any]) -> Drawing:
    """Return a neutral placeholder if parsed workflow topology is unavailable."""
    drawing = Drawing(480, 100)
    drawing.add(Rect(0, 0, 480, 100, rx=8, ry=8, fillColor=colors.HexColor('#F8FAFC'),
                     strokeColor=colors.HexColor('#E2E8F0'), strokeWidth=1))
    drawing.add(String(20, 50, "Workflow topology is unavailable", fontName="Helvetica-Oblique",
                       fontSize=10, fillColor=colors.HexColor('#64748B')))
    return drawing


def _draw_actual_workflow_diagram(analysis_result: Dict[str, Any]) -> Drawing:
    """Draw the parsed BPMN topology rather than a synthesized example."""
    workflow = analysis_result.get('workflow', {})
    nodes = workflow.get('events', []) + workflow.get('gateways', []) + workflow.get('tasks', [])
    flows = workflow.get('sequence_flows', workflow.get('flows', []))
    if not nodes:
        return _draw_workflow_bpmn_diagram(analysis_result)

    incoming = {node['id']: 0 for node in nodes}
    successors = {node['id']: [] for node in nodes}
    for flow in flows:
        if flow['sourceRef'] in successors and flow['targetRef'] in incoming:
            successors[flow['sourceRef']].append(flow['targetRef'])
            incoming[flow['targetRef']] += 1

    # Assign a left-to-right rank while retaining branches on separate rows.
    ranks = {}
    frontier = [node['id'] for node in nodes if incoming[node['id']] == 0]
    for node_id in frontier:
        ranks[node_id] = 0
    while frontier:
        current = frontier.pop(0)
        for target in successors[current]:
            ranks[target] = max(ranks.get(target, 0), ranks[current] + 1)
            incoming[target] -= 1
            if incoming[target] == 0:
                frontier.append(target)
    for node in nodes:
        ranks.setdefault(node['id'], 0)

    columns = {}
    for node_id, rank in ranks.items():
        columns.setdefault(rank, []).append(node_id)
    col_count = max(columns) + 1
    canvas_w = 480
    canvas_h = max(170, 70 + max(len(items) for items in columns.values()) * 58)
    drawing = Drawing(canvas_w, canvas_h)
    drawing.add(Rect(0, 0, canvas_w, canvas_h, rx=8, ry=8, fillColor=colors.HexColor('#F8FAFC'),
                     strokeColor=colors.HexColor('#E2E8F0')))
    positions = {}
    for rank, ids in columns.items():
        x = 45 + rank * ((canvas_w - 90) / max(1, col_count - 1))
        spacing = canvas_h / (len(ids) + 1)
        for index, node_id in enumerate(ids):
            positions[node_id] = (x, canvas_h - (index + 1) * spacing)

    def arrow(x1, y1, x2, y2):
        drawing.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor('#64748B'), strokeWidth=1))
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 5
        drawing.add(Polygon(points=[x2, y2,
                                    x2 - size * math.cos(angle - 0.5), y2 - size * math.sin(angle - 0.5),
                                    x2 - size * math.cos(angle + 0.5), y2 - size * math.sin(angle + 0.5)],
                             fillColor=colors.HexColor('#64748B'), strokeColor=colors.HexColor('#64748B')))

    for flow in flows:
        if flow['sourceRef'] not in positions or flow['targetRef'] not in positions:
            continue
        sx, sy = positions[flow['sourceRef']]
        tx, ty = positions[flow['targetRef']]
        arrow(sx + 28, sy, tx - 28, ty)

    for node in nodes:
        x, y = positions[node['id']]
        category = node.get('type', '')
        if category.endswith('Event'):
            drawing.add(Circle(x, y, 14, fillColor=colors.HexColor('#DCFCE7' if category == 'startEvent' else '#FEE2E2'),
                                strokeColor=colors.HexColor('#16A34A' if category == 'startEvent' else '#DC2626'), strokeWidth=2))
        elif category.endswith('Gateway'):
            drawing.add(Polygon(points=[x, y + 17, x + 17, y, x, y - 17, x - 17, y],
                                fillColor=colors.HexColor('#FEF3C7'), strokeColor=colors.HexColor('#D97706'), strokeWidth=1.5))
        else:
            drawing.add(Rect(x - 40, y - 15, 80, 30, rx=5, ry=5, fillColor=colors.HexColor('#EFF6FF'),
                             strokeColor=colors.HexColor('#2563EB'), strokeWidth=1.2))
        label = str(node.get('name') or node['id'])
        label = label[:16] + '...' if len(label) > 19 else label
        drawing.add(String(x - min(35, len(label) * 2.5), y - 3, label, fontName='Helvetica', fontSize=6.5,
                           fillColor=colors.HexColor('#1E293B')))
    drawing.add(String(12, 10, 'Parsed BPMN topology; arrows represent sequence flows', fontName='Helvetica-Oblique',
                       fontSize=6.5, fillColor=colors.HexColor('#64748B')))
    return drawing


def build_comparative_pdf_report(analysis_result: Dict[str, Any], output_path: str):
    """Builds a complete, multi-page comparison report PDF with embedded visual diagrams."""
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch
    )

    base_styles = getSampleStyleSheet()

    # Custom typography
    styles = {
        'DocTitle': ParagraphStyle('DocTitle', parent=base_styles['Title'], fontName='Helvetica-Bold', fontSize=20, leading=24, alignment=TA_CENTER, textColor=colors.HexColor('#0F172A')),
        'DocSub': ParagraphStyle('DocSub', parent=base_styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, alignment=TA_CENTER, textColor=colors.HexColor('#475569')),
        'SectionHeader': ParagraphStyle('SectionHeader', parent=base_styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=16, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor('#1E3A8A')),
        'Body': ParagraphStyle('Body', parent=base_styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12.5, alignment=TA_JUSTIFY, textColor=colors.HexColor('#334155')),
        'BodyBold': ParagraphStyle('BodyBold', parent=base_styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=12.5, textColor=colors.HexColor('#0F172A')),
        'Cell': ParagraphStyle('Cell', parent=base_styles['Normal'], fontName='Helvetica', fontSize=8, leading=10.5, textColor=colors.HexColor('#1E293B')),
        'CellBold': ParagraphStyle('CellBold', parent=base_styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10.5, textColor=colors.HexColor('#0F172A')),
        'BadgeSuccess': ParagraphStyle('BadgeSuccess', parent=base_styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10.5, textColor=colors.HexColor('#047857')),
        'SmallCenter': ParagraphStyle('SmallCenter', parent=base_styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=10, alignment=TA_CENTER, textColor=colors.HexColor('#64748B')),
    }

    elements = []

    base_m = analysis_result['baseline_metrics']
    opt_m = analysis_result['optimized_metrics']
    history = analysis_result['iteration_history']

    # ================= HEADER =================
    elements.append(Paragraph("BPMN-Based Workflow Analysis and Iterative Optimization", styles['DocTitle']))
    elements.append(Spacer(1, 3))
    elements.append(Paragraph("Automated Petri-Net Verification, Discrete-Event Simulation &amp; Performance Engineering", styles['DocSub']))
    elements.append(Spacer(1, 3))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1E3A8A'), spaceBefore=2, spaceAfter=8))

    # ================= 1. EXECUTIVE SUMMARY =================
    elements.append(Paragraph("1. Executive Summary &amp; Objective", styles['SectionHeader']))
    elements.append(Paragraph(
        "This report summarizes automated workflow analysis and timed simulation of the supplied BPMN model. "
        "It maps supported elements to a Petri net, explores its bounded state space and simulates task durations "
        "with a simplified shared-worker model. It evaluated "
        f"{len(history)-1} candidate iterations. "
        f"The baseline simulated process completion time (makespan) was <b>{base_m['makespan']}</b>; "
        f"the best simulated candidate measured <b>{opt_m['makespan']} time units</b>, "
        f"a <b>{analysis_result['overall_improvement_pct']}% simulated change</b> under the configured worker-pool assumptions.",
        styles['Body']
    ))
    elements.append(Spacer(1, 4))

    # ================= VISUAL BPMN DIAGRAM =================
    elements.append(Paragraph("2. Visual BPMN Workflow &amp; Execution Topology", styles['SectionHeader']))
    elements.append(Paragraph(
        "The diagram below is derived from parsed BPMN events, gateways, tasks and sequence flows:",
        styles['Body']
    ))
    elements.append(Spacer(1, 4))
    workflow = analysis_result.get('workflow', {})
    if workflow.get('tasks'):
        elements.append(render_graph(bpmn_graph(workflow)))
    else:
        elements.append(_draw_workflow_bpmn_diagram(analysis_result))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph("<i>Figure 1: Parsed BPMN topology</i>", styles['SmallCenter']))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Petri-net representation", styles['SectionHeader']))
    elements.append(Paragraph(
        "The converted net used for verification is shown below. Circles are places, rectangles are "
        "transitions, and the dot marks the initial token. Exclusive gateways may map to multiple transitions.",
        styles['Body']))
    elements.append(Spacer(1, 4))
    if workflow.get('tasks'):
        elements.append(render_graph(petri_graph(workflow)))
    else:
        elements.append(_draw_workflow_bpmn_diagram(analysis_result))
    elements.append(Paragraph("<i>Figure 2: Petri net and initial marking</i>", styles['SmallCenter']))
    elements.append(Spacer(1, 6))

    # ================= 3. INITIAL VS FINAL COMPARISON TABLE =================
    elements.append(Paragraph("3. Initial vs. Final Performance Metrics Comparison", styles['SectionHeader']))

    def calc_pct_reduction(b, o):
        if b == 0:
            return "0.0%"
        diff = ((b - o) / b) * 100.0
        return f"{diff:+.1f}%"

    def calc_pct_increase(b, o):
        if b == 0:
            return "0.0%"
        diff = ((o - b) / b) * 100.0
        return f"{diff:+.1f}%"

    comp_rows = [
        ["Performance Metric", "Baseline", "Best Candidate", "Observed Change"],
        ["Makespan (Total Execution Time)", f"{base_m['makespan']} time units", f"{opt_m['makespan']} time units", calc_pct_reduction(base_m['makespan'], opt_m['makespan']) + " simulated change"],
        ["Throughput", f"{base_m['throughput']} instances/unit", f"{opt_m['throughput']} instances/unit", calc_pct_increase(base_m['throughput'], opt_m['throughput']) + " throughput"],
        ["Resource Utilization", f"{base_m['resource_utilization']}%", f"{opt_m['resource_utilization']}%", f"{opt_m['resource_utilization'] - base_m['resource_utilization']:+.1f}% capacity shift"],
        ["Average Waiting Time", f"{base_m['average_waiting_time']} time units", f"{opt_m['average_waiting_time']} time units", calc_pct_reduction(base_m['average_waiting_time'], opt_m['average_waiting_time']) + " wait reduction"],
        ["Time Wasted (Idle + Queue)", f"{base_m['time_wasted']} time units", f"{opt_m['time_wasted']} time units", calc_pct_reduction(base_m['time_wasted'], opt_m['time_wasted']) + " waste eliminated"],
        ["Maximum Concurrency", f"{base_m['maximum_concurrency']} activities", f"{opt_m['maximum_concurrency']} activities", "Estimated structural concurrency"],
        ["Reachable States", f"{base_m['reachable_states']} markings", f"{opt_m['reachable_states']} markings", "Exploration count"],
        ["Deadlocks", f"{base_m['deadlocks']} states", f"{opt_m['deadlocks']} states", "Exploration count"],
        ["Bottleneck Activity", str(base_m['bottlenecks']), str(opt_m['bottlenecks']), "Observed candidate result"],
        ["Synchronization Overhead", f"{base_m['synchronization_overhead']} time units", f"{opt_m['synchronization_overhead']} time units", calc_pct_reduction(base_m['synchronization_overhead'], opt_m['synchronization_overhead']) + " join wait"],
        ["Resource Conflicts", f"{base_m['resource_conflicts']} queue events", f"{opt_m['resource_conflicts']} queue events", f"-{base_m['resource_conflicts'] - opt_m['resource_conflicts']} contention events"],
    ]

    table_data = []
    for r_idx, row in enumerate(comp_rows):
        table_data.append([
            Paragraph(row[0], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[1], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[2], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[3], styles['CellBold'] if r_idx == 0 else styles['BadgeSuccess'])
        ])

    comp_table = Table(table_data, colWidths=[2.2 * inch, 1.6 * inch, 1.6 * inch, 1.8 * inch])
    comp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8FAFC'), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(comp_table)
    elements.append(Spacer(1, 8))

    # ================= 4. PROBLEM DIAGNOSIS & PETRI NET VERIFICATION =================
    elements.append(Paragraph("4. Problem Diagnostics &amp; Formal Petri-Net Verification", styles['SectionHeader']))
    problems = analysis_result.get('problems_identified', [])
    for prob in problems:
        elements.append(Paragraph(f"• <b>Identified Inefficiency:</b> {escape(str(prob))}", styles['Body']))
    elements.append(Spacer(1, 3))
    verification = analysis_result.get('net_analysis', {})
    if verification.get('truncated'):
        verification_status = 'inconclusive: state-space exploration was truncated'
    elif verification.get('is_sound'):
        verification_status = 'bounded soundness checks passed'
    else:
        verification_status = 'soundness checks did not pass'
    elements.append(Paragraph(
        f"<b>Petri-net exploration:</b> {base_m['reachable_states']} markings explored; "
        f"{base_m['deadlocks']} deadlock(s) detected. Result: <b>{verification_status}</b>. "
        "This bounded exploration is not a general behavioral-correctness or production-readiness guarantee.",
        styles['Body']
    ))
    elements.append(Spacer(1, 6))

    # ================= 5. ITERATIVE OPTIMIZATION SUMMARY =================
    elements.append(Paragraph("5. Candidate Simulation Progression", styles['SectionHeader']))
    iter_rows = [["Cycle", "Candidate Scenario", "Makespan", "Avg Wait", "Utilization", "Change", "Status"]]
    for item in history:
        iter_rows.append([
            f"Iter {item['iteration']}",
            item['strategy'],
            f"{item['makespan']} u",
            f"{item['waiting_time']} u",
            f"{item['utilization']}%",
            f"{item['improvement_pct']}%",
            item['status']
        ])

    iter_table_data = []
    for r_idx, row in enumerate(iter_rows):
        iter_table_data.append([
            Paragraph(f"<b>{row[0]}</b>", styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[1], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[2], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[3], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[4], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[5], styles['CellBold'] if r_idx == 0 else styles['BadgeSuccess']),
            Paragraph(row[6], styles['CellBold'] if r_idx == 0 else styles['Cell'])
        ])

    iter_table = Table(iter_table_data, colWidths=[0.8*inch, 2.3*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.9*inch, 0.8*inch])
    iter_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8FAFC'), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(iter_table)
    elements.append(Spacer(1, 8))

    # ================= 6. TIMED SIMULATION SCHEDULES =================
    elements.append(Paragraph("6. Activity Execution Schedule &amp; Resource Allocation", styles['SectionHeader']))
    sched_header = ["Task Activity", "Duration", "Ready", "Start", "Finish", "Wait", "Resource"]
    sched_rows = [sched_header]
    for task in analysis_result['optimized_schedule']:
        sched_rows.append([
            task['name'],
            f"{task['duration']} u",
            f"{task['ready_time']} u",
            f"{task['start_time']} u",
            f"{task['finish_time']} u",
            f"{task['waiting_time']} u",
            task['resource']
        ])

    sched_table_data = []
    for r_idx, row in enumerate(sched_rows):
        sched_table_data.append([
            Paragraph(f"<b>{row[0]}</b>", styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[1], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[2], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[3], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[4], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[5], styles['CellBold'] if r_idx == 0 else styles['Cell']),
            Paragraph(row[6], styles['CellBold'] if r_idx == 0 else styles['Cell'])
        ])

    sched_table = Table(sched_table_data, colWidths=[2.1*inch, 0.8*inch, 0.7*inch, 0.7*inch, 0.8*inch, 0.7*inch, 1.4*inch])
    sched_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F766E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8FAFC'), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(sched_table)
    elements.append(Spacer(1, 8))

    # ================= 7. CONCLUSION =================
    elements.append(Paragraph("7. Technical Conclusion", styles['SectionHeader']))
    elements.append(Paragraph(
        f"The workflow analysis and scheduling/capacity candidates produced a simulated makespan "
        f"from <b>{base_m['makespan']} to {opt_m['makespan']} time units</b> ({analysis_result['overall_improvement_pct']}% simulated change). "
        f"The selected candidate had throughput of <b>{opt_m['throughput']} instances/unit</b> and average waiting time of <b>{opt_m['average_waiting_time']} time units</b>. "
        "These results reflect the simulator's assumptions and do not constitute a behavioral-correctness "
        "or production-readiness guarantee.",
        styles['Body']
    ))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#94A3B8'), spaceBefore=2, spaceAfter=6))
    elements.append(Paragraph("Report generated automatically by BPMN Analysis &amp; Optimization Engine • All rights reserved", styles['SmallCenter']))

    doc.build(elements)
