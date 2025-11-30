from sqlalchemy import create_engine
from config.settings import settings
from apps.auth.infrastructure.db.models import AuthBase

engine = create_engine(settings.mysql_dsn, future=True)
AuthBase.metadata.create_all(engine)
print("Táblák létrehozva (auth).")
