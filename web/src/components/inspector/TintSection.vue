<script setup lang="ts">
// A card's colour by state (app 0.4.91, docs/THEME.md, tint.py): the whole card takes the colour of what the entity is
// doing - a thermostat heating, a light on, the weather by its temperature - or a colour that changes with a temperature
// the card knows. The rules go to the tile's options as they are; the add-on resolves them for the screens, so the
// panel shows the colours it offers and never a rule the screen could not draw. A rule is one row: what it is for, the
// temperature it compares (for the two temperature kinds) and its colour.
import { computed, ref } from "vue";
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from "reka-ui";
import { editorLanguage, languageMarks, t } from "../../i18n";
import { hasTint, stateLabel, TINT_RULES, tintColors, tintHex, tintRules, tintStates, type TintRule } from "../../model/tint";
import { soften } from "../../model/tint";
import { unitSuffix } from "../../model/tile-text";
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

// The temperature a rule compares: the card's own where it has one, else the one of the entity its second line reads.
const temperature = computed(() => {
  const own = live.value?.a?.current_temperature ?? live.value?.a?.temperature;
  return typeof own === "number" && Number.isFinite(own) ? own : 20;
});
const shown = (value: number) => String(Math.round(value * 10) / 10).replace(".", languageMarks(editorLanguage()).decimal);

function write(list: TintRule[]) {
  setTileOption(props.tile, "tint", list.length ? list : undefined);
}
function pickWhen(index: number, value: string) {
  const list = [...rules.value], rule = list[index];
  if (!rule) return;
  if (value.startsWith("when:")) list[index] = { when: value.slice(5), c: rule.c };
  else if (value === "above") list[index] = { above: temperature.value, c: rule.c };
  else list[index] = { below: temperature.value, c: rule.c };
  write(list);
}
function writeTemperature(index: number, text: string) {
  const value = Number(text.replace(/\s/g, "").replace(",", ".")), rule = rules.value[index];
  if (!rule || text.trim() === "" || !Number.isFinite(value)) return;
  const list = [...rules.value];
  list[index] = rule.when !== undefined ? { when: rule.when, c: rule.c } : { ...(rule.above !== undefined ? { above: value } : { below: value }), c: rule.c };
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
            <button type="button" class="tint-swatch" :style="{ background: swatch(rule.c) }" :title="t(`editor.tile.meter.colors.${rule.c}`)"
              :aria-label="t('editor.tile.tint.colour_aria', { colour: t(`editor.tile.meter.colors.${rule.c}`) })"></button>
          </PopoverTrigger>
          <PopoverPortal>
            <PopoverContent class="ui-popover meter-palette" align="start" :side-offset="6" :collision-padding="10">
              <div class="sw">
                <button v-for="choice in tintColors" :key="choice" type="button" :aria-pressed="rule.c === choice ? 'true' : 'false'"
                  :title="t(`editor.tile.meter.colors.${choice}`)" :aria-label="t(`editor.tile.meter.colors.${choice}`)"
                  @click="pickColour(index, choice)"><i :style="{ background: tintHex(choice) }"></i></button>
              </div>
            </PopoverContent>
          </PopoverPortal>
        </PopoverRoot>
        <button type="button" class="icon-btn tint-remove" :aria-label="t('editor.tile.tint.remove')" @click="remove(index)"><Icon name="close" /></button>
      </div>
    </div>
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
.tint-palette .sw { max-width: 236px; }
</style>
