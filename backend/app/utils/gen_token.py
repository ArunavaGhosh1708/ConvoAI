"""
CLI helper to generate a signed JWT for local development.

Usage:
    python -m app.utils.gen_token --role admin
    python -m app.utils.gen_token --role user --sub my-user-id
"""

import argparse
import time
import jwt
from app.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a dev JWT token")
    parser.add_argument("--role", default="user", choices=["user", "admin"])
    parser.add_argument("--sub",  default="dev-user")
    parser.add_argument("--exp",  type=int, default=86400, help="Expiry seconds (default 24h)")
    args = parser.parse_args()

    payload = {
        "sub":  args.sub,
        "role": args.role,
        "iat":  int(time.time()),
        "exp":  int(time.time()) + args.exp,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    print(token)


if __name__ == "__main__":
    main()
