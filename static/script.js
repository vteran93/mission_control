// script.js - Mission Control Frontend Logic (Enhanced with Drag & Drop + Task Modal + Sprint Filter)
console.log('🚀 Mission Control JS loaded at:', new Date().toISOString());
const API_BASE = '/api';
let refreshInterval;
let countdown = 5;
let currentTaskId = null; // For modal
let currentSprintFilter = ''; // For sprint filtering
let allTasks = []; // Cache all tasks

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
        
    } catch (error) {
        console.error('❌ Error fetching dashboard:', error);
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
