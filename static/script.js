// script.js - Mission Control Frontend Logic
console.log('🚀 Mission Control JS loaded at:', new Date().toISOString());
const API_BASE = 'http://localhost:5001/api';
let refreshInterval;
let countdown = 5;

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
        populateAgentSelect(data.agents);  // NEW: Popular dropdown de destinatarios
        
        document.getElementById('notif-count').textContent = data.unread_notifications;
        
        // Fetch detailed data
        fetchTasks();
        fetchNotifications();
        fetchDocuments();
        
    } catch (error) {
        console.error('❌ Error fetching dashboard:', error);
    }
}

async function fetchTasks() {
    try {
        const response = await fetch(`${API_BASE}/tasks`);
        const tasks = await response.json();
        
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
    console.log('🤖 renderAgents() llamado con:', agents);
    const container = document.getElementById('agents-list');
    console.log('📦 Container:', container);
    
    if (agents.length === 0) {
        container.innerHTML = '<div class="empty-state">No hay agentes registrados</div>';
        return;
    }
    
    container.innerHTML = agents.map(agent => `
        <div class="agent-card">
            <div class="name">🤖 ${agent.name}</div>
            <div class="role">${agent.role.toUpperCase()}</div>
            <div class="status ${agent.status}">${agent.status.toUpperCase()}</div>
            <div class="last-seen">Última vez: ${formatTime(agent.last_seen_at)}</div>
        </div>
    `).join('');
    console.log('✅ Agentes renderizados');
}

function populateAgentSelect(agents) {
    console.log('📝 populateAgentSelect() llamado con:', agents);
    const selectEl = document.getElementById('target-agents');
    
    if (!selectEl) {
        console.warn('⚠️ Select element not found');
        return;
    }
    
    // Clear existing options
    selectEl.innerHTML = '';
    
    // Add agents (exclude Victor)
    agents
        .filter(agent => agent.name !== 'Victor')
        .forEach(agent => {
            const option = document.createElement('option');
            const label = agent.name.toLowerCase().replace(' ', '-');
            option.value = label;
            option.textContent = agent.name;
            selectEl.appendChild(option);
        });
    
    // Add "TODOS" option
    const allOption = document.createElement('option');
    allOption.value = 'all';
    allOption.textContent = '📢 TODOS';
    selectEl.appendChild(allOption);
    
    console.log('✅ Agent select populated with', selectEl.options.length, 'options');
}

function renderTaskColumn(status, tasks) {
    const container = document.getElementById(`tasks-${status}`);
    
    if (tasks.length === 0) {
        container.innerHTML = '<div class="empty-state" style="padding: 10px; font-size: 0.8em;">Sin tareas</div>';
        return;
    }
    
    container.innerHTML = tasks.map(task => `
        <div class="task-card priority-${task.priority}" onclick="showTaskDetail(${task.id})">
            <div class="title">${task.title}</div>
            <div class="meta">
                Prioridad: ${task.priority} | 
                Asignado: ${task.assignee_agent_ids || 'Sin asignar'}
            </div>
        </div>
    `).join('');
}

function renderTasksSummary(summary) {
    // This data is already handled by renderTaskColumn
    console.log('Tasks summary:', summary);
}

function renderRecentMessages(messages) {
    const container = document.getElementById('messages-list');
    
    if (messages.length === 0) {
        container.innerHTML = '<div class="empty-state">No hay mensajes recientes</div>';
        return;
    }
    
    container.innerHTML = messages.map(msg => `
        <div class="message ${msg.from_agent.includes('QA') ? 'from-qa' : ''}">
            <div class="header">
                <span class="from">${msg.from_agent}</span>
                <span class="msg-id" style="color: #8b949e; font-size: 0.85em; margin-left: 8px;">#${msg.id}</span>
                <span class="timestamp">${formatTime(msg.created_at)}</span>
            </div>
            <div class="content">${msg.content}</div>
            ${msg.task_id ? `<div class="meta" style="font-size: 0.75em; color: #8b949e; margin-top: 5px;">Task #${msg.task_id}</div>` : ''}
        </div>
    `).join('');
}

function renderNotifications(notifications) {
    const container = document.getElementById('notifications-list');
    
    if (notifications.length === 0) {
        container.innerHTML = '<div class="empty-state">No hay notificaciones</div>';
        return;
    }
    
    container.innerHTML = notifications.map(notif => `
        <div class="notification ${notif.delivered ? 'delivered' : ''}">
            ${notif.content}
            <div class="time">${formatTime(notif.created_at)}</div>
        </div>
    `).join('');
}

function renderDocuments(documents) {
    const container = document.getElementById('documents-list');
    
    if (documents.length === 0) {
        container.innerHTML = '<div class="empty-state">No hay documentos generados</div>';
        return;
    }
    
    container.innerHTML = documents.map(doc => `
        <div class="document-card" onclick="showDocument(${doc.id})">
            <div class="title">📄 ${doc.title}</div>
            <div class="type">${doc.type}</div>
            <div class="meta" style="font-size: 0.7em; color: #8b949e; margin-top: 5px;">
                ${formatTime(doc.created_at)}
            </div>
        </div>
    `).join('');
}

// ============================================
// UTILS
// ============================================

function formatTime(isoString) {
    if (!isoString) return 'N/A';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Ahora';
    if (diffMins < 60) return `Hace ${diffMins}m`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `Hace ${diffHours}h`;
    const diffDays = Math.floor(diffHours / 24);
    return `Hace ${diffDays}d`;
}

function showTaskDetail(taskId) {
    alert(`Task #${taskId} - Funcionalidad en desarrollo`);
    // TODO: Modal con detalles completos
}

function showDocument(docId) {
    alert(`Document #${docId} - Funcionalidad en desarrollo`);
    // TODO: Modal con contenido markdown renderizado
}

// ============================================
// AUTO-REFRESH
// ============================================

function startAutoRefresh() {
    // Initial load
    fetchDashboard();
    
    // Countdown
    const countdownEl = document.getElementById('refresh-countdown');
    setInterval(() => {
        countdown--;
        if (countdown <= 0) {
            countdown = 5;
            fetchDashboard();
        }
        countdownEl.textContent = countdown;
    }, 1000);
}

// ============================================
// SEND MESSAGE TO AGENT
// ============================================

async function sendMessageToAgent(targetAgents, message, taskId = null) {
    const statusEl = document.getElementById('send-status');
    const submitBtn = document.querySelector('.btn-send');
    
    // Show loading
    submitBtn.disabled = true;
    submitBtn.textContent = '📤 Enviando...';
    statusEl.className = 'send-status info';
    statusEl.textContent = 'Preparando mensaje...';
    
    // Handle "all" option
    if (targetAgents.includes('all')) {
        targetAgents = ['jarvis-pm', 'jarvis-dev', 'jarvis-qa'];
    }
    
    try {
        let successCount = 0;
        let errors = [];
        
        // Send to each agent
        for (const targetAgent of targetAgents) {
            try {
                const response = await fetch(`${API_BASE}/send-agent-message`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target_agent: targetAgent,
                        message: message,
                        task_id: taskId
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    successCount++;
                } else {
                    errors.push(`${targetAgent}: ${data.error || 'Error desconocido'}`);
                }
            } catch (err) {
                errors.push(`${targetAgent}: ${err.message}`);
            }
        }
        
        // Show results
        if (successCount > 0 && errors.length === 0) {
            statusEl.className = 'send-status success';
            const agentList = targetAgents.join(', ');
            statusEl.innerHTML = `
                ✅ Mensaje enviado a <strong>${successCount}</strong> agente(s): ${agentList}<br>
                <small>Los mensajes serán entregados automáticamente en el próximo heartbeat.</small>
            `;
            
            // Clear form
            document.getElementById('send-message-form').reset();
            
            // Refresh messages
            fetchDashboard();
            
            // Hide status after 5s
            setTimeout(() => {
                statusEl.style.display = 'none';
            }, 5000);
        } else if (successCount > 0 && errors.length > 0) {
            statusEl.className = 'send-status info';
            statusEl.innerHTML = `
                ⚠️ Enviado a ${successCount} agente(s), ${errors.length} fallaron:<br>
                <small>${errors.join('<br>')}</small>
            `;
        } else {
            throw new Error(errors.join('; '));
        }
        
    } catch (error) {
        statusEl.className = 'send-status error';
        statusEl.textContent = `❌ Error: ${error.message}`;
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '📤 Enviar Mensaje';
    }
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    startAutoRefresh();
    
    // Handle send message form
    const sendForm = document.getElementById('send-message-form');
    if (sendForm) {
        sendForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const selectEl = document.getElementById('target-agents');
            const targetAgents = Array.from(selectEl.selectedOptions).map(opt => opt.value);
            const message = document.getElementById('message-content').value;
            const taskId = document.getElementById('task-id-optional').value || null;
            
            if (targetAgents.length === 0) {
                alert('Selecciona al menos un destinatario');
                return;
            }
            
            await sendMessageToAgent(targetAgents, message, taskId);
        });
    }
});

// ============================================
// DAEMON LOGS (Real-time)
// ============================================

async function refreshDaemonLogs(agentName) {
    const logsContainer = document.getElementById(`${agentName}-logs`);
    const levelFilter = document.getElementById(`${agentName}-log-level`).value;
    
    try {
        let url = `/api/daemons/${agentName}/logs?limit=50`;
        if (levelFilter) {
            url += `&level=${levelFilter}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.logs && data.logs.length > 0) {
            logsContainer.innerHTML = data.logs
                .reverse() // Show oldest first (chronological)
                .map(log => {
                    const timestamp = new Date(log.timestamp).toLocaleTimeString('es-CO', {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                    });
                    
                    return `
                        <div class="log-entry ${log.level}">
                            <span class="log-timestamp">${timestamp}</span>
                            <span class="log-level ${log.level}">${log.level}</span>
                            <span class="log-message">${escapeHtml(log.message)}</span>
                        </div>
                    `;
                })
                .join('');
            
            // Auto-scroll to bottom (latest logs)
            logsContainer.scrollTop = logsContainer.scrollHeight;
        } else {
            logsContainer.innerHTML = '<p class="loading">Sin logs recientes</p>';
        }
    } catch (error) {
        console.error(`Error loading ${agentName} logs:`, error);
        logsContainer.innerHTML = '<p class="loading" style="color: #f85149;">Error cargando logs</p>';
    }
}

// Auto-refresh daemon logs every 5 seconds
setInterval(() => {
    refreshDaemonLogs('dev');
    refreshDaemonLogs('qa');
}, 5000);

// Initial load
setTimeout(() => {
    refreshDaemonLogs('dev');
    refreshDaemonLogs('qa');
}, 500);
