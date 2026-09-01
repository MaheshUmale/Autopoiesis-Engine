"""Global Real-Time Web Dashboard UI for Autopoiesis Engine."""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autopoiesis Engine - Global Agent Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
    <style>
        :root {
            --bs-body-bg: #0f172a;
            --bs-body-color: #f8fafc;
            --card-bg: #1e293b;
            --card-border: #334155;
            --accent-cyan: #38bdf8;
            --accent-green: #4ade80;
            --accent-purple: #c084fc;
        }
        body {
            background-color: var(--bs-body-bg);
            color: var(--bs-body-color);
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        }
        .navbar-brand {
            font-weight: 700;
            letter-spacing: 0.5px;
            color: var(--accent-cyan) !important;
        }
        .stat-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 1.25rem;
            transition: transform 0.2s;
        }
        .stat-card:hover {
            transform: translateY(-2px);
        }
        .agent-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.2s ease-in-out;
        }
        .agent-card:hover {
            border-color: var(--accent-cyan);
            box-shadow: 0 4px 20px rgba(56, 189, 248, 0.15);
        }
        .badge-core { background-color: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid #0284c7; }
        .badge-variant { background-color: rgba(192, 132, 252, 0.2); color: #c084fc; border: 1px solid #9333ea; }
        .badge-template { background-color: rgba(74, 222, 128, 0.2); color: #4ade80; border: 1px solid #16a34a; }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
        }
        .status-dot.active { background-color: #4ade80; box-shadow: 0 0 8px #4ade80; }
        .status-dot.idle { background-color: #94a3b8; }
        .log-terminal {
            background-color: #020617;
            color: #38bdf8;
            font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
            font-size: 0.875rem;
            padding: 1rem;
            border-radius: 8px;
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid var(--card-border);
            white-space: pre-wrap;
        }
        .search-box {
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            color: white;
        }
        .search-box:focus {
            background-color: var(--card-bg);
            border-color: var(--accent-cyan);
            color: white;
            box-shadow: none;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-slate-900 border-bottom border-slate-800 py-3 mb-4" style="background-color: #020617;">
        <div class="container-fluid px-4">
            <a class="navbar-brand d-flex align-items-center gap-2" href="#">
                <i class="bi bi-cpu-fill fs-4"></i>
                AUTOPOIESIS ENGINE — GLOBAL AGENT DASHBOARD
            </a>
            <div class="d-flex align-items-center gap-3">
                <span class="badge bg-success-subtle text-success border border-success px-3 py-2">
                    <span class="status-dot active"></span> DAEMON ONLINE
                </span>
                <button class="btn btn-outline-info btn-sm" onclick="fetchDashboardData()">
                    <i class="bi bi-arrow-clockwise me-1"></i> Refresh Now
                </button>
            </div>
        </div>
    </nav>

    <div class="container-fluid px-4 mb-5">
        <!-- System Summary Cards -->
        <div class="row g-3 mb-4">
            <div class="col-md-2">
                <div class="stat-card">
                    <div class="text-secondary small fw-semibold text-uppercase">Total Active Agents</div>
                    <div class="fs-2 fw-bold text-info mt-1" id="stat-total-agents">0</div>
                    <div class="text-secondary small mt-1">Level 1, Level 2 & Macro Templates</div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="stat-card">
                    <div class="text-secondary small fw-semibold text-uppercase">Level 1 Core Base Pack</div>
                    <div class="fs-2 fw-bold text-success mt-1" id="stat-core-agents">0</div>
                    <div class="text-secondary small mt-1">Native OS & File Primitives</div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="stat-card">
                    <div class="text-secondary small fw-semibold text-uppercase">Synthesized Variants</div>
                    <div class="fs-2 fw-bold text-purple mt-1" style="color: #c084fc;" id="stat-variant-agents">0</div>
                    <div class="text-secondary small mt-1">Domain-Specific Auto Skills</div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="stat-card">
                    <div class="text-secondary small fw-semibold text-uppercase">Total Execution Runs</div>
                    <div class="fs-2 fw-bold text-warning mt-1" id="stat-execution-runs">0</div>
                    <div class="text-secondary small mt-1">Traces Recorded in .autopoiesis/</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="text-secondary small fw-semibold text-uppercase">Active Agent Sessions</div>
                    <div class="fs-2 fw-bold text-success mt-1" id="stat-active-sessions">0</div>
                    <div class="text-secondary small mt-1">
                        <span class="status-dot active"></span><span id="stat-active-count">0</span> active |
                        <span class="status-dot idle"></span><span id="stat-idle-count">0</span> idle |
                        <span class="status-dot" style="background:#f59e0b" id="stat-stale-count">0</span> stale
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="text-secondary small fw-semibold text-uppercase">Session Memory</div>
                    <div class="fs-2 fw-bold text-info mt-1" id="stat-total-memory">0</div>
                    <div class="text-secondary small mt-1" id="stat-memory-detail">Total keys stored across sessions</div>
                </div>
            </div>
        </div>

        <!-- Active Sessions Section -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card bg-slate-800 border-slate-700">
                    <div class="card-header border-slate-700 d-flex justify-content-between align-items-center">
                        <h5 class="mb-0 text-light"><i class="bi bi-people-fill text-success me-2"></i>Active Agent Sessions</h5>
                        <span class="badge bg-success-subtle text-success">Live</span>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-dark table-hover table-sm mb-0">
                                <thead>
                                    <tr>
                                        <th>Session ID</th>
                                        <th>Agent ID</th>
                                        <th>Namespace</th>
                                        <th>Status</th>
                                        <th>Invocations</th>
                                        <th>Last Active</th>
                                        <th>Memory Keys</th>
                                        <th>Tags</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="sessions-table-body">
                                    <tr><td colspan="9" class="text-center text-secondary">Loading active sessions...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Filter & Search Bar -->
        <div class="row mb-4 align-items-center">
            <div class="col-md-6">
                <div class="input-group">
                    <span class="input-group-text bg-slate-800 border-secondary text-secondary"><i class="bi bi-search"></i></span>
                    <input type="text" id="agent-search" class="form-control search-box" placeholder="Search agents by ID, description, or namespace..." oninput="filterAgents()">
                </div>
            </div>
            <div class="col-md-6 text-end text-secondary small">
                Live Auto-polling every 2s | Storage: <code class="text-info">.autopoiesis/traces/</code>
            </div>
        </div>

        <!-- Agent Cards Grid -->
        <div class="row g-4" id="agent-grid">
            <!-- Dynamically populated -->
        </div>
    </div>

    <!-- Agent Log Modal -->
    <div class="modal fade" id="logModal" tabindex="-1" aria-labelledby="logModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-xl modal-dialog-centered">
            <div class="modal-content bg-slate-900 border-slate-700" style="background-color: #0f172a; border-color: #334155;">
                <div class="modal-header border-slate-800">
                    <h5 class="modal-title d-flex align-items-center gap-2" id="logModalLabel">
                        <i class="bi bi-terminal-fill text-info"></i>
                        <span id="modal-agent-id">Agent Logs</span>
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3 d-flex justify-content-between align-items-center">
                        <div>
                            <span class="badge badge-core me-2" id="modal-agent-namespace">global</span>
                            <span class="text-secondary small" id="modal-agent-path">path/to/skill.py</span>
                        </div>
                        <button class="btn btn-sm btn-outline-secondary" onclick="reloadAgentLogs()">
                            <i class="bi bi-arrow-clockwise me-1"></i> Refresh Logs
                        </button>
                    </div>
                    <div class="log-terminal" id="modal-log-terminal">Loading logs...</div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/bootstrap.bundle.min.js"></script>
    <script>
        let allAgents = [];
        let currentModalAgentId = null;

        async function fetchDashboardData() {
            try {
                // Fetch agents data
                const agentsRes = await fetch('/api/dashboard/agents');
                const agentsData = await agentsRes.json();

                allAgents = agentsData.agents || [];

                document.getElementById('stat-total-agents').innerText = agentsData.stats.total || 0;
                document.getElementById('stat-core-agents').innerText = agentsData.stats.core || 0;
                document.getElementById('stat-variant-agents').innerText = agentsData.stats.variant || 0;
                document.getElementById('stat-execution-runs').innerText = agentsData.stats.execution_runs || 0;

                filterAgents();

                // Fetch sessions data
                const sessionsRes = await fetch('/api/dashboard/sessions');
                const sessionsData = await sessionsRes.json();

                document.getElementById('stat-active-sessions').innerText = sessionsData.stats.total || 0;
                document.getElementById('stat-active-count').innerText = sessionsData.stats.active || 0;
                document.getElementById('stat-idle-count').innerText = sessionsData.stats.idle || 0;
                document.getElementById('stat-stale-count').innerText = sessionsData.stats.stale || 0;

                const totalMemoryKeys = sessionsData.sessions.reduce((sum, s) => sum + (s.memory_keys?.length || 0), 0);
                document.getElementById('stat-total-memory').innerText = totalMemoryKeys;
                document.getElementById('stat-memory-detail').innerText = `${totalMemoryKeys} keys across ${sessionsData.sessions.length} sessions`;

                renderSessionsTable(sessionsData.sessions || []);
            } catch (err) {
                console.error('Failed to fetch dashboard data:', err);
            }
        }

        function renderSessionsTable(sessions) {
            const tbody = document.getElementById('sessions-table-body');
            if (!tbody) return;

            if (sessions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" class="text-center text-secondary">No active sessions</td></tr>';
                return;
            }

            tbody.innerHTML = sessions.map(s => {
                let statusClass = 'status-dot idle';
                let statusText = 'IDLE';
                if (s.status === 'active') {
                    statusClass = 'status-dot active';
                    statusText = 'ACTIVE';
                } else if (s.status === 'stale') {
                    statusClass = 'status-dot';
                    statusText = 'STALE';
                }

                const lastActive = s.last_active_at ? new Date(s.last_active_at).toLocaleString() : 'N/A';
                const memoryKeys = s.memory_keys?.join(', ') || '—';
                const tags = s.tags?.join(', ') || '—';
                const invocations = s.total_invocations || 0;

                return `
                    <tr>
                        <td><code class="text-info small">${s.session_id}</code></td>
                        <td><strong class="text-light">${s.agent_id}</strong></td>
                        <td><span class="badge bg-secondary">${s.namespace}</span></td>
                        <td><span class="${statusClass} me-1"></span><span class="small fw-semibold">${statusText}</span></td>
                        <td><span class="text-info">${invocations}</span></td>
                        <td class="text-secondary small">${lastActive}</td>
                        <td class="text-secondary small">${memoryKeys}</td>
                        <td class="text-secondary small">${tags}</td>
                        <td>
                            <button class="btn btn-outline-info btn-sm" onclick="openSessionDetail('${s.session_id}')">
                                <i class="bi bi-eye"></i>
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');
        }

        async function openSessionDetail(sessionId) {
            try {
                const res = await fetch('/api/dashboard/sessions');
                const data = await res.json();
                const session = (data.sessions || []).find(s => s.session_id === sessionId);
                if (!session) return;

                let details = `[SESSION DETAIL: ${sessionId}]\n`;
                details += `Agent ID: ${session.agent_id}\n`;
                details += `Namespace: ${session.namespace}\n`;
                details += `Created: ${session.created_at}\n`;
                details += `Last Active: ${session.last_active_at}\n`;
                details += `Status: ${session.status}\n`;
                details += `Idle: ${session.idle_seconds ? Math.round(session.idle_seconds) + 's' : 'N/A'}\n`;
                details += `Invocations: ${session.total_invocations}\n`;
                details += `Tags: ${session.tags?.join(', ') || '—'}\n`;
                details += `Memory Keys: ${session.memory_keys?.join(', ') || '—'}\n`;
                details += `Context: ${JSON.stringify(session.context, null, 2)}\n\n`;
                details += `RECENT HISTORY:\n`;

                if (session.recent_history?.length > 0) {
                    session.recent_history.forEach(h => {
                        details += `[${h.timestamp}] ${h.tool} -> ${h.success ? 'OK' : 'FAIL'}\n`;
                        if (h.error) details += `  Error: ${h.error}\n`;
                    });
                } else {
                    details += '(no recent history)';
                }

                alert(details);
            } catch (err) {
                alert('Failed to load session detail: ' + err);
            }
        }

        function filterAgents() {
            const query = document.getElementById('agent-search').value.toLowerCase();
            const grid = document.getElementById('agent-grid');
            grid.innerHTML = '';

            const filtered = allAgents.filter(a =>
                a.id.toLowerCase().includes(query) ||
                a.description.toLowerCase().includes(query) ||
                a.namespace.toLowerCase().includes(query)
            );

            if (filtered.length === 0) {
                grid.innerHTML = `<div class="col-12 text-center py-5 text-secondary"><i class="bi bi-inbox fs-1 d-block mb-2"></i>No matching agents found.</div>`;
                return;
            }

            filtered.forEach(agent => {
                const badgeClass = agent.scope_level === 'core' ? 'badge-core' : (agent.scope_level === 'template' ? 'badge-template' : 'badge-variant');
                const runsCount = agent.execution_count || 0;
                const statusHtml = runsCount > 0 ? `<span class="status-dot active"></span> <span class="text-success small fw-semibold">EXECUTED (${runsCount})</span>` : `<span class="status-dot idle"></span> <span class="text-secondary small">READY</span>`;

                const cardHtml = `
                    <div class="col-md-4 col-lg-3">
                        <div class="agent-card p-3">
                            <div>
                                <div class="d-flex justify-content-between align-items-start mb-2">
                                    <span class="badge ${badgeClass} px-2 py-1 text-uppercase">${agent.scope_level}</span>
                                    <div>${statusHtml}</div>
                                </div>
                                <h6 class="fw-bold text-light mb-1 text-truncate" title="${agent.id}">
                                    <i class="bi bi-robot me-1 text-info"></i> ${agent.id}
                                </h6>
                                <p class="text-secondary small mb-3 text-truncate-2" style="display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; height: 38px;">
                                    ${agent.description || 'No description provided.'}
                                </p>
                            </div>
                            <div>
                                <div class="d-flex justify-content-between text-secondary small pt-2 border-top border-slate-700 mb-3">
                                    <span>Namespace: <strong class="text-light">${agent.namespace}</strong></span>
                                    <span>Runs: <strong class="text-info">${runsCount}</strong></span>
                                </div>
                                <button class="btn btn-outline-info btn-sm w-100 d-flex align-items-center justify-content-center gap-1" onclick="openAgentLogs('${agent.id}', '${agent.namespace}', '${agent.file_path || ''}')">
                                    <i class="bi bi-file-earmark-text"></i> View Agent Logs
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                grid.innerHTML += cardHtml;
            });
        }

        async function openAgentLogs(agentId, namespace, filePath) {
            currentModalAgentId = agentId;
            document.getElementById('modal-agent-id').innerText = `Agent Logs: ${agentId}`;
            document.getElementById('modal-agent-namespace').innerText = namespace;
            document.getElementById('modal-agent-path').innerText = filePath || 'In-Memory / Dynamic';
            document.getElementById('modal-log-terminal').innerText = 'Fetching execution logs & trace snapshots...';

            const modal = new bootstrap.Modal(document.getElementById('logModal'));
            modal.show();

            await reloadAgentLogs();
        }

        async function reloadAgentLogs() {
            if (!currentModalAgentId) return;
            try {
                const res = await fetch(`/api/dashboard/logs/${encodeURIComponent(currentModalAgentId)}`);
                const data = await res.json();

                const term = document.getElementById('modal-log-terminal');
                if (data.logs && data.logs.length > 0) {
                    term.innerText = data.logs.join('\\n\\n' + '-'.repeat(60) + '\\n\\n');
                } else {
                    term.innerText = `[AUTOPOIESIS AGENT LOGS: ${currentModalAgentId}]\\n` +
                                     `Status: READY / WAITING FOR INVOCATION\\n` +
                                     `Registered Namespace: ${data.namespace || 'global'}\\n` +
                                     `AST Hash: ${data.ast_hash || 'N/A'}\\n` +
                                     `No execution traces recorded yet.`;
                }
            } catch (err) {
                document.getElementById('modal-log-terminal').innerText = 'Failed to load logs: ' + err;
            }
        }

        // Live auto-refresh every 2 seconds
        fetchDashboardData();
        setInterval(fetchDashboardData, 2000);
    </script>
</body>
</html>
"""
