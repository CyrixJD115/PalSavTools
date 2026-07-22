/**
 * Map rendering configuration — exact port of `MapTab._load_config()` in
 * `src/palworld_aio/ui/tabs/map_tab.py`. Keep values in sync.
 */

export interface MapConfig {
  marker: {
    type: 'dot' | 'icon';
    dot: {
      size: number;
      color: [number, number, number];
      border_width: number;
      border_color: [number, number, number];
      size_min: number;
      size_max: number;
      dynamic_sizing: boolean;
      dynamic_sizing_formula: 'sqrt' | 'linear' | 'log';
    };
    icon: {
      path: string;
      size_min: number;
      size_max: number;
      base_size: number;
      dynamic_sizing: boolean;
      dynamic_sizing_formula: 'sqrt' | 'linear' | 'log';
    };
  };
  glow: {
    enabled: boolean;
    color: [number, number, number];
    selected_alpha_min: number;
    selected_alpha_max: number;
    animation_speed: number;
    hover_alpha: number;
    radius_multiplier: number;
  };
  zoom: {
    factor: number;
    min: number;
    max: number;
    double_click_target: number;
    animation_speed: number;
    animation_fps: number;
  };
  effects: {
    delete: {
      enabled: boolean;
      duration: number;
      max_radius: number;
      colors: {
        outer: [number, number, number];
        inner: [number, number, number];
        flash: [number, number, number];
      };
    };
    import: {
      enabled: boolean;
      duration: number;
      pulse_count: number;
      color: [number, number, number];
      sparkle_color: [number, number, number];
    };
    export: {
      enabled: boolean;
      duration: number;
      color: [number, number, number];
    };
  };
}

export const MAP_CONFIG: MapConfig = {
  marker: {
    type: 'icon',
    dot: {
      size: 24,
      color: [255, 0, 0],
      border_width: 3,
      border_color: [180, 0, 0],
      size_min: 24,
      size_max: 24,
      dynamic_sizing: false,
      dynamic_sizing_formula: 'sqrt',
    },
    icon: {
      path: '/assets/icons/game/baseicon.webp',
      size_min: 32,
      size_max: 64,
      base_size: 48,
      dynamic_sizing: true,
      dynamic_sizing_formula: 'sqrt',
    },
  },
  glow: {
    enabled: true,
    color: [59, 142, 208],
    selected_alpha_min: 80,
    selected_alpha_max: 180,
    animation_speed: 8,
    hover_alpha: 80,
    radius_multiplier: 1.5,
  },
  zoom: {
    factor: 1.15,
    min: 1.0,
    max: 30.0,
    double_click_target: 26.0,
    animation_speed: 0.2,
    animation_fps: 60,
  },
  effects: {
    delete: {
      enabled: true,
      duration: 1000,
      max_radius: 150,
      colors: {
        outer: [255, 80, 80],
        inner: [255, 150, 0],
        flash: [255, 200, 0],
      },
    },
    import: {
      enabled: true,
      duration: 1000,
      pulse_count: 3,
      color: [0, 255, 150],
      sparkle_color: [100, 255, 200],
    },
    export: {
      enabled: true,
      duration: 1000,
      color: [100, 200, 255],
    },
  },
};

/** Player marker constants (PlayerMarker in map_markers.py). */
export const PLAYER_MARKER = {
  glow_color: [0, 255, 150] as [number, number, number],
  size_min: 32,
  size_max: 64,
  base_size: 48,
  selected_alpha_min: 80,
  selected_alpha_max: 180,
  animation_speed: 8,
  hover_alpha: 80,
  radius_multiplier: 1.5,
};

/** Background fill (MapTab sets view.setBackgroundBrush(QColor(14,16,20))). */
export const MAP_BG_COLOR = '#0e1014';

/**
 * ``sav_to_map`` scale: raw-cm per world-coord unit.
 * World map: ``__scale_new = 725``, Tree map: ``__treemap_scale = 724``.
 */
export const MAP_SCALE: Record<'world' | 'tree', number> = { world: 725, tree: 724 };


/**
 * Convert a base `area_range` (save-space cm) to image-space pixel radius.
 *
 * ``area_range`` is in cm.  ``sav_to_map`` divides by ``scale`` (725 world,
 * 724 tree) to produce world coords.  ``worldToImage`` stretches the
 * ``±coordRange`` world extent across ``mapSize`` image pixels.
 *
 *    radius_image_px = (area_range_cm / scale) * (mapSize / (2 * coordRange))
 *
 * Mirrors PSP Rust's ``areaRange / cmPerPx(area)`` — the same screen-space
 * result at fit-zoom because the PSP 8192² texture has 4× the pixels at the
 * same cm extent, cancelling the 4× difference in raw image-px.
 *
 * Was ``save_radius_to_scene_pixels`` — a 3×-too-big approximation clamped
 * to min 15px (the true default is ~4.95px on the world map).
 */
export function area_range_to_image_px(
  area_range_cm: number,
  scale: number,
  mapSize: number,
  coordRange: number,
): number {
  return (area_range_cm / scale) * (mapSize / (2 * coordRange));
}

/** Asset paths. */
export const MAP_ASSETS = {
  worldMap: '/assets/maps/T_WorldMap.webp',
  treeMap: '/assets/maps/T_TreeMap.webp',
  baseIcon: '/assets/icons/game/baseicon.webp',
  playerIcon: '/assets/icons/game/playericon.webp',
  ringIcon: '/assets/icons/game/ring.webp',
  zonesIcon: '/assets/icons/game/zones.webp',
  calibrateIcon: '/assets/icons/game/calibrate.webp',

  // POI icons (ported from PSP Rust → src/_resources/assets/icons/map/)
  bossIcon: '/assets/icons/map/t_icon_compass_06.webp',
  dungeonIcon: '/assets/icons/map/t_icon_compass_08.webp',
  fastTravelIcon: '/assets/icons/map/t_icon_compass_fttower.webp',
  baseCampIcon: '/assets/icons/map/t_icon_compass_camp.webp',
  relicGenericIcon: '/assets/icons/map/t_icon_compass_relic.webp',

  /** Pal portrait: uses existing game_data/icons/pals/ with PascalCase names. */
  palPortrait: (palId: string) =>
    `/game-icons/pals/T_${palId}_icon_normal.webp`,

  /** Relic per-type icon: ``/assets/icons/map/relic_<relic_type>.webp``. */
  relicTypeIcon: (relicType: string) =>
    `/assets/icons/map/relic_${relicType}.webp`,
} as const;
