    let currentAnalysisData = null;
    let bpmnViewer = null;
    let progressionChart = null;

    // DOM Elements
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('bpmnFileInput');
    const dropZone = document.getElementById('dropZone');
    const selectedFileName = document.getElementById('selectedFileName');
    const workersSelect = document.getElementById('workersSelect');
    const iterationsSelect = document.getElementById('iterationsSelect');
    const btnAnalyze = document.getElementById('btnAnalyze');
    const progressSection = document.getElementById('progressSection');
    const progressBar = document.getElementById('progressBar');
    const progressStatusText = document.getElementById('progressStatusText');
    const progressPercentText = document.getElementById('progressPercentText');
    const alertMessage = document.getElementById('alertMessage');
    const resultsDashboard = document.getElementById('resultsDashboard');

    if (window.lucide) lucide.createIcons();

    document.querySelectorAll('[role="tablist"]').forEach((list) => {
      list.querySelectorAll('[role="tab"]').forEach((tab) => {
        tab.addEventListener('click', () => {
          list.querySelectorAll('[role="tab"]').forEach((item) => {
            const selected = item === tab;
            item.classList.toggle('tab-active', selected);
            item.setAttribute('aria-selected', String(selected));
            document.getElementById(item.dataset.target).hidden = !selected;
          });
          tab.dispatchEvent(new Event('tabshown'));
        });
      });
    });

    // Sample Loaders
    document.getElementById('btnLoadSample1').addEventListener('click', async () => {
      try {
        const resp = await fetch('1.xml');
        const text = await resp.text();
        const file = new File([text], '1.xml', { type: 'application/xml' });
        setFileInput(file);
      } catch (e) {
        showAlert('Could not load Sample 1: ' + e.message, 'danger');
      }
    });

    document.getElementById('btnLoadSample2').addEventListener('click', async () => {
      try {
        const resp = await fetch('2.xml');
        const text = await resp.text();
        const file = new File([text], '2.xml', { type: 'application/xml' });
        setFileInput(file);
      } catch (e) {
        showAlert('Could not load Sample 2: ' + e.message, 'danger');
      }
    });

    function setFileInput(file) {
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files = dt.files;
      selectedFileName.textContent = `Selected: ${file.name} (${(file.size/1024).toFixed(1)} KB)`;
      document.getElementById('mode-file-tab').click();
    }

    fileInput.addEventListener('change', () => {
      if (fileInput.files.length > 0) {
        setFileInput(fileInput.files[0]);
      }
    });

    // Drag and drop handling
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) {
        setFileInput(e.dataTransfer.files[0]);
      }
    });

    function showAlert(msg, type='danger') {
      const alert = document.createElement('div');
      alert.className = type === 'warning' ? 'alert alert-warning' : 'alert alert-error';
      alert.setAttribute('role', 'alert');
      alert.textContent = msg;
      alertMessage.replaceChildren(alert);
    }

    const API_BASE = 'http://localhost:8000';

    // FORM SUBMIT
    uploadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      alertMessage.innerHTML = '';
      const promptMode = document.getElementById('mode-prompt-tab').classList.contains('tab-active');
      const prompt = document.getElementById('nlpPromptInput').value.trim();
      if (promptMode && !prompt) {
        showAlert('Please describe the workflow first.', 'warning');
        return;
      }
      if (!promptMode && (!fileInput.files || fileInput.files.length === 0)) {
        showAlert('Please choose or drag a BPMN XML file first.', 'warning');
        return;
      }

      const file = promptMode ? null : fileInput.files[0];
      const workers = workersSelect.value;
      const iterations = iterationsSelect.value;

      btnAnalyze.disabled = true;
      progressSection.classList.remove('hidden');
      resultsDashboard.classList.add('hidden');

      // Animated multi-step progress feedback
      const steps = [
        { pct: 20, text: 'Stage 1: Parsing BPMN XML & Constructing Workflow Graph...', active: 'step1' },
        { pct: 45, text: 'Stage 2: Petri-Net Conversion & State-Space Exploration...', active: 'step2' },
        { pct: 70, text: 'Stage 3: Timed Discrete-Event Simulation & Bottleneck Detection...', active: 'step3' },
        { pct: 90, text: 'Stage 4: Executing Iterative Optimization Cycles...', active: 'step4' },
      ];

      let stepIndex = 0;
      const interval = setInterval(() => {
        if (stepIndex < steps.length) {
          const s = steps[stepIndex];
          progressBar.value = s.pct;
          progressPercentText.textContent = s.pct + '%';
          progressStatusText.innerHTML = `<i class="bi bi-gear-wide-connected spin me-1"></i> ${s.text}`;
          document.querySelectorAll('#step1, #step2, #step3, #step4, #step5').forEach(el => el.classList.remove('fw-bold', 'text-primary'));
          const activeEl = document.getElementById(s.active);
          if (activeEl) activeEl.classList.add('fw-bold', 'text-primary');
          stepIndex++;
        }
      }, 450);

      try {
        let resp;
        if (promptMode) {
          resp = await fetch(`${API_BASE}/prompt-to-workflow`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, workers: Number(workers), max_iterations: Number(iterations) })
          });
        } else {
          const formData = new FormData();
          formData.append('file', file);
          formData.append('workers', workers);
          formData.append('max_iterations', iterations);
          resp = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: formData });
        }

        clearInterval(interval);

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({ detail: 'Unknown error occurred.' }));
          throw new Error(errData.detail || 'Analysis request failed.');
        }

        const data = await resp.json();
        currentAnalysisData = data;

        // Complete progress
        progressBar.value = 100;
        progressPercentText.textContent = '100%';
        progressStatusText.innerHTML = '<i class="bi bi-check-circle-fill text-success me-1"></i> Analysis and Optimization Completed!';
        document.querySelectorAll('#step1, #step2, #step3, #step4, #step5').forEach(el => el.classList.add('fw-bold', 'text-success'));

        setTimeout(() => {
          renderDashboard(data);
          btnAnalyze.disabled = false;
        }, 500);

      } catch (err) {
        clearInterval(interval);
        btnAnalyze.disabled = false;
        progressSection.classList.add('hidden');
        showAlert(`Error: ${err.message}`, 'danger');
      }
    });

    // RENDER DASHBOARD
    function renderDashboard(data) {
      const b = data.baseline_metrics;
      const o = data.optimized_metrics;

      // Stats Cards
      document.getElementById('statBaselineMakespan').textContent = b.makespan + ' u';
      document.getElementById('statOptimizedMakespan').textContent = o.makespan + ' u';
      document.getElementById('badgeMakespanImprovement').textContent = `${data.overall_improvement_pct}% simulated change`;

      document.getElementById('statThroughput').textContent = o.throughput;
      document.getElementById('statThroughputNote').textContent = `Baseline: ${b.throughput} / unit`;

      document.getElementById('statUtilization').textContent = o.resource_utilization + '%';
      document.getElementById('statWaitingNote').textContent = `Avg Wait: ${o.average_waiting_time} u`;

      const verification = data.petri_net_analysis || {};
      document.getElementById('statSoundness').textContent = verification.truncated ? 'Inconclusive (limit)' :
        (verification.is_sound ? 'Checks Passed' : 'Checks Not Passed');
      document.getElementById('statStatesNote').textContent = `${verification.total_reachable_states ?? b.reachable_states} markings explored; bounded check only`;

      document.getElementById('summaryTotalIters').textContent = data.total_iterations;
      document.getElementById('summaryBestStrategy').textContent = data.best_strategy;

      // Tab 1: Metrics Table
      const metricsRows = [
        { label: 'Makespan (Total Completion Time)', base: b.makespan + ' units', opt: o.makespan + ' units', imp: `${data.overall_improvement_pct}% simulated change`, isPositive: true },
        { label: 'Throughput', base: b.throughput + ' inst/u', opt: o.throughput + ' inst/u', imp: `+${((o.throughput - b.throughput)/Math.max(b.throughput, 0.0001)*100).toFixed(1)}% Increase`, isPositive: true },
        { label: 'Resource Utilization', base: b.resource_utilization + '%', opt: o.resource_utilization + '%', imp: `${(o.resource_utilization - b.resource_utilization).toFixed(1)}% Capacity Shift`, isPositive: true },
        { label: 'Average Waiting Time', base: b.average_waiting_time + ' units', opt: o.average_waiting_time + ' units', imp: b.average_waiting_time > 0 ? `-${(((b.average_waiting_time - o.average_waiting_time)/b.average_waiting_time)*100).toFixed(1)}% Less Wait` : '0.0% Minimum', isPositive: true },
        { label: 'Time Wasted (Idle + Queue)', base: b.time_wasted + ' units', opt: o.time_wasted + ' units', imp: `-${(((b.time_wasted - o.time_wasted)/Math.max(b.time_wasted, 0.001))*100).toFixed(1)}% Waste Cut`, isPositive: true },
        { label: 'Maximum Concurrency', base: b.maximum_concurrency + ' tasks', opt: o.maximum_concurrency + ' tasks', imp: 'Structural estimate', isPositive: true },
        { label: 'Petri-Net Reachable States', base: b.reachable_states + ' markings', opt: o.reachable_states + ' markings', imp: verification.truncated ? 'Exploration truncated' : 'Exploration count', isPositive: true },
        { label: 'Deadlock States', base: b.deadlocks + ' states', opt: o.deadlocks + ' states', imp: verification.truncated ? 'Bounded check inconclusive' : (verification.is_sound ? 'No deadlocks found in explored space' : 'Bounded check did not pass'), isPositive: true },
        { label: 'Critical Bottleneck Activity', base: b.bottlenecks, opt: o.bottlenecks, imp: 'Observed candidate result', isPositive: true },
        { label: 'Synchronization Overhead', base: b.synchronization_overhead + ' units', opt: o.synchronization_overhead + ' units', imp: b.synchronization_overhead > 0 ? `-${(((b.synchronization_overhead - o.synchronization_overhead)/b.synchronization_overhead)*100).toFixed(1)}% Join Delay` : '0 Join Delay', isPositive: true },
        { label: 'Resource Conflicts / Starvation', base: b.resource_conflicts + ' events', opt: o.resource_conflicts + ' events', imp: `${o.resource_conflicts - b.resource_conflicts} Contention Events`, isPositive: o.resource_conflicts <= b.resource_conflicts }
      ];

      const tbody = document.getElementById('metricsTableBody');
      tbody.innerHTML = '';
      metricsRows.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="fw-semibold">${row.label}</td>
          <td class="text-secondary">${row.base}</td>
          <td class="fw-bold text-dark">${row.opt}</td>
          <td><span class="${row.isPositive ? 'badge-improvement' : 'badge-neutral'}">${row.imp}</span></td>
        `;
        tbody.appendChild(tr);
      });

      // Problems List
      const probContainer = document.getElementById('problemListContainer');
      probContainer.innerHTML = '';
      if (data.problems_identified && data.problems_identified.length > 0) {
        data.problems_identified.forEach(p => {
          const item = document.createElement('div');
          item.className = 'd-flex align-items-start gap-2 mb-2';
          item.innerHTML = `<i class="bi bi-arrow-right-circle-fill text-primary mt-1"></i><div>${p}</div>`;
          probContainer.appendChild(item);
        });
      } else {
        probContainer.innerHTML = '<div class="text-muted"><i class="bi bi-info-circle me-1"></i> No issues were flagged by the configured heuristics.</div>';
      }

      // Tab 3: Iteration Log Table & Chart
      const iterTbody = document.getElementById('iterationTableBody');
      iterTbody.innerHTML = '';
      const labels = [];
      const makespanPoints = [];
      const waitPoints = [];

      data.iteration_history.forEach(item => {
        labels.push(`Iter ${item.iteration}`);
        makespanPoints.push(item.makespan);
        waitPoints.push(item.waiting_time);

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="fw-bold">${item.iteration}</td>
          <td><b>${item.strategy}</b><br><small class="text-muted">${item.description}</small></td>
          <td class="fw-bold text-primary">${item.makespan} u</td>
          <td><span class="badge bg-light text-dark border">${item.status}</span></td>
        `;
        iterTbody.appendChild(tr);
      });

      renderProgressionChart(labels, makespanPoints, waitPoints);

      // Tab 4: Schedule Table
      const schedTbody = document.getElementById('scheduleTableBody');
      schedTbody.innerHTML = '';
      data.optimized_schedule.forEach(s => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="fw-bold">${s.name} <span class="text-muted small">(${s.id})</span></td>
          <td>${s.duration} u</td>
          <td>${s.ready_time} u</td>
          <td class="text-primary fw-semibold">${s.start_time} u</td>
          <td class="text-success fw-semibold">${s.finish_time} u</td>
          <td>${s.waiting_time} u</td>
          <td><span class="badge bg-secondary">${s.resource}</span></td>
        `;
        schedTbody.appendChild(tr);
      });

      // Refresh PDF preview in Tab 5
      refreshPdfPreview();

      // Show results dashboard
      resultsDashboard.classList.remove('hidden');
      resultsDashboard.scrollIntoView({ behavior: 'smooth' });

      // Render BPMN in Tab 2
      renderBpmnDiagram(data.initial_bpmn_xml, false);
    }

    // Chart.js Iteration Progression
    function renderProgressionChart(labels, makespanData, waitData) {
      const ctx = document.getElementById('progressionChart').getContext('2d');
      if (progressionChart) {
        progressionChart.destroy();
      }

      progressionChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Makespan (Execution Time)',
              data: makespanData,
              borderColor: '#1e3a8a',
              backgroundColor: 'rgba(30, 58, 138, 0.1)',
              tension: 0.3,
              fill: true,
              pointRadius: 5,
              pointBackgroundColor: '#1e3a8a',
              borderWidth: 2.5
            },
            {
              label: 'Average Waiting Time',
              data: waitData,
              borderColor: '#06b6d4',
              backgroundColor: 'transparent',
              tension: 0.3,
              borderDash: [5, 5],
              pointRadius: 4,
              pointBackgroundColor: '#06b6d4',
              borderWidth: 2
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'top' },
            tooltip: { mode: 'index', intersect: false }
          },
          scales: {
            y: {
              beginAtZero: true,
              title: { display: true, text: 'Time Units' }
            }
          }
        }
      });
    }

    // BPMN Diagram Viewer (Hybrid bpmn-js + High-Resolution SVG Fallback)
    async function renderBpmnDiagram(xml, isOptimized = false) {
      const container = document.getElementById('bpmnCanvas');
      if (!container) return;

      let renderedSuccessfully = false;

      // Attempt rendering via bpmn-js if library is loaded
      if (typeof BpmnJS !== 'undefined') {
        try {
          if (bpmnViewer) {
            try { bpmnViewer.destroy(); } catch(e) {}
            bpmnViewer = null;
          }
          container.innerHTML = '';
          bpmnViewer = new BpmnJS({ container: '#bpmnCanvas' });
          await bpmnViewer.importXML(xml);

          // Only zoom if container is currently rendered with positive dimensions
          if (container.offsetWidth > 50 && container.offsetHeight > 50) {
            const canvas = bpmnViewer.get('canvas');
            canvas.zoom('fit-viewport');
          }
          renderedSuccessfully = true;
        } catch (err) {
          console.warn('bpmn-js parsing threw an error, switching to SVG renderer:', err);
          renderedSuccessfully = false;
        }
      }

      // If bpmn-js is unavailable, CDN failed, or XML parsing had issues, render the topology-based SVG fallback.
      if (!renderedSuccessfully) {
        renderSvgBPMNDiagram(container, isOptimized);
      }
    }

      // High-Resolution SVG fallback renderer based on the submitted BPMN topology.
    function renderSvgBPMNDiagram(container, isOptimized = false) {
      container.innerHTML = '';
      if (!currentAnalysisData) return;

      const xml = isOptimized ? currentAnalysisData.optimized_bpmn_xml : currentAnalysisData.initial_bpmn_xml;
      const doc = new DOMParser().parseFromString(xml, 'application/xml');
      // BPMN XML normally uses a default namespace; filter by localName so the
      // fallback works for both namespaced and namespace-free documents.
      const supportedTypes = new Set(['task', 'userTask', 'serviceTask', 'scriptTask', 'manualTask', 'businessRuleTask', 'parallelGateway', 'exclusiveGateway', 'inclusiveGateway', 'eventBasedGateway', 'complexGateway', 'startEvent', 'endEvent', 'intermediateThrowEvent', 'intermediateCatchEvent']);
      const elements = [...doc.getElementsByTagName('*')].filter((element) => supportedTypes.has(element.localName));
      const flows = [...doc.getElementsByTagName('*')].filter((element) => element.localName === 'sequenceFlow');
      if (!elements.length) {
        container.textContent = 'Unable to render the submitted BPMN topology.';
        return;
      }
      const successors = new Map(elements.map((element) => [element.getAttribute('id'), []]));
      const incoming = new Map(elements.map((element) => [element.getAttribute('id'), 0]));
      flows.forEach((flow) => {
        const source = flow.getAttribute('sourceRef');
        const target = flow.getAttribute('targetRef');
        if (successors.has(source) && incoming.has(target)) {
          successors.get(source).push(target);
          incoming.set(target, incoming.get(target) + 1);
        }
      });
      const rank = new Map([...incoming].filter(([, count]) => count === 0).map(([id]) => [id, 0]));
      const queue = [...rank.keys()];
      while (queue.length) {
        const source = queue.shift();
        successors.get(source).forEach((target) => {
          rank.set(target, Math.max(rank.get(target) || 0, rank.get(source) + 1));
          incoming.set(target, incoming.get(target) - 1);
          if (incoming.get(target) === 0) queue.push(target);
        });
      }
      elements.forEach((element) => { if (!rank.has(element.getAttribute('id'))) rank.set(element.getAttribute('id'), 0); });
      const columns = new Map();
      elements.forEach((element) => {
        const id = element.getAttribute('id');
        if (!columns.has(rank.get(id))) columns.set(rank.get(id), []);
        columns.get(rank.get(id)).push(id);
      });
      const svgW = Math.max(860, columns.size * 180 + 80);
      const maxRows = Math.max(...[...columns.values()].map((items) => items.length));
      const svgH = Math.max(340, maxRows * 100 + 80);
      const positions = new Map();
      const maxRank = Math.max(...rank.values());
      columns.forEach((ids, column) => ids.forEach((id, index) => {
        positions.set(id, { x: 40 + (column * (svgW - 80) / Math.max(1, maxRank)), y: 40 + (index + 1) * (svgH - 60) / (ids.length + 1) });
      }));
      const schedule = new Map((isOptimized ? currentAnalysisData.optimized_schedule : currentAnalysisData.baseline_schedule).map((task) => [task.id, task]));
      const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

      let svgHtml = `
      <div style="position: absolute; top: 10px; right: 15px; z-index: 10;" class="badge bg-dark bg-opacity-75 p-2">
        <i class="bi bi-diagram-3 me-1"></i> ${isOptimized ? 'Analyzed BPMN Model' : 'Submitted BPMN Model'}
      </div>
      <svg viewBox="0 0 ${svgW} ${svgH}" width="100%" height="100%" style="display: block; background: #f8fafc;" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#475569"/>
          </marker>
          <filter id="shadow" x="-5%" y="-5%" width="115%" height="115%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.08"/>
          </filter>
        </defs>

      `;

      flows.forEach((flow) => {
        const source = positions.get(flow.getAttribute('sourceRef'));
        const target = positions.get(flow.getAttribute('targetRef'));
        if (source && target) svgHtml += `<line x1="${source.x + 30}" y1="${source.y}" x2="${target.x - 30}" y2="${target.y}" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>`;
      });
      elements.forEach((element) => {
        const id = element.getAttribute('id');
        const point = positions.get(id);
        const type = element.localName;
        const task = schedule.get(id);
        const label = esc(element.getAttribute('name') || id);
        if (type.endsWith('Event')) {
          svgHtml += `<circle cx="${point.x}" cy="${point.y}" r="22" fill="${type === 'startEvent' ? '#dcfce7' : '#fee2e2'}" stroke="${type === 'startEvent' ? '#16a34a' : '#dc2626'}" stroke-width="2.5"/><text x="${point.x}" y="${point.y + 4}" text-anchor="middle" font-size="10">${type === 'startEvent' ? 'Start' : 'End'}</text>`;
        } else if (type.endsWith('Gateway')) {
          const mark = type === 'parallelGateway' ? '+' : '×';
          svgHtml += `<polygon points="${point.x},${point.y - 25} ${point.x + 25},${point.y} ${point.x},${point.y + 25} ${point.x - 25},${point.y}" fill="#fef3c7" stroke="#d97706" stroke-width="2.5"/><text x="${point.x}" y="${point.y + 6}" text-anchor="middle" font-size="20" font-weight="bold">${mark}</text><text x="${point.x}" y="${point.y + 42}" text-anchor="middle" font-size="9">${esc(type.replace('Gateway',''))}</text>`;
        } else {
          const details = task ? `Duration: ${esc(task.duration)} units` : 'Task';
          svgHtml += `
          <g class="bpmn-node" filter="url(#shadow)" style="cursor: pointer;">
            <rect x="${point.x - 75}" y="${point.y - 34}" width="150" height="68" rx="10" fill="#fff" stroke="${isOptimized ? '#0284c7' : '#3b82f6'}" stroke-width="2"/>
            <text x="${point.x - 63}" y="${point.y - 10}" font-size="11" font-weight="bold">${label}</text>
            <text x="${point.x - 63}" y="${point.y + 14}" font-size="10" fill="#475569">${details}</text>
          </g>`;
        }
      });
      svgHtml += '</svg>';

      container.innerHTML = svgHtml;
    }

    // BPMN View Toggle (Original vs Optimized)
    document.getElementById('toggleViewInitial').addEventListener('change', () => {
      if (currentAnalysisData) {
        renderBpmnDiagram(currentAnalysisData.initial_bpmn_xml, false);
      }
    });

    document.getElementById('toggleViewOptimized').addEventListener('change', () => {
      if (currentAnalysisData) {
        renderBpmnDiagram(currentAnalysisData.optimized_bpmn_xml, true);
      }
    });

    // Redraw BPMN when switching to its tab
    document.getElementById('tab-bpmn-btn').addEventListener('tabshown', () => {
      if (currentAnalysisData) {
        const isOpt = document.getElementById('toggleViewOptimized').checked;
        const xml = isOpt ? currentAnalysisData.optimized_bpmn_xml : currentAnalysisData.initial_bpmn_xml;
        renderBpmnDiagram(xml, isOpt);
      }
    });

    // PDF Preview Loader
    let currentPdfBlobUrl = null;
    async function refreshPdfPreview() {
      const iframe = document.getElementById('pdfPreviewFrame');
      const notice = document.getElementById('pdfLoadingNotice');
      if (!iframe) return;

      if (notice) notice.classList.remove('hidden');
      iframe.classList.add('hidden');

      try {
        const resp = await fetch(`http://localhost:8000/view-report?t=` + new Date().getTime());
        if (!resp.ok) throw new Error('Fetch failed');
        const blob = await resp.blob();
        if (currentPdfBlobUrl) {
          URL.revokeObjectURL(currentPdfBlobUrl);
        }
        currentPdfBlobUrl = URL.createObjectURL(blob);
        iframe.src = currentPdfBlobUrl;
        iframe.onload = () => {
          if (notice) notice.classList.add('hidden');
          iframe.classList.remove('hidden');
        };
      } catch (err) {
        if (notice) notice.classList.add('hidden');
        iframe.classList.remove('hidden');
        iframe.src = `http://localhost:8000/view-report?t=` + new Date().getTime();
      }
    }

    // Load PDF Preview when Tab 5 is opened
    document.getElementById('tab-report-btn').addEventListener('tabshown', () => {
      refreshPdfPreview();
    });

    // Download Utilities
    async function downloadFileFromBackend(url, defaultFileName) {
      try {
        const resp = await fetch(url);
        if (!resp.ok) {
          throw new Error(`Server returned ${resp.status}: ${resp.statusText}`);
        }
        const blob = await resp.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = blobUrl;
        a.download = defaultFileName;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          window.URL.revokeObjectURL(blobUrl);
          document.body.removeChild(a);
        }, 150);
      } catch (err) {
        showAlert('Download failed: ' + err.message, 'danger');
      }
    }

    // Attach Download Handlers
    document.getElementById('btnDownloadPdf').addEventListener('click', (e) => {
      e.preventDefault();
      downloadFileFromBackend(`${API_BASE}/download-report`, 'bpmn_workflow_analysis_report.pdf');
    });

    const btnTabPdf = document.getElementById('btnTabDownloadPdf');
    if (btnTabPdf) {
      btnTabPdf.addEventListener('click', (e) => {
        e.preventDefault();
        downloadFileFromBackend(`${API_BASE}/download-report`, 'bpmn_workflow_analysis_report.pdf');
      });
    }

    document.getElementById('btnDownloadBpmn').addEventListener('click', (e) => {
      e.preventDefault();
      if (currentAnalysisData && currentAnalysisData.optimized_bpmn_xml) {
        const blob = new Blob([currentAnalysisData.optimized_bpmn_xml], { type: 'application/xml' });
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = blobUrl;
        a.download = 'optimized_workflow.bpmn';
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          window.URL.revokeObjectURL(blobUrl);
          document.body.removeChild(a);
        }, 150);
      } else {
        downloadFileFromBackend(`${API_BASE}/download-optimized-bpmn`, 'optimized_workflow.bpmn');
      }
    });

    // Redraw BPMN when switching to its tab
    document.getElementById('tab-bpmn-btn').addEventListener('tabshown', () => {
      if (bpmnViewer) {
        const canvas = bpmnViewer.get('canvas');
        canvas.zoom('fit-viewport');
      }
    });
