#!/usr/bin/env python3
"""Create admin user for initial setup.

Usage: python scripts/create_admin.py
"""

import asyncio
import getpass
import sys

sys.path.insert(0, "apps/backend")

from app.config import settings
from app.core.security import hash_password, generate_totp_secret, get_totp_provisioning_uri
from app.database.session import async_session_factory, engine
from app.database.base import Base
from app.models.user import User


async def create_admin() -> None:
    """Interactive admin user creation."""
    print("=" * 50)
    print("ACTA — Create Admin User")
    print("=" * 50)
    print()

    email = input("Email [admin@acta.local]: ").strip() or "admin@acta.local"

    while True:
        password = getpass.getpass("Password (min 12 chars): ")
        if len(password) < 12:
            print("Password must be at least 12 characters.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            continue
        break

    setup_mfa = input("Enable MFA (2FA)? [Y/n]: ").strip().lower() != "n"

    async with async_session_factory() as session:
        # Check if user already exists
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"\n⚠️  User '{email}' already exists!")
            overwrite = input("Overwrite? [y/N]: ").strip().lower() == "y"
            if not overwrite:
                print("Aborted.")
                return
            await session.delete(existing)
            await session.commit()

        mfa_secret = None
        if setup_mfa:
            mfa_secret = generate_totp_secret()

        user = User(
            email=email,
            password_hash=hash_password(password),
            role="ADMIN",
            is_active=True,
            mfa_enabled=setup_mfa,
            mfa_secret=mfa_secret,
        )
        session.add(user)
        await session.commit()

        print(f"\n✅ Admin user created successfully!")
        print(f"   Email: {email}")
        print(f"   Role: ADMIN")
        print(f"   MFA: {'enabled' if setup_mfa else 'disabled'}")

        if setup_mfa and mfa_secret:
            uri = get_totp_provisioning_uri(mfa_secret, email)
            print(f"\n📱 Scan this URI with your authenticator app:")
            print(f"   {uri}")
            print(f"\n   Or manually enter secret: {mfa_secret}")


if __name__ == "__main__":
    asyncio.run(create_admin())
