-- Create lego_sets table to store LEGO set definitions
CREATE TABLE IF NOT EXISTS lego_sets (
    set_id TEXT PRIMARY KEY,  -- e.g., "75192-1" (Rebrickable format includes variant)
    set_num TEXT NOT NULL,     -- e.g., "75192" (without variant)
    name TEXT NOT NULL,        -- e.g., "Millennium Falcon"
    year INTEGER,
    theme TEXT,
    num_parts INTEGER,
    set_img_url TEXT,
    rebrickable_url TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Create set_inventories table to track which pieces belong to which sets
CREATE TABLE IF NOT EXISTS set_inventories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id TEXT NOT NULL,
    item_id TEXT NOT NULL,              -- BrickLink part ID
    color_id TEXT,                      -- BrickLink color ID
    quantity_needed INTEGER NOT NULL,   -- How many of this piece the set needs
    quantity_found INTEGER DEFAULT 0,   -- How many we've found during sorting
    is_spare BOOLEAN DEFAULT 0,         -- Whether this is a spare piece
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (set_id) REFERENCES lego_sets(set_id) ON DELETE CASCADE,
    UNIQUE(set_id, item_id, color_id)   -- One entry per unique piece+color per set
);

-- Create index for faster lookups when checking if a piece belongs to a set
CREATE INDEX IF NOT EXISTS idx_set_inventories_item_color
    ON set_inventories(item_id, color_id);

-- Create active_sorting_sets table to track which sets are currently being sorted
CREATE TABLE IF NOT EXISTS active_sorting_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,               -- Links to the current sorting run
    set_id TEXT NOT NULL,
    priority INTEGER DEFAULT 0,         -- Higher priority = preferred when piece matches multiple sets
    reserved_bins TEXT,                 -- JSON array of reserved bin coordinates: [[dm_idx, bin_idx], ...]
    enabled_at INTEGER NOT NULL,
    disabled_at INTEGER,                -- NULL if still active
    created_at INTEGER NOT NULL,
    FOREIGN KEY (set_id) REFERENCES lego_sets(set_id) ON DELETE CASCADE
);

-- Create index for finding active sets in current run
CREATE INDEX IF NOT EXISTS idx_active_sorting_sets_run
    ON active_sorting_sets(run_id, disabled_at);

-- Create set_piece_observations table to link observations to sets
CREATE TABLE IF NOT EXISTS set_piece_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL,    -- Links to observations table
    set_id TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (set_id) REFERENCES lego_sets(set_id) ON DELETE CASCADE
);

-- Create index for faster lookups of set-specific observations
CREATE INDEX IF NOT EXISTS idx_set_piece_observations_set
    ON set_piece_observations(set_id);
CREATE INDEX IF NOT EXISTS idx_set_piece_observations_observation
    ON set_piece_observations(observation_id);
