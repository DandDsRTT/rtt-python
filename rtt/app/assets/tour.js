// Guided first-run tour. A tiny self-contained walkthrough engine — no library, in the same
// hand-rolled style as audio.js / freeze.js. The page injects window.rttTour = {steps, autostart}
// (see app._TOUR_JS): `steps` is an array of {selector, title, body, place, open} and `autostart` asks
// the tour to run itself once per browser on first load.
//
// Each step spotlights the element matched by its CSS selector `selector` (a region class like
// .rtt-gridcontent or .rtt-titletile — NOT a NiceGUI .mark(), which is test-only and never reaches
// the DOM) and floats a card of copy beside it. A step with `open:true` opens the settings drawer
// first (clicking the hamburger if it's still collapsed) so its target is on screen. A step whose
// `selector` is empty — or whose element isn't present — shows a centred card with the page dimmed evenly,
// so a missing region degrades to a plain slide rather than breaking the run.
//
// "Seen" is a per-browser localStorage flag, the natural home for a one-time viewing preference (it
// needs no server round-trip and is independent of the document / dark-mode prefs). The corner tour
// button calls window.rttTour.start() to replay it anytime, regardless of the flag.
(function () {
  "use strict";

  var SEEN_KEY = "rttTourSeen";
  var PAD = 6;            // px breathing room the spotlight leaves around the target
  var GAP = 14;           // px gap between the spotlight and the card

  var config = window.rttTour || {};
  var steps = Array.isArray(config.steps) ? config.steps : [];
  var index = -1;
  var root = null;        // the live tour DOM (block + spot + card), null while closed

  function panelOpen() {
    var pg = document.querySelector(".rtt-panelgroup");
    return !!(pg && pg.classList.contains("rtt-open"));
  }

  function openDrawer() {
    if (panelOpen()) return;
    var burger = document.querySelector(".rtt-hamburger");
    if (burger) burger.click();
  }

  function build() {
    root = document.createElement("div");
    root.className = "rtt-tour-root";

    var block = document.createElement("div");
    block.className = "rtt-tour-block";
    block.addEventListener("click", function (e) { e.stopPropagation(); });

    var spot = document.createElement("div");
    spot.className = "rtt-tour-spot";

    var card = document.createElement("div");
    card.className = "rtt-tour-card";
    card.innerHTML =
      '<div class="rtt-tour-title"></div>' +
      '<div class="rtt-tour-body"></div>' +
      '<div class="rtt-tour-foot">' +
      '<span class="rtt-tour-count"></span>' +
      '<span class="rtt-tour-buttons">' +
      '<button type="button" class="rtt-tour-skip">Skip</button>' +
      '<button type="button" class="rtt-tour-back">Back</button>' +
      '<button type="button" class="rtt-tour-next">Next</button>' +
      "</span></div>";

    root.appendChild(block);
    root.appendChild(spot);
    root.appendChild(card);
    document.body.appendChild(root);

    card.querySelector(".rtt-tour-skip").addEventListener("click", stop);
    card.querySelector(".rtt-tour-back").addEventListener("click", function () { go(index - 1); });
    card.querySelector(".rtt-tour-next").addEventListener("click", function () { go(index + 1); });
  }

  function place(rect, card, spot, where) {
    // seat the card next to the spotlight, clamped to the viewport. Falls back from the requested
    // side to whichever direction has room, then pins inside the screen edges.
    var vw = window.innerWidth, vh = window.innerHeight;
    var cw = card.offsetWidth, ch = card.offsetHeight;
    var top, left;
    var below = rect.bottom + GAP, above = rect.top - GAP - ch;
    var right = rect.right + GAP, leftOf = rect.left - GAP - cw;

    if (where === "right" && right + cw <= vw) { left = right; top = rect.top; }
    else if (where === "left" && leftOf >= 0) { left = leftOf; top = rect.top; }
    else if (where === "top" && above >= 0) { top = above; left = rect.left; }
    else if (below + ch <= vh) { top = below; left = rect.left; }       // default: below
    else if (above >= 0) { top = above; left = rect.left; }             // else above
    else if (right + cw <= vw) { left = right; top = rect.top; }        // else to the right
    else { left = leftOf >= 0 ? leftOf : 12; top = rect.top; }

    top = Math.max(12, Math.min(top, vh - ch - 12));
    left = Math.max(12, Math.min(left, vw - cw - 12));
    card.style.top = top + "px";
    card.style.left = left + "px";
  }

  function position() {
    if (!root) return;
    var step = steps[index];
    var spot = root.querySelector(".rtt-tour-spot");
    var card = root.querySelector(".rtt-tour-card");
    var element = step.selector ? document.querySelector(step.selector) : null;

    if (!element || !element.getClientRects().length) {                          // centred / missing target
      // clear any inline rect from a previous anchored step — inline styles beat the
      // .rtt-tour-spot-center CSS, so without this the spotlight stays on the prior target
      spot.style.top = spot.style.left = spot.style.width = spot.style.height = "";
      spot.classList.add("rtt-tour-spot-center");
      card.style.top = Math.max(12, (window.innerHeight - card.offsetHeight) / 2) + "px";
      card.style.left = Math.max(12, (window.innerWidth - card.offsetWidth) / 2) + "px";
      return;
    }
    spot.classList.remove("rtt-tour-spot-center");
    var r = element.getBoundingClientRect();
    spot.style.top = (r.top - PAD) + "px";
    spot.style.left = (r.left - PAD) + "px";
    spot.style.width = (r.width + PAD * 2) + "px";
    spot.style.height = (r.height + PAD * 2) + "px";
    place({ top: r.top - PAD, bottom: r.bottom + PAD, left: r.left - PAD, right: r.right + PAD },
          card, spot, step.place);
  }

  function go(n) {
    if (n < 0) return;
    if (n >= steps.length) { stop(); return; }
    index = n;
    var step = steps[index];
    if (step.open) openDrawer();
    if (!root) build();

    root.querySelector(".rtt-tour-title").textContent = step.title || "";
    root.querySelector(".rtt-tour-body").innerHTML = step.body || "";
    root.querySelector(".rtt-tour-count").textContent = (index + 1) + " / " + steps.length;
    root.querySelector(".rtt-tour-back").style.visibility = index === 0 ? "hidden" : "visible";
    root.querySelector(".rtt-tour-next").textContent =
      index === steps.length - 1 ? "Done" : "Next";

    // bring the target into view first, then settle the spotlight/card once it's stopped moving
    var element = step.selector ? document.querySelector(step.selector) : null;
    if (element && element.scrollIntoView) element.scrollIntoView({ block: "nearest", inline: "nearest" });
    setTimeout(position, step.open && !panelOpen() ? 320 : 60);  // wait out the drawer transition
  }

  function start() {
    if (!steps.length) return;
    go(0);
  }

  function stop() {
    try { localStorage.setItem(SEEN_KEY, "1"); } catch (e) { /* private mode: just don't persist */ }
    if (root && root.parentNode) root.parentNode.removeChild(root);
    root = null;
    index = -1;
  }

  function onKey(e) {
    if (!root) return;
    if (e.key === "Escape") { stop(); }
    else if (e.key === "ArrowRight") { go(index + 1); }
    else if (e.key === "ArrowLeft") { go(index - 1); }
  }

  window.addEventListener("keydown", onKey);
  window.addEventListener("resize", position);
  window.addEventListener("scroll", position, true);

  window.rttTour = window.rttTour || {};
  window.rttTour.steps = steps;
  window.rttTour.start = start;
  window.rttTour.stop = stop;

  function seen() {
    try { return localStorage.getItem(SEEN_KEY) === "1"; } catch (e) { return false; }
  }

  if (config.autostart && !seen()) {
    // let the grid finish its first render (the layout settles a beat after load) before the
    // spotlight measures anything
    setTimeout(function () { if (!seen()) start(); }, 700);
  }
})();
