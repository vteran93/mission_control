// script.js - Mission Control Frontend Logic
const API_BASE = 'http://localhost:5001/api';
let refreshInterval;
let countdown = 5;

// ============================================
// DATA FETCHING
// ============================================

async function fetchDashboard() {
    try {
        const response = await fetch(`${API_BASE}/dashboard`);
        const data = await response.json();
        
        renderAgents(data.agents);
        renderTasksSummary(data.tasks_summary);
        renderRecentMessages(data.recent_messages);
        
        document.getElementById('notif-count').textContent = data.unread_notifications;
        
        // Fetch detailed data
        fetchTasks();
        fetchNotifications();
        fetchDocuments();
        
    } catch (error) {
        console.error('Error fetching dashboard:', error);
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
    const container = document.getElementById('agents-list');
    
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

async function sendMessageToAgent(targetAgent, message, taskId = null) {
    const statusEl = document.getElementById('send-status');
    const submitBtn = document.querySelector('.btn-send');
    
    // Show loading
    submitBtn.disabled = true;
    submitBtn.textContent = '📤 Enviando...';
    statusEl.className = 'send-status info';
    statusEl.textContent = 'Preparando mensaje...';
    
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
            statusEl.className = 'send-status success';
            statusEl.innerHTML = `
                ✅ Mensaje enviado a <strong>${targetAgent}</strong><br>
                <small>Registrado en Mission Control. El agente recibirá el mensaje.</small>
            `;
            
            // Clear form
            document.getElementById('send-message-form').reset();
            
            // Refresh messages
            fetchDashboard();
            
            // Hide status after 5s
            setTimeout(() => {
                statusEl.style.display = 'none';
            }, 5000);
        } else {
            throw new Error(data.error || 'Error desconocido');
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
            
            const targetAgent = document.getElementById('target-agent').value;
            const message = document.getElementById('message-content').value;
            const taskId = document.getElementById('task-id-optional').value || null;
            
            await sendMessageToAgent(targetAgent, message, taskId);
        });
    }
});
