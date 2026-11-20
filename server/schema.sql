CREATE TABLE IF NOT EXISTS scores (
  user    TEXT PRIMARY KEY,   -- X-Badge-User: the badge owner's id
  badge   TEXT NOT NULL,      -- X-Badge-Id (emulators start with "e")
  name    TEXT NOT NULL,      -- what the player chose to show
  score   INTEGER NOT NULL,   -- best "ms saved"
  lap     INTEGER NOT NULL,   -- lap reached in that run
  tunnels INTEGER NOT NULL,
  runs    INTEGER NOT NULL DEFAULT 0,
  at      INTEGER NOT NULL    -- unix ms of the best score
);
CREATE INDEX IF NOT EXISTS scores_by_score ON scores (score DESC, at ASC);
CREATE TABLE IF NOT EXISTS daily (
  day   INTEGER NOT NULL,     -- UTC day number (unix ms / 86400000)
  user  TEXT NOT NULL,
  name  TEXT NOT NULL,
  score INTEGER NOT NULL,
  lap   INTEGER NOT NULL,
  at    INTEGER NOT NULL,
  PRIMARY KEY (day, user)
);
CREATE INDEX IF NOT EXISTS daily_by_score ON daily (day, score DESC, at ASC);
