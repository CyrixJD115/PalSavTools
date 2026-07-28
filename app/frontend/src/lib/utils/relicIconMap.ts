/** Relic type → icon path mapping.
 *
 * Order sourced from the PSP project's relic icon index (confirmed against
 * in-game relic types). Each icon shows a pal face representing the mechanic:
 *
 *   00  Capture Power (Lifmunk Effigy)  — Lifmunk
 *   01  Hunger Reduction                — Lamball
 *   02  Swim Speed                      — Pengullet
 *   03  Food Decay Reduction            — Swee
 *   04  Jump Power                      — Rooby
 *   05  Glider Speed                    — Foxsparks
 *   06  Climb Speed                     — Tanzee
 *   07  Status Ailment Resist           — Depresso
 *   08  Exp Bonus                       — Cattiva
 *   09  Rainbow Passive Rate            — Lunaris
 *   10  Move Speed                      — Relaxaurus
 *   11  Sphere Homing                   — Yakumo
 *   12  Stamina Reduction               — Mimog
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
  "EPalRelicType::ExpBonus":            "icons/relics/t_itemicon_relic_08.webp",
  "EPalRelicType::RainbowPassiveRate":  "icons/relics/t_itemicon_relic_09.webp",
  "EPalRelicType::MoveSpeed":           "icons/relics/t_itemicon_relic_10.webp",
  "EPalRelicType::SphereHoming":        "icons/relics/t_itemicon_relic_11.webp",
  "EPalRelicType::StaminaReduction":    "icons/relics/t_itemicon_relic_12.webp",
};

export function relicIconPath(relicType: string): string {
  return RELIC_ICON_MAP[relicType] ?? "icons/relics/t_itemicon_relic.webp";
}
