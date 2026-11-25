<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  modelValue: {
    type: [String, Number, null],
    default: null,
  },
  options: {
    type: Array,
    default: () => [],
  },
  placeholder: {
    type: String,
    default: 'Select an option...',
  },
  searchPlaceholder: {
    type: String,
    default: 'Search...',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  clearable: {
    type: Boolean,
    default: true,
  },
  includeAll: {
    type: Boolean,
    default: false,
  },
  allLabel: {
    type: String,
    default: 'All',
  },
  includeUnassigned: {
    type: Boolean,
    default: false,
  },
  unassignedLabel: {
    type: String,
    default: 'Unassigned',
  },
  loading: {
    type: Boolean,
    default: false,
  },
  ariaLabel: {
    type: String,
    default: 'Searchable select',
  },
  placement: {
    type: String,
    default: 'down',
  },
})

const emit = defineEmits(['update:modelValue', 'change'])

const isOpen = ref(false)
const searchQuery = ref('')
const highlightedIndex = ref(-1)
const wrapperRef = ref(null)
const searchInputRef = ref(null)

// Normalize options
const normalizedOptions = computed(() => {
  const list = []
  if (props.includeAll) {
    list.push({ id: '', name: props.allLabel, isSpecial: true })
  }
  if (props.includeUnassigned) {
    list.push({ id: 'unassigned', name: props.unassignedLabel, isSpecial: true })
  }
  for (const opt of props.options) {
    if (typeof opt === 'object' && opt !== null) {
      list.push({
        id: opt.id ?? opt.value,
        name: opt.name ?? opt.label ?? String(opt.id),
        alias: opt.alias ?? opt.alias_name ?? '',
        subtext: opt.subtext ?? '',
        raw: opt,
      })
    } else {
      list.push({
        id: opt,
        name: String(opt),
        alias: '',
        subtext: '',
        raw: opt,
      })
    }
  }
  return list
})

const filteredOptions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return normalizedOptions.value
  return normalizedOptions.value.filter((opt) => {
    const nameMatch = opt.name && opt.name.toLowerCase().includes(q)
    const aliasMatch = opt.alias && opt.alias.toLowerCase().includes(q)
    const subMatch = opt.subtext && opt.subtext.toLowerCase().includes(q)
    return nameMatch || aliasMatch || subMatch
  })
})

const selectedOption = computed(() => {
  if (props.modelValue === '' && props.includeAll) {
    return { id: '', name: props.allLabel }
  }
  if (props.modelValue === 'unassigned' && props.includeUnassigned) {
    return { id: 'unassigned', name: props.unassignedLabel }
  }
  if (props.modelValue === null || props.modelValue === undefined || props.modelValue === '') {
    return null
  }
  return normalizedOptions.value.find((opt) => String(opt.id) === String(props.modelValue)) || null
})

function toggleDropdown() {
  if (props.disabled) return
  if (isOpen.value) {
    closeDropdown()
  } else {
    openDropdown()
  }
}

function openDropdown() {
  if (props.disabled) return
  isOpen.value = true
  searchQuery.value = ''
  highlightedIndex.value = -1
  nextTick(() => {
    searchInputRef.value?.focus()
  })
}

function closeDropdown() {
  isOpen.value = false
  searchQuery.value = ''
  highlightedIndex.value = -1
}

function selectOption(opt) {
  const val = opt.id
  emit('update:modelValue', val)
  emit('change', val, opt)
  closeDropdown()
}

function clearSelection(e) {
  e?.stopPropagation()
  if (props.disabled) return
  const val = props.includeAll ? '' : null
  emit('update:modelValue', val)
  emit('change', val, null)
  closeDropdown()
}

function onKeyDown(e) {
  if (props.disabled) return

  if (!isOpen.value) {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openDropdown()
    }
    return
  }

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (filteredOptions.value.length === 0) return
    highlightedIndex.value = (highlightedIndex.value + 1) % filteredOptions.value.length
    scrollToHighlighted()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (filteredOptions.value.length === 0) return
    highlightedIndex.value = (highlightedIndex.value - 1 + filteredOptions.value.length) % filteredOptions.value.length
    scrollToHighlighted()
  } else if (e.key === 'Enter') {
    e.preventDefault()
    if (highlightedIndex.value >= 0 && highlightedIndex.value < filteredOptions.value.length) {
      selectOption(filteredOptions.value[highlightedIndex.value])
    } else if (filteredOptions.value.length === 1) {
      selectOption(filteredOptions.value[0])
    }
  } else if (e.key === 'Escape' || e.key === 'Tab') {
    closeDropdown()
  }
}

function scrollToHighlighted() {
  nextTick(() => {
    const listEl = wrapperRef.value?.querySelector('.select-menu')
    const itemEl = listEl?.querySelector('.select-item.highlighted')
    if (listEl && itemEl) {
      itemEl.scrollIntoView({ block: 'nearest' })
    }
  })
}

function handleOutsideClick(e) {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target)) {
    closeDropdown()
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', handleOutsideClick)
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', handleOutsideClick)
})
</script>

<template>
  <div
    ref="wrapperRef"
    class="searchable-select-wrap"
    :class="{ disabled, open: isOpen }"
    @keydown="onKeyDown"
  >
    <div
      class="select-trigger"
      tabindex="0"
      role="combobox"
      :aria-expanded="isOpen"
      :aria-label="ariaLabel"
      :aria-disabled="disabled"
      @click.prevent.stop="toggleDropdown"
    >
      <span v-if="selectedOption" class="selected-text">
        {{ selectedOption.name }}
        <span v-if="selectedOption.alias" class="alias-sub">({{ selectedOption.alias }})</span>
      </span>
      <span v-else class="placeholder-text">{{ placeholder }}</span>

      <div class="trigger-icons">
        <button
          v-if="clearable && selectedOption && !disabled"
          type="button"
          class="clear-btn"
          aria-label="Clear selection"
          @click="clearSelection"
        >
          &times;
        </button>
        <span class="arrow-indicator">&#9662;</span>
      </div>
    </div>

    <div v-if="isOpen" class="select-dropdown" :class="{ dropup: placement === 'up' }" role="listbox">
      <div class="search-box">
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          type="text"
          class="search-input"
          :placeholder="searchPlaceholder"
          autocomplete="off"
          @click.stop
        />
      </div>

      <div v-if="loading" class="select-msg">Loading options…</div>
      <div v-else-if="filteredOptions.length === 0" class="select-msg none">
        No matching options
      </div>
      <div v-else class="select-menu">
        <div
          v-for="(opt, idx) in filteredOptions"
          :key="String(opt.id)"
          class="select-item"
          :class="{
            selected: selectedOption && String(selectedOption.id) === String(opt.id),
            highlighted: idx === highlightedIndex,
            special: opt.isSpecial
          }"
          role="option"
          :aria-selected="selectedOption && String(selectedOption.id) === String(opt.id)"
          @click.stop="selectOption(opt)"
          @mouseenter="highlightedIndex = idx"
        >
          <span class="opt-name">{{ opt.name }}</span>
          <span v-if="opt.alias || opt.subtext" class="opt-secondary">
            <span v-if="opt.alias" class="opt-alias">{{ opt.alias }}</span>
            <span v-if="opt.alias && opt.subtext"> · </span>
            <span v-if="opt.subtext" class="opt-subtext">{{ opt.subtext }}</span>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.searchable-select-wrap {
  position: relative;
  width: 100%;
}

.select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  width: 100%;
  min-height: 38px;
  padding: 0.5rem 0.65rem;
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--line);
  border-radius: 6px;
  cursor: pointer;
  user-select: none;
  font: inherit;
}

.searchable-select-wrap.disabled .select-trigger {
  opacity: 0.6;
  cursor: not-allowed;
  background: var(--sunken);
}

.selected-text {
  flex: 1;
  min-width: 0;
  white-space: normal;
  word-break: break-word;
  line-height: 1.3;
}

.alias-sub {
  color: var(--muted);
  font-size: 0.85em;
  margin-left: 0.35rem;
}

.placeholder-text {
  color: var(--muted);
  flex: 1;
}

.trigger-icons {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
}

.clear-btn {
  background: none;
  border: none;
  padding: 0 0.2rem;
  font-size: 1.1rem;
  line-height: 1;
  color: var(--muted);
  cursor: pointer;
  border-radius: 4px;
}
.clear-btn:hover {
  color: var(--danger);
}

.arrow-indicator {
  font-size: 0.75rem;
  color: var(--muted);
  transition: transform 0.15s ease;
}
.searchable-select-wrap.open .arrow-indicator {
  transform: rotate(180deg);
}

.select-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 50;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 6px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  max-height: 280px;
  overflow: hidden;
}

.select-dropdown.dropup {
  top: auto;
  bottom: calc(100% + 4px);
  box-shadow: 0 -4px 14px rgba(0, 0, 0, 0.15);
}

.search-box {
  padding: 0.5rem;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
}

.search-input {
  width: 100%;
  padding: 0.4rem 0.6rem;
  font-size: 0.88rem;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--paper);
  color: var(--ink);
}

.select-menu {
  flex: 1;
  overflow-y: auto;
  max-height: 220px;
}

.select-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.1rem;
  padding: 0.45rem 0.75rem;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--ink);
  transition: background 0.1s ease;
}

.select-item:hover,
.select-item.highlighted {
  background: var(--sunken);
}

.select-item.selected {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}

.select-item.special {
  font-style: italic;
  color: var(--muted);
  border-bottom: 1px solid var(--line);
}

.opt-name {
  width: 100%;
  white-space: normal;
  word-break: break-word;
  line-height: 1.3;
  font-weight: 500;
}

.opt-secondary,
.opt-alias,
.opt-subtext {
  font-size: 0.78rem;
  line-height: 1.25;
  color: var(--muted);
}

.select-msg {
  padding: 1rem;
  text-align: center;
  font-size: 0.85rem;
  color: var(--muted);
}
</style>
