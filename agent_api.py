# agent_api.py - Helper para que los agentes (Jarvis) interactúen con Mission Control
import requests
from datetime import datetime
from typing import Optional

class MissionControlAPI:
    """Cliente Python para que agentes escriban a Mission Control"""
    
    def __init__(self, agent_name: str, base_url: str = "http://localhost:5001/api"):
        self.agent_name = agent_name
        self.base_url = base_url
        self.agent_id = self._get_or_create_agent()
    
    def _get_or_create_agent(self) -> int:
        """Obtiene ID del agente o lo crea"""
        # Get agents
        response = requests.get(f"{self.base_url}/agents")
        agents = response.json()
        
        for agent in agents:
            if agent['name'] == self.agent_name:
                return agent['id']
        
        # Agent doesn't exist, create it
        response = requests.post(f"{self.base_url}/agents", json={
            'name': self.agent_name,
            'role': 'dev' if 'Dev' in self.agent_name else 'qa',
            'status': 'idle'
        })
        return response.json()['id']
    
    def update_status(self, status: str):
        """Actualizar estado del agente: idle, working, blocked, offline"""
        requests.put(f"{self.base_url}/agents/{self.agent_id}", json={
            'status': status,
            'last_seen_at': True
        })
        print(f"✅ {self.agent_name} status → {status}")
    
    def create_task(self, title: str, description: str = "", priority: str = "medium", 
                    status: str = "todo", assignee_agent_ids: str = "") -> int:
        """Crear nueva tarea"""
        response = requests.post(f"{self.base_url}/tasks", json={
            'title': title,
            'description': description,
            'status': status,
            'priority': priority,
            'assignee_agent_ids': assignee_agent_ids or str(self.agent_id),
            'created_by': self.agent_name
        })
        task_id = response.json()['id']
        print(f"✅ Task #{task_id} creada: {title}")
        return task_id
    
    def update_task(self, task_id: int, status: Optional[str] = None, 
                    assignee: Optional[str] = None, priority: Optional[str] = None):
        """Actualizar tarea existente"""
        data = {}
        if status:
            data['status'] = status
        if assignee:
            data['assignee_agent_ids'] = assignee
        if priority:
            data['priority'] = priority
        
        requests.put(f"{self.base_url}/tasks/{task_id}", json=data)
        print(f"✅ Task #{task_id} actualizada: {data}")
    
    def send_message(self, content: str, task_id: Optional[int] = None):
        """Enviar mensaje (asociado a una tarea o general)"""
        requests.post(f"{self.base_url}/messages", json={
            'task_id': task_id,
            'from_agent': self.agent_name,
            'content': content
        })
        print(f"💬 {self.agent_name}: {content[:50]}...")
    
    def create_document(self, title: str, content_md: str, doc_type: str = "code", 
                       task_id: Optional[int] = None):
        """Crear documento/artefacto"""
        response = requests.post(f"{self.base_url}/documents", json={
            'title': title,
            'content_md': content_md,
            'type': doc_type,
            'task_id': task_id
        })
        doc_id = response.json()['id']
        print(f"📄 Documento #{doc_id} creado: {title}")
        return doc_id
    
    def notify_scrum_master(self, message: str):
        """Enviar notificación al Scrum Master (Victor)"""
        requests.post(f"{self.base_url}/notifications", json={
            'agent_id': None,  # None = para Scrum Master
            'content': f"[{self.agent_name}] {message}"
        })
        print(f"🔔 Notificación enviada: {message}")
    
    def send_message_to_agent(self, target_agent: str, message: str, task_id: Optional[int] = None):
        """
        Enviar mensaje a otro agente (via Clawdbot sessions_send)
        
        Args:
            target_agent: Nombre del agente destino (ej: "Jarvis-QA")
            message: Contenido del mensaje
            task_id: (Opcional) ID de la tarea relacionada
        
        Returns:
            dict con resultado de sessions_send
        """
        # Determinar el label del agente destino
        label_map = {
            'Jarvis-QA': 'jarvis-qa',
            'Jarvis-Dev': 'jarvis-dev',
            'jarvis-qa': 'jarvis-qa',
            'jarvis-dev': 'jarvis-dev'
        }
        
        label = label_map.get(target_agent, target_agent.lower())
        
        # Log en Mission Control
        self.send_message(
            content=f"📤 Enviando mensaje a {target_agent}: {message[:80]}...",
            task_id=task_id
        )
        
        # Enviar via sessions_send (esto lo ejecutará el agente que llama)
        print(f"📨 Mensaje para {target_agent} (label: {label})")
        print(f"💬 Contenido: {message}")
        print(f"\n⚠️ NOTA: Debes ejecutar este comando desde Clawdbot:")
        print(f"   sessions_send(label='{label}', message='''")
        print(f"   {message}")
        print(f"   ''')")
        
        return {
            'target_agent': target_agent,
            'label': label,
            'message': message,
            'status': 'ready_to_send'
        }


# ============================================
# EJEMPLO DE USO
# ============================================

if __name__ == "__main__":
    # Inicializar agente
    jarvis = MissionControlAPI("Jarvis-Dev")
    
    # Actualizar estado
    jarvis.update_status("working")
    
    # Crear tarea
    task_id = jarvis.create_task(
        title="TICKET-001: Pydantic Models",
        description="Implementar schemas con TDD (RED-GREEN-REFACTOR)",
        priority="critical",
        status="in_progress"
    )
    
    # Enviar mensaje sobre la tarea
    jarvis.send_message(
        content="🔴 RED: Tests escritos para DocumentaryScript. 5 tests failing como esperado.",
        task_id=task_id
    )
    
    # Crear documento (código)
    jarvis.create_document(
        title="test_documentary_script.py",
        content_md="""```python
def test_documentary_script_valid_data():
    script = DocumentaryScript(
        metadata={'title': 'Test', 'duration': 420},
        scenes=[{'order': 1, 'narration': 'Test'}]
    )
    assert script.metadata['title'] == 'Test'
```""",
        doc_type="test",
        task_id=task_id
    )
    
    # Actualizar tarea a "done"
    jarvis.update_task(task_id, status="done")
    
    # Notificar a Scrum Master
    jarvis.notify_scrum_master("✅ TICKET-001 completado con 100% coverage")
    
    # Enviar mensaje a otro agente
    jarvis.send_message_to_agent(
        target_agent="Jarvis-QA",
        message="🔔 TICKET-002 está listo para review. Ejecuta: docker-compose up --build -d",
        task_id=task_id
    )
    
    # Actualizar estado a idle
    jarvis.update_status("idle")
