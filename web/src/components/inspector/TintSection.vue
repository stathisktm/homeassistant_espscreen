<script setup lang="ts">
// A card's colour by state (app 0.4.91, docs/THEME.md, tint.py): the whole card takes the colour of what the entity is
// doing - a thermostat heating, a light on, the weather by its temperature - or a colour that changes with a temperature
// the card knows. The rules go to the tile's options as they are; the add-on resolves them for the screens, so the
// panel shows the colours it offers and never a rule the screen could not draw. A rule is one row: what it is for, the
// temperature it compares (for the two temperature kinds) and its colour.
import { computed, ref } from "vue";
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from "reka-ui";
import { editorLanguage, languageMarks, t } from "../../i18n";
import { hasTint, lineEntity, stateLabel, temperatureOf, TINT_HEX, TINT_RULES, tintColors, tintHex, tintRules, tintStates, type TintRule } from "../../model/tint";
import { soften } from "../../model/tint";
import type { Tile } from "../../types";
import Icon from "../ui/Icon.vue";
import Section from "../ui/Section.vue";
import UiSelect from "../ui/UiSelect.vue";
import { setTileOption } from "../../editor/tiles";
import { useEntitiesStore } from "../../stores/entities";

const props = defineProps<{ tile: Tile }>();
const entities = useEntitiesStore();
const live = computed(() => entities.liveOf(props.tile.entity));
const rules = computed(() => tintRules(props.tile));
const unit = computed(() => String(live.value?.a?.unit_of_measurement ?? "").trim());

// What a row is for: a state or an action the entity can be in, or a temperature beside it.
const choices = computed<[string, string][]>(() => [
  ...tintStates(props.tile.entity, live.value).map((word) => [`when:${word}`, stateLabel(word)] as [string, string]),
  ["above", t("editor.tile.tint.above")],
  ["below", t("editor.tile.tint.below")],
]);
const keyOf = (rule: TintRule) => (typeof rule.when === "string" ? `when:${rule.when}` : rule.above !== undefined ? "above" : "below");

// The other entity the tile's line reads (app 0.4.101): a temperature rule may read it instead of the card's own.
const line = computed(() => lineEntity(props.tile, (id: string) => entities.liveOf(id)));
const fromLine = computed(() => rules.value.some((rule) => rule.when === undefined && rule.of === "line"));
const sources = computed<[string, string][]>(() => [
  ["card", t("editor.tile.tint.from_card")],
  ["line", String(entities.liveOf(line.value)?.a?.friendly_name || line.value)],
]);
function pickSource(value: string) {
  write(rules.value.map((rule) => {
    if (rule.when !== undefined) return rule;
    const { of: _of, ...rest } = rule;
    return value === "line" ? { ...rest, of: "line" as const } : rest;
  }));
}
// The temperature a new rule starts at: the one it compares now, else 20.
const temperature = computed(() => {
  const now = fromLine.value && line.value ? temperatureOf(line.value, entities.liveOf(line.value))
    : (temperatureOf(props.tile.entity, live.value) ?? (line.value ? temperatureOf(line.value, entities.liveOf(line.value)) : null));
  return typeof now === "number" && Number.isFinite(now) ? now : 20;
});
const shown = (value: number) => String(Math.round(value * 10) / 10).replace(".", languageMarks(editorLanguage()).decimal);

function write(list: TintRule[]) {
  setTileOption(props.tile, "tint", list.length ? list : undefined);
}
function pickWhen(index: number, value: string) {
  const list = [...rules.value], rule = list[index];
  if (!rule) return;
  const of = fromLine.value ? { of: "line" as const } : {};
  if (value.startsWith("when:")) list[index] = { when: value.slice(5), c: rule.c };
  else if (value === "above") list[index] = { above: temperature.value, c: rule.c, ...of };
  else list[index] = { below: temperature.value, c: rule.c, ...of };
  write(list);
}
function writeTemperature(index: number, text: string) {
  const value = Number(text.replace(/\s/g, "").replace(",", ".")), rule = rules.value[index];
  if (!rule || text.trim() === "" || !Number.isFinite(value)) return;
  const list = [...rules.value];
  list[index] = rule.when !== undefined ? { when: rule.when, c: rule.c }
    : { ...(rule.above !== undefined ? { above: value } : { below: value }), c: rule.c, ...(rule.of === "line" ? { of: "line" as const } : {}) };
  write(list);
}
const open = ref(-1);
function pickColour(index: number, name: string) {
  open.value = -1;
  const list = [...rules.value], rule = list[index];
  if (!rule) return;
  list[index] = { ...rule, c: name };
  write(list);
}
function add() {
  const word = live.value?.state || "on";
  write([...rules.value, { when: word, c: "amber" }]);
}
function remove(index: number) {
  open.value = -1;
  write(rules.value.filter((_, row) => row !== index));
}
// A colour of one's own (app 0.4.105): typed as #RRGGBB (or without the #) or picked, kept as tint.HEX has it.
function ownColour(text: string) {
  const hex = text.trim().replace(/^#?/, "#").toLowerCase();
  return TINT_HEX.test(hex) ? hex : "";
}
function typeColour(index: number, text: string) {
  const hex = ownColour(text);
  if (hex) pickColour(index, hex);
}
/** A rule's colour by name: the palette's own words, or the colour itself as it was typed. */
const colourName = (colour: string) => (TINT_HEX.test(colour) ? colour.toUpperCase() : t(`editor.tile.meter.colors.${colour}`));
/** The swatch shows what the glass draws: the colour laid over the card the way the firmware lays it. */
const swatch = (colour: string) => soften(colour);
</script>

<template>
  <Section :title="t('editor.tile.tint.title')" :aside="hasTint(tile) ? String(rules.length) : undefined">
    <p class="hint">{{ t("editor.tile.tint.hint") }}</p>
    <div v-if="rules.length" class="tint-rows">
      <div v-for="(rule, index) in rules" :key="index" class="tint-row">
        <UiSelect class="tint-when" :model-value="keyOf(rule)" :options="choices" :aria-label="t('editor.tile.tint.when_aria')"
          @update:model-value="(value: string) => pickWhen(index, value)" />
        <span v-if="rule.when === undefined" class="tint-number">
          <input inputmode="decimal" :value="shown(Number(rule.above ?? rule.below ?? temperature))"
            :aria-label="t('editor.tile.tint.temperature_aria')" @blur="writeTemperature(index, ($event.target as HTMLInputElement).value)"
            @keydown.enter="($event.target as HTMLInputElement).blur()" />
          <small class="tint-unit">{{ unit || t("editor.tile.tint.degrees") }}</small>
        </span>
        <PopoverRoot :open="open === index" @update:open="(on: boolean) => (open = on ? index : -1)">
          <PopoverTrigger as-child>
            <button type="button" class="tint-swatch" :style="{ background: swatch(rule.c) }" :title="colourName(rule.c)"
              :aria-label="t('editor.tile.tint.colour_aria', { colour: colourName(rule.c) })"></button>
          </PopoverTrigger>
          <PopoverPortal>
            <PopoverContent class="ui-popover meter-palette" align="start" :side-offset="6" :collision-padding="10">
              <div class="sw">
                <button v-for="choice in tintColors" :key="choice" type="button" :aria-pressed="rule.c === choice ? 'true' : 'false'"
                  :title="t(`editor.tile.meter.colors.${choice}`)" :aria-label="t(`editor.tile.meter.colors.${choice}`)"
                  @click="pickColour(index, choice)"><i :style="{ background: tintHex(choice) }"></i></button>
              </div>
              <label class="tint-own">
                <span>{{ t("editor.tile.tint.own") }}</span>
                <input type="color" class="tint-own-pick" :value="tintHex(rule.c) || tintHex('amber')" :aria-label="t('editor.tile.tint.own')"
                  @change="pickColour(index, ($event.target as HTMLInputElement).value.toLowerCase())" />
                <input type="text" class="tint-own-text" maxlength="7" placeholder="#RRGGBB" spellcheck="false"
                  :value="TINT_HEX.test(rule.c) ? rule.c.toUpperCase() : ''" :aria-label="t('editor.tile.tint.own_aria')"
                  @keydown.enter="typeColour(index, ($event.target as HTMLInputElement).value)"
                  @blur="typeColour(index, ($event.target as HTMLInputElement).value)" />
              </label>
            </PopoverContent>
          </PopoverPortal>
        </PopoverRoot>
        <button type="button" class="icon-btn tint-remove" :aria-label="t('editor.tile.tint.remove')" @click="remove(index)"><Icon name="close" /></button>
      </div>
    </div>
    <label v-if="line && rules.some((rule) => rule.when === undefined)" class="tint-source">
      <span>{{ t("editor.tile.tint.from") }}</span>
      <UiSelect class="tint-source-pick" :model-value="fromLine ? 'line' : 'card'" :options="sources"
        :aria-label="t('editor.tile.tint.from')" @update:model-value="pickSource" />
    </label>
    <button v-if="rules.length < TINT_RULES" type="button" class="ghost-btn tint-add" @click="add"><Icon name="plus" />{{ t("editor.tile.tint.add") }}</button>
    <small class="help">{{ t("editor.tile.tint.first") }}</small>
  </Section>
</template>

<style scoped>
.tint-rows { display: grid; gap: 8px; padding: 4px 0 8px; }
.tint-row { display: flex; align-items: center; gap: 8px; min-width: 0; }
.tint-when { flex: 1 1 auto; min-width: 0; }
.tint-number { display: flex; align-items: center; gap: 4px; flex: 0 1 96px; }
.tint-number input { width: 100%; min-width: 0; height: 30px; padding: 4px 8px; font-size: 13px; border-radius: 7px; }
.tint-unit { font-size: 12px; color: var(--muted); white-space: nowrap; }
.tint-swatch { width: 26px; height: 26px; flex: none; border-radius: 50%; border: 1px solid rgba(0, 0, 0, 0.12); padding: 0; }
.tint-swatch:focus-visible { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--accent); }
.tint-remove { flex: none; }
.tint-add { justify-self: start; }
.tint-source { display: flex; align-items: center; gap: 8px; padding: 0 0 8px; font-size: 13px; color: var(--muted); }
.tint-source-pick { flex: 1 1 auto; min-width: 0; }
.tint-palette .sw { max-width: 236px; }
.tint-own { display: flex; align-items: center; gap: 8px; padding-top: 10px; font-size: 12px; color: var(--muted); }
.tint-own span { flex: 1 1 auto; }
.tint-own-pick { width: 30px; height: 30px; flex: none; padding: 0; border: 1px solid rgba(0, 0, 0, 0.12); border-radius: 7px; background: none; }
.tint-own-text { width: 84px; height: 30px; padding: 4px 8px; font: 13px ui-monospace, monospace; border-radius: 7px; text-transform: uppercase; }
</style>
