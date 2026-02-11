# Streamlit Cloud MySQL Connection Fix

## Problem
The app works locally but crashes on Streamlit Cloud with `mysql.connector.errors.DatabaseError: 2027 (HY000): Malformed packet` after running for a while.

## Root Cause
The MySQL connection is being cached by Streamlit's `@st.cache_resource` decorator and becomes stale over time, causing "Malformed packet" errors. The single cached connection doesn't properly handle reconnection on Streamlit Cloud.

## Solution: Use Connection Pooling

Replace the single cached connection with a **MySQL connection pool** that provides fresh connections for each request.

### Changes Required in `app.py`:

**1. Replace `get_db()` with connection pooling:**

```python
@st.cache_resource
def get_db_pool():
    """Create a connection pool instead of a single connection"""
    try:
        logger.info("Initializing Cloud SQL connection pool...")
        from mysql.connector import pooling

        db_config = config.get_db_config()
        pool = pooling.MySQLConnectionPool(
            pool_name="streamlit_pool",
            pool_size=5,
            pool_reset_session=True,
            **db_config
        )
        logger.info("Cloud SQL connection pool established")
        return pool
    except Exception as e:
        logger.error(f"Failed to create connection pool: {str(e)}")
        raise DatabaseConnectionError(f"Could not create database pool: {str(e)}")

def get_db_connection():
    """Get a fresh connection from the pool with automatic retry"""
    pool = get_db_pool()
    try:
        conn = pool.get_connection()
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=1)
        return conn
    except Exception as e:
        logger.error(f"Failed to get connection from pool: {str(e)}")
        raise DatabaseConnectionError(f"Could not get database connection: {str(e)}")
```

**2. Update `get_recommendation()` function:**

Replace `db = get_db()` with `db = get_db_connection()` and wrap the entire function body in try-finally to ensure connections are closed:

```python
def get_recommendation(part_id: int):
    qdrant = get_qdrant()
    model = get_gemini_model()

    # Get a fresh connection from the pool
    db = get_db_connection()
    cursor = None

    try:
        cursor = db.cursor()

        # All the existing database operations here...
        # (part queries, location checks, etc.)

        return result_dict

    finally:
        # Always close cursor and connection
        if cursor:
            cursor.close()
        if db:
            db.close()
```

## Benefits

1. **Prevents stale connections**: Each request gets a fresh connection from the pool
2. **Automatic reconnection**: Pool handles connection failures gracefully
3. **Better resource management**: Connections are properly closed after use
4. **Production-ready**: Connection pooling is the standard approach for web applications

## Testing

After applying these changes:
1. Deploy to Streamlit Cloud
2. Test multiple recommendations over 10-15 minutes
3. Verify no "Malformed packet" errors appear in logs

## Related Error Logs

```
2026-02-11 21:56:46,008 - __main__ - ERROR - Recommendation failed
Traceback (most recent call last):
  ...
mysql.connector.errors.DatabaseError: 2027 (HY000): Malformed packet
```

This error indicates the cached MySQL connection became corrupted/stale and needs to be replaced with proper connection pooling.
