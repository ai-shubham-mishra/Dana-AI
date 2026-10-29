import argparse
import asyncio
from datetime import datetime, timedelta, timezone

import jwt
from motor.motor_asyncio import AsyncIOMotorClient

from config.settings import get_settings


def mint_dev_token(user_id: str, org_id: str, email: str, role: str, hours: int) -> str:
    settings = get_settings()
    if settings.jwt_master_token is None:
        raise SystemExit("JWT_MASTER_TOKEN is not set in backend/.env")
    now = datetime.now(timezone.utc)
    payload = {
        "userId": user_id,
        "organizationId": org_id,
        "email": email,
        "role": role,
        "typ": "access",
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(hours=hours),
    }
    return jwt.encode(payload, settings.jwt_master_token.get_secret_value(), algorithm="HS256")


async def seed(args: argparse.Namespace) -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    db = client[settings.mongo_db]
    now = datetime.now(timezone.utc)

    await db.memberships.update_one(
        {"user_id": args.user_id, "org_id": args.org_id},
        {"$set": {"role": args.role, "status": "active"}},
        upsert=True,
    )

    if await db.chats.count_documents({"user_id": args.user_id, "org_id": args.org_id}) == 0:
        await db.chats.insert_one(
            {
                "id": "seed-chat-1",
                "title": "Welcome to Dana AI",
                "user_id": args.user_id,
                "org_id": args.org_id,
                "created_at": now,
                "updated_at": now,
            }
        )

    if await db.jobs.count_documents({"user_id": args.user_id, "org_id": args.org_id}) == 0:
        await db.jobs.insert_one(
            {
                "id": "seed-job-1",
                "title": "Sample MMM training run",
                "kind": "mmm",
                "status": "succeeded",
                "user_id": args.user_id,
                "org_id": args.org_id,
                "created_at": now,
                "updated_at": now,
            }
        )

    client.close()
    print(f"Seeded membership ({args.user_id}, {args.org_id}, role={args.role}).")
    if args.mint_token:
        print(mint_dev_token(args.user_id, args.org_id, args.email, args.role, args.hours))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a dev membership and optionally mint a dev token.")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--email", default="dev@example.com")
    parser.add_argument("--role", default="admin")
    parser.add_argument("--mint-token", action="store_true")
    parser.add_argument("--hours", type=int, default=8)
    asyncio.run(seed(parser.parse_args()))


if __name__ == "__main__":
    main()
