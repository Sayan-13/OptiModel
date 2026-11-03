# OptiModel

**BPMN Workflow Analysis and Iterative Optimization System**

OptiModel is a web-based tool for **analyzing, simulating, verifying, and optimizing BPMN business-process workflows**.

The system accepts either:

- a BPMN/XML workflow file, or
- a natural-language description of a business process.

It then converts the workflow into an internal model, performs workflow analysis and optimization, compares the original and optimized workflows, and generates an optimized BPMN file together with a detailed PDF report.

---

## Features

### BPMN File Analysis

Upload an existing `.bpmn` or `.xml` workflow and analyze its structure and execution characteristics.

### Natural Language to BPMN

Describe a workflow in plain English, for example:

```text
When an order is received, packing, invoice generation,
and courier booking happen in parallel.
After all three activities finish, dispatch the order.
```

OptiModel generates BPMN 2.0 XML from the description and sends it through the analysis and optimization pipeline.

### Workflow Modeling

The uploaded/generated BPMN workflow is parsed and converted into an internal workflow graph for further analysis.

### Petri-Net Based Analysis

The workflow can be analyzed using Petri-Net concepts to study properties such as:

- reachable states
- synchronization
- concurrency
- deadlocks
- workflow soundness

### Timed Workflow Simulation

OptiModel simulates the execution of workflow activities while considering:

- activity duration
- available workers/resources
- parallel activities
- waiting time
- execution order
- resource conflicts

### Bottleneck Detection

The system identifies possible workflow problems such as:

- long-running activities
- excessive waiting
- synchronization delays
- resource conflicts
- inefficient resource allocation

### Iterative Optimization

OptiModel performs multiple optimization cycles and attempts to improve workflow performance.

The system keeps track of:

- optimization iteration
- strategy used
- makespan
- waiting time
- best iteration
- best optimization strategy

### Performance Comparison

The dashboard compares the **baseline workflow** with the **optimized workflow** using metrics such as:

| Metric | Description |
|---|---|
| Makespan | Total workflow completion time |
| Throughput | Number of process instances completed per time unit |
| Resource Utilization | Percentage of available resource capacity being used |
| Average Waiting Time | Average time activities wait before execution |
| Time Wasted | Idle and queue-related delay |
| Maximum Concurrency | Maximum activities executing simultaneously |
| Reachable States | Reachable Petri-Net markings |
| Deadlocks | Number of detected deadlock states |
| Synchronization Overhead | Delay caused by synchronization |
| Resource Conflicts | Contention for available resources |

### Interactive BPMN Visualization

The frontend uses **bpmn-js** to visualize BPMN workflows directly in the browser.

### Optimization Progress Visualization

Optimization results across multiple iterations are displayed using charts so that changes in makespan and waiting time can be observed.

### PDF Report Generation

After analysis, OptiModel generates a comparative PDF report containing the workflow-analysis and optimization results.

### Optimized BPMN Export

The optimized workflow can be downloaded as a `.bpmn` file for further editing or analysis using BPMN-compatible tools.

---

# System Workflow

```text
                     ┌───────────────────────┐
                     │      User Input       │
                     └───────────┬───────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
       Natural Language                    BPMN / XML File
                │                                 │
                ▼                                 │
      NLP Workflow Generator                     │
                │                                 │
                └────────────────┬────────────────┘
                                 ▼
                         BPMN XML Parser
                                 │
                                 ▼
                         Workflow Graph
                                 │
                                 ▼
                       Petri-Net Analysis
                                 │
                                 ▼
                      Workflow Simulation
                                 │
                                 ▼
                       Problem Detection
                                 │
                                 ▼
                     Iterative Optimization
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
           Optimized BPMN XML          Comparative Metrics
                    │                         │
                    └────────────┬────────────┘
                                 ▼
                         PDF Report
```

---

# Technology Stack

## Backend

- Python
- FastAPI
- Uvicorn
- NetworkX
- lxml
- Pydantic
- ReportLab
- python-multipart

## Frontend

- HTML5
- CSS3
- JavaScript
- Bootstrap 5
- Chart.js
- bpmn-js

---

# Project Structure

```text
OptiModel/
│
├── backend/
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── optimizer.py
│   │   ├── nlp_generator.py
│   │   ├── analysis.py
│   │   ├── report_builder.py
│   │   │
│   │   └── output/
│   │       ├── bpmn_workflow_analysis_report.pdf
│   │       └── optimized_workflow.bpmn
│   │
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── 1.xml
│   ├── 2.xml
│   │
│   └── css/
│       └── main.css
│
├── diagram_1.bpmn
├── bpmn_workflow_analysis_report.pdf
├── run_all.bat
└── README.md
```

---

# Installation

## Prerequisites

Make sure the following are installed:

- Python 3
- pip
- Git
- A modern web browser

Check Python installation:

```bash
python --version
```

Check Git installation:

```bash
git --version
```

---

# Clone the Repository

```bash
git clone https://github.com/Sayan-13/OptiModel.git
```

Move into the project directory:

```bash
cd OptiModel
```

---

# Quick Start on Windows

A one-click startup script is included.

Run:

```bat
run_all.bat
```

The script will automatically:

1. Create a Python virtual environment if required.
2. Install backend dependencies.
3. Start the FastAPI backend.
4. Start the frontend HTTP server.
5. Open the application in your default browser.

The services run at:

```text
Frontend:
http://localhost:8080

Backend:
http://localhost:8000
```

---

# Manual Setup

If you do not want to use `run_all.bat`, the frontend and backend can be started manually.

## 1. Create Virtual Environment

From the project root:

```bash
python -m venv backend/.venv
```

### Windows

```bash
backend\.venv\Scripts\activate
```

### Linux / macOS

```bash
source backend/.venv/bin/activate
```

---

## 2. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

---

## 3. Start the Backend

Move to the backend directory:

```bash
cd backend
```

Run FastAPI using Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at:

```text
http://localhost:8000
```

FastAPI interactive API documentation can normally be accessed at:

```text
http://localhost:8000/docs
```

---

## 4. Start the Frontend

Open another terminal and move into the frontend directory:

```bash
cd frontend
```

Start a local HTTP server:

```bash
python -m http.server 8080
```

Open:

```text
http://localhost:8080
```

---

# Using OptiModel

OptiModel provides two main input modes.

## Option 1 — Natural Language Workflow

Select:

```text
Natural Language Prompt to BPMN
```

Describe your process.

Example:

```text
When a customer loan application is received,
verify credit history and review employment documents
in parallel.

After both are completed, calculate underwriting risk
and then disburse approved funds.
```

Configure:

- Resource Pool Capacity
- Maximum Optimization Cycles

Then select:

```text
Generate & Optimize Workflow
```

The application will:

```text
Process Description
       ↓
Generate BPMN
       ↓
Parse Workflow
       ↓
Build Workflow Model
       ↓
Petri-Net Analysis
       ↓
Simulation
       ↓
Bottleneck Detection
       ↓
Iterative Optimization
       ↓
Optimized Workflow
```

---

## Option 2 — BPMN/XML File

Switch to:

```text
Upload BPMN XML File
```

Upload a:

```text
.xml
```

or:

```text
.bpmn
```

file.

Sample workflows are already available in:

```text
frontend/1.xml
frontend/2.xml
```

Configure the number of workers and optimization iterations, then run the analysis.

---

# Dashboard

After successful analysis, the dashboard displays several sections.

## Initial vs Final Metrics

Compares the baseline workflow with the optimized workflow.

## Interactive BPMN Diagram

Displays the workflow graphically using BPMN notation.

## Iteration Progression

Shows how optimization metrics change over multiple iterations.

## Execution Schedule & Resources

Displays information such as:

- Task
- Duration
- Ready Time
- Start Time
- Finish Time
- Waiting Time
- Assigned Resource

## Report Preview

Allows the generated workflow-analysis report to be viewed directly from the application.

---

# API Endpoints

The FastAPI backend provides the following main endpoints.

## Analyze BPMN

```http
POST /analyze
```

Accepts a BPMN/XML file and runs the complete analysis and optimization pipeline.

Parameters include:

```text
file
workers
max_iterations
```

---

## Generate and Analyze Workflow from Prompt

```http
POST /prompt-to-workflow
```

Example request:

```json
{
  "prompt": "Receive order, then pack product and prepare invoice in parallel, followed by dispatch.",
  "workers": 2,
  "max_iterations": 5
}
```

The endpoint:

1. Generates BPMN XML.
2. Parses the workflow.
3. Performs analysis.
4. Runs iterative optimization.
5. Generates the optimized BPMN.
6. Generates the comparison report.

---

## Generate BPMN XML Only

```http
POST /generate-xml-only
```

Generates BPMN XML from a natural-language process description without running the complete analysis pipeline.

---

## View Report

```http
GET /view-report
```

Displays the latest generated PDF report in the browser.

---

## Download Report

```http
GET /download-report
```

Downloads:

```text
bpmn_workflow_analysis_report.pdf
```

---

## Download Optimized BPMN

```http
GET /download-optimized-bpmn
```

Downloads:

```text
optimized_workflow.bpmn
```

---

# Example Workflow

Consider an order-fulfilment process:

```text
                    Order Received
                          │
                          ▼
                    Parallel Split
                    /      |       \
                   /       |        \
                  ▼        ▼         ▼
              Packing   Invoice    Courier
                                      Booking
                  \        |         /
                   \       |        /
                    └── Parallel Join
                           │
                           ▼
                        Dispatch
                           │
                           ▼
                          End
```

The three activities can execute concurrently.

The optimizer can analyze factors such as:

- which activity forms the bottleneck
- whether workers are available
- how long activities wait
- synchronization delay at the join
- overall process completion time

---

# Optimization Output

A successful analysis returns information including:

```text
Baseline Metrics
Optimized Metrics
Baseline Schedule
Optimized Schedule
Iteration History
Problems Identified
Overall Improvement
Best Iteration
Best Strategy
Optimized BPMN XML
```

This makes it possible to compare the process before and after optimization.

---

# Generated Files

After successful execution, the backend can generate:

```text
backend/app/output/bpmn_workflow_analysis_report.pdf
```

and:

```text
backend/app/output/optimized_workflow.bpmn
```

These can also be downloaded directly through the web interface.

---

# Sample Workflows

The repository contains example BPMN/XML workflows:

```text
frontend/1.xml
frontend/2.xml
```

These are useful for testing the analysis and optimization pipeline without creating a new BPMN process manually.

---

# Possible Future Improvements

Future versions of OptiModel could include:

- additional BPMN element support
- more advanced optimization algorithms
- automatic resource-cost optimization
- workflow cost analysis
- event-log import
- process-mining integration
- larger workflow benchmarks
- automated unit and integration testing
- Docker deployment
- database support
- optimization-strategy comparison
- multi-objective optimization
- real-world workflow datasets

---

# Contributing

Contributions are welcome.

For significant changes, it is recommended to create a separate branch rather than modifying `main` directly.

## 1. Clone the Repository

```bash
git clone https://github.com/Sayan-13/OptiModel.git
cd OptiModel
```

## 2. Create a New Branch

```bash
git checkout -b feature/your-feature-name
```

Example:

```bash
git checkout -b docs/add-readme
```

## 3. Make Your Changes

Add or modify the required files.

## 4. Stage Changes

```bash
git add .
```

## 5. Commit

```bash
git commit -m "Add project documentation"
```

## 6. Push the Branch

```bash
git push origin feature/your-feature-name
```

## 7. Create a Pull Request

Open GitHub and create a pull request from your branch into:

```text
main
```

Clearly describe:

- what you changed
- why the change was needed
- how the change was tested

---

# Areas for Contribution

Contributors can help improve:

- BPMN parsing
- Petri-Net analysis
- workflow simulation
- optimization algorithms
- performance metrics
- frontend visualization
- PDF reporting
- API validation
- automated testing
- documentation

---

# Development Notes

The frontend expects the backend API at:

```text
http://localhost:8000
```

The recommended local frontend address is:

```text
http://localhost:8080
```

When developing new features, make sure both services are running.

---

# Important Note

OptiModel is currently intended primarily for workflow analysis, experimentation, education, and optimization research.

Results produced by heuristic optimization should be validated before using them for critical real-world business decisions.

---

# Repository

**OptiModel**

```text
https://github.com/Sayan-13/OptiModel
```

---

## Summary

OptiModel provides an end-to-end workflow pipeline:

```text
Describe / Upload Process
          ↓
      BPMN Model
          ↓
   Workflow Parsing
          ↓
     Petri-Net Model
          ↓
      Verification
          ↓
      Simulation
          ↓
 Bottleneck Detection
          ↓
 Iterative Optimization
          ↓
Performance Comparison
          ↓
 Optimized BPMN + PDF
```

The goal of the project is to make **BPMN workflow analysis and optimization easier to visualize, evaluate, and experiment with through a single interactive application**.
