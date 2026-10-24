<script setup lang="ts">
// An icon by state (app 0.4.112, model/icon-rules.ts, tint.validate_icons in the add-on): the tile takes another icon
// for what the entity is doing, or for its temperature, from the first rule that fits; with none, its own icon stands.
// A rule is one row: what it is for, the temperature it compares (for the two temperature kinds) and its icon, picked
// from the same set as the tile's own. The add-on resolves the rules and sends the screen the icon itself.
import { computed, ref } from "vue";
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from "reka-ui";
import { editorLanguage, languageMarks, t } from "../../i18n";
import { ICON_RULES, iconRules, type IconRule } from "../../model/icon-rules";
import { stateLabel, temperatureOf, tintStates } from "../../model/tint";
import { glyph } from "../../model/topbar";
import type { Tile } from "../../types";
import Icon from "../ui/Icon.vue";
import Section from "../ui/Section.vue";
import UiSelect from "../ui/UiSelect.vue";
import IconChoices from "../IconChoices.vue";
import { setTileOption } from "../../editor/tiles";
import { useEntitiesStore } from "../../stores/entities";

const props = defineProps<{ tile: Tile }>();
const entities = useEntitiesStore();
const live = computed(() => entities.liveOf(props.tile.entity));
const rules = computed(() => iconRules(props.tile));
const unit = computed(() => String(live.value?.a?.unit_of_measurement ?? "").trim());

const choices = computed<[string, string][]>(() => [
  ...tintStates(props.tile.entity, live.value).map((word) => [`when:${word}`, stateLabel(word)] as [string, string]),
  ["above", t("editor.tile.tint.above")],
  ["below", t("editor.tile.tint.below")],
]);
const keyOf = (rule: IconRule) => (typeof rule.when === "string" ? `when:${rule.when}` : rule.above !== undefined ? "above" : "below");
const whenText = (rule: IconRule) => choices.value.find(([key]) => key === keyOf(rule))?.[1] ?? "";
const temperature = computed(() => temperatureOf(props.tile.entity, live.value) ?? 20);
const shown = (value: number) => String(Math.round(value * 10) / 10).replace(".", languageMarks(editorLanguage()).decimal);
const glyphOf = (name: string) => { const cp = entities.iconNamed(name)?.cp; return cp ? glyph(cp) : ""; };
const automatic = computed(() => entities.automaticIcon(props.tile.entity));

function write(list: IconRule[]) {
  setTileOption(props.tile, "icons", list.length ? list : undefined);
}
function pickWhen(index: number, value: string) {
  const list = [...rules.value], rule = list[index];
  if (!rule) return;
  if (value.startsWith("when:")) list[index] = { when: value.slice(5), icon: rule.icon };
  else if (value === "above") list[index] = { above: temperature.value, icon: rule.icon };
  else list[index] = { below: temperature.value, icon: rule.icon };
  write(list);
}
function writeTemperature(index: number, text: string) {
  const value = Number(text.replace(/\s/g, "").replace(",", ".")), rule = rules.value[index];
  if (!rule || rule.when !== undefined || text.trim() === "" || !Number.isFinite(value)) return;
  const list = [...rules.value];
  list[index] = { ...(rule.above !== undefined ? { above: value } : { below: value }), icon: rule.icon };
  write(list);
}
const open = ref(-1);
function pickIcon(index: number, name: string) {
  open.value = -1;
  const list = [...rules.value], rule = list[index];
  // "Automatic" and "none" are the tile's own icon, not a rule's: picking them changes nothing.
  if (!rule || !entities.iconNamed(name)) return;
  list[index] = { ...rule, icon: name };
  write(list);
}
function add() {
  // The state the entity is in now, with the tile's own icon to start from (or the set's first).
  const word = live.value?.state || "on";
  const icon = (props.tile.options?.icon && entities.iconNamed(props.tile.options.icon) ? props.tile.options.icon : "") || "lightbulb";
  write([...rules.value, { when: word, icon }]);
}
function remove(index: number) {
  open.value = -1;
  write(rules.value.filter((_, row) => row !== index));
}
</script>

<template>
  <Section :title="t('editor.tile.icon_rules.title')" :aside="rules.length ? String(rules.length) : undefined">
    <p class="hint">{{ t("editor.tile.icon_rules.hint") }}</p>
    <div v-if="rules.length" class="icon-rows">
      <div v-for="(rule, index) in rules" :key="index" class="icon-row">
        <UiSelect class="icon-when" :model-value="keyOf(rule)" :options="choices" :aria-label="t('editor.tile.icon_rules.when_aria')"
          @update:model-value="(value: string) => pickWhen(index, value)" />
        <span v-if="rule.when === undefined" class="icon-number">
          <input inputmode="decimal" :value="shown(Number(rule.above ?? rule.below ?? temperature))"
            :aria-label="t('editor.tile.tint.temperature_aria')" @blur="writeTemperature(index, ($event.target as HTMLInputElement).value)"
            @keydown.enter="($event.target as HTMLInputElement).blur()" />
          <small class="icon-unit">{{ unit || t("editor.tile.tint.degrees") }}</small>
        </span>
        <PopoverRoot :open="open === index" @update:open="(on: boolean) => (open = on ? index : -1)">
          <PopoverTrigger as-child>
            <button type="button" class="icon-pick" :title="entities.iconNamed(rule.icon)?.label || rule.icon"
              :aria-label="t('editor.tile.icon_rules.icon_aria', { when: whenText(rule) })">
              <span class="mdi" aria-hidden="true">{{ glyphOf(rule.icon) }}</span>
            </button>
          </PopoverTrigger>
          <PopoverPortal>
            <PopoverContent class="ui-popover icon-rule-choices" align="end" :side-offset="6" :collision-padding="10">
              <IconChoices :selected="rule.icon" :automatic="automatic" :auto-label="t('editor.tile.icon.auto_default')"
                @pick="(name: string) => pickIcon(index, name)" />
            </PopoverContent>
          </PopoverPortal>
        </PopoverRoot>
        <button type="button" class="icon-btn icon-remove" :aria-label="t('editor.tile.icon_rules.remove')" @click="remove(index)"><Icon name="close" /></button>
      </div>
    </div>
    <button v-if="rules.length < ICON_RULES" type="button" class="ghost-btn icon-add" @click="add"><Icon name="plus" />{{ t("editor.tile.icon_rules.add") }}</button>
    <small class="help">{{ t("editor.tile.icon_rules.first") }}</small>
  </Section>
</template>

<style scoped>
.icon-rows { display: grid; gap: 8px; padding: 4px 0 8px; }
.icon-row { display: flex; align-items: center; gap: 8px; min-width: 0; }
.icon-when { flex: 1 1 auto; min-width: 0; }
.icon-number { display: flex; align-items: center; gap: 4px; flex: 0 1 96px; }
.icon-number input { width: 100%; min-width: 0; height: 30px; padding: 4px 8px; font-size: 13px; border-radius: 7px; }
.icon-unit { font-size: 12px; color: var(--muted); white-space: nowrap; }
.icon-pick { width: 34px; height: 30px; flex: none; display: grid; place-items: center; border-radius: 7px; padding: 0; font-size: 20px; }
.icon-remove { flex: none; }
.icon-add { justify-self: start; }
</style>
