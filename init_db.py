from app import create_app, init_db


def init_database() -> None:
    app = create_app()
    init_db(app)
    print("✅ Base de datos lista.")
    print(f"   URI: {app.config['SQLALCHEMY_DATABASE_URI']}")


if __name__ == "__main__":
    init_database()
