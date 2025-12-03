#!/usr/bin/env python3
import asyncio
import argparse
import asyncpg
import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Config'den al
DB_URL = os.getenv("POSTGRES_URL", "postgres://sentiric:sentiric_pass@localhost:5432/sentiric_db")

async def add_source(tenant_id, source_type, uri):
    """Yeni bir veri kaynağı ekler."""
    conn = await asyncpg.connect(DB_URL)
    try:
        print(f"🔌 Veritabanına bağlanılıyor...")
        await conn.execute(
            """
            INSERT INTO datasources (tenant_id, source_type, source_uri)
            VALUES ($1, $2, $3)
            ON CONFLICT (tenant_id, source_uri) 
            DO UPDATE SET is_active = TRUE, updated_at = NOW();
            """,
            tenant_id, source_type, uri
        )
        print(f"✅ Kaynak Eklendi: [{tenant_id}] {source_type} -> {uri}")
    except Exception as e:
        print(f"❌ Hata: {e}")
    finally:
        await conn.close()

async def list_sources(tenant_id=None):
    """Mevcut kaynakları listeler."""
    conn = await asyncpg.connect(DB_URL)
    try:
        query = "SELECT id, tenant_id, source_type, source_uri, last_status, last_indexed_at FROM datasources"
        args = []
        if tenant_id:
            query += " WHERE tenant_id = $1"
            args.append(tenant_id)
        
        rows = await conn.fetch(query, *args)
        
        print(f"{'ID':<5} {'TENANT':<15} {'TYPE':<10} {'STATUS':<10} {'URI'}")
        print("-" * 80)
        for row in rows:
            print(f"{row['id']:<5} {row['tenant_id']:<15} {row['source_type']:<10} {row['last_status']:<10} {row['source_uri']}")
            
    finally:
        await conn.close()

async def trigger_indexing(host="localhost", port=17030):
    """İndekslemeyi tetikler (HTTP isteği ile)."""
    import httpx
    url = f"http://{host}:{port}/reindex"
    print(f"🚀 Tetikleniyor: {url}")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={})
            if resp.status_code in [200, 202]:
                print("✅ İndeksleme tetiklendi.")
            else:
                print(f"⚠️ Başarısız: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ Bağlantı hatası: {e}")

def main():
    parser = argparse.ArgumentParser(description="Sentiric Knowledge Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new datasource")
    add_parser.add_argument("--tenant", default="sentiric_demo", help="Tenant ID")
    add_parser.add_argument("--type", default="web", choices=["web", "file", "postgres"], help="Source Type")
    add_parser.add_argument("uri", help="URL or Path")

    # List command
    list_parser = subparsers.add_parser("list", help="List datasources")
    list_parser.add_argument("--tenant", help="Filter by Tenant ID")

    # Trigger command
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