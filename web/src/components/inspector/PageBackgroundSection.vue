<script setup lang="ts">
// A page's own background picture (app 0.4.109, firmware 0.65.0, docs/PICTURES.md): one picture behind the whole page,
// from an address on the internet, a file of Home Assistant's www folder or media, or an entity's picture, darkened so
// the cards stay readable. The add-on fetches it and paints it at the glass's size; the screen never learns where it is.
// Only what page_backdrop.validate keeps is stored: a kind chosen without its address yet stays in the panel alone.
import { computed, ref, watch } from "vue";
import { t } from "../../i18n";
import { setPageBackground } from "../../editor/pages";
import { BACKGROUND_DIM_DEFAULT, BACKGROUND_DIMS, BACKGROUND_REFRESHES, backgroundKind, backgroundRefresh, type BackgroundKind,
  type PageBackground } from "../../model/page-background";
import type { Page } from "../../types";
import { useEntitiesStore } from "../../stores/entities";
import { useInventoryStore } from "../../stores/inventory";
import Icon from "../ui/Icon.vue";
import Section from "../ui/Section.vue";
import UiPicker from "../ui/UiPicker.vue";
import UiSelect from "../ui/UiSelect.vue";

const props = defineProps<{ page: Page; disabled?: boolean }>();
const entities = useEntitiesStore();
const inv = useInventoryStore();

const stored = computed<PageBackground | undefined>(() => props.page.background);
// The kind shown: the stored source's, or one picked whose address is still to come.
const picked = ref<BackgroundKind | "none" | null>(null);
watch(() => props.page.id, () => { picked.value = null; });
const kind = computed<BackgroundKind | "none">(() => picked.value ?? backgroundKind(stored.value?.source) ?? "none");
const kinds = computed<[string, string][]>(() => (["none", "url", "www", "media", "entity"] as const)
  .map((key) => [key, t(`editor.pages.background.kinds.${key}`)] as [string, string]));
const placeholders: Record<string, string> = { url: "https://", www: "/local/", media: "media-source://media_source/local/" };

const draft = ref("");
watch(() => [stored.value?.source, kind.value] as const, ([source, now]) => {
  draft.value = source && backgroundKind(source) === now ? source : "";
}, { immediate: true });
const wrong = ref(false);

function write(next: Partial<PageBackground> & { source?: string }) {
  const source = next.source ?? stored.value?.source;
  if (!source) return;
  const background: PageBackground = { source };
  const dim = next.dim ?? stored.value?.dim;
  const refresh = next.refresh ?? stored.value?.refresh;
  if (dim !== undefined && dim !== BACKGROUND_DIM_DEFAULT) background.dim = dim;
  if (refresh !== undefined) background.refresh = refresh;
  setPageBackground(props.page.id, background);
}
function pickKind(value: string) {
  wrong.value = false;
  if (value === "none") { picked.value = null; setPageBackground(props.page.id, undefined); return; }
  picked.value = value as BackgroundKind;
}
function commitAddress() {
  const source = draft.value.trim();
  if (!source) { wrong.value = false; return; }
  wrong.value = backgroundKind(source) !== kind.value;
  if (wrong.value) return;
  picked.value = null;
  write({ source });
}
function pickEntity(id: string) {
  picked.value = null;
  write({ source: id });
}
// The entities a picture comes from first: cameras, image entities, people and players; any other with a picture too.
const PICTURED = ["camera", "image", "person", "media_player"];
const entityChoices = computed(() => inv.inventory.entities
  .filter((item) => PICTURED.includes(item.id.split(".")[0]) || Boolean(entities.liveOf(item.id)?.a?.entity_picture))
  .map((item) => ({ id: item.id, name: item.name, hint: item.area })));

const dims = computed<[string, string][]>(() => BACKGROUND_DIMS.map((value) => [String(value), `${value} %`] as [string, string]));
const dim = computed(() => String(stored.value?.dim ?? BACKGROUND_DIM_DEFAULT));
const refreshes = computed<[string, string][]>(() => BACKGROUND_REFRESHES.map((value) =>
  [String(value), value === 0 ? t("editor.pages.background.refresh_once")
    : value < 3600 ? t("editor.pages.background.refresh_minutes", { n: value / 60 }) : t("editor.pages.background.refresh_hour")] as [string, string]));
const refresh = computed(() => String(backgroundRefresh(stored.value)));
</script>

<template>
  <Section :title="t('editor.pages.background.title')" icon="image-multiple-outline">
    <p class="hint">{{ t("editor.pages.background.hint") }}</p>
    <div class="f">
      <span class="f-label"><label>{{ t("editor.pages.background.kind") }}</label></span>
      <UiSelect :model-value="kind" :options="kinds" :disabled="disabled" :aria-label="t('editor.pages.background.kind')"
        @update:model-value="pickKind" />
    </div>
    <div v-if="kind === 'url' || kind === 'www' || kind === 'media'" class="f">
      <span class="f-label"><label :for="`page-bg-${page.id}`">{{ t(`editor.pages.background.address.${kind}`) }}</label></span>
      <input :id="`page-bg-${page.id}`" v-model="draft" type="text" spellcheck="false" maxlength="512" :disabled="disabled"
        :placeholder="placeholders[kind]" @keydown.enter="($event.target as HTMLInputElement).blur()" @blur="commitAddress" />
      <small v-if="wrong" class="help warn">{{ t(`editor.pages.background.wrong.${kind}`) }}</small>
      <small v-else class="help">{{ t(`editor.pages.background.help.${kind}`) }}</small>
    </div>
    <div v-else-if="kind === 'entity'" class="f">
      <UiPicker :items="entityChoices" :placeholder="t('editor.pages.background.entity_search')" :empty="t('editor.pages.background.entity_none')"
        width="320px" @pick="pickEntity">
        <template #trigger>
          <button type="button" class="ghost-btn page-bg-entity" :disabled="disabled">
            <Icon name="swap-horizontal" />{{ stored && backgroundKind(stored.source) === 'entity' ? entities.entityName(stored.source) : t('editor.pages.background.entity_pick') }}
          </button>
        </template>
      </UiPicker>
    </div>
    <template v-if="stored">
      <div class="f two">
        <span class="f-label"><label>{{ t("editor.pages.background.dim") }}</label></span>
        <UiSelect :model-value="dim" :options="dims" :disabled="disabled" :aria-label="t('editor.pages.background.dim')"
          @update:model-value="(value: string) => write({ dim: Number(value) })" />
      </div>
      <div class="f two">
        <span class="f-label"><label>{{ t("editor.pages.background.refresh") }}</label></span>
        <UiSelect :model-value="refresh" :options="refreshes" :disabled="disabled" :aria-label="t('editor.pages.background.refresh')"
          @update:model-value="(value: string) => write({ refresh: Number(value) })" />
      </div>
      <small class="help">{{ t("editor.pages.background.cards") }}</small>
    </template>
  </Section>
</template>

<style scoped>
.page-bg-entity { max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.warn { color: var(--danger, var(--accent)); }
</style>
