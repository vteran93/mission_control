# init_db.py - Script para inicializar la base de datos
from app import app, db, Agent

def init_database():
    """Crea las tablas y datos iniciales"""
    with app.app_context():
        # Drop all existing tables (WARNING: Destructive!)
        # db.drop_all()
        
        # Create all tables
        db.create_all()
        print("✅ Tablas creadas: agents, tasks, messages, documents, notifications")
        
        # Create initial agents if they don't exist
        if Agent.query.count() == 0:
            jarvis_dev = Agent(
                name='Jarvis-Dev',
                role='dev',
                status='idle'
            )
            jarvis_qa = Agent(
                name='Jarvis-QA',
                role='qa',
                status='idle'
            )
            
            db.session.add_all([jarvis_dev, jarvis_qa])
            db.session.commit()
            print("✅ Agentes iniciales creados:")
            print("   - Jarvis-Dev (ID: 1, Role: dev)")
            print("   - Jarvis-QA (ID: 2, Role: qa)")
        else:
            print(f"ℹ️  Ya existen {Agent.query.count()} agentes en la base de datos")
        
        print("\n🚀 Base de datos lista. Inicia el servidor con: python app.py")


if __name__ == '__main__':
    init_database()
