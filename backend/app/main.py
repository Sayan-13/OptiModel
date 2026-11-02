from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import pathlib
import traceback

from .optimizer import BPMNParser, WorkflowGraph, IterativeOptimizer
from .report_builder import build_comparative_pdf_report
from .nlp_generator import ProcessNLPGenerator
from pydantic import BaseModel

class PromptWorkflowRequest(BaseModel):
    prompt: str
    workers: int = 2
    max_iterations: int = 5

app = FastAPI(title="BPMN Workflow Analysis & Iterative Optimization API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = pathlib.Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
PDF_PATH = OUTPUT_DIR / "bpmn_workflow_analysis_report.pdf"
OPTIMIZED_BPMN_PATH = OUTPUT_DIR / "optimized_workflow.bpmn"

# Pre-build initial default report on startup if not yet created
if not PDF_PATH.exists():
    try:
        sample_path = pathlib.Path(__file__).parent.parent.parent / "frontend" / "2.xml"
        if not sample_path.exists():
            sample_path = pathlib.Path(__file__).parent.parent.parent / "frontend" / "1.xml"
        if sample_path.exists():
            with open(sample_path, "r", encoding="utf-8") as f:
                _raw = f.read()
            _parsed = BPMNParser.parse(_raw)
            _wf = WorkflowGraph(_parsed)
            _opt = IterativeOptimizer(_wf, base_resources=2, max_iterations=5)
            _res = _opt.run()
            build_comparative_pdf_report(_res, str(PDF_PATH))
            with open(OPTIMIZED_BPMN_PATH, "w", encoding="utf-8") as f:
                f.write(_res['optimized_bpmn_xml'])
    except Exception:
        pass


@app.post("/analyze")
async def analyze_bpmn(
    file: UploadFile = File(...),
    workers: int = Form(default=2),
    max_iterations: int = Form(default=5)
):
    """Executes the full 10-stage BPMN analysis and iterative optimization pipeline."""
    if not file.filename.lower().endswith(('.xml', '.bpmn')):
        raise HTTPException(status_code=400, detail="Only .xml or .bpmn workflow files are accepted.")

    try:
        content_bytes = await file.read()
        xml_content = content_bytes.decode('utf-8', errors='replace')

        # 1. Parse BPMN XML
        parsed = BPMNParser.parse(xml_content)
        if not parsed['tasks']:
            raise ValueError("No executable tasks found in the uploaded BPMN XML.")

        # 2. Workflow Modeling
        wf = WorkflowGraph(parsed)

        # 3-9. Petri-Net Conversion, Verification, Simulation, Problem Identification & Optimization
        optimizer = IterativeOptimizer(wf, base_resources=workers, max_iterations=max_iterations)
        result = optimizer.run()

        # 10. Generate publication-quality Comparative PDF Report
        build_comparative_pdf_report(result, str(PDF_PATH))

        # Save optimized BPMN file
        with open(OPTIMIZED_BPMN_PATH, "w", encoding="utf-8") as f:
            f.write(result['optimized_bpmn_xml'])

        # Return full analysis payload for rich dashboard display
        return JSONResponse(content={
            "status": "success",
            "filename": file.filename,
            "baseline_metrics": result['baseline_metrics'],
            "optimized_metrics": result['optimized_metrics'],
            "baseline_schedule": result['baseline_schedule'],
            "optimized_schedule": result['optimized_schedule'],
            "iteration_history": result['iteration_history'],
            "problems_identified": result['problems_identified'],
            "overall_improvement_pct": result['overall_improvement_pct'],
            "total_iterations": result['total_iterations'],
            "best_iteration": result['best_iteration'],
            "best_strategy": result['best_strategy'],
            "optimized_bpmn_xml": result['optimized_bpmn_xml'],
            "initial_bpmn_xml": xml_content,
            "report_download_url": "/download-report",
            "bpmn_download_url": "/download-optimized-bpmn"
        })

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/prompt-to-workflow")
async def prompt_to_workflow(req: PromptWorkflowRequest):
    """Understands natural language prompt, generates BPMN 2.0 XML,
    and automatically feeds it directly into the analysis & optimization pipeline."""
    try:
        xml_content = ProcessNLPGenerator.generate_bpmn_xml(req.prompt)

        # 1. Parse generated BPMN XML
        parsed = BPMNParser.parse(xml_content)
        if not parsed['tasks']:
            raise ValueError("No activities could be parsed from the generated workflow.")

        # 2. Workflow Modeling
        wf = WorkflowGraph(parsed)

        # 3-9. Petri-Net Conversion, Verification, Simulation & Iterative Optimization
        optimizer = IterativeOptimizer(wf, base_resources=req.workers, max_iterations=req.max_iterations)
        result = optimizer.run()

        # 10. Generate publication-quality Comparative PDF Report
        build_comparative_pdf_report(result, str(PDF_PATH))

        # Save optimized BPMN file
        with open(OPTIMIZED_BPMN_PATH, "w", encoding="utf-8") as f:
            f.write(result['optimized_bpmn_xml'])

        return JSONResponse(content={
            "status": "success",
            "filename": "ai_generated_workflow.bpmn",
            "prompt_source": req.prompt,
            "baseline_metrics": result['baseline_metrics'],
            "optimized_metrics": result['optimized_metrics'],
            "baseline_schedule": result['baseline_schedule'],
            "optimized_schedule": result['optimized_schedule'],
            "iteration_history": result['iteration_history'],
            "problems_identified": result['problems_identified'],
            "overall_improvement_pct": result['overall_improvement_pct'],
            "total_iterations": result['total_iterations'],
            "best_iteration": result['best_iteration'],
            "best_strategy": result['best_strategy'],
            "optimized_bpmn_xml": result['optimized_bpmn_xml'],
            "initial_bpmn_xml": xml_content,
            "report_download_url": "/download-report",
            "bpmn_download_url": "/download-optimized-bpmn"
        })

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-xml-only")
async def generate_xml_only(req: PromptWorkflowRequest):
    """Generates only the BPMN 2.0 XML from natural language prompt."""
    try:
        xml = ProcessNLPGenerator.generate_bpmn_xml(req.prompt)
        return JSONResponse(content={"status": "success", "xml": xml})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/view-report")
async def view_report():
    """Serves the generated comparative PDF report for inline viewing."""
    if not PDF_PATH.exists():
        raise HTTPException(status_code=404, detail="No report has been generated yet.")
    return FileResponse(
        path=str(PDF_PATH),
        filename="bpmn_workflow_analysis_report.pdf",
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline; filename=bpmn_workflow_analysis_report.pdf",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@app.get("/download-report")
async def download_report():
    """Serves the generated comparative PDF report."""
    if not PDF_PATH.exists():
        raise HTTPException(status_code=404, detail="No report has been generated yet.")
    return FileResponse(
        path=str(PDF_PATH),
        filename="bpmn_workflow_analysis_report.pdf",
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=bpmn_workflow_analysis_report.pdf",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@app.get("/download-optimized-bpmn")
async def download_optimized_bpmn():
    """Serves the generated optimized BPMN 2.0 XML."""
    if not OPTIMIZED_BPMN_PATH.exists():
        raise HTTPException(status_code=404, detail="No optimized BPMN has been generated yet.")
    return FileResponse(
        path=str(OPTIMIZED_BPMN_PATH),
        filename="optimized_workflow.bpmn",
        media_type="application/xml",
        headers={
            "Content-Disposition": "attachment; filename=optimized_workflow.bpmn",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
