# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a LEGO® sorting machine that uses computer vision (YOLO segmentation models) and physical hardware (Arduino + motors/servos) to automatically sort LEGO pieces into bins based on their classification. The system consists of:

- **Python robot control system** (`robot/`): Core sorting logic, hardware interface, vision system, state machine
- **SvelteKit web UI** (`ui/`): Control interface for monitoring and managing the sorting system
- **YOLO labeling tool** (`yolo/labeler/`): SvelteKit app for creating training datasets
- **Arduino firmware** (`embedded/firmata/`): Firmata-based firmware for hardware control

## Recent Changes

**Set-Specific Sorting (Added)**: The system now supports sorting pieces for specific LEGO sets. Pieces belonging to active sets are routed to dedicated bins, while non-set pieces continue to use category-based sorting. See "Set-Specific Sorting System" section below for details.

## Development Commands

### Python Robot System

The robot system requires Python with dependencies from `robot/requirements.txt`. Note that pyFirmata must be installed from source (not pip) as documented in `setup.md`.

**Environment Setup:**
- Set `MC_PATH` environment variable to Arduino device path (e.g., `/dev/cu.usbmodem14201`)
- Optional: Set `DEBUG=1` for debug logging

**Running the system:**
```bash
# Full run with all systems enabled
make run
# or directly:
./robot/run.sh -y --dump --use_prev_bin_state

# Run with specific systems disabled
make conveyor    # Disable feeder conveyor, vibration hopper, distribution
make feeder      # Disable main conveyor
make no-distribution  # Disable distribution only

# Test individual components
python robot/test_motors.py
python robot/test_servos.py
python robot/test_yolo.py
```

**Code quality:**
```bash
make check       # Type check with pyright
make format      # Format Python code with ruff
make vulture     # Find dead code
```

**Database:**
```bash
make migrate     # Run database migrations
make db          # Open SQLite3 shell
```

### Web UI

The UI is a SvelteKit application in `ui/`:

```bash
cd ui
npm install
npm run dev           # Development server
npm run build         # Production build
npm run check         # Type check
npm run typecheck     # Type check with errors only
npm run format        # Format with Prettier
```

**Generate API types from backend:**
```bash
make generate
# or directly:
cd ui && npx openapi-typescript http://localhost:8000/openapi.json -o src/lib/api-types.ts
```
This requires the Python backend to be running on port 8000.

### YOLO Labeling Tool

The labeling tool is in `yolo/labeler/`:

```bash
cd yolo/labeler
npm install
npm run dev       # Development server
npm run build     # Production build
npm run check     # Type check
```

### Arduino Firmware

Setup and compilation instructions are in `setup.md`. The firmware uses Firmata with custom extensions.

## Architecture

### Python Robot System (`robot/`)

**Entry Point:**
- `main.py`: Initializes global config, IRL (In Real Life) system interface, controller, and FastAPI server

**Core Components:**

1. **Controller** (`controller.py`): Main orchestrator that manages system lifecycle
   - Initializes hardware (servos to correct positions)
   - Manages database/blob storage
   - Runs the sorting state machine
   - Broadcasts system status via WebSocket every 500ms
   - Handles pause/resume/run commands

2. **Global Config** (`global_config.py`): Central configuration via CLI arguments and TypedDict
   - Hardware settings (servo angles, motor speeds, timing parameters)
   - YOLO model paths (separate models for main and feeder cameras)
   - Debug/profiling/preview flags
   - Disable flags for testing individual subsystems

3. **IRL System Interface** (`irl/config.py`): Hardware abstraction layer
   - Arduino communication via pyFirmata
   - Motor control (DC motors via PCA9685 for conveyors/hoppers)
   - Servo control (distribution system doors)
   - Camera management (main + feeder cameras)
   - Encoder for position tracking

4. **Vision System** (`vision_system.py`): Computer vision using YOLO11 segmentation
   - Dual camera system (main conveyor + feeder)
   - Separate YOLO models for each camera
   - Threaded processing for real-time performance
   - Detects objects and regions (feeders, conveyors)
   - Tracks object positions and determines when centered

5. **Sorting State Machine** (`sorting_state_machine.py`): Five-state FSM
   - States in `states/` directory:
     - `GETTING_NEW_OBJECT_FROM_FEEDER`: Controls vibration hoppers and feeder conveyor
     - `WAITING_FOR_OBJECT_TO_APPEAR_UNDER_MAIN_CAMERA`: Detects object arrival
     - `WAITING_FOR_OBJECT_TO_CENTER_UNDER_MAIN_CAMERA`: Ensures proper positioning
     - `CLASSIFYING`: Captures frames and sends to classification API (Brickognize)
     - `SENDING_OBJECT_TO_BIN`: Opens appropriate bin door based on classification
   - Each state implements `IStateMachine` interface with `step()` and `cleanup()` methods

6. **Bin State Tracker** (`bin_state_tracker.py`): Manages bin capacity and assignments
   - Tracks which categories map to which physical bins
   - Handles bin fullness
   - Can persist/restore state across runs

7. **Sorting Profiles** (`sorting/`): Define how pieces are categorized
   - `bricklink_categories_sorting_profile.py`: Maps BrickLink categories to bins
   - `piece_sorting_profile.py`: Per-piece sorting logic
   - Pluggable system via `SortingProfile` interface

8. **API Server** (`api/server.py`): FastAPI REST + WebSocket interface
   - Control endpoints: `/pause`, `/resume`, `/run`
   - Status endpoints: `/bin-state`, `/irl-runtime-params`
   - BrickLink integration: `/bricklink/part/{part_id}/`
   - WebSocket for real-time updates

9. **Storage** (`storage/`):
   - SQLite3 database for metadata
   - Blob storage for images/videos
   - Migration system

### Web UI (`ui/`)

SvelteKit 2 application with:
- **API Client** (`src/lib/api-client.ts`): OpenAPI-typed client for backend
- **WebSocket Integration** (`src/lib/types/websocket.ts`): Real-time system status
- **User Settings** (`src/lib/stores/user-settings.svelte.ts`): Svelte 5 runes-based state
- Tailwind CSS for styling

### YOLO Labeling Tool (`yolo/labeler/`)

SvelteKit app for creating polygon annotations:
- Camera utilities for image capture
- Polygon drawing and editing
- Dataset management (API routes in `src/routes/api/`)
- Export labels for YOLO training

## Important Implementation Details

### Hardware Timing and Coordination

- The system uses careful timing (delays, durations) defined in `GlobalConfig` for servo movements, door operations, motor pulses
- Servos may need commands sent twice due to power delivery issues (see `controller._initHardware()`)
- There's a mandatory delay between Firmata commands (`delay_between_firmata_commands_ms`)

### Vision System

- Uses two separate YOLO models (one per camera) with different weight files
- Model paths are hardcoded in `global_config.py` and need updating for your environment
- Classes: 0=object, 1=first_feeder, 2=second_feeder, 3=main_conveyor, 4=feeder_conveyor
- Maintains frame history (30 frames) for classification
- Performance metrics tracked for monitoring

### State Machine Flow

The sorting process follows a strict sequence:
1. Vibration hoppers pulse to move a single piece onto feeder conveyor
2. Feeder camera detects when piece reaches end of feeder
3. Piece transfers to main conveyor
4. Main camera detects piece arrival and waits for centering
5. Captures multiple frames, sends to Brickognize API for classification
6. Uses encoder to calculate when piece reaches correct distribution module
7. Opens appropriate bin door to sort the piece

### Disabling Systems for Testing

The `--disable` flag is crucial for development:
- Test conveyors without distribution system
- Test vision without motor movement
- Test feeders independently
- Enables safe incremental testing

### Camera Setup

- Uses Logitech BRIO/Pro 4k Webcam
- Focus must be manually set via Logitech G HUB before running
- Two cameras: main conveyor (top-down) + feeder (side view)

### Type Safety

- Python uses TypedDict extensively for configuration and interfaces
- UI uses OpenAPI-generated types from backend
- Run `make generate` after backend API changes to update frontend types

## Set-Specific Sorting System

The system supports sorting pieces for specific LEGO sets while maintaining category-based sorting for other pieces.

### Architecture Overview

**Flow:**
```
Piece Classification
  ↓
Check if piece belongs to active set(s)
  ├─ YES → Route to set-specific bin → Track quantity found
  └─ NO  → Route to category bin (existing behavior)
```

**Key Components:**

1. **Rebrickable API Integration** (`robot/external/rebrickable/`)
   - Fetches set information and inventories from Rebrickable
   - `RebrickableClient` handles API requests with rate limiting
   - Set inventories cached in local database after first fetch

2. **Set Manager** (`robot/set_manager.py`)
   - `add_set(set_num)`: Fetch set from Rebrickable and sync inventory to database
   - `activate_set(set_id, priority)`: Mark set as active for current run
   - `deactivate_set(set_id)`: Remove set from active sorting
   - `check_piece_in_sets(item_id, color_id)`: Check if piece belongs to active sets
   - `increment_piece_found(set_id, item_id)`: Track when set pieces are found
   - `get_set_progress(set_id)`: Get completion percentage and statistics

3. **Set-Aware Sorting Profile** (`robot/sorting/set_aware_sorting_profile.py`)
   - Extends `PieceSortingProfile` with set awareness
   - `get_destination(item_id, color_id)` returns either:
     - `(None, SetDestination)` for set pieces
     - `(category_id, None)` for non-set pieces
   - Priority handling: When piece matches multiple sets, uses highest priority

4. **Bin State Tracker Extensions** (`robot/bin_state_tracker.py`)
   - `reserve_bins_for_set(set_id, num_bins)`: Reserve bins for a set
   - `release_set_bins(set_id)`: Free bins when set is deactivated
   - `find_bin_for_set_piece(set_id)`: Find appropriate bin for set pieces
   - Bins use category format `"set:{set_id}"` to distinguish from regular categories

5. **Modified Classification Flow** (`robot/states/classifying.py`)
   - `_determineBinCoordinates()` now checks for set membership first
   - Records quantity found in database when set piece is sorted
   - Falls back to category sorting for non-set pieces

### Database Schema

**Tables:**
- `lego_sets`: Set definitions (set_id, name, year, theme, num_parts, img_url)
- `set_inventories`: Parts per set (set_id, item_id, color_id, quantity_needed, quantity_found)
- `active_sorting_sets`: Currently active sets (run_id, set_id, priority, reserved_bins)
- `set_piece_observations`: Links observations to sets for tracking

**Migration:** `robot/storage/sqlite3/migrations/011_create_set_tables.sql`

### API Endpoints

All endpoints at `/sets/*`:

- `GET /sets/search?query={query}`: Search Rebrickable for sets
- `POST /sets/add?set_num={set_num}`: Add set to database and sync inventory
- `POST /sets/activate`: Activate set for sorting (body: `{set_num, priority}`)
- `DELETE /sets/{set_id}/deactivate`: Deactivate set
- `GET /sets/active`: Get all active sets with progress
- `GET /sets/{set_id}/progress`: Get detailed progress for one set
- `GET /sets/{set_id}/inventory`: Get full inventory with found counts

### WebSocket Messages

**Set Progress Updates:**
```json
{
  "type": "set_progress",
  "sets": [{
    "set_id": "75192-1",
    "name": "Millennium Falcon",
    "total_parts_needed": 7541,
    "total_parts_found": 342,
    "completion_percentage": 4.5
  }]
}
```

**Set Piece Found:**
```json
{
  "type": "set_piece_found",
  "set_id": "75192-1",
  "item_id": "3001",
  "quantity_found": 3,
  "quantity_needed": 8
}
```

### Configuration

**Environment Variables:**
- `REBRICKABLE_API_KEY`: Required for Rebrickable API access (get free key at rebrickable.com)

**GlobalConfig additions needed (if not using defaults):**
- `max_active_sets`: Maximum simultaneous active sets (default: 5)
- `bins_per_set`: Bins to reserve per set (default: 2)

### Usage Example

**Python API:**
```python
from robot.set_manager import SetManager
from robot.global_config import buildGlobalConfig

gc = buildGlobalConfig()
set_mgr = SetManager(gc)

# 1. Search for sets on Rebrickable
results = set_mgr.search_sets("Millennium Falcon")
print(f"Found {len(results)} sets")

# 2. Add a set to database (fetches inventory from Rebrickable)
set_id = set_mgr.add_set("75192-1")  # Millennium Falcon
# This syncs ~7500 parts from Rebrickable to local database

# 3. Activate set for sorting (higher priority = preferred when piece matches multiple sets)
set_mgr.activate_set(set_id, priority=1)

# 4. Check which sets are active
active_sets = set_mgr.get_active_sets()
for s in active_sets:
    print(f"{s['name']}: {s['completion_percentage']:.1f}% complete")

# 5. Get detailed progress for a specific set
progress = set_mgr.get_set_progress(set_id)
print(f"Found {progress['total_parts_found']} of {progress['total_parts_needed']} pieces")
print(f"Completed {progress['complete_part_types']} of {progress['total_unique_parts']} part types")

# 6. When done, deactivate the set
set_mgr.deactivate_set(set_id)
```

**REST API:**
```bash
# Search for sets
curl "http://localhost:8000/sets/search?query=75192"

# Add a set
curl -X POST "http://localhost:8000/sets/add?set_num=75192-1"

# Activate for sorting
curl -X POST "http://localhost:8000/sets/activate" \
  -H "Content-Type: application/json" \
  -d '{"set_num": "75192-1", "priority": 1}'

# Get active sets
curl "http://localhost:8000/sets/active"

# Get progress
curl "http://localhost:8000/sets/75192-1/progress"

# Deactivate
curl -X DELETE "http://localhost:8000/sets/75192-1/deactivate"
```

### Multiple Set Handling

- **Priority System**: When a piece matches multiple active sets, the highest priority set gets the piece
- **Bin Allocation**: Each active set reserves 2 bins by default (configurable)
- **Dynamic Allocation**: If reserved bins are full, system dynamically allocates new bins
- **Fallback**: If no bins available, pieces go to fallback bin

### Implementation Notes

**Part ID Mapping:**
- Rebrickable and BrickLink use different part numbering systems
- Current implementation uses Rebrickable IDs directly
- TODO: Implement proper Rebrickable→BrickLink ID mapping for accurate matching
- Mapping can be done via Rebrickable's `/parts/{part_num}/` endpoint which includes BrickLink IDs

**Performance Considerations:**
- Set inventories are cached locally after first fetch (stored in `set_inventories` table)
- Only re-sync when explicitly requested or set is added
- Database queries optimized with indexes on `item_id` and `color_id`

**Testing Without Hardware:**
- Use `--disable distribution` to test set logic without physical bins
- Check database directly: `sqlite3 database.db "SELECT * FROM set_inventories WHERE set_id='75192-1' LIMIT 10;"`

### Frontend Integration (To Be Implemented)

**Recommended UI Components:**
1. Set search modal with Rebrickable search
2. Active sets list showing progress bars
3. Set inventory viewer with checkmarks for found pieces
4. Real-time WebSocket updates for piece discoveries
