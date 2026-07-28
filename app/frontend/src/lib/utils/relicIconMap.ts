/** Relic type → icon path mapping.
 *
 * Icons are pal-face representations of each relic mechanic, extracted from
 * the PSP project's assets. The unnumbered icon (relic) is Lifmunk = Capture
 * Power; numbered files (01-12) follow the relic_to_status backend order:
 *
 *   00  Capture Power (Lifmunk Effigy)
 *   01  Hunger Reduction
 *   02  Swim Speed
 *   03  Food Decay Reduction
 *   04  Jump Power
 *   05  Glider Speed
 *   06  Climb Speed
 *   07  Status Ailment Resist
 *   08  Exp Bonus
 *   09  Rainbow Passive Rate
 *   10  Move Speed
 *   11  Sphere Homing
 *   12  Stamina Reduction
 */

const RELIC_ICON_MAP: Record<string, string> = {
  "EPalRelicType::CapturePower":       "icons/relics/t_itemicon_relic.webp",
  "EPalRelicType::HungerReduction":    "icons/relics/t_itemicon_relic_01.webp",
  "EPalRelicType::SwimSpeed":          "icons/relics/t_itemicon_relic_02.webp",
  "EPalRelicType::FoodDecayReduction": "icons/relics/t_itemicon_relic_03.webp",
  "EPalRelicType::JumpPower":          "icons/relics/t_itemicon_relic_04.webp",
  "EPalRelicType::GliderSpeed":        "icons/relics/t_itemicon_relic_05.webp",
  "EPalRelicType::ClimbSpeed":         "icons/relics/t_itemicon_relic_06.webp",
  "EPalRelicType::StatusAilmentResist":"icons/relics/t_itemicon_relic_07.webp",
  "EPalRelicType::ExpBonus":           "icons/relics/t_itemicon_relic_08.webp",
  "EPalRelicType::RainbowPassiveRate": "icons/relics/t_itemicon_relic_09.webp",
  "EPalRelicType::MoveSpeed":          "icons/relics/t_itemicon_relic_10.webp",
  "EPalRelicType::SphereHoming":       "icons/relics/t_itemicon_relic_11.webp",
  "EPalRelicType::StaminaReduction":   "icons/relics/t_itemicon_relic_12.webp",
};

export function relicIconPath(relicType: string): string {
  return RELIC_ICON_MAP[relicType] ?? "icons/relics/t_itemicon_relic.webp";
}
