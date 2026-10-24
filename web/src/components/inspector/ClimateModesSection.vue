<script setup lang="ts">
// The modes a thermostat's tile shows (app 0.4.113, model/climate-modes.ts): as Home Assistant's own climate features
// choose them, a chip per mode of each kind the entity lists (its HVAC, fan and swing modes), on when the tile shows it.
// All of them on is no key at all, and at least one stays on. The screen gets only the modes kept.
import { computed } from "vue";
import { t } from "../../i18n";
import { CLIMATE_MODE_LISTS, type ClimateModeList } from "../../model/climate-modes";
import { stateLabel } from "../../model/tint";
import type { Tile } from "../../types";
import Section from "../ui/Section.vue";
import UiChips from "../ui/UiChips.vue";
import { setTileOption } from "../../editor/tiles";
import { useEntitiesStore } from "../../stores/entities";

const props = defineProps<{ tile: Tile }>();
const entities = useEntitiesStore();
const live = computed(() => entities.liveOf(props.tile.entity));

// Each kind the entity lists two modes or more of, with the modes it lists and the ones the tile keeps.
const kinds = computed(() => CLIMATE_MODE_LISTS.map((key) => {
  const listed = Array.isArray(live.value?.a?.[key]) ? (live.value!.a![key] as unknown[]).map(String) : [];
  const kept = props.tile.options?.[key];
  return { key, listed, shown: Array.isArray(kept) ? listed.filter((mode) => kept.includes(mode)) : listed };
}).filter((kind) => kind.listed.length >= 2));
const chips = (listed: string[]) => listed.map((mode) => ({ value: mode, label: stateLabel(mode) }));

function pick(key: ClimateModeList, listed: string[], value: string[]) {
  if (!value.length) return;  // at least one mode stays
  const kept = listed.filter((mode) => value.includes(mode));
  setTileOption(props.tile, key, kept.length === listed.length ? undefined : kept);
}
</script>

<template>
  <Section v-if="kinds.length" :title="t('editor.tile.modes.title')">
    <p class="hint">{{ t("editor.tile.modes.hint") }}</p>
    <div v-for="kind in kinds" :key="kind.key" class="f modes">
      <span class="f-label"><label>{{ t(`editor.tile.modes.${kind.key}`) }}</label></span>
      <UiChips :model-value="kind.shown" :chips="chips(kind.listed)" :label="t(`editor.tile.modes.${kind.key}`)"
        @update:model-value="(value: string[]) => pick(kind.key, kind.listed, value)" />
    </div>
  </Section>
</template>

<style scoped>
.modes { padding-bottom: 8px; }
</style>
