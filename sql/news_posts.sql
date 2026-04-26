CREATE TABLE IF NOT EXISTS news_posts (
    id bigserial PRIMARY KEY,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    published_at timestamp with time zone,
    day_of_week integer NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    topic_category text NOT NULL CHECK (topic_category IN ('roadmap', 'ai_tools', 'tip', 'user_case', 'behind_scenes', 'industry_news', 'light')),
    title text NOT NULL,
    body text NOT NULL,
    image_url text,
    image_prompt text,
    status text NOT NULL CHECK (status IN ('draft', 'approved', 'rejected', 'published', 'failed')),
    telegram_message_id bigint,
    admin_decision_at timestamp with time zone,
    rejection_reason text
);

CREATE INDEX IF NOT EXISTS idx_news_posts_status ON news_posts (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_posts_topic ON news_posts (topic_category, created_at DESC);
