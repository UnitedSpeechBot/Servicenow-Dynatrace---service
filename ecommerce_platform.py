import logging
import psycopg2
import smtplib
import time
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S.%fZ'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

# Database configuration
DB_CONFIG = {
    'host': 'db.internal',
    'port': 5432,
    'database': 'appdb',
    'user': 'app_user',
    'password': 'app_password',
    'connect_timeout': 5,
}

# Email configuration
SMTP_CONFIG = {
    'host': 'smtp.internal',
    'port': 587,
    'username': 'notifications',
    'password': 'smtp_password',
    'timeout': 10,
}

# Connection pool
db_pool = []
DB_POOL_SIZE = 20
DB_POOL_TIMEOUT = 5000  # ms

def get_db_connection():
    """Get a database connection from the pool or create a new one"""
    if db_pool:
        return db_pool.pop()
    
    logger.info(f"Attempting connection to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info(f"Connected to PostgreSQL successfully db={DB_CONFIG['database']}")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise

def release_connection(conn):
    """Return a connection to the pool"""
    if len(db_pool) < DB_POOL_SIZE:
        db_pool.append(conn)
    else:
        conn.close()

def execute_query(query, params=None, timeout_ms=5000):
    """Execute a database query with timeout"""
    start_time = time.time()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        # Check if query is slow
        duration_ms = int((time.time() - start_time) * 1000)
        if duration_ms > 1000:  # 1 second threshold
            logger.warning(f"Slow query detected: {query[:50]}... rows={cursor.rowcount} duration={duration_ms}ms threshold=1000ms")
        
        return cursor
    except Exception as e:
        if time.time() - start_time > timeout_ms/1000:
            logger.error(f"Connection timeout: failed to acquire connection from pool after {timeout_ms}ms pool_size={DB_POOL_SIZE} active={DB_POOL_SIZE-len(db_pool)} waiting=3")
        else:
            logger.error(f"Database error: {str(e)}")
        raise
    finally:
        if conn:
            release_connection(conn)

def send_email(to_email, subject, body, email_type="notification"):
    """Send an email via SMTP"""
    try:
        server = smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port'], timeout=SMTP_CONFIG['timeout'])
        server.starttls()
        server.login(SMTP_CONFIG['username'], SMTP_CONFIG['password'])
        
        message = f"From: {SMTP_CONFIG['username']}@example.com\nTo: {to_email}\nSubject: {subject}\n\n{body}"
        server.sendmail(f"{SMTP_CONFIG['username']}@example.com", to_email, message)
        server.quit()
        
        logger.info(f"Email sent successfully type={email_type} to={to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email type={email_type} to={to_email} error=\"{str(e)}\" smtp_host={SMTP_CONFIG['host']}:{SMTP_CONFIG['port']}")
        return False

@app.route('/api/v1/orders', methods=['GET'])
def get_orders():
    user_email = request.headers.get('X-User-Email', 'anonymous')
    start_time = time.time()
    
    try:
        cursor = execute_query("SELECT * FROM orders WHERE user_email = %s", (user_email,))
        orders = cursor.fetchall()
        
        response = jsonify({'orders': orders})
        status_code = 200
    except Exception as e:
        response = jsonify({'error': str(e)})
        status_code = 503
        
    latency_ms = int((time.time() - start_time) * 1000)
    if status_code >= 400:
        logger.error(f"GET /api/v1/orders status={status_code} latency={latency_ms}ms user={user_email} error=\"{str(e)}\"")
    else:
        logger.info(f"GET /api/v1/orders status={status_code} latency={latency_ms}ms user={user_email}")
        
    return response, status_code

@app.route('/api/v1/orders', methods=['POST'])
def create_order():
    user_email = request.headers.get('X-User-Email', 'anonymous')
    start_time = time.time()
    
    try:
        order_data = request.json
        cursor = execute_query(
            "INSERT INTO orders (user_email, product_id, quantity, price) VALUES (%s, %s, %s, %s) RETURNING id",
            (user_email, order_data['product_id'], order_data['quantity'], order_data['price'])
        )
        order_id = cursor.fetchone()[0]
        
        # Process payment
        transaction_id = f"txn-stripe-{order_id + 99000}"
        logger.info(f"Payment authorized order_id=ORD-{order_id} transaction_id={transaction_id}")
        
        response = jsonify({'order_id': f"ORD-{order_id}", 'transaction_id': transaction_id})
        status_code = 201
    except Exception as e:
        response = jsonify({'error': str(e)})
        status_code = 400
        
    latency_ms = int((time.time() - start_time) * 1000)
    logger.info(f"POST /api/v1/orders status={status_code} latency={latency_ms}ms user={user_email}")
    
    return response, status_code

@app.route('/api/v1/weekly_digest', methods=['POST'])
def send_weekly_digest():
    try:
        recipients = request.json.get('recipients', [])
        for email in recipients:
            send_email(
                email,
                "Your Weekly Digest",
                "Here's your weekly summary of activity...",
                email_type="weekly_digest"
            )
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Application starting up... version=2.4.1 env=production")
    app.run(host='0.0.0.0', port=8080)
