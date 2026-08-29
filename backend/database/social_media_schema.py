"""
LifeOS — Social Media Hub PostgreSQL Database Schema & Migrations
Defines and updates tables for connected social accounts, master content items,
per-platform publishing targets, audit attempts, platform analytics snapshots,
and SHA-256 hashed OAuth state validation tokens.
"""

def create_social_media_schema(conn):
    """
    Creates or updates the Social Media Hub database schema idempotently inside a transaction.
    Preserves all existing data in user_master, job_apply, discipline, and social media tables.
    """
    cur = conn.cursor()
    try:
        # =====================================================================
        # 0. Reusable Trigger Function for Automatic updated_at Timestamps
        # =====================================================================
        cur.execute("""
            CREATE OR REPLACE FUNCTION set_updated_at_timestamp()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)

        # =====================================================================
        # 1. Table: social_accounts
        # Stores official OAuth account connections (YouTube channels, IG Pro, FB Pages)
        # =====================================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_accounts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES user_master(user_id) ON DELETE CASCADE,
                platform VARCHAR(50) NOT NULL,
                platform_account_id VARCHAR(255) NOT NULL,
                account_name VARCHAR(255),
                account_username VARCHAR(255),
                profile_image_url TEXT,
                encrypted_access_token TEXT,
                encrypted_refresh_token TEXT,
                token_expires_at TIMESTAMP WITH TIME ZONE,
                raw_scopes TEXT,
                connection_status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_social_accounts_user_platform_acc UNIQUE (user_id, platform, platform_account_id)
            );
        """)

        # Constraints for social_accounts
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_social_accounts_platform'
                ) THEN
                    ALTER TABLE social_accounts
                    ADD CONSTRAINT chk_social_accounts_platform
                    CHECK (platform IN ('YOUTUBE', 'INSTAGRAM', 'FACEBOOK'));
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_social_accounts_status'
                ) THEN
                    ALTER TABLE social_accounts
                    ADD CONSTRAINT chk_social_accounts_status
                    CHECK (connection_status IN ('ACTIVE', 'EXPIRED', 'REVOKED', 'DISCONNECTED', 'ERROR'));
                END IF;
            END $$;
        """)

        # Indexes for social_accounts
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_accounts_user_id ON social_accounts(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_accounts_platform ON social_accounts(platform);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_accounts_status ON social_accounts(connection_status);")

        # Trigger for social_accounts
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_social_accounts_updated_at'
                ) THEN
                    CREATE TRIGGER trg_social_accounts_updated_at
                    BEFORE UPDATE ON social_accounts
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();
                END IF;
            END $$;
        """)

        # =====================================================================
        # 2. Table: social_content
        # Master post metadata, temporary upload references, dimensions, and overall status.
        # NEVER stores video binary data.
        # =====================================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_content (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES user_master(user_id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                common_caption TEXT,
                hashtags TEXT,
                media_type VARCHAR(50) NOT NULL DEFAULT 'VIDEO',
                temp_media_path VARCHAR(500),
                temp_thumbnail_path VARCHAR(500),
                file_size_bytes BIGINT,
                duration_seconds NUMERIC(10, 2),
                width INTEGER,
                height INTEGER,
                aspect_ratio VARCHAR(20),
                overall_status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
                original_timezone VARCHAR(50) DEFAULT 'UTC',
                temp_file_expires_at TIMESTAMP WITH TIME ZONE,
                scheduled_at_utc TIMESTAMP WITH TIME ZONE,
                published_at TIMESTAMP WITH TIME ZONE,
                temp_file_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                temp_file_deleted_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Add any missing columns to social_content
        cur.execute("""
            ALTER TABLE social_content ADD COLUMN IF NOT EXISTS original_timezone VARCHAR(50) DEFAULT 'UTC';
            ALTER TABLE social_content ADD COLUMN IF NOT EXISTS temp_file_expires_at TIMESTAMP WITH TIME ZONE;
            ALTER TABLE social_content ADD COLUMN IF NOT EXISTS privacy_status VARCHAR(50) DEFAULT 'PUBLIC';
            ALTER TABLE social_content ADD COLUMN IF NOT EXISTS made_for_kids BOOLEAN DEFAULT FALSE;
            ALTER TABLE social_content ADD COLUMN IF NOT EXISTS category_id VARCHAR(50) DEFAULT '22';
        """)

        # Status check constraint for social_content
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_social_content_overall_status'
                ) THEN
                    ALTER TABLE social_content
                    ADD CONSTRAINT chk_social_content_overall_status
                    CHECK (overall_status IN ('DRAFT', 'SCHEDULED', 'PROCESSING', 'PUBLISHED', 'PARTIALLY_PUBLISHED', 'FAILED', 'DELETED'));
                END IF;
            END $$;
        """)

        # Constraints for social_content
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_social_content_media_type'
                ) THEN
                    ALTER TABLE social_content
                    ADD CONSTRAINT chk_social_content_media_type
                    CHECK (media_type IN ('VIDEO', 'IMAGE', 'CAROUSEL', 'TEXT'));
                END IF;
            END $$;
        """)

        # Indexes for social_content
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_content_user_id ON social_content(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_content_status ON social_content(overall_status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_content_scheduled ON social_content(scheduled_at_utc);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_content_temp_expiry ON social_content(temp_file_expires_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_content_created_at ON social_content(created_at DESC);")

        # Trigger for social_content
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_social_content_updated_at'
                ) THEN
                    CREATE TRIGGER trg_social_content_updated_at
                    BEFORE UPDATE ON social_content
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();
                END IF;
            END $$;
        """)

        # =====================================================================
        # 3. Table: social_content_platforms
        # Represents target platforms selected for publishing a single post.
        # =====================================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_content_platforms (
                id SERIAL PRIMARY KEY,
                content_id INTEGER NOT NULL REFERENCES social_content(id) ON DELETE CASCADE,
                account_id INTEGER NOT NULL REFERENCES social_accounts(id) ON DELETE RESTRICT,
                platform VARCHAR(50) NOT NULL,
                custom_title VARCHAR(255),
                custom_caption TEXT,
                custom_description TEXT,
                privacy_status VARCHAR(50) DEFAULT 'PUBLIC',
                platform_status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
                processing_status VARCHAR(50) NOT NULL DEFAULT 'IDLE',
                platform_post_id VARCHAR(255),
                platform_post_url TEXT,
                platform_error_code VARCHAR(100),
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_attempt_at TIMESTAMP WITH TIME ZONE,
                published_at TIMESTAMP WITH TIME ZONE,
                error_message TEXT,
                upload_progress_percent INTEGER DEFAULT 0,
                bytes_sent BIGINT DEFAULT 0,
                total_bytes BIGINT DEFAULT 0,
                encrypted_session_uri TEXT,
                thumbnail_status VARCHAR(50) DEFAULT 'IDLE',
                made_for_kids BOOLEAN DEFAULT FALSE,
                category_id VARCHAR(50) DEFAULT '22',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_content_platform_account UNIQUE (content_id, platform, account_id)
            );
        """)

        # Add missing columns to social_content_platforms
        cur.execute("""
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS custom_description TEXT;
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS processing_status VARCHAR(50) DEFAULT 'IDLE';
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS platform_error_code VARCHAR(100);
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS published_at TIMESTAMP WITH TIME ZONE;
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS upload_progress_percent INTEGER DEFAULT 0;
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS bytes_sent BIGINT DEFAULT 0;
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS total_bytes BIGINT DEFAULT 0;
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS encrypted_session_uri TEXT;
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS thumbnail_status VARCHAR(50) DEFAULT 'IDLE';
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS made_for_kids BOOLEAN DEFAULT FALSE;
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS category_id VARCHAR(50) DEFAULT '22';
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS claim_token VARCHAR(64);
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS claim_expires_at TIMESTAMP WITH TIME ZONE;
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS next_processing_check_at TIMESTAMP WITH TIME ZONE;
            ALTER TABLE social_content_platforms ADD COLUMN IF NOT EXISTS processing_check_count INTEGER NOT NULL DEFAULT 0;
        """)

        # Constraints for social_content_platforms
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conrelid = 'social_content_platforms'::regclass AND conname = 'chk_scp_platform'
                ) THEN
                    ALTER TABLE social_content_platforms
                    ADD CONSTRAINT chk_scp_platform
                    CHECK (platform IN ('YOUTUBE', 'INSTAGRAM', 'FACEBOOK'));
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conrelid = 'social_content_platforms'::regclass AND conname = 'chk_scp_platform_status'
                ) THEN
                    ALTER TABLE social_content_platforms
                    ADD CONSTRAINT chk_scp_platform_status
                    CHECK (platform_status IN ('PENDING', 'PROCESSING', 'PUBLISHED', 'FAILED', 'CANCELLED'));
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conrelid = 'social_content_platforms'::regclass AND conname = 'chk_scp_processing_status'
                ) THEN
                    ALTER TABLE social_content_platforms
                    ADD CONSTRAINT chk_scp_processing_status
                    CHECK (processing_status IN ('IDLE', 'UPLOADING', 'PROCESSING', 'READY', 'FAILED'));
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conrelid = 'social_content_platforms'::regclass AND conname = 'chk_scp_privacy_status'
                ) THEN
                    ALTER TABLE social_content_platforms
                    ADD CONSTRAINT chk_scp_privacy_status
                    CHECK (privacy_status IN ('PUBLIC', 'PRIVATE', 'UNLISTED'));
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conrelid = 'social_content_platforms'::regclass AND conname = 'chk_scp_upload_progress'
                ) THEN
                    ALTER TABLE social_content_platforms
                    ADD CONSTRAINT chk_scp_upload_progress
                    CHECK (upload_progress_percent >= 0 AND upload_progress_percent <= 100);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conrelid = 'social_content_platforms'::regclass AND conname = 'chk_scp_bytes_sent'
                ) THEN
                    ALTER TABLE social_content_platforms
                    ADD CONSTRAINT chk_scp_bytes_sent
                    CHECK (bytes_sent >= 0);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conrelid = 'social_content_platforms'::regclass AND conname = 'chk_scp_total_bytes'
                ) THEN
                    ALTER TABLE social_content_platforms
                    ADD CONSTRAINT chk_scp_total_bytes
                    CHECK (total_bytes >= 0);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conrelid = 'social_content_platforms'::regclass AND conname = 'chk_scp_bytes_relation'
                ) THEN
                    ALTER TABLE social_content_platforms
                    ADD CONSTRAINT chk_scp_bytes_relation
                    CHECK (total_bytes = 0 OR bytes_sent <= total_bytes);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conrelid = 'social_content_platforms'::regclass AND conname = 'chk_scp_thumbnail_status'
                ) THEN
                    ALTER TABLE social_content_platforms
                    ADD CONSTRAINT chk_scp_thumbnail_status
                    CHECK (thumbnail_status IN ('IDLE', 'UPLOADING', 'UPLOADED', 'FAILED'));
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conrelid = 'social_content_platforms'::regclass AND conname = 'chk_scp_check_count'
                ) THEN
                    ALTER TABLE social_content_platforms
                    ADD CONSTRAINT chk_scp_check_count
                    CHECK (processing_check_count >= 0);
                END IF;
            END $$;
        """)

        # Indexes for social_content_platforms
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scp_content_id ON social_content_platforms(content_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scp_account_id ON social_content_platforms(account_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scp_platform_status ON social_content_platforms(platform, platform_status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scp_claim_recovery ON social_content_platforms(platform_status, processing_status, claim_expires_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scp_processing_recovery ON social_content_platforms(platform, platform_status, next_processing_check_at, claim_expires_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scp_post_id ON social_content_platforms(platform_post_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sc_user_created ON social_content(user_id, created_at DESC);")

        # Trigger for social_content_platforms
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_social_content_platforms_updated_at'
                ) THEN
                    CREATE TRIGGER trg_social_content_platforms_updated_at
                    BEFORE UPDATE ON social_content_platforms
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();
                END IF;
            END $$;
        """)

        # =====================================================================
        # 4. Table: social_publish_attempts
        # Audit trail of individual API requests. Never stores secrets or raw payloads.
        # =====================================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_publish_attempts (
                id SERIAL PRIMARY KEY,
                content_platform_id INTEGER NOT NULL REFERENCES social_content_platforms(id) ON DELETE CASCADE,
                attempt_number INTEGER NOT NULL DEFAULT 1,
                status VARCHAR(50) NOT NULL,
                idempotency_key VARCHAR(128),
                error_code VARCHAR(100),
                error_message TEXT,
                duration_ms INTEGER,
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP WITH TIME ZONE,
                next_retry_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Add missing columns to social_publish_attempts
        cur.execute("""
            ALTER TABLE social_publish_attempts ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);
            ALTER TABLE social_publish_attempts ADD COLUMN IF NOT EXISTS error_code VARCHAR(100);
            ALTER TABLE social_publish_attempts ADD COLUMN IF NOT EXISTS error_message TEXT;
            ALTER TABLE social_publish_attempts ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
            ALTER TABLE social_publish_attempts ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;
            ALTER TABLE social_publish_attempts ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMP WITH TIME ZONE;
        """)

        # Constraints for social_publish_attempts
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_spa_status'
                ) THEN
                    ALTER TABLE social_publish_attempts
                    ADD CONSTRAINT chk_spa_status
                    CHECK (status IN ('STARTED', 'SUCCESS', 'FAILED', 'RETRYING'));
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_publish_attempt_idempotency'
                ) THEN
                    ALTER TABLE social_publish_attempts
                    ADD CONSTRAINT uq_publish_attempt_idempotency
                    UNIQUE (idempotency_key);
                END IF;
            END $$;
        """)

        # Indexes for social_publish_attempts
        cur.execute("CREATE INDEX IF NOT EXISTS idx_spa_content_platform_id ON social_publish_attempts(content_platform_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_spa_idempotency_key ON social_publish_attempts(idempotency_key);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_spa_created_at ON social_publish_attempts(created_at DESC);")

        # =====================================================================
        # 5. Table: social_analytics
        # Timestamped performance snapshots from official platform insights
        # =====================================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_analytics (
                id SERIAL PRIMARY KEY,
                content_platform_id INTEGER NOT NULL REFERENCES social_content_platforms(id) ON DELETE CASCADE,
                views_count BIGINT NOT NULL DEFAULT 0,
                likes_count BIGINT NOT NULL DEFAULT 0,
                comments_count BIGINT NOT NULL DEFAULT 0,
                shares_count BIGINT NOT NULL DEFAULT 0,
                followers_gained INTEGER NOT NULL DEFAULT 0,
                engagement_rate NUMERIC(6, 4) NOT NULL DEFAULT 0.0000,
                raw_metrics JSONB DEFAULT '{}'::jsonb,
                fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Constraints for social_analytics (prevent negative metric counts & invalid rates, unique snapshot)
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_sa_non_negative_views'
                ) THEN
                    ALTER TABLE social_analytics ADD CONSTRAINT chk_sa_non_negative_views CHECK (views_count >= 0);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_sa_non_negative_likes'
                ) THEN
                    ALTER TABLE social_analytics ADD CONSTRAINT chk_sa_non_negative_likes CHECK (likes_count >= 0);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_sa_non_negative_comments'
                ) THEN
                    ALTER TABLE social_analytics ADD CONSTRAINT chk_sa_non_negative_comments CHECK (comments_count >= 0);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_sa_non_negative_shares'
                ) THEN
                    ALTER TABLE social_analytics ADD CONSTRAINT chk_sa_non_negative_shares CHECK (shares_count >= 0);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_sa_engagement_rate_range'
                ) THEN
                    ALTER TABLE social_analytics ADD CONSTRAINT chk_sa_engagement_rate_range CHECK (engagement_rate >= 0.0000 AND engagement_rate <= 100.0000);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_social_analytics_snapshot'
                ) THEN
                    ALTER TABLE social_analytics ADD CONSTRAINT uq_social_analytics_snapshot UNIQUE (content_platform_id, fetched_at);
                END IF;
            END $$;
        """)

        # Indexes for social_analytics
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sa_content_platform_id ON social_analytics(content_platform_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sa_fetched_at ON social_analytics(fetched_at DESC);")

        # =====================================================================
        # 6. Table: oauth_states
        # Stores SHA-256 hashed state tokens with separate PK, consumed timestamp, and expiration
        # Never stores raw OAuth state tokens
        # =====================================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS oauth_states (
                id SERIAL PRIMARY KEY,
                state_hash VARCHAR(64) NOT NULL UNIQUE,
                user_id INTEGER NOT NULL REFERENCES user_master(user_id) ON DELETE CASCADE,
                platform VARCHAR(50) NOT NULL,
                redirect_uri TEXT,
                consumed_at TIMESTAMP WITH TIME ZONE,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Migrate oauth_states safely if created previously with old schema
        cur.execute("""
            ALTER TABLE oauth_states ADD COLUMN IF NOT EXISTS id SERIAL;
            ALTER TABLE oauth_states ADD COLUMN IF NOT EXISTS state_hash VARCHAR(64);
            ALTER TABLE oauth_states ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMP WITH TIME ZONE;
        """)

        cur.execute("""
            DO $$
            BEGIN
                -- Safely drop old PRIMARY KEY constraint on 'state' if present
                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'oauth_states'::regclass AND conname = 'oauth_states_pkey'
                ) THEN
                    -- Check if primary key is on 'state'
                    IF EXISTS (
                        SELECT 1 FROM information_schema.key_column_usage
                        WHERE table_name = 'oauth_states' AND constraint_name = 'oauth_states_pkey' AND column_name = 'state'
                    ) THEN
                        ALTER TABLE oauth_states DROP CONSTRAINT oauth_states_pkey;
                        ALTER TABLE oauth_states ALTER COLUMN state DROP NOT NULL;
                        ALTER TABLE oauth_states ADD PRIMARY KEY (id);
                    END IF;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'oauth_states'::regclass AND contype = 'p'
                ) THEN
                    ALTER TABLE oauth_states ADD PRIMARY KEY (id);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_oauth_states_platform'
                ) THEN
                    ALTER TABLE oauth_states
                    ADD CONSTRAINT chk_oauth_states_platform
                    CHECK (platform IN ('YOUTUBE', 'INSTAGRAM', 'FACEBOOK', 'META'));
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_oauth_states_state_hash'
                ) THEN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'oauth_states' AND column_name = 'state_hash'
                    ) THEN
                        ALTER TABLE oauth_states ADD CONSTRAINT uq_oauth_states_state_hash UNIQUE (state_hash);
                    END IF;
                END IF;
            END $$;
        """)

        # Indexes for oauth_states
        cur.execute("CREATE INDEX IF NOT EXISTS idx_oauth_states_hash ON oauth_states(state_hash);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_oauth_states_user_platform ON oauth_states(user_id, platform);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_oauth_states_expires_at ON oauth_states(expires_at);")

    finally:
        cur.close()
