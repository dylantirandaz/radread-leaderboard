(() => {
  "use strict";

  const readout = document.querySelector("[data-readout]");
  if (!readout) return;
  const bars = readout.querySelectorAll(".bar .fill");
  if (!bars.length) return;

  const replay = readout.querySelector("[data-queue-replay]");
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const duration = 3250 + (bars.length - 1) * 220;
  bars.forEach((bar, index) => bar.style.setProperty("--queue-delay", `${index * 220}ms`));
  let timer = 0;
  let enabled = false;
  let visible = false;
  let played = false;

  function settle() {
    window.clearTimeout(timer);
    timer = 0;
    readout.classList.remove("is-replaying");
  }

  function start() {
    if (!enabled || document.hidden || !visible) return;
    settle();
    // Move only a faint highlight inside each fixed, score-proportional bar.
    void readout.offsetWidth;
    played = true;
    readout.classList.add("is-replaying");
    timer = window.setTimeout(settle, duration);
  }

  function setVisible(nextVisible) {
    visible = nextVisible;
    if (!visible) settle();
    else if (!played) start();
  }

  function updateMotion() {
    enabled = !motion.matches && bars[0].getClientRects().length > 0;
    if (replay) replay.hidden = !enabled;
    if (!enabled) settle();
    else if (!played) start();
  }

  motion.addEventListener("change", updateMotion);
  window.addEventListener("resize", updateMotion);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) settle();
    else if (!played) start();
  });
  if (replay) replay.addEventListener("click", start);

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(([entry]) => {
      setVisible(entry.isIntersecting && entry.intersectionRatio >= 0.2);
    }, { threshold: 0.2 });
    observer.observe(readout);
  } else {
    const checkVisible = () => {
      const bounds = readout.getBoundingClientRect();
      setVisible(bounds.bottom > 0 && bounds.top < window.innerHeight &&
        bounds.right > 0 && bounds.left < window.innerWidth);
    };
    window.addEventListener("scroll", checkVisible, { passive: true });
    window.addEventListener("resize", checkVisible);
    checkVisible();
  }
  updateMotion();
})();
