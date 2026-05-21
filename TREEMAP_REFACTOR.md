# Tree Map Coordinate Refactoring

## Overview
Consolidated all Tree Map coordinate conversion logic into the `palworld_coord` module, removing scattered offsets from multiple files.

## Changes

### 1. palworld_coord/__init__.py
Added constants and functions for Tree Map conversion:

```python
# Constants
__treemap_transl_x = 485699
__treemap_transl_y = 681305
__treemap_scale = 724
__treemap_pixel_offset_x = 1760
__treemap_pixel_offset_y = 2571
__treemap_cursor_offset_x = -1075
__treemap_cursor_offset_y = 1568
__treemap_coord_range = 2500

# Functions
sav_to_treemap(x, y) → Point  # Save coords to Tree Map coords
treemap_to_sav(x, y) → Point  # Reverse conversion
treemap_to_pixel(x, y, width, height) → (img_x, img_y)  # For marker positioning
treemap_pixel_to_cursor(img_x, img_y, width, height) → (x, y)  # For cursor display
```

### 2. map_tab.py
**Removed:**
- `MAP_TREEMAP_RANGE` constant (now uses `palworld_coord.__treemap_coord_range`)
- Pixel offset logic from `_to_image_coordinates` (now uses `palworld_coord.treemap_to_pixel`)

**Updated:**
- `_recalc_img_coords()` uses `palworld_coord.treemap_to_pixel()` for Tree Map markers
- `_get_players()` uses standard `_to_image_coordinates` (World Map only)

### 3. map_view.py
**Removed:**
- `tree_cursor_offset_x` and `tree_cursor_offset_y` attributes
- Offset calculation in `mouseMoveEvent`

**Updated:**
- Uses `palworld_coord.treemap_pixel_to_cursor()` for Tree Map cursor coordinates

### 4. map_generator.py
**Removed:**
- `tree_marker_offset_x`, `tree_marker_offset_y`, `tree_cursor_offset_x`, `tree_cursor_offset_y` variables
- Offset calculation in `to_image_coordinates()`

**Updated:**
- Uses `palworld_coord.treemap_to_pixel()` for Tree Map generation

## Benefits

### Centralized Logic
- All coordinate conversion math in one place
- Easy to adjust offsets and ranges
- Single source of truth for all Tree Map calculations

### Simplified Code
- Removed ~30 lines of offset math from 3 different files
- Each file now calls simple function instead of complex formulas
- Less code duplication

### Easier Maintenance
- Future changes only need updates in `palworld_coord/__init__.py`
- Clear separation between World Map and Tree Map logic
- Better testability

## Usage Examples

### Displaying Tree Map Coordinates
```python
import palworld_coord
pt = palworld_coord.sav_to_treemap(501113, -748595)
# Returns: Point(x=-1975, y=1363)
```

### Positioning Markers
```python
img_x, img_y = palworld_coord.treemap_to_pixel(-1975, 1363, 8192, 8192)
# Returns: (2620, 4433)
```

### Cursor Coordinates
```python
x, y = palworld_coord.treemap_pixel_to_cursor(2620, 4433, 8192, 8192)
# Returns: (-1975.88, 1362.31)
```

## Testing Verified
```bash
Raw (501113, -748595) → Tree coords (-1975, 1363) ✓
Tree coords (-1975, 1363) → Pixel (2620, 4433) ✓
Pixel (2620, 4433) → Cursor coords (-1975, 1363) ✓
```

## Critical Bug Fix
**Issue**: After refactoring, cursor showed wrong coordinates (-945, -461) instead of (-1975, 1363) when hovering over markers.

**Root Cause**: Duplicate code block in `map_view.py` (lines 255-283) was overwriting correct Tree Map coords with World Map formula.

**Solution**: Removed duplicate code block that used World Map's `2000/1000` range for all maps.

**Files Modified**
1. `src/palworld_aio/ui/map_view.py` - Removed duplicate cursor coordinate code

**Note**: This bug was introduced during the refactoring when code was consolidated, showing the importance of thorough testing after refactoring.

## Files Modified
1. `src/palworld_coord/__init__.py` - Added Tree Map functions and constants
2. `src/palworld_aio/ui/map_tab.py` - Removed offsets, uses palworld_coord functions
3. `src/palworld_aio/ui/map_view.py` - Removed offsets, uses palworld_coord.treemap_pixel_to_cursor()
4. `src/palworld_aio/map_generator.py` - Removed offsets, uses palworld_coord.treemap_to_pixel()

## Result
All Tree Map coordinate logic is now centralized in `palworld_coord`, making the codebase cleaner and more maintainable.