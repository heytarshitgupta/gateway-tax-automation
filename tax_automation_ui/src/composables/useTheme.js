import { ref } from 'vue'

const dark = ref(false)
const apply = () => (document.documentElement.dataset.theme = dark.value ? 'dark' : 'light')
const store = (fn) => { try { fn() } catch { /* storage may be blocked */ } }

export function useTheme() {
  const init = () => { store(() => (dark.value = localStorage.getItem('theme') === 'dark')); apply() }
  const toggle = () => { dark.value = !dark.value; apply(); store(() => localStorage.setItem('theme', dark.value ? 'dark' : 'light')) }
  return { dark, init, toggle }
}