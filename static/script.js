// script.js - Mission Control Frontend Logic (Enhanced with Drag & Drop + Task Modal + Sprint Filter)
console.log('🚀 Mission Control JS loaded at:', new Date().toISOString());
const API_BASE = '/api';
let refreshInterval;
let countdown = 5;
let currentTaskId = null; // For modal
let currentSprintFilter = ''; // For sprint filtering
let allTasks = []; // Cache all tasks
let currentBlueprintId = null;

// ============================================
// UTILITY FUNCTIONS
// ============================================

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function formatDate(isoString) {
    if (!isoString) return 'N/A';
    const date = new Date(isoString);
    return date.toLocaleString('es-CO', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// ============================================
// DATA FETCHING
// ============================================

async function fetchDashboard() {
    console.log('📊 fetchDashboard() llamado');
    try {
        const response = await fetch(`${API_BASE}/dashboard`);
        const data = await response.json();
        console.log('✅ Dashboard data:', data);
        
        renderAgents(data.agents);
        renderTasksSummary(data.tasks_summary);
        renderRecentMessages(data.recent_messages);
        populateAgentSelect(data.agents);
        
        document.getElementById('notif-count').textContent = data.unread_notifications;
        
        // Fetch detailed data
        await fetchSprints();
        await fetchTasks();
        fetchNotifications();
        fetchDocuments();
        fetchOperatorDashboard();
        await fetchBlueprints();
        
    } catch (error) {
        console.error('❌ Error fetching dashboard:', error);
    }
}

async function fetchOperatorDashboard() {
    try {
        const response = await fetch(`${API_BASE}/operator/dashboard`);
        const data = await response.json();
        renderOperatorDashboard(data);
    } catch (error) {
        console.error('Error fetching operator dashboard:', error);
    }
}

async function fetchBlueprints() {
    try {
        const response = await fetch(`${API_BASE}/blueprints`);
        const blueprints = await response.json();
        populateBlueprintSelect(blueprints);
        if (blueprints.length > 0) {
            const selectedId = currentBlueprintId || String(blueprints[0].id);
            currentBlueprintId = selectedId;
            const select = document.getElementById('blueprint-select');
            if (select) {
                select.value = selectedId;
            }
            fetchBlueprintDashboard(selectedId);
        } else {
            renderBlueprintDashboard(null);
        }
    } catch (error) {
        console.error('Error fetching blueprints:', error);
    }
}

async function fetchBlueprintDashboard(blueprintId) {
    if (!blueprintId) {
        renderBlueprintDashboard(null);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/blueprints/${blueprintId}/operator-dashboard`);
        const data = await response.json();
        renderBlueprintDashboard(data);
    } catch (error) {
        console.error('Error fetching blueprint dashboard:', error);
    }
}

async function fetchSprints() {
    try {
        const response = await fetch(`${API_BASE}/sprints`);
        const sprints = await response.json();
        
        const sprintSelect = document.getElementById('sprint-select');
        sprintSelect.innerHTML = '<option value="">Todos los sprints</option>';
        
        sprints.forEach(sprint => {
            const option = document.createElement('option');
            option.value = sprint.id;
            option.textContent = `${sprint.name} (${sprint.status})`;
            if (sprint.status === 'active') {
                option.selected = true;
                currentSprintFilter = sprint.id.toString();
            }
            sprintSelect.appendChild(option);
        });
        
    } catch (error) {
        console.error('Error fetching sprints:', error);
    }
}

async function fetchTasks() {
    try {
        const url = currentSprintFilter 
            ? `${API_BASE}/tasks?sprint_id=${currentSprintFilter}`
            : `${API_BASE}/tasks`;
            
        const response = await fetch(url);
        const tasks = await response.json();
        allTasks = tasks; // Cache for filtering
        
        // Group by status
        const tasksByStatus = {
            todo: [],
            in_progress: [],
            review: [],
            done: [],
            blocked: []
        };
        
        tasks.forEach(task => {
            if (tasksByStatus[task.status]) {
                tasksByStatus[task.status].push(task);
            }
        });
        
        Object.keys(tasksByStatus).forEach(status => {
            renderTaskColumn(status, tasksByStatus[status]);
        });
        
    } catch (error) {
        console.error('Error fetching tasks:', error);
    }
}

async function fetchNotifications() {
    try {
        const response = await fetch(`${API_BASE}/notifications`);
        const notifications = await response.json();
        renderNotifications(notifications);
    } catch (error) {
        console.error('Error fetching notifications:', error);
    }
}

async function fetchDocuments() {
    try {
        const response = await fetch(`${API_BASE}/documents`);
        const documents = await response.json();
        renderDocuments(documents);
    } catch (error) {
        console.error('Error fetching documents:', error);
    }
}

// ============================================
// RENDERING
// ============================================

function renderAgents(agents) {
    const container = document.getElementById('agents-list');
    container.innerHTML = agents.map(agent => `
        <div class="agent-card status-${agent.status}">
            <div class="agent-name">${escapeHtml(agent.name)}</div>
            <div class="agent-role">${escapeHtml(agent.role)}</div>
            <div class="agent-status">${getStatusEmoji(agent.status)} ${agent.status}</div>
        </div>
    `).join('');
}

function getStatusEmoji(status) {
    const emojiMap = {
        'idle': '😴',
        'working': '⚡',
        'blocked': '🚫',
        'offline': '💤'
    };
    return emojiMap[status] || '❓';
}

function renderTasksSummary(summary) {
    // This is already handled by renderTaskColumn
}

function renderTaskColumn(status, tasks) {
    const container = document.getElementById(`tasks-${status}`);
    if (!container) return;
    
    container.innerHTML = tasks.map(task => createTaskCard(task)).join('');
    
    // Enable drag & drop
    tasks.forEach(task => {
        const taskElement = document.getElementById(`task-${task.id}`);
        if (taskElement) {
            taskElement.draggable = true;
            taskElement.addEventListener('dragstart', handleDragStart);
            taskElement.addEventListener('dragend', handleDragEnd);
            taskElement.addEventListener('click', (e) => {
                if (!e.target.closest('.task-card').classList.contains('dragging')) {
                    openTaskModal(task.id);
                }
            });
        }
    });
    
    // Enable drop zones
    container.addEventListener('dragover', handleDragOver);
    container.addEventListener('drop', handleDrop);
    container.addEventListener('dragleave', handleDragLeave);
}

function createTaskCard(task) {
    const priorityColors = {
        'low': '#3fb950',
        'medium': '#d29922',
        'high': '#f85149',
        'critical': '#dc2626'
    };
    
    const priorityEmojis = {
        'low': '🟢',
        'medium': '🟡',
        'high': '🟠',
        'critical': '🔴'
    };
    
    return `
        <div id="task-${task.id}" 
             class="task-card priority-${task.priority}" 
             data-task-id="${task.id}"
             data-status="${task.status}"
             style="border-left: 4px solid ${priorityColors[task.priority]};">
            <div class="task-header">
                <span class="task-id">#${task.id}</span>
                <span class="task-priority">${priorityEmojis[task.priority]}</span>
            </div>
            <div class="task-title">${escapeHtml(task.title)}</div>
            ${task.assignee_agent_ids ? `<div class="task-assignee">👤 ${task.assignee_agent_ids}</div>` : ''}
            ${task.sprint_name ? `<div class="task-sprint">📅 ${task.sprint_name}</div>` : ''}
        </div>
    `;
}

function renderRecentMessages(messages) {
    const container = document.getElementById('messages-list');
    if (messages.length === 0) {
        container.innerHTML = '<p class="empty-state">No hay mensajes recientes</p>';
        return;
    }
    
    container.innerHTML = messages.map(msg => `
        <div class="message-item">
            <div class="message-header">
                <strong>${escapeHtml(msg.from_agent)}</strong>
                <span class="message-time">${formatDate(msg.created_at)}</span>
            </div>
            <div class="message-content">${escapeHtml(msg.content.substring(0, 200))}${msg.content.length > 200 ? '...' : ''}</div>
            ${msg.task_id ? `<div class="message-task">📋 Task #${msg.task_id}</div>` : ''}
        </div>
    `).join('');
}

function renderNotifications(notifications) {
    const container = document.getElementById('notifications-list');
    if (notifications.length === 0) {
        container.innerHTML = '<p class="empty-state">No hay notificaciones</p>';
        return;
    }
    
    container.innerHTML = notifications.map(notif => `
        <div class="notification-item ${notif.delivered ? 'read' : 'unread'}">
            <div class="notif-content">${escapeHtml(notif.content)}</div>
            <div class="notif-time">${formatDate(notif.created_at)}</div>
            ${!notif.delivered ? `<button onclick="markAsRead(${notif.id})">Marcar leído</button>` : ''}
        </div>
    `).join('');
}

function renderDocuments(documents) {
    const container = document.getElementById('documents-list');
    if (documents.length === 0) {
        container.innerHTML = '<p class="empty-state">No hay documentos generados</p>';
        return;
    }
    
    container.innerHTML = documents.map(doc => `
        <div class="document-card">
            <div class="doc-icon">${getDocIcon(doc.type)}</div>
            <div class="doc-title">${escapeHtml(doc.title)}</div>
            <div class="doc-type">${doc.type}</div>
            <div class="doc-time">${formatDate(doc.created_at)}</div>
        </div>
    `).join('');
}

function renderOperatorDashboard(data) {
    renderOperatorOverview(data.overview || {});
    renderProviderHealth(data.providers || {});
    populateOperatorSettings(data.settings || {});
    fetchGitHubTimeline();

    const runtimeState = document.getElementById('operator-runtime-state');
    if (runtimeState) {
        const applied = data.runtime_config_applied === true;
        runtimeState.textContent = applied ? 'Runtime alineado' : 'Runtime desalineado';
        runtimeState.className = `runtime-state-pill ${applied ? 'ok' : 'warn'}`;
    }
}

async function fetchGitHubTimeline() {
    try {
        const [timelineResponse, githubDashboardResponse] = await Promise.all([
            fetch(`${API_BASE}/operator/github/timeline?limit=20`),
            fetch(`${API_BASE}/operator/github/dashboard`)
        ]);
        const timeline = await timelineResponse.json();
        const githubDashboard = await githubDashboardResponse.json();
        renderGitHubTimeline(timeline.events || []);
        renderGitHubPullRequests(
            (timeline.events || []).filter(event => event.pull_request_number)
        );
        populateGitHubControls(githubDashboard);
    } catch (error) {
        console.error('Error fetching GitHub timeline:', error);
    }
}

function renderOperatorOverview(overview) {
    const container = document.getElementById('operator-overview');
    if (!container) return;

    const items = [
        ['Blueprints', overview.blueprints ?? 0],
        ['Scrum plans', overview.scrum_plans ?? 0],
        ['Sprints activas', overview.active_sprints ?? 0],
        ['Sprints bloqueadas', overview.blocked_sprints ?? 0],
        ['Agent runs', overview.agent_runs ?? 0],
        ['Artifacts', overview.artifacts ?? 0],
        ['Queued messages', overview.queued_messages ?? 0]
    ];

    container.innerHTML = items.map(([label, value]) => `
        <div class="operator-overview-card">
            <span class="operator-overview-value">${value}</span>
            <span class="operator-overview-label">${label}</span>
        </div>
    `).join('');
}

function renderProviderHealth(providers) {
    const container = document.getElementById('provider-health-grid');
    if (!container) return;

    container.innerHTML = Object.entries(providers).map(([name, provider]) => `
        <article class="provider-card ${provider.ok ? 'provider-ok' : 'provider-issue'}">
            <div class="provider-card-header">
                <strong>${escapeHtml(name)}</strong>
                <span>${provider.ok ? 'OK' : (provider.configured ? 'ISSUE' : 'PENDING')}</span>
            </div>
            <p>${escapeHtml(provider.detail || 'Sin detalle')}</p>
        </article>
    `).join('');
}

function populateOperatorSettings(settings) {
    const ollama = settings.ollama || {};
    const bedrock = settings.bedrock || {};
    const github = settings.github || {};

    const fieldMap = {
        'operator-ollama-base-url': ollama.base_url || '',
        'operator-ollama-default-model': ollama.default_model || '',
        'operator-bedrock-region': bedrock.region || '',
        'operator-bedrock-planner-model': bedrock.planner_model || '',
        'operator-bedrock-reviewer-model': bedrock.reviewer_model || '',
        'operator-github-api-url': github.api_url || '',
        'operator-github-auth-mode': github.auth_mode || 'none',
        'operator-github-repository': github.repository || '',
        'operator-github-base-branch': github.default_base_branch || '',
        'operator-github-protected-branches': (github.protected_branches || []).join(', '),
        'operator-github-approvals': github.required_approving_review_count ?? 1,
        'operator-github-app-id': github.app_id || '',
        'operator-github-installation-id': github.app_installation_id || ''
    };

    Object.entries(fieldMap).forEach(([fieldId, value]) => {
        const field = document.getElementById(fieldId);
        if (field) field.value = value;
    });

    const tokenField = document.getElementById('operator-github-token');
    if (tokenField) tokenField.value = '';
    const appKeyField = document.getElementById('operator-github-app-private-key');
    if (appKeyField) appKeyField.value = '';

    const tokenHint = document.getElementById('operator-github-token-hint');
    if (tokenHint) {
        const tokenText = github.token_configured ? 'Token configurado' : 'Token no configurado';
        const appText = github.app_private_key_configured ? 'App key configurada' : 'App key no configurada';
        tokenHint.textContent = `${tokenText} · ${appText}`;
    }
}

function populateGitHubControls(githubDashboard) {
    const authModeField = document.getElementById('operator-github-auth-mode');
    if (authModeField) {
        authModeField.value = githubDashboard.auth_mode || 'none';
    }
}

function renderGitHubTimeline(events) {
    const container = document.getElementById('github-timeline-list');
    if (!container) return;
    if (events.length === 0) {
        container.innerHTML = '<p class="empty-state">No hay eventos GitHub sincronizados</p>';
        return;
    }

    container.innerHTML = events.map(event => `
        <article class="feed-item">
            <div class="feed-item-header">
                <strong>${escapeHtml(event.event_type)}</strong>
                <span>${escapeHtml(event.status)}</span>
            </div>
            <p>${escapeHtml(event.summary || '')}</p>
            <small>${escapeHtml(event.branch_name || event.repository || '')} · ${formatDate(event.created_at)}</small>
        </article>
    `).join('');
}

function renderGitHubPullRequests(events) {
    const container = document.getElementById('github-pr-list');
    if (!container) return;
    const latestByPr = new Map();
    events.forEach(event => {
        if (!latestByPr.has(event.pull_request_number)) {
            latestByPr.set(event.pull_request_number, event);
        }
    });
    const items = Array.from(latestByPr.values());
    if (items.length === 0) {
        container.innerHTML = '<p class="empty-state">No hay pull requests sincronizados</p>';
        return;
    }
    container.innerHTML = items.map(event => {
        const payload = event.payload || {};
        const url = payload.html_url || '#';
        return `
            <article class="feed-item">
                <div class="feed-item-header">
                    <strong>PR #${event.pull_request_number}</strong>
                    <span>${escapeHtml(payload.state || 'unknown')}</span>
                </div>
                <p>${escapeHtml(payload.title || '')}</p>
                <small>${escapeHtml(payload.head_ref || '')} → ${escapeHtml(payload.base_ref || '')}</small>
                <a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Abrir PR</a>
            </article>
        `;
    }).join('');
}

function populateBlueprintSelect(blueprints) {
    const select = document.getElementById('blueprint-select');
    if (!select) return;
    if (blueprints.length === 0) {
        select.innerHTML = '<option value="">Sin blueprints</option>';
        return;
    }

    select.innerHTML = blueprints.map(blueprint => `
        <option value="${blueprint.id}">${escapeHtml(blueprint.project_name)} · #${blueprint.id}</option>
    `).join('');
}

function renderBlueprintDashboard(payload) {
    const overview = document.getElementById('blueprint-overview-grid');
    const feedbackList = document.getElementById('blueprint-feedback-list');
    const runsList = document.getElementById('blueprint-runs-list');
    const prList = document.getElementById('blueprint-pr-list');

    if (!overview || !feedbackList || !runsList || !prList) return;
    if (!payload) {
        overview.innerHTML = '<p class="empty-state">No hay blueprint seleccionado</p>';
        feedbackList.innerHTML = '';
        runsList.innerHTML = '';
        prList.innerHTML = '';
        return;
    }

    const report = payload.report || {};
    const counts = (report.counts || {});
    const delivery = (report.delivery_metrics || {});
    const items = [
        ['Requirements', counts.requirements ?? 0],
        ['Tasks', counts.delivery_tasks ?? 0],
        ['Scrum plans', counts.scrum_plans ?? 0],
        ['Agent runs', counts.agent_runs ?? 0],
        ['Artifacts', counts.artifacts ?? 0],
        ['Retry rate', delivery.retry_rate ?? 0]
    ];
    overview.innerHTML = items.map(([label, value]) => `
        <div class="operator-overview-card">
            <span class="operator-overview-value">${value}</span>
            <span class="operator-overview-label">${label}</span>
        </div>
    `).join('');

    const feedbackItems = [
        ...(payload.recent_feedback || []).map(item => ({
            title: `${item.stage_name} · ${item.status}`,
            body: item.feedback_text,
            meta: formatDate(item.created_at)
        })),
        ...(payload.retrospective_items || []).map(item => ({
            title: `${item.category} · ${item.status}`,
            body: item.summary,
            meta: formatDate(item.created_at)
        }))
    ].slice(0, 10);

    feedbackList.innerHTML = feedbackItems.length
        ? feedbackItems.map(item => `
            <article class="feed-item">
                <div class="feed-item-header">
                    <strong>${escapeHtml(item.title)}</strong>
                    <span>${escapeHtml(item.meta)}</span>
                </div>
                <p>${escapeHtml(item.body || '')}</p>
            </article>
        `).join('')
        : '<p class="empty-state">Sin feedback ni retrospective todavía</p>';

    const runItems = [
        ...(payload.recent_agent_runs || []).map(item => ({
            title: `${item.agent_name} · ${item.status}`,
            body: item.output_summary || item.input_summary || '',
            meta: formatDate(item.started_at)
        })),
        ...(payload.recent_artifacts || []).map(item => ({
            title: `${item.artifact_type} · ${item.name}`,
            body: item.uri,
            meta: formatDate(item.created_at)
        }))
    ].slice(0, 10);

    runsList.innerHTML = runItems.length
        ? runItems.map(item => `
            <article class="feed-item">
                <div class="feed-item-header">
                    <strong>${escapeHtml(item.title)}</strong>
                    <span>${escapeHtml(item.meta)}</span>
                </div>
                <p>${escapeHtml(item.body || '')}</p>
            </article>
        `).join('')
        : '<p class="empty-state">Sin runs ni artifacts todavía</p>';

    const pullRequests = payload.github?.pull_requests || [];
    prList.innerHTML = pullRequests.length
        ? pullRequests.map(pr => `
            <article class="feed-item">
                <div class="feed-item-header">
                    <strong>PR #${pr.number}</strong>
                    <span>${escapeHtml(pr.state || 'unknown')}</span>
                </div>
                <p>${escapeHtml(pr.title || '')}</p>
                <small>${escapeHtml(pr.head_ref || '')} → ${escapeHtml(pr.base_ref || '')}</small>
            </article>
        `).join('')
        : '<p class="empty-state">Este blueprint no tiene PRs sincronizados</p>';
}

function getDocIcon(type) {
    const icons = {
        'code': '💻',
        'spec': '📝',
        'test': '🧪',
        'report': '📊'
    };
    return icons[type] || '📄';
}

function populateAgentSelect(agents) {
    // Implementation for multi-send form
}

// ============================================
// DRAG & DROP HANDLERS
// ============================================

function handleDragStart(e) {
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', e.target.dataset.taskId);
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
    
    // Remove all drop-zone highlights
    document.querySelectorAll('.task-list').forEach(list => {
        list.classList.remove('drag-over');
    });
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    
    const taskList = e.currentTarget;
    taskList.classList.add('drag-over');
}

function handleDragLeave(e) {
    const taskList = e.currentTarget;
    if (!taskList.contains(e.relatedTarget)) {
        taskList.classList.remove('drag-over');
    }
}

async function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    
    const taskList = e.currentTarget;
    taskList.classList.remove('drag-over');
    
    const taskId = e.dataTransfer.getData('text/plain');
    const newStatus = taskList.dataset.status;
    
    if (!taskId || !newStatus) return;
    
    console.log(`Moving task ${taskId} to ${newStatus}`);
    
    try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (response.ok) {
            console.log('✅ Task status updated');
            fetchTasks(); // Refresh board
        } else {
            console.error('❌ Failed to update task');
            alert('Error al actualizar la tarea');
        }
    } catch (error) {
        console.error('Error updating task:', error);
        alert('Error de conexión al actualizar la tarea');
    }
}

// ============================================
// TASK MODAL
// ============================================

async function openTaskModal(taskId) {
    currentTaskId = taskId;
    
    try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}`);
        const task = await response.json();
        
        // Populate modal
        document.getElementById('modal-task-title').textContent = task.title;
        document.getElementById('modal-task-id').textContent = `#${task.id}`;
        document.getElementById('modal-task-sprint').textContent = task.sprint_name || 'Sin sprint';
        document.getElementById('modal-task-status').value = task.status;
        document.getElementById('modal-task-priority').value = task.priority;
        document.getElementById('modal-task-assignee').textContent = task.assignee_agent_ids || 'Sin asignar';
        document.getElementById('modal-task-created').textContent = formatDate(task.created_at);
        document.getElementById('modal-task-updated').textContent = formatDate(task.updated_at);
        document.getElementById('modal-task-description').innerHTML = task.description 
            ? `<pre>${escapeHtml(task.description)}</pre>` 
            : '<em>Sin descripción</em>';
        
        // Show modal
        document.getElementById('task-modal').style.display = 'flex';
        
    } catch (error) {
        console.error('Error loading task:', error);
        alert('Error al cargar el detalle de la tarea');
    }
}

function closeTaskModal() {
    document.getElementById('task-modal').style.display = 'none';
    currentTaskId = null;
}

async function updateTaskFromModal() {
    if (!currentTaskId) return;
    
    const status = document.getElementById('modal-task-status').value;
    const priority = document.getElementById('modal-task-priority').value;
    
    try {
        const response = await fetch(`${API_BASE}/tasks/${currentTaskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status, priority })
        });
        
        if (response.ok) {
            console.log('✅ Task updated from modal');
            fetchTasks(); // Refresh board
        } else {
            console.error('❌ Failed to update task');
        }
    } catch (error) {
        console.error('Error updating task:', error);
    }
}

// Close modal when clicking outside
window.addEventListener('click', (e) => {
    const modal = document.getElementById('task-modal');
    if (e.target === modal) {
        closeTaskModal();
    }
});

// ============================================
// SPRINT FILTER
// ============================================

function filterBySprint() {
    const sprintSelect = document.getElementById('sprint-select');
    currentSprintFilter = sprintSelect.value;
    fetchTasks();
}

function filterByBlueprint() {
    const blueprintSelect = document.getElementById('blueprint-select');
    currentBlueprintId = blueprintSelect.value;
    fetchBlueprintDashboard(currentBlueprintId);
}

async function syncGitHubBranches() {
    const statusDiv = document.getElementById('operator-settings-status');
    statusDiv.innerHTML = '<p class="loading">Sincronizando protected branches...</p>';
    try {
        const response = await fetch(`${API_BASE}/operator/github/sync-branches`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dry_run: false })
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || 'No se pudieron sincronizar las ramas');
        }
        statusDiv.innerHTML = `<p class="success">✅ ${payload.branch_count} ramas sincronizadas</p>`;
        fetchGitHubTimeline();
    } catch (error) {
        console.error('Error syncing protected branches:', error);
        statusDiv.innerHTML = `<p class="error">❌ ${escapeHtml(error.message)}</p>`;
    }
}

async function syncGitHubPullRequests() {
    const statusDiv = document.getElementById('operator-settings-status');
    statusDiv.innerHTML = '<p class="loading">Sincronizando pull requests...</p>';
    try {
        const response = await fetch(`${API_BASE}/operator/github/pull-requests/sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state: 'all', per_page: 20 })
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || 'No se pudieron sincronizar los pull requests');
        }
        statusDiv.innerHTML = `<p class="success">✅ ${payload.pull_request_count} pull requests sincronizados</p>`;
        fetchGitHubTimeline();
        if (currentBlueprintId) {
            fetchBlueprintDashboard(currentBlueprintId);
        }
    } catch (error) {
        console.error('Error syncing pull requests:', error);
        statusDiv.innerHTML = `<p class="error">❌ ${escapeHtml(error.message)}</p>`;
    }
}

// ============================================
// DAEMON LOGS
// ============================================

async function refreshDaemonLogs(agentName) {
    const logsContainer = document.getElementById(`${agentName}-logs`);
    const levelSelect = document.getElementById(`${agentName}-log-level`);
    const level = levelSelect.value;
    
    try {
        let url = `${API_BASE}/daemons/${agentName}/logs?limit=50`;
        if (level) {
            url += `&level=${level}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.logs.length === 0) {
            logsContainer.innerHTML = '<p class="empty-state">No hay logs disponibles</p>';
            return;
        }
        
        logsContainer.innerHTML = data.logs.map(log => `
            <div class="log-entry log-${log.level.toLowerCase()}">
                <span class="log-time">${formatDate(log.timestamp)}</span>
                <span class="log-level">[${log.level}]</span>
                <span class="log-message">${escapeHtml(log.message)}</span>
            </div>
        `).join('');
        
        // Auto-scroll to bottom
        logsContainer.scrollTop = logsContainer.scrollHeight;
        
    } catch (error) {
        console.error(`Error fetching ${agentName} logs:`, error);
        logsContainer.innerHTML = '<p class="error">❌ Error cargando logs</p>';
    }
}

// ============================================
// MESSAGE SENDING
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('send-message-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const targetSelect = document.getElementById('target-agents');
            const messageContent = document.getElementById('message-content').value;
            const taskId = document.getElementById('task-id-optional').value || null;
            
            const selectedAgents = Array.from(targetSelect.selectedOptions).map(opt => opt.value);
            
            if (selectedAgents.length === 0) {
                alert('Selecciona al menos un destinatario');
                return;
            }
            
            const statusDiv = document.getElementById('send-status');
            statusDiv.innerHTML = '<p class="loading">Enviando...</p>';
            
            try {
                for (const agent of selectedAgents) {
                    const response = await fetch(`${API_BASE}/send-agent-message`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            target_agent: agent,
                            message: messageContent,
                            task_id: taskId ? parseInt(taskId) : null
                        })
                    });
                    
                    if (!response.ok) {
                        throw new Error(`Failed to send to ${agent}`);
                    }
                }
                
                statusDiv.innerHTML = '<p class="success">✅ Mensaje(s) enviado(s) correctamente</p>';
                form.reset();
                
                setTimeout(() => {
                    statusDiv.innerHTML = '';
                }, 3000);
                
                fetchDashboard(); // Refresh
                
            } catch (error) {
                console.error('Error sending message:', error);
                statusDiv.innerHTML = '<p class="error">❌ Error al enviar mensaje</p>';
            }
        });
    }

    const operatorForm = document.getElementById('operator-settings-form');
    if (operatorForm) {
        operatorForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const statusDiv = document.getElementById('operator-settings-status');
            statusDiv.innerHTML = '<p class="loading">Guardando configuración...</p>';

            const payload = {
                ollama: {
                    base_url: document.getElementById('operator-ollama-base-url').value,
                    default_model: document.getElementById('operator-ollama-default-model').value
                },
                bedrock: {
                    region: document.getElementById('operator-bedrock-region').value,
                    planner_model: document.getElementById('operator-bedrock-planner-model').value,
                    reviewer_model: document.getElementById('operator-bedrock-reviewer-model').value
                },
                github: {
                    api_url: document.getElementById('operator-github-api-url').value,
                    repository: document.getElementById('operator-github-repository').value,
                    default_base_branch: document.getElementById('operator-github-base-branch').value,
                    protected_branches: document.getElementById('operator-github-protected-branches').value,
                    required_approving_review_count: parseInt(document.getElementById('operator-github-approvals').value || '1', 10),
                    app_id: document.getElementById('operator-github-app-id').value,
                    app_installation_id: document.getElementById('operator-github-installation-id').value,
                    token: document.getElementById('operator-github-token').value,
                    app_private_key: document.getElementById('operator-github-app-private-key').value
                }
            };

            try {
                const response = await fetch(`${API_BASE}/operator/settings`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || 'No se pudo guardar la configuración');
                }

                renderOperatorDashboard(result);
                statusDiv.innerHTML = '<p class="success">✅ Configuración actualizada</p>';
                setTimeout(() => {
                    statusDiv.innerHTML = '';
                }, 3000);
            } catch (error) {
                console.error('Error saving operator settings:', error);
                statusDiv.innerHTML = `<p class="error">❌ ${escapeHtml(error.message)}</p>`;
            }
        });
    }

    const githubBranchesBtn = document.getElementById('github-sync-branches-btn');
    if (githubBranchesBtn) {
        githubBranchesBtn.addEventListener('click', syncGitHubBranches);
    }

    const githubPrsBtn = document.getElementById('github-sync-prs-btn');
    if (githubPrsBtn) {
        githubPrsBtn.addEventListener('click', syncGitHubPullRequests);
    }

    const blueprintSelect = document.getElementById('blueprint-select');
    if (blueprintSelect) {
        blueprintSelect.addEventListener('change', filterByBlueprint);
    }
});

// ============================================
// AUTO-REFRESH
// ============================================

function startRefreshTimer() {
    countdown = 5;
    updateCountdown();
    
    refreshInterval = setInterval(() => {
        countdown--;
        updateCountdown();
        
        if (countdown <= 0) {
            fetchDashboard();
            countdown = 5;
        }
    }, 1000);
}

function updateCountdown() {
    const countdownEl = document.getElementById('refresh-countdown');
    if (countdownEl) {
        countdownEl.textContent = countdown;
    }
}

async function markAsRead(notifId) {
    try {
        await fetch(`${API_BASE}/notifications/${notifId}/mark-delivered`, {
            method: 'POST'
        });
        fetchNotifications();
    } catch (error) {
        console.error('Error marking notification:', error);
    }
}

// ============================================
// INITIALIZATION
// ============================================

console.log('🎬 Initializing Mission Control...');
fetchDashboard();
startRefreshTimer();

// Refresh daemon logs every 10 seconds
setInterval(() => {
    refreshDaemonLogs('dev');
    refreshDaemonLogs('qa');
}, 10000);

// Initial daemon logs load
setTimeout(() => {
    refreshDaemonLogs('dev');
    refreshDaemonLogs('qa');
}, 1000);

console.log('✅ Mission Control initialized');
