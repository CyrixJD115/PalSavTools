/** Relic type → icon path mapping.
 *
 * Order sourced from Palworld's official per-pal effigy effects (post-1.0).
 * Each icon is named by the pal face it shows, mapped to the relic type
 * that pal's effigy unlocks at the Statue of Power:
 *
 *   00  Lifmunk    → Capture Power      (CapturePower)
 *   01  Lamball    → Satiety Duration   (HungerReduction)
 *   02  Pengullet  → Swimming Ability   (SwimSpeed)
 *   03  Munchill   → Food Preservation  (FoodDecayReduction)
 *   04  Rooby      → Jump Power         (JumpPower)
 *   05  Herbil     → Flight Capacity    (GliderSpeed)
 *   06  Tanzee     → Climbing           (ClimbSpeed)
 *   07  Depresso   → Status Resistance  (StatusAilmentResist)
 *   08  Cattiva    → Endurance          (StaminaReduction)
 *   09  Lunaris    → Sphere Tracking    (SphereHoming)
 *   10  Relaxaurus → EXP Gain           (ExpBonus)
 *   11  Yakumo     → Rainbow Fortune    (RainbowPassiveRate)
 *   12  Mimog      → Movement Speed     (MoveSpeed)
 */

const RELIC_ICON_MAP: Record<string, string> = {
  "EPalRelicType::CapturePower":        "icons/relics/t_itemicon_relic.webp",
  "EPalRelicType::HungerReduction":     "icons/relics/t_itemicon_relic_01.webp",
  "EPalRelicType::SwimSpeed":           "icons/relics/t_itemicon_relic_02.webp",
  "EPalRelicType::FoodDecayReduction":  "icons/relics/t_itemicon_relic_03.webp",
  "EPalRelicType::JumpPower":           "icons/relics/t_itemicon_relic_04.webp",
  "EPalRelicType::GliderSpeed":         "icons/relics/t_itemicon_relic_05.webp",
  "EPalRelicType::ClimbSpeed":          "icons/relics/t_itemicon_relic_06.webp",
  "EPalRelicType::StatusAilmentResist": "icons/relics/t_itemicon_relic_07.webp",
  "EPalRelicType::StaminaReduction":    "icons/relics/t_itemicon_relic_08.webp",
  "EPalRelicType::SphereHoming":        "icons/relics/t_itemicon_relic_09.webp",
  "EPalRelicType::ExpBonus":            "icons/relics/t_itemicon_relic_10.webp",
  "EPalRelicType::RainbowPassiveRate":  "icons/relics/t_itemicon_relic_11.webp",
  "EPalRelicType::MoveSpeed":           "icons/relics/t_itemicon_relic_12.webp",
};

export function relicIconPath(relicType: string): string {
  return RELIC_ICON_MAP[relicType] ?? "icons/relics/t_itemicon_relic.webp";
}
