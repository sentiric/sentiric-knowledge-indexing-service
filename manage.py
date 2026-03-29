#!/usr/bin/env python3
# manage.py
import asyncio
import argparse
import asyncpg
import os
import structlog
from dotenv import load_dotenv

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

load_dotenv()
DB_URL = os.getenv("POSTGRES_URL", "postgres://sentiric:sentiric_pass@localhost:5432/sentiric_knowledge?sslmode=disable")

async def add_source(tenant_id, source_type, uri):
    logger.info("Connecting to database...", event_name="CLI_DB_CONNECT")
    conn = None
    try:
        conn = await asyncpg.connect(DB_URL)
        await conn.execute(
            """
            INSERT INTO datasources (tenant_id, source_type, source_uri)
            VALUES ($1, $2, $3)
            ON CONFLICT (tenant_id, source_uri) 
            DO UPDATE SET is_active = TRUE, updated_at = NOW();
            """,
            tenant_id, source_type, uri
        )
        logger.info(f"Source added: [{tenant_id}] {source_type} -> {uri}", event_name="CLI_SOURCE_ADDED", tenant_id=tenant_id, source_type=source_type, uri=uri)
    except Exception as e:
        logger.error(f"Error adding source: {e}", event_name="CLI_DB_ERROR", exc_info=True)
    finally:
        if conn:
            await conn.close()

async def list_sources(tenant_id=None):
    conn = None
    try:
        conn = await asyncpg.connect(DB_URL)
        query = "SELECT id, tenant_id, source_type, source_uri, last_status, last_indexed_at FROM datasources"
        args = []
        if tenant_id:
            query += " WHERE tenant_id = $1"
            args.append(tenant_id)
        
        rows = await conn.fetch(query, *args)
        
        sources_list = [dict(r) for r in rows]
        logger.info("Retrieved sources list", event_name="CLI_SOURCES_LIST", sources=sources_list)
    except Exception as e:
        logger.error(f"Error listing sources: {e}", event_name="CLI_DB_ERROR", exc_info=True)
    finally:
        if conn:
            await conn.close()

async def trigger_indexing(host="localhost", port=17030):
    import httpx
    url = f"http://{host}:{port}/reindex"
    logger.info(f"Triggering re-index via HTTP: {url}", event_name="CLI_HTTP_TRIGGER")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={})
            if resp.status_code in [200, 202]:
                logger.info("Indexing triggered successfully.", event_name="CLI_HTTP_SUCCESS")
            else:
                logger.warn(f"Failed to trigger indexing: {resp.status_code} - {resp.text}", event_name="CLI_HTTP_FAILED")
    except Exception as e:
        logger.error(f"Connection error: {e}", event_name="CLI_HTTP_ERROR", exc_info=True)

def main():
    parser = argparse.ArgumentParser(description="Sentiric Knowledge Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a new datasource")
    add_parser.add_argument("--tenant", default="sentiric_demo", help="Tenant ID")
    add_parser.add_argument("--type", default="web", choices=["web", "file", "postgres"], help="Source Type")
    add_parser.add_argument("uri", help="URL or Path")

    list_parser = subparsers.add_parser("list", help="List datasources")
    list_parser.add_argument("--tenant", help="Filter by Tenant ID")

    trigger_parser = subparsers.add_parser("run", help="Trigger immediate re-indexing")
    
    args = parser.parse_args()

    if args.command == "add":
        asyncio.run(add_source(args.tenant, args.type, args.uri))
    elif args.command == "list":
        asyncio.run(list_sources(args.tenant))
    elif args.command == "run":
        asyncio.run(trigger_indexing())

if __name__ == "__main__":
    main()