import asyncio, asyncpg, ssl

async def test():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    conn = await asyncpg.connect(
        host='skyro-db.cl4o2c2matz8.ap-south-1.rds.amazonaws.com',
        port=5432, user='skyro_admin', password='Skyro5172',
        database='skyro', ssl=ctx
    )
    # Check what columns exist in the AWS orders table
    rows = await conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='orders' ORDER BY ordinal_position"
    )
    print('AWS orders table columns:')
    for r in rows:
        print(' ', r['column_name'], '->', r['data_type'])

    # Try a direct SELECT
    try:
        rows2 = await conn.fetch('SELECT id, status, created_at FROM orders LIMIT 3')
        print('\nDirect query OK:', len(rows2), 'rows')
        for r in rows2:
            print('  ', dict(r))
    except Exception as e:
        print('\nDirect query ERROR:', e)

    await conn.close()

asyncio.run(test())
