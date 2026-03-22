from app import create_app
from db_bootstrap import initialize_database


def init_database() -> None:
    app = create_app()
    initialize_database(app)
    print("✅ Base de datos lista.")
    print(f"   URI: {app.config['SQLALCHEMY_DATABASE_URI']}")


if __name__ == "__main__":
    init_database()
