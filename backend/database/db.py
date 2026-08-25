import os
import psycopg2
from dotenv import load_dotenv

# Ensure .env is properly loaded from backend folder or current working dir
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(backend_dir, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "lifeos"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "")
    )

# Alias for backwards compatibility
get_db_connection = get_connection

def init_db():
    """Ensure all required tables and columns exist for LifeOS modules."""
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. Master Table: job_apply_mt
        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_apply_mt (
                id SERIAL PRIMARY KEY,
                job_no VARCHAR(100),
                organization_name VARCHAR(255) NOT NULL,
                post_name VARCHAR(255) NOT NULL,
                is_govt BOOLEAN DEFAULT FALSE,
                application_start_date DATE,
                application_end_date DATE,
                exam_date DATE,
                official_url VARCHAR(500),
                amount NUMERIC(10, 2) DEFAULT 0.00,
                status VARCHAR(50) DEFAULT 'Applied',
                remarks TEXT,
                created_date TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Add optional/enhanced columns to job_apply_mt if they don't exist
        enhanced_columns = [
            ("location", "VARCHAR(255)"),
            ("work_mode", "VARCHAR(50) DEFAULT 'Remote'"),
            ("job_portal", "VARCHAR(100)"),
            ("salary_range", "VARCHAR(100)"),
            ("resume_version", "VARCHAR(255)"),
            ("skills", "TEXT"),
            ("hr_contact", "VARCHAR(255)"),
            ("user_id", "INTEGER"),
            ("updated_at", "TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP")
        ]

        for col_name, col_type in enhanced_columns:
            cur.execute(f"""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='job_apply_mt' AND column_name='{col_name}'
                    ) THEN 
                        ALTER TABLE job_apply_mt ADD COLUMN {col_name} {col_type}; 
                    END IF; 
                END $$;
            """)

        # 2. Detail/Activity Table: job_apply_dt
        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_apply_dt (
                id SERIAL PRIMARY KEY,
                mt_id INTEGER REFERENCES job_apply_mt(id) ON DELETE CASCADE,
                activity_name VARCHAR(255) NOT NULL,
                activity_status VARCHAR(50),
                activity_date DATE,
                remarks TEXT,
                created_date TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Discipline Table: discipline_daily
        cur.execute("""
            CREATE TABLE IF NOT EXISTS discipline_daily (
                id SERIAL PRIMARY KEY,
                user_id INTEGER DEFAULT 1,
                date DATE NOT NULL,
                gym_completed BOOLEAN DEFAULT FALSE,
                job_completed BOOLEAN DEFAULT FALSE,
                study_completed BOOLEAN DEFAULT FALSE,
                project_completed BOOLEAN DEFAULT FALSE,
                daily_score NUMERIC(5, 2) DEFAULT 0.00,
                notes TEXT,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_discipline_user_date UNIQUE (user_id, date)
            );
        """)

        # Index for fast date lookups
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_discipline_user_date ON discipline_daily(user_id, date);
        """)

        # 4. Ensure Discipline Module is in module_master
        cur.execute("SELECT id FROM module_master WHERE module_name = 'Discipline' OR route = '/discipline';")
        disc_mod = cur.fetchone()
        if not disc_mod:
            cur.execute("""
                INSERT INTO module_master (module_name, route, sequence_no, is_active, created_at)
                VALUES ('Discipline', '/discipline', 1, TRUE, CURRENT_TIMESTAMP)
                RETURNING id;
            """)
            disc_mod_id = cur.fetchone()[0]
            # Grant permission to all existing users
            cur.execute("SELECT user_id FROM user_master;")
            users = cur.fetchall()
            for (uid,) in users:
                cur.execute("""
                    INSERT INTO user_module_permission (user_id, module_id, created_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT DO NOTHING;
                """, (uid, disc_mod_id))
        else:
            disc_mod_id = disc_mod[0]
            # Grant permission if missing
            cur.execute("SELECT user_id FROM user_master;")
            users = cur.fetchall()
            for (uid,) in users:
                cur.execute("""
                    SELECT 1 FROM user_module_permission WHERE user_id = %s AND module_id = %s;
                """, (uid, disc_mod_id))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO user_module_permission (user_id, module_id, created_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP);
                    """, (uid, disc_mod_id))

        # 5. Ensure Social Media Hub Module is in module_master
        cur.execute("SELECT id FROM module_master WHERE module_name = 'Social Media Hub' OR route = '/social-media';")
        sm_mod = cur.fetchone()
        if not sm_mod:
            cur.execute("""
                INSERT INTO module_master (module_name, route, sequence_no, is_active, created_at)
                VALUES ('Social Media Hub', '/social-media', 4, TRUE, CURRENT_TIMESTAMP)
                RETURNING id;
            """)
            sm_mod_id = cur.fetchone()[0]
            # Grant permission to all existing users
            cur.execute("SELECT user_id FROM user_master;")
            users = cur.fetchall()
            for (uid,) in users:
                cur.execute("""
                    INSERT INTO user_module_permission (user_id, module_id, created_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT DO NOTHING;
                """, (uid, sm_mod_id))
        else:
            sm_mod_id = sm_mod[0]
            cur.execute("SELECT user_id FROM user_master;")
            users = cur.fetchall()
            for (uid,) in users:
                cur.execute("""
                    SELECT 1 FROM user_module_permission WHERE user_id = %s AND module_id = %s;
                """, (uid, sm_mod_id))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO user_module_permission (user_id, module_id, created_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP);
                    """, (uid, sm_mod_id))

        conn.commit()
        cur.close()
        conn.close()
        print("✓ Database tables, indexes, Discipline, and Social Media Hub module verified successfully.")
    except Exception as e:
        print("Warning: Database init failed or could not connect:", e)