// Test engine — Alpine component + timer + keyboard shortcuts.
// Persistence goes through /api/attempt/<id>/{answer,mark,strikethrough,report,timer}.
// Server is authoritative for timer; we poll every 15s to correct drift.

function csrfToken() {
  return document.querySelector('meta[name="csrf-token"]').content;
}

async function postForm(url, params) {
  const body = new FormData();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) body.append(k, v);
  }
  const res = await fetch(url, {
    method: "POST",
    headers: { "X-CSRFToken": csrfToken() },
    body,
  });
  return res.ok ? res.json() : Promise.reject(res);
}

function testEngine(cfg) {
  return {
    // config
    ...cfg,

    // state
    chosenId: cfg.savedChoiceId,
    chosenLabel: null,
    freeText: cfg.savedFreeText || "",
    strikeEnabled: !!(cfg.savedStrike && cfg.savedStrike.enabled),
    struck: (cfg.savedStrike && cfg.savedStrike.struck) || [],
    marked: cfg.marked,

    // UI toggles
    showDirections: false,
    showMore: false,
    showShortcuts: false,
    showReport: false,
    showBugReport: false,
    showReference: false,
    showNavigator: false,
    timerHidden: false,

    // timer bookkeeping
    startTs: Date.now(),
    reportReason: "",

    init() {
      this._tick();
      this._syncTimer(); // immediate correction
      this._syncInterval = setInterval(() => this._syncTimer(), 15000);
      this._keyHandler = (e) => this._onKey(e);
      window.addEventListener("keydown", this._keyHandler);
    },

    destroy() {
      clearInterval(this._syncInterval);
      window.removeEventListener("keydown", this._keyHandler);
    },

    // -- timer -------------------------------------------------------------

    _tick() {
      // Local decrement between server syncs
      this._tickInterval = setInterval(() => {
        if (this.secondsRemaining > 0) this.secondsRemaining--;
        else this._onTimeUp();
      }, 1000);
    },

    async _syncTimer() {
      try {
        const res = await fetch(
          `/api/attempt/${this.attemptId}/timer?module_num=${this.moduleNum}`,
          { headers: { "X-CSRFToken": csrfToken() } },
        );
        if (!res.ok) return;
        const data = await res.json();
        this.secondsRemaining = data.seconds_remaining;
        if (this.secondsRemaining <= 0) this._onTimeUp();
      } catch (e) { /* stay on last known value */ }
    },

    _onTimeUp() {
      // Force submit / advance — for now, redirect to review page.
      window.location.href = `/attempt/${this.attemptId}/module/${this.moduleNum}/review`;
    },

    fmt(s) {
      const m = Math.floor(s / 60), ss = s % 60;
      return `${m}:${String(ss).padStart(2, "0")}`;
    },

    // -- keyboard shortcuts ------------------------------------------------

    _onKey(e) {
      const ae = document.activeElement;
      if (ae && (ae.tagName === "INPUT" || ae.tagName === "TEXTAREA" || ae.isContentEditable)) {
        // per §2.5: never intercept typing inside grid-in, textarea, or calculator input
        return;
      }
      if (this.isGridIn) return;
      const map = { "1": "A", "2": "B", "3": "C", "4": "D" };
      if (map[e.key]) {
        e.preventDefault();
        this._selectByLabel(map[e.key]);
      } else if (e.key === "Enter") {
        e.preventDefault();
        this.goNext();
      }
    },

    _selectByLabel(label) {
      const inputs = document.querySelectorAll('input[type="radio"][name="choice"]');
      for (const el of inputs) {
        const li = el.closest(".choice");
        if (li && li.querySelector(".choice-label")?.textContent.trim() === label) {
          el.checked = true;
          this.pickChoice(parseInt(el.value, 10), label);
          return;
        }
      }
    },

    // -- answering ---------------------------------------------------------

    _elapsed() {
      const dt = Math.floor((Date.now() - this.startTs) / 1000);
      this.startTs = Date.now();
      return Math.max(0, dt);
    },

    async pickChoice(choiceId, label) {
      this.chosenId = choiceId;
      this.chosenLabel = label;
      await postForm(`/api/attempt/${this.attemptId}/answer`, {
        question_id: this.questionId,
        choice_id: choiceId,
        time_delta_seconds: this._elapsed(),
      }).catch(() => {});
    },

    async saveFreeText() {
      await postForm(`/api/attempt/${this.attemptId}/answer`, {
        question_id: this.questionId,
        free_response_text: this.freeText,
        time_delta_seconds: this._elapsed(),
      }).catch(() => {});
    },

    // -- mark / report -----------------------------------------------------

    async toggleMark() {
      const res = await postForm(`/api/attempt/${this.attemptId}/mark`, {
        question_id: this.questionId,
      }).catch(() => null);
      if (res) this.marked = res.marked;
    },

    async submitReport() {
      if (!this.reportReason.trim()) return;
      await postForm(`/api/attempt/${this.attemptId}/report`, {
        question_id: this.questionId,
        reason: this.reportReason,
      }).catch(() => {});
      this.reportReason = "";
      this.showReport = false;
    },

    // -- strikethrough -----------------------------------------------------

    async toggleStrikeMode() {
      this.strikeEnabled = !this.strikeEnabled;
      if (!this.strikeEnabled) this.struck = [];
      await this._saveStrike();
    },

    async toggleStrike(label) {
      if (!this.strikeEnabled) return;
      const i = this.struck.indexOf(label);
      if (i >= 0) this.struck.splice(i, 1);
      else this.struck.push(label);
      await this._saveStrike();
    },

    isStruck(label) { return this.struck.includes(label); },

    async _saveStrike() {
      await postForm(`/api/attempt/${this.attemptId}/strikethrough`, {
        question_id: this.questionId,
        enabled: this.strikeEnabled ? "1" : "",
        struck: this.struck.join(","),
      }).catch(() => {});
    },

    // -- navigation --------------------------------------------------------

    goNext() {
      if (this.nextUrl) window.location.href = this.nextUrl;
    },
    goPrev() {
      if (this.prevUrl) window.location.href = this.prevUrl;
    },

    // -- tools -------------------------------------------------------------

    toggleFullscreen() {
      const el = document.documentElement;
      if (!document.fullscreenElement) el.requestFullscreen?.();
      else document.exitFullscreen?.();
      this.showMore = false;
    },
    toggleTheme() {
      const el = document.documentElement;
      const next = el.getAttribute("data-theme") === "dark" ? "light" : "dark";
      if (next === "dark") el.setAttribute("data-theme", "dark");
      else el.removeAttribute("data-theme");
      try { localStorage.setItem("theme", next); } catch (e) {}
      this.showMore = false;
    },
    toggleHighlight() { /* Phase-4.5 enhancement */ },
    toggleCalculator() { window.open("https://www.desmos.com/scientific", "calc", "width=420,height=560"); },
    async saveAndExit() {
      window.location.href = "/student/dashboard";
    },
  };
}

// expose globally for Alpine
window.testEngine = testEngine;
