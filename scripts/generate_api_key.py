"""
Generate an admin API key.

Usage:
    python scripts/generate_api_key.py --user-id 1 --name "Admin Key"
    python scripts/generate_api_key.py --admin  # Generate admin-level key

The script will:
1. Generate a cryptographically secure random API key
2. Hash it using bcrypt
3. Store the hash in the database
4. Display the raw key (only time it's visible)
"""

import argparse
import asyncio
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from predict.core.security.hashing import hash_api_key


async def generate_key(
    pg_url: str,
    user_id: int,
    name: str,
    is_admin: bool = False,
    expires_days: int = 365,
) -> str:
    """Generate and store a new API key."""
    from predict.core.db.models.user import APIKey
    
    # Create engine and session
    engine = create_async_engine(pg_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    
    async with session_factory() as session:
        # Verify user exists
        from predict.core.db.models.user import User
        
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"Error: User {user_id} not found", file=sys.stderr)
            await engine.dispose()
            sys.exit(1)
        
        # Generate key
        prefix = "pred_admin" if is_admin else "pred"
        random_part = secrets.token_urlsafe(32)
        raw_key = f"{prefix}_{random_part}"
        
        # Hash key
        key_hash = hash_api_key(raw_key)
        
        # Calculate expiration
        current_time = time.time()
        expires_at = current_time + (expires_days * 86400)
        
        # Store in database
        api_key = APIKey(
            user_id=user_id,
            key_hash=key_hash,
            name=name,
            is_active=True,
            is_admin=is_admin,
            expires_at=expires_at,
            created_at=current_time,
            updated_at=current_time,
        )
        
        session.add(api_key)
        await session.commit()
        
        await engine.dispose()
        
        return raw_key, api_key.id, expires_at


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate an API key for PREDICT"
    )
    parser.add_argument(
        "--user-id",
        type=int,
        required=True,
        help="User ID to associate the key with",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="Generated Key",
        help="Name/description for the key",
    )
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Generate admin-level key",
    )
    parser.add_argument(
        "--expires-days",
        type=int,
        default=365,
        help="Number of days until key expires",
    )
    parser.add_argument(
        "--pg-url",
        type=str,
        default="postgresql+asyncpg://predict_admin:password@localhost:5432/predict",
        help="PostgreSQL connection URL",
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("PREDICT API Key Generator")
    print("="*60)
    
    try:
        raw_key, key_id, expires_at = asyncio.run(generate_key(
            pg_url=args.pg_url,
            user_id=args.user_id,
            name=args.name,
            is_admin=args.admin,
            expires_days=args.expires_days,
        ))
        
        expires_str = datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n✅ API Key generated successfully!")
        print(f"\n{'='*60}")
        print("🔑 YOUR API KEY (copy this now - it won't be shown again):")
        print(f"{'='*60}")
        print(f"\n{raw_key}\n")
        print(f"{'='*60}")
        print(f"Key ID:        {key_id}")
        print(f"User ID:       {args.user_id}")
        print(f"Name:          {args.name}")
        print(f"Admin:         {'Yes' if args.admin else 'No'}")
        print(f"Expires:       {expires_str}")
        print(f"{'='*60}")
        print("\n⚠️  WARNING: Store this key securely. It cannot be retrieved later.")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
