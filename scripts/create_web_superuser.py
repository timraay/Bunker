import asyncio

from bunker.db import session_factory, create_tables
from bunker.web.schemas import WebUserCreateParams
from bunker.web.scopes import Scopes
from bunker.web.security import create_user

async def main(username: str = None, password: str = None):
    username = username or input("Username: ")
    password = password or input("Password: ")

    await create_tables()
    async with session_factory.begin() as db:
        await create_user(db, WebUserCreateParams(
            username=username,
            password=password,
            scopes=Scopes.all()
        ))
    
    print("\nSuperuser created!")


if __name__ == "__main__":
    asyncio.run(main())