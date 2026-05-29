-- problem_meta: one row per problem, used for paginated listing + filtering
CREATE TABLE IF NOT EXISTS problem_meta (
    problem_id      INTEGER PRIMARY KEY,
    slug            TEXT    NOT NULL UNIQUE,
    problem_name    TEXT    NOT NULL,
    difficulty      TEXT    CHECK (difficulty IN ('Easy', 'Medium', 'Hard', 'Basic', 'School')),
    marks           INTEGER,
    accuracy        NUMERIC(5, 2),
    all_submissions INTEGER,
    topics          TEXT[]  NOT NULL DEFAULT '{}',
    companies       TEXT[]  NOT NULL DEFAULT '{}',
    tags            TEXT[]  NOT NULL DEFAULT '{}',
    problem_url     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast single-column filter (difficulty is the primary filter in listings)
CREATE INDEX IF NOT EXISTS idx_problem_meta_difficulty
    ON problem_meta (difficulty);

-- GIN indexes so array @> operators stay fast even at 3 500+ rows
CREATE INDEX IF NOT EXISTS idx_problem_meta_topics
    ON problem_meta USING GIN (topics);

CREATE INDEX IF NOT EXISTS idx_problem_meta_companies
    ON problem_meta USING GIN (companies);

CREATE INDEX IF NOT EXISTS idx_problem_meta_tags
    ON problem_meta USING GIN (tags);


-- problem_latex: revision history of a problem's LaTeX statement
--   revision_number 1 = first authored version, increments on each edit
CREATE TABLE IF NOT EXISTS problem_latex (
    problem_id      INTEGER NOT NULL REFERENCES problem_meta (problem_id),
    revision_number INTEGER NOT NULL DEFAULT 1,
    latex           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (problem_id, revision_number)
);

-- Retrieve the current (latest) revision quickly
CREATE INDEX IF NOT EXISTS idx_problem_latex_latest
    ON problem_latex (problem_id, revision_number DESC);
