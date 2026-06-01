"""
setup.py — allows `pip install -e .` for editable installs.
This registers the project root on sys.path so all internal packages
(app, broker, ml, auth, observability) resolve without PYTHONPATH hacks.
"""
from setuptools import setup, find_packages

setup(
    name="blockshield",
    version="1.0.0",
    packages=find_packages(exclude=["tests*", "frontend*"]),
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.115",
        "uvicorn[standard]>=0.32",
        "sqlalchemy[asyncio]>=2.0",
        "asyncpg>=0.30",
        "aiosqlite>=0.20",
        "alembic>=1.14",
        "python-jose[cryptography]>=3.3",
        "passlib[bcrypt]>=1.7",
        "redis[asyncio]>=5.2",
        "httpx>=0.28",
        "scikit-learn>=1.5",
        "numpy>=2.0",
        "networkx>=3.4",
        "prometheus-client>=0.21",
        "structlog>=24.4",
        "pydantic>=2.10",
        "pydantic-settings>=2.7",
        "python-multipart>=0.0.20",
    ],
)
