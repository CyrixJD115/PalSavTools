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
 * Convert a base `area_range` (save-space) to a scene-pixel radius.
 * Exact port of `BaseRadiusRing._save_radius_to_scene_pixels`.
 */
export function save_radius_to_scene_pixels(saveRadius: number): number {
  const display_radius = (saveRadius / 3500.0) * 7.9;
  let scene_radius = display_radius * (2048 / 2000);
  scene_radius = scene_radius + 5;
  return Math.max(scene_radius, 15);
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
} as const;
