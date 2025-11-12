# Set-Specific Sorting - Quick Start Guide

## ⚡ TL;DR - Get Started in 3 Minutes

```bash
# 1. Set your Rebrickable API key
export REBRICKABLE_API_KEY="your_key_here"

# 2. Run database migrations
make migrate

# 3. Test the system
python robot/test_set_sorting.py

# 4. Run with set sorting enabled
./robot/run.sh --enable-set-sorting -y
```

## 🧪 Testing Checklist

Before using set-specific sorting with hardware, verify:

- [ ] Database migration completed (`make migrate`)
- [ ] Rebrickable API key is set (`echo $REBRICKABLE_API_KEY`)
- [ ] Test script passes (`python robot/test_set_sorting.py`)
- [ ] Can search for sets via API
- [ ] Can add a test set
- [ ] Can activate/deactivate sets

## 🚀 What's Ready to Test

### ✅ **Backend (100% Complete)**

1. **Database Schema** - 4 new tables for sets, inventories, tracking
2. **Rebrickable API Client** - Search sets, fetch inventories with caching
3. **Set Manager** - Add, activate, track progress for sets
4. **Set-Aware Sorting** - Routes pieces to set bins or category bins
5. **Bin Management** - Reserves bins for sets, handles dynamic allocation
6. **REST API** - 7 endpoints for set operations
7. **WebSocket Updates** - Real-time progress broadcasts
8. **Classification Integration** - Checks set membership during sorting

### ⚠️ **Known Limitations**

1. **Part ID Mapping**: Currently uses Rebrickable IDs directly
   - Your Brickognize classification returns BrickLink IDs
   - **TODO**: Map Rebrickable IDs ↔ BrickLink IDs for accurate matching
   - Can be done via Rebrickable's `/parts/{part_num}/` endpoint

2. **UI Not Implemented**: Backend is complete, but no web interface yet
   - Use REST API or Python directly for now
   - See workflow examples in README.md

## 📝 Test Workflow

### 1. Run the Test Script

```bash
export REBRICKABLE_API_KEY="your_key"
python robot/test_set_sorting.py
```

Expected output:
```
✓ Testing imports...
✓ Testing database migration...
✓ Testing Rebrickable API...
✓ Testing SetManager...
✓ Testing SetAwareSortingProfile...
✓ Testing API endpoints...

Result: 6/6 tests passed
```

### 2. Test API Endpoints Manually

```bash
# Start the system (in one terminal)
./robot/run.sh --enable-set-sorting -y

# In another terminal:

# Search for a set
curl "http://localhost:8000/sets/search?query=21318"

# Add the set
curl -X POST "http://localhost:8000/sets/add?set_num=21318-1"

# Activate it
curl -X POST "http://localhost:8000/sets/activate" \
  -H "Content-Type: application/json" \
  -d '{"set_num": "21318-1", "priority": 1}'

# Check active sets
curl "http://localhost:8000/sets/active"

# Check progress
curl "http://localhost:8000/sets/21318-1/progress"
```

### 3. Test With Python

```python
from robot.set_manager import SetManager
from robot.global_config import buildGlobalConfig

gc = buildGlobalConfig()
set_mgr = SetManager(gc)

# Search
results = set_mgr.search_sets("Tree House")
print(f"Found {len(results)} sets")

# Add small set for testing
set_id = set_mgr.add_set("21318-1")  # Tree House (~3000 pieces)

# Activate
set_mgr.activate_set(set_id, priority=1)

# Check what's active
active = set_mgr.get_active_sets()
print(active[0]['name'], active[0]['total_parts_needed'], "parts")

# Get progress
progress = set_mgr.get_set_progress(set_id)
print(f"{progress['completion_percentage']:.1f}% complete")

# Deactivate
set_mgr.deactivate_set(set_id)
```

## 🔧 Troubleshooting

### "REBRICKABLE_API_KEY not set"

```bash
# Get free API key at rebrickable.com
export REBRICKABLE_API_KEY="your_key_here"

# Make permanent (add to ~/.bashrc or ~/.zshrc):
echo 'export REBRICKABLE_API_KEY="your_key_here"' >> ~/.bashrc
```

### "Migration failed" or "Tables don't exist"

```bash
# Run migrations explicitly
cd robot
python storage/sqlite3/migrate.py

# Check tables exist
sqlite3 ../database.db "SELECT name FROM sqlite_master WHERE type='table';"
# Should show: lego_sets, set_inventories, active_sorting_sets, set_piece_observations
```

### "No category mappings loaded"

This means your database doesn't have piece data yet. The system will still work for set-specific sorting, but non-set pieces won't have category fallbacks.

To populate:
1. Run the system and let it classify pieces
2. Pieces will be added to database automatically
3. Or manually populate from BrickLink data

### "Piece ID not matching"

**This is expected!** Current limitation:
- Classification returns: BrickLink IDs (e.g., "3001")
- Rebrickable uses: Different IDs (e.g., "300126")

**Workaround**: Add manual ID mapping or implement the mapping logic using Rebrickable's external_ids field.

## 🎯 Testing Strategy

### Phase 1: Software Only (No Hardware)

```bash
# Run with distribution disabled
./robot/run.sh --enable-set-sorting --disable distribution -y

# Add and activate a set via API
# Manually trigger classification of known pieces
# Verify routing logic in logs
```

### Phase 2: With Hardware (Dry Run)

```bash
# Use a small set (100-200 pieces)
# Activate only 1 set
# Verify:
#   - Bins are reserved correctly
#   - Set pieces go to set bins
#   - Non-set pieces go to category bins
#   - Progress tracking is accurate
```

### Phase 3: Production (Multiple Sets)

```bash
# Activate 2-3 sets with different priorities
# Test priority handling when piece matches multiple sets
# Monitor bin allocation as sets fill up
# Test deactivation and bin release
```

## 📊 What to Monitor

When testing with real sorting:

1. **Log Messages** - Look for:
   - "Using set-aware sorting profile"
   - "Piece X belongs to set: Y"
   - "Assigned set piece X to bin..."
   - "Recorded piece X found for set Y"

2. **Database** - Check quantities:
   ```sql
   SELECT set_id, SUM(quantity_found), SUM(quantity_needed)
   FROM set_inventories
   GROUP BY set_id;
   ```

3. **API Progress** - Should increment in real-time:
   ```bash
   watch -n 1 "curl -s http://localhost:8000/sets/active | jq"
   ```

4. **Bin State** - Set bins should show `"set:75192-1"` format

## 🎉 Success Criteria

You're ready to use set-specific sorting when:

- ✅ All tests pass
- ✅ Can search and add sets
- ✅ Can activate/deactivate sets
- ✅ Set pieces route to correct bins
- ✅ Non-set pieces still sort by category
- ✅ Progress tracking updates correctly
- ✅ Multiple sets work with priority

## 🐛 Found a Bug?

Common areas to check:

1. **Set Manager** (`robot/set_manager.py`) - Database operations
2. **Sorting Profile** (`robot/sorting/set_aware_sorting_profile.py`) - Routing logic
3. **Bin Tracker** (`robot/bin_state_tracker.py`) - Bin allocation
4. **Classification** (`robot/states/classifying.py`) - Set checking
5. **API Endpoints** (`robot/api/server.py`, `robot/api/client.py`) - REST interface

Check logs with `DEBUG=1` for detailed output.

## 📚 More Documentation

- **README.md** - Full workflow with examples
- **CLAUDE.md** - Complete architecture and implementation details
- **API Docs** - `http://localhost:8000/docs` when running
