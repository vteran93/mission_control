#!/usr/bin/env python3
"""
send_agent_message.py - Helper para enviar mensajes entre agentes

Uso:
    python3 send_agent_message.py --to Jarvis-QA --message "Revisa TICKET-002"
    python3 send_agent_message.py --to jarvis-dev --message "Buena work!" --task 2
"""

import argparse
import sys
from agent_api import MissionControlAPI

def main():
    parser = argparse.ArgumentParser(description='Enviar mensaje a un agente via Clawdbot')
    parser.add_argument('--from', dest='from_agent', default='Victor', help='Tu nombre (default: Victor)')
    parser.add_argument('--to', required=True, help='Agente destino (Jarvis-QA, Jarvis-Dev, etc.)')
    parser.add_argument('--message', '-m', required=True, help='Contenido del mensaje')
    parser.add_argument('--task', '-t', type=int, help='ID de tarea relacionada (opcional)')
    
    args = parser.parse_args()
    
    # Inicializar API
    api = MissionControlAPI(args.from_agent)
    
    # Enviar mensaje
    result = api.send_message_to_agent(
        target_agent=args.to,
        message=args.message,
        task_id=args.task
    )
    
    print("\n✅ Mensaje preparado para envío")
    print(f"   Target: {result['target_agent']} (label: {result['label']})")
    print(f"   Status: {result['status']}")
    print("\n📋 Ahora copia este comando en Clawdbot (chat principal):")
    print(f"\n   sessions_send(label='{result['label']}', message='''{args.message}''')\n")

if __name__ == "__main__":
    main()
