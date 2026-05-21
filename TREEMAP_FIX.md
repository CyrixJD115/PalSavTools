# Tree Map Coordinate System Fix

## Problem
Palworld added a second map (Tree Map / World Tree) that uses:
- Different coordinate conversion formula
- Different pixel offset on the image
- Z-based filtering (ground bases vs sky islands)
- Both 8192x8192 images, but Tree Map coords extend beyond the -1000 to 1000 range

## Changes Made

### 1. Coordinate Conversion (`palworld_coord/__init__.py`)
```python
# Added Tree Map conversion functions
__treemap_transl_x = 485699
__treemap_transl_y = 681305
__treemap_scale = 724

def sav_to_treemap(x, y) → Point(x, y)
# Converts raw save coords to in-game Tree Map coords
# Example: (501113, -748595) → (-1975, 1363)

def treemap_to_sav(x, y) → Point(x, y)
# Reverse conversion
```

### 2. Map Viewer Toggle (`map_tab.py`)
```python
# Added constants
MAP_Z_THRESHOLD = 5000  # Z height filter
MAP_TREEMAP_RANGE = 2500  # Coordinate range (-2500 to 2500)

# Added toggle button between World Map and Tree Map
toggle_map_type → switches maps and recalculates coordinates

# Added _recalc_img_coords() method
# - Recalculates marker positions when switching maps
# - Converts coords using appropriate formula (World vs Tree)
# - Updates display coords to match in-game
```

### 3. Pixel Position Offset (`map_tab.py`)
```python
def _to_image_coordinates(x, y, width, height, coord_range, is_tree):
    if is_tree:
        # Apply Tree Map pixel offset
        img_x += 1760
        img_y += 2571
```
- Tree Map image origin is offset relative to coordinate system
- Markers need +1760 pixels in X, +2571 pixels in Y to appear in correct position
- Example: Coords (-1975, 1363) → Pixel (2620, 4433)

### 4. Cursor Coordinate Display (`map_view.py`)
```python
if self.current_map == 'tree':
    x_world = img_x / width * 5000 - 2500 - 1075
    y_world = 2500 - img_y / height * 5000 + 1568
```
- Cursor shows different coords at the same pixel position
- Offset (-1075, 1568) ensures cursor at marker shows matching display coords
- Example: Pixel (2620, 4433) → Cursor shows (-1975, 1363)

### 5. Generate Map Support (`map_generator.py`)
```python
# Added map_type parameter
generate_world_map(output_path, map_type='world'|'tree')

# Generates both World Map and Tree Map images
# - Uses treemap_to_treemap conversion for Tree Map
# - Applies same pixel offset
# - Filters bases by Z threshold
```

### 6. Z-Based Filtering
```python
# World Map: Show bases with Z < 5000 (ground level)
# Tree Map: Show bases with Z >= 5000 (sky islands)

if map_type == 'world' and base_z >= 5000: continue
if map_type == 'tree' and base_z < 5000: continue
```

## Key Discoveries

### Translation Values
- Initial reverse-engineer: (467404, 757500, 724) → Wrong
- Calculated from player data: (485699, 681305, 724) → Correct for display

### Pixel Offset
- Test coordinates showed marker at wrong pixel position
- Calculated offset from actual vs expected pixel positions
- Marker offset: (1760, 2571) pixels
- Cursor offset: (-1075, 1568) coords

### Coordinate Range
- World Map: -1000 to 1000
- Tree Map: -2500 to 2500 (extended for sky islands)

## Files Modified
1. `src/palworld_coord/__init__.py` - Coordinate conversion functions
2. `src/palworld_aio/ui/map_tab.py` - Toggle, recalc, pixel offset
3. `src/palworld_aio/ui/map_view.py` - Cursor display with offset
4. `src/palworld_aio/map_generator.py` - Generate both maps
5. `src/palworld_aio/ui/main_window.py` - Calls generate for both types

## Final Result
- Display coords match in-game (-1975, 1363) ✓
- Markers appear at correct pixel positions (2620, 4433) ✓
- Cursor at marker shows matching coords ✓
- Generate Map produces both World and Tree images correctly ✓
- Z-based filtering separates ground vs sky bases ✓

## Refactoring
All Tree Map coordinate logic consolidated into `palworld_coord` module (see TREEMAP_REFACTOR.md).