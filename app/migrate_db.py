import asyncio
from sqlalchemy import text
from app.database import engine

async def migrate():
    async with engine.begin() as conn:
        print("Migrating Database...")
        try:
            await conn.execute(text("ALTER TABLE page ADD COLUMN assigned_team_id INTEGER REFERENCES team(id);"))
            print("Added assigned_team_id column.")
        except Exception as e:
            print(f"assigned_team_id might exist: {e}")

        try:
            await conn.execute(text("ALTER TABLE page ADD COLUMN is_global BOOLEAN DEFAULT FALSE;"))
            print("Added is_global column.")
        except Exception as e:
            print(f"is_global might exist: {e}")
            
    print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
