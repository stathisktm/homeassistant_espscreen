// A tile's line set by hand that is wider than its card goes round slowly on the mockup (app 0.4.114), as on the glass
// (firmware 0.63.0, runtime_tiles::fit_or_scroll): a CSS animation of its text-indent with a pause at each end, so the
// text Vue writes stays as it is. A line that fits, or one the card works out itself, keeps its dots.
import type { Directive } from "vue";

function measure(el: HTMLElement, on: boolean) {
  el.classList.remove("marquee");
  el.style.removeProperty("--marquee-shift");
  if (!on) return;
  const over = el.scrollWidth - el.clientWidth;
  if (over <= 1) return;
  el.style.setProperty("--marquee-shift", `-${over + 4}px`);
  el.style.setProperty("--marquee-seconds", `${Math.max(4, Math.round(over / 18) + 3)}s`);
  el.classList.add("marquee");
}

export const vMarquee: Directive<HTMLElement, boolean> = {
  mounted(el, binding) { requestAnimationFrame(() => measure(el, binding.value)); },
  updated(el, binding) { requestAnimationFrame(() => measure(el, binding.value)); },
};
