"""
Map generation — produces world/tree map images from save data.

Replaced Qt (QPainter/QImage) rendering with Pillow (PIL).
All PySide6 references removed.
"""

import os
import time
import logging
from palsav import json_tools
import coord as palworld_coord
from i18n import t
from palworld_aio import constants
from resource_resolver import resource_path

logger = logging.getLogger("pst.map_generator")

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("Pillow not installed — map generation will be unavailable")


def extract_guild_bases_from_save():
    """Extract guild base locations from the loaded save data."""
    if not constants.loaded_level_json:
        return []
    wsd = constants.loaded_level_json["properties"]["worldSaveData"]["value"]
    base_map = {
        str(b["key"]).replace("-", ""): b["value"]
        for b in wsd.get("BaseCampSaveData", {}).get("value", [])
    }
    group_map = wsd.get("GroupSaveDataMap", {}).get("value", [])
    guild_bases = []
    for entry in group_map:
        try:
            if (
                entry["value"]["GroupType"]["value"]["value"]
                != "EPalGroupType::Guild"
            ):
                continue
        except Exception:
            continue
        g_val = entry["value"]
        guild_name = g_val["RawData"]["value"].get("guild_name", "Unknown Guild")
        admin_uid = str(g_val["RawData"]["value"].get("admin_player_uid", ""))
        leader_name = "Unknown"
        players_list = g_val["RawData"]["value"].get("players", [])
        for p in players_list:
            if str(p.get("player_uid", "")) == admin_uid:
                leader_name = p.get("player_info", {}).get(
                    "player_name", admin_uid
                )
                break
        if leader_name == "Unknown" and players_list:
            leader_name = players_list[0].get("player_info", {}).get(
                "player_name", "Unknown"
            )
        for bid in g_val["RawData"]["value"].get("base_ids", []):
            bid_str = str(bid).replace("-", "")
            if bid_str in base_map:
                try:
                    translation = base_map[bid_str]["RawData"]["value"][
                        "transform"
                    ]["translation"]
                    pt = palworld_coord.sav_to_map_by_z(
                        translation["x"], translation["y"], translation["z"]
                    )
                    guild_bases.append(
                        {
                            "guild": guild_name,
                            "leader": leader_name,
                            "x": pt.x,
                            "y": pt.y,
                            "z": translation["z"],
                            "raw_x": translation["x"],
                            "raw_y": translation["y"],
                        }
                    )
                except Exception:
                    continue
    return guild_bases


def extract_stats_from_save():
    """Extract summary stats from the loaded save data."""
    if not constants.loaded_level_json:
        return {}
    wsd = constants.loaded_level_json["properties"]["worldSaveData"]["value"]
    group_map = wsd.get("GroupSaveDataMap", {}).get("value", [])
    guild_count = sum(
        (
            1
            for e in group_map
            if e["value"]["GroupType"]["value"]["value"]
            == "EPalGroupType::Guild"
        )
    )
    base_count = len(wsd.get("BaseCampSaveData", {}).get("value", []))
    player_count = len(constants.player_levels)
    total_pals = (
        sum(constants.PLAYER_PAL_COUNTS.values())
        if constants.PLAYER_PAL_COUNTS
        else 0
    )
    return {
        "Total Bases": base_count,
        "Total Active Guilds": guild_count,
        "Total Players": player_count,
        "Total Overall Pals": total_pals,
        "Total Caught Pals": total_pals,
        "Total Owned Pals": total_pals,
        "Total Worker/Dropped Pals": 0,
    }


def _get_font(size: int):
    """Try to find a CJK-capable font, falling back to default."""
    from PIL import ImageFont
    cjk_candidates = [
        "Malgun Gothic.ttf",
        "gulim.ttc",
        "batang.ttc",
        "msyh.ttc",
        "simsun.ttc",
        "msgothic.ttc",
        "meiryo.ttc",
        "Arial.ttf",
        "NotoSansCJK-Regular.ttc",
        "DejaVuSans.ttf",
    ]
    # Common font directories
    font_dirs = []
    if os.name == "nt":
        font_dirs.append("C:\\Windows\\Fonts")
    elif os.uname().sysname == "Darwin":
        font_dirs.extend([
            "/System/Library/Fonts",
            "/Library/Fonts",
            os.path.expanduser("~/Library/Fonts"),
        ])
    else:
        font_dirs.extend([
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            os.path.expanduser("~/.fonts"),
        ])
    for d in font_dirs:
        for name in cjk_candidates:
            path = os.path.join(d, name)
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
    return ImageFont.load_default()


def generate_world_map(output_path=None, map_type="world"):
    """Generate and save a world map image annotated with guild bases.

    Parameters
    ----------
    output_path : str or None
        File path to save the map PNG.  Auto-generated if None.
    map_type : str
        ``"world"`` for the overworld map, ``"tree"`` for the skill tree map.

    Returns
    -------
    str or None
        The output path on success, None on failure.
    """
    if not HAS_PIL:
        logger.error("Pillow is required for map generation")
        return None

    if not constants.loaded_level_json:
        msg = t("error.no_save_loaded") if t else "No save file loaded."
        logger.error(msg)
        print(msg)
        return None

    from PIL import Image, ImageDraw

    start_time = time.time()
    base_dir = constants.get_base_path()

    guild_bases = extract_guild_bases_from_save()
    stats = extract_stats_from_save()

    map_filename = (
        "T_WorldMap.webp" if map_type == "world" else "T_TreeMap.webp"
    )
    worldmap_path = resource_path(base_dir, map_filename)
    marker_path = resource_path(base_dir, "baseicon.webp")

    if not os.path.exists(worldmap_path):
        logger.error("Map not found: %s", worldmap_path)
        print(f"Map not found: {worldmap_path}")
        return None
    if not os.path.exists(marker_path):
        logger.error("Marker icon not found: %s", marker_path)
        print(f"Marker icon not found: {marker_path}")
        return None

    base_map = Image.open(worldmap_path).convert("RGBA")
    marker = Image.open(marker_path).convert("RGBA")

    scale = 2
    output_width = base_map.width * scale
    output_height = base_map.height * scale

    output_image = Image.new("RGBA", (output_width, output_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(output_image)

    # Draw the base map scaled up
    base_scaled = base_map.resize(
        (output_width, output_height), Image.LANCZOS
    )
    output_image.paste(base_scaled, (0, 0))

    marker_size = 64 * scale
    marker_resized = marker.resize(
        (marker_size, marker_size), Image.LANCZOS
    )

    font = _get_font(20 * scale)

    coord_range = 2500 if map_type == "tree" else 1000

    def to_image_coordinates(x_world, y_world):
        if map_type == "tree":
            return palworld_coord.treemap_to_pixel(
                x_world, y_world, base_map.width, base_map.height
            )
        x_min, x_max = -coord_range, coord_range
        y_min, y_max = -coord_range, coord_range
        x_scale_img = base_map.width / (x_max - x_min)
        y_scale_img = base_map.height / (y_max - y_min)
        x_img = int((x_world - x_min) * x_scale_img)
        y_img = int((y_max - y_world) * y_scale_img)
        return (x_img, y_img)

    map_z_threshold = palworld_coord.MAP_Z_THRESHOLD
    base_count = 0

    for base_data in guild_bases:
        base_z = base_data.get("z", 0)
        if map_type == "world" and base_z >= map_z_threshold:
            continue
        if map_type == "tree" and base_z < map_z_threshold:
            continue
        try:
            if map_type == "tree" and "raw_x" in base_data:
                pt = palworld_coord.sav_to_treemap(
                    base_data["raw_x"], base_data["raw_y"]
                )
                xi, yi = to_image_coordinates(pt.x, pt.y)
            else:
                xi, yi = to_image_coordinates(
                    base_data["x"], base_data["y"]
                )

            x_img = xi * scale
            y_img = yi * scale

            # Red circle highlight
            radius = 35 * scale
            draw.ellipse(
                [
                    x_img - radius,
                    y_img - radius,
                    x_img + radius,
                    y_img + radius,
                ],
                outline=(255, 0, 0),
                width=4 * scale,
            )

            # Marker icon
            marker_x = x_img - marker_resized.width // 2
            marker_y = y_img - marker_resized.height // 2
            output_image.paste(
                marker_resized,
                (marker_x, marker_y),
                marker_resized,
            )

            # Draw text with outline
            text = f"{base_data['guild']} | {base_data['leader']}"
            # Measure text
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
            except AttributeError:
                text_width = len(text) * font.size * 0.6

            text_y = marker_y + marker_resized.height + 30 * scale
            text_x_centered = int(x_img - text_width // 2)

            # Outline
            for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
                draw.text(
                    (text_x_centered + dx, text_y + dy),
                    text,
                    font=font,
                    fill=(0, 0, 0),
                )
            # Foreground
            draw.text(
                (text_x_centered, text_y),
                text,
                font=font,
                fill=(255, 0, 0),
            )
            base_count += 1
        except Exception as e:
            logger.debug("Skipping base: %s", e)
            continue

    # Stats text block (bottom-right)
    ordered_stats = [
        ("Total Bases", "stats.total_bases"),
        ("Total Active Guilds", "stats.total_guilds"),
        ("Total Overall Pals", "stats.total_overall"),
        ("Total Players", "stats.total_players"),
    ]
    y_offset = output_height - 50 * scale
    x_offset = output_width - 50 * scale
    for raw_key, lang_key in ordered_stats:
        line = (
            f"{(t(lang_key) if t else raw_key)}: {stats.get(raw_key, '0')}"
        )
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except AttributeError:
            tw = len(line) * font.size * 0.6
            th = font.size + 4
        y_offset -= th
        draw.text(
            (x_offset - tw - 2, y_offset - 2),
            line,
            font=font,
            fill=(0, 0, 0),
        )
        draw.text(
            (x_offset - tw, y_offset),
            line,
            font=font,
            fill=(255, 0, 0),
        )

    # Logo
    logo_candidates = [
        "logo.png",
        "PalworldSaveTools_Blue.png",
        "PalworldSaveTools_Black.png",
    ]
    logo_path = None
    for name in logo_candidates:
        p = resource_path(base_dir, name)
        if os.path.exists(p):
            logo_path = p
            break
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo_width = int(output_width * 0.18)
            logo_height = int(logo.height * (logo_width / logo.width))
            logo_resized = logo.resize(
                (logo_width, logo_height), Image.LANCZOS
            )
            output_image.paste(
                logo_resized, (50 * scale, 50 * scale), logo_resized
            )
        except Exception as e:
            logger.warning("Could not add logo: %s", e)

    # Downscale to original map size
    final_image = output_image.resize(
        (base_map.width, base_map.height), Image.LANCZOS
    )

    if output_path is None:
        suffix = "worldmap" if map_type == "world" else "treemap"
        output_path = os.path.join(base_dir, f"updated_{suffix}.png")

    try:
        final_image.save(output_path, "PNG")
        duration = time.time() - start_time
        msg_done = (
            t("mapgen.done_time") if t else "Done in"
        )
        print(f"{msg_done}: {duration:.2f}s")
        print(f"Map saved to: {output_path}")
        return output_path
    except Exception as e:
        logger.error("Error saving map: %s", e)
        print(f"Error saving map: {e}")
        return None
