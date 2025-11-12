# Sorter
## A LEGO® Sorting Machine

An automated LEGO sorting system that uses computer vision (YOLO segmentation) and physical hardware (Arduino, conveyors, servos) to sort LEGO pieces into bins. The system supports both **category-based sorting** (e.g., all round bricks together) and **set-specific sorting** (e.g., pieces for specific LEGO sets like 75192 Millennium Falcon).

[More details](https://basically.website/sorter-v1)

[demo1](https://www.youtube.com/shorts/IlnTYL_7sjE)

[demo2](https://www.youtube.com/shorts/xnIVpVIdlaA)

## Features

- **Computer Vision**: YOLO11 segmentation models for object detection and tracking
- **AI Classification**: Integration with Brickognize API for LEGO piece identification
- **Set-Specific Sorting**: Sort pieces for specific LEGO sets while maintaining category sorting for others
- **Multi-Set Support**: Sort for multiple sets simultaneously with priority handling
- **Real-Time Tracking**: WebSocket-based progress updates and live camera feeds
- **Web UI**: SvelteKit-based control interface
- **Persistent State**: SQLite database for tracking bins, pieces, and set progress

## Quick Start

### Prerequisites

- Python 3.x with dependencies from `robot/requirements.txt`
- Node.js for the web UI
- **Hardware controller** (choose one):
  - **Arduino** with Firmata firmware (recommended, see `setup.md`)
  - **Raspberry Pi** with direct GPIO control (alternative, see `HARDWARE_OPTIONS.md`)
- Rebrickable API key for set-specific sorting (free at [rebrickable.com](https://rebrickable.com))

### Environment Setup

```bash
# Set Arduino device path
export MC_PATH="/dev/cu.usbmodem14201"  # Your Arduino path

# Optional: For set-specific sorting
export REBRICKABLE_API_KEY="your_key_here"

# Optional: Enable debug logging
export DEBUG=1
```

### Running the System

```bash
# Run database migrations
make migrate

# Start the robot system
make run

# In another terminal, start the web UI
cd ui
npm install
npm run dev
```

Visit `http://localhost:5173` to access the control interface.

## Set-Specific Sorting Workflow

The system can sort pieces for specific LEGO sets. Here's a complete workflow:

### 1. Search for a Set

**Via API:**
```bash
curl "http://localhost:8000/sets/search?query=Millennium Falcon"
```

**Via Python:**
```python
from robot.set_manager import SetManager
from robot.global_config import buildGlobalConfig

gc = buildGlobalConfig()
set_mgr = SetManager(gc)

results = set_mgr.search_sets("Millennium Falcon")
```

### 2. Add Set to Database

This fetches the set's inventory from Rebrickable and stores it locally:

```bash
curl -X POST "http://localhost:8000/sets/add?set_num=75192-1"
```

Or in Python:
```python
set_id = set_mgr.add_set("75192-1")  # Syncs ~7500 parts for Millennium Falcon
```

### 3. Activate Set for Sorting

Start sorting pieces for this set:

```bash
curl -X POST "http://localhost:8000/sets/activate" \
  -H "Content-Type: application/json" \
  -d '{"set_num": "75192-1", "priority": 1}'
```

Or in Python:
```python
set_mgr.activate_set(set_id, priority=1)
```

**Priority**: When a piece matches multiple active sets, the highest priority set gets the piece.

### 4. Monitor Progress

**Get all active sets:**
```bash
curl "http://localhost:8000/sets/active"
```

**Get specific set progress:**
```bash
curl "http://localhost:8000/sets/75192-1/progress"
```

In Python:
```python
# All active sets
active_sets = set_mgr.get_active_sets()
for s in active_sets:
    print(f"{s['name']}: {s['completion_percentage']:.1f}% complete")

# Detailed progress
progress = set_mgr.get_set_progress(set_id)
print(f"Found {progress['total_parts_found']} of {progress['total_parts_needed']} pieces")
```

### 5. Real-Time Updates

The system broadcasts WebSocket messages when set pieces are found:

```json
{
  "type": "set_piece_found",
  "set_id": "75192-1",
  "item_id": "3001",
  "quantity_found": 3,
  "quantity_needed": 8
}
```

### 6. Deactivate When Done

```bash
curl -X DELETE "http://localhost:8000/sets/75192-1/deactivate"
```

Or in Python:
```python
set_mgr.deactivate_set(set_id)
```

## How Set Sorting Works

1. **Classification**: Piece is identified using Brickognize AI
2. **Set Check**: System checks if piece belongs to any active set
3. **Routing**:
   - If **in active set** → Routes to set-specific bin
   - If **not in set** → Routes to category bin (normal behavior)
4. **Tracking**: Quantity found is incremented in database
5. **Progress**: Real-time updates sent via WebSocket

## Architecture

- **`robot/`**: Python control system (FastAPI, computer vision, hardware control)
- **`ui/`**: SvelteKit web interface
- **`yolo/labeler/`**: Tool for creating YOLO training datasets
- **`embedded/firmata/`**: Arduino firmware

See `CLAUDE.md` for detailed architecture documentation.

## Development

```bash
# Type checking
make check

# Format code
make format

# Run with specific systems disabled (for testing)
make feeder       # Disable main conveyor
make conveyor     # Disable feeder systems
make no-distribution  # Disable distribution

# Database
make migrate      # Run migrations
make db          # Open SQLite shell

# Generate TypeScript types from backend
make generate
```

## Configuration

Key settings in `robot/global_config.py`:
- Camera indices and YOLO model paths
- Motor speeds and timing parameters
- Servo angles for doors
- System enable/disable flags

## Testing

### Test Set-Specific Sorting

Run the comprehensive test suite:

```bash
# Set API key first
export REBRICKABLE_API_KEY="your_key_here"

# Run tests
python robot/test_set_sorting.py
```

This tests:
- ✓ Database migration
- ✓ Rebrickable API connection
- ✓ SetManager operations (search, add, activate, deactivate)
- ✓ Sorting profile integration
- ✓ API endpoints

### Test Without Hardware

```bash
./robot/run.sh --disable distribution -y
```

This runs the vision and classification systems without actuating physical hardware.

### Test With Set Sorting Enabled

```bash
# Enable set-specific sorting
./robot/run.sh --enable-set-sorting -y
```

Then use the API or web UI to activate sets.

## Documentation

- **CLAUDE.md**: Complete architecture and implementation guide
- **setup.md**: Arduino hardware setup instructions
- **HARDWARE_OPTIONS.md**: Arduino vs Raspberry Pi comparison and setup
- **SET_SORTING_QUICKSTART.md**: Testing guide for set-specific sorting
- **API docs**: Available at `http://localhost:8000/docs` when running
