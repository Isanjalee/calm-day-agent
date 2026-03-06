const state = {
  config: {
    user_name: "You",
    partner_name: "Boyfriend",
    timezone: "Asia/Colombo",
    can_send_plan: false,
  },
  plan: null,
  documents: [],
};

const elements = {
  tabs: [...document.querySelectorAll(".tab")],
  panels: {
    day: document.getElementById("panel-day"),
    diary: document.getElementById("panel-diary"),
    book: document.getElementById("panel-book"),
  },
  partnerLabel: document.getElementById("partner-label"),
  timezoneLabel: document.getElementById("timezone-label"),
  statuses: {
    plan: document.getElementById("plan-status"),
    diary: document.getElementById("diary-status"),
    book: document.getElementById("book-status"),
  },
  prompt: document.getElementById("plan-prompt"),
  date: document.getElementById("plan-date"),
  summary: document.getElementById("plan-summary"),
  top: [
    document.getElementById("top-1"),
    document.getElementById("top-2"),
    document.getElementById("top-3"),
  ],
  notes: document.getElementById("plan-notes"),
  scheduleList: document.getElementById("schedule-list"),
  rowTemplate: document.getElementById("schedule-row-template"),
  generatePlan: document.getElementById("generate-plan"),
  clearPlan: document.getElementById("clear-plan"),
  addRow: document.getElementById("add-row"),
  savePlan: document.getElementById("save-plan"),
  sendPlan: document.getElementById("send-plan"),
  diaryTitle: document.getElementById("diary-title"),
  diaryContent: document.getElementById("diary-content"),
  saveDiary: document.getElementById("save-diary"),
  diaryList: document.getElementById("diary-list"),
  bookTitle: document.getElementById("book-title"),
  bookContent: document.getElementById("book-content"),
  saveBook: document.getElementById("save-book"),
  bookList: document.getElementById("book-list"),
};

function partnerName() {
  return state.config.partner_name || "your partner";
}

function setStatus(kind, text, isError = false) {
  const node = elements.statuses[kind];
  if (!node) {
    return;
  }
  node.textContent = text;
  node.style.color = isError ? "#a53a1c" : "";
}

async function request(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || data.message || "Request failed.");
  }
  return data;
}

function switchTab(tabId) {
  elements.tabs.forEach((tab) => {
    const active = tab.dataset.tab === tabId;
    tab.classList.toggle("active", active);
    elements.panels[tab.dataset.tab].classList.toggle("active", active);
  });
}

function buildOptions(select, values, selected) {
  select.innerHTML = values
    .map((value) => {
      const isSelected = String(value.value) === String(selected) ? " selected" : "";
      return `<option value="${value.value}"${isSelected}>${value.label}</option>`;
    })
    .join("");
}

function toClockParts(value) {
  const raw = String(value || "09:00");
  const [rawHour, rawMinute] = raw.split(":");
  let hour = Number(rawHour);
  const minute = String(rawMinute || "00").padStart(2, "0");
  let meridiem = "AM";

  if (Number.isNaN(hour)) {
    hour = 9;
  }
  if (hour >= 12) {
    meridiem = "PM";
  }
  hour = hour % 12 || 12;

  return { hour: String(hour), minute, meridiem };
}

function to24HourTime(hour, minute, meridiem) {
  let parsedHour = Number(hour);
  if (Number.isNaN(parsedHour) || parsedHour < 1) {
    parsedHour = 12;
  }

  parsedHour = parsedHour % 12;
  if (String(meridiem).toUpperCase() === "PM") {
    parsedHour += 12;
  }

  const paddedHour = String(parsedHour).padStart(2, "0");
  const paddedMinute = String(minute || "00").padStart(2, "0");
  return `${paddedHour}:${paddedMinute}`;
}

function displayParticipants(participants) {
  return (participants || []).map((name) => {
    const text = String(name || "").trim();
    if (!text) {
      return "";
    }
    const lowered = text.toLowerCase();
    if (lowered === state.config.user_name.toLowerCase() || lowered === "me" || lowered === "myself") {
      return "Me";
    }
    return text;
  }).filter(Boolean);
}

function createRow(item = {}) {
  const fragment = elements.rowTemplate.content.cloneNode(true);
  const row = fragment.querySelector(".schedule-row");
  const clock = toClockParts(item.time);
  const hourSelect = row.querySelector('[data-field="hour"]');
  const minuteSelect = row.querySelector('[data-field="minute"]');
  const meridiemSelect = row.querySelector('[data-field="meridiem"]');
  const inviteInput = row.querySelector('[data-field="invite"]');
  const inviteButton = row.querySelector(".invite-toggle");

  buildOptions(
    hourSelect,
    Array.from({ length: 12 }, (_, index) => {
      const value = String(index + 1);
      return { value, label: value };
    }),
    clock.hour,
  );
  buildOptions(
    minuteSelect,
    Array.from({ length: 12 }, (_, index) => {
      const value = String(index * 5).padStart(2, "0");
      return { value, label: value };
    }),
    clock.minute,
  );
  meridiemSelect.value = clock.meridiem;

  row.querySelector('[data-field="title"]').value = item.title || "";
  row.querySelector('[data-field="duration"]').value = item.duration_min || 60;
  row.querySelector('[data-field="participants"]').value = displayParticipants(item.participants).join(", ") || "Me";
  inviteInput.checked = Boolean(item.calendar_invite);

  const syncInviteState = () => {
    inviteButton.classList.toggle("active", inviteInput.checked);
    inviteButton.setAttribute("aria-pressed", inviteInput.checked ? "true" : "false");
    inviteButton.textContent = "Invite";
  };

  inviteButton.addEventListener("click", () => {
    inviteInput.checked = !inviteInput.checked;
    syncInviteState();
  });
  syncInviteState();

  row.querySelector(".remove-row").addEventListener("click", () => {
    row.remove();
    if (!elements.scheduleList.children.length) {
      elements.scheduleList.appendChild(createRow());
    }
  });

  return row;
}

function renderPlan(plan) {
  const normalized = plan || {
    date: new Date().toISOString().slice(0, 10),
    summary: "",
    top_3: ["", "", ""],
    schedule: [],
    notes: [],
  };

  elements.date.value = normalized.date || new Date().toISOString().slice(0, 10);
  elements.summary.value = normalized.summary || "";
  elements.top.forEach((input, index) => {
    input.value = (normalized.top_3 || [])[index] || "";
  });
  elements.notes.value = (normalized.notes || []).join("\n");

  elements.scheduleList.innerHTML = "";
  const schedule = normalized.schedule && normalized.schedule.length ? normalized.schedule : [{}];
  schedule.forEach((item) => elements.scheduleList.appendChild(createRow(item)));
}

function collectPlan() {
  const schedule = [...elements.scheduleList.querySelectorAll(".schedule-row")].map((row) => {
    const participants = row
      .querySelector('[data-field="participants"]')
      .value.split(",")
      .map((part) => part.trim())
      .filter(Boolean);

    return {
      time: to24HourTime(
        row.querySelector('[data-field="hour"]').value,
        row.querySelector('[data-field="minute"]').value,
        row.querySelector('[data-field="meridiem"]').value,
      ),
      title: row.querySelector('[data-field="title"]').value.trim(),
      duration_min: Number(row.querySelector('[data-field="duration"]').value || 0),
      participants,
      calendar_invite: row.querySelector('[data-field="invite"]').checked,
    };
  });

  return {
    date: elements.date.value,
    summary: elements.summary.value.trim(),
    top_3: elements.top.map((input) => input.value.trim()).filter(Boolean),
    schedule: schedule.filter((item) => item.time && item.title),
    notes: elements.notes.value
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean),
  };
}

function renderDocuments(kind) {
  const target = kind === "diary" ? elements.diaryList : elements.bookList;
  const docs = state.documents.filter((item) => item.kind === kind);
  target.innerHTML = "";

  if (!docs.length) {
    target.innerHTML = `<div class="document-card"><p>No ${kind} entries saved yet.</p></div>`;
    return;
  }

  docs.forEach((doc) => {
    const card = document.createElement("article");
    card.className = "document-card";
    const preview = doc.content.length > 180 ? `${doc.content.slice(0, 180)}...` : doc.content;
    card.innerHTML = `
      <h4>${escapeHtml(doc.title || kind)}</h4>
      <p class="document-meta">Updated ${escapeHtml(doc.updated_at || "")}</p>
      <p>${escapeHtml(preview)}</p>
    `;
    target.appendChild(card);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function initializeImageCards() {
  document.querySelectorAll(".image-card").forEach((card) => {
    const image = card.querySelector(".image-fill");
    if (!image) {
      return;
    }

    const activateImage = () => card.classList.remove("is-fallback");
    const activateFallback = () => card.classList.add("is-fallback");

    if (image.complete && image.naturalWidth > 0) {
      activateImage();
      return;
    }

    if (image.complete && image.naturalWidth === 0) {
      activateFallback();
      return;
    }

    image.addEventListener("load", activateImage, { once: true });
    image.addEventListener("error", activateFallback, { once: true });
  });
}

async function loadState() {
  const response = await fetch("/api/state");
  const data = await response.json();
  state.config = data.config || state.config;
  state.plan = data.plan || null;
  state.documents = Array.isArray(data.documents) ? data.documents : [];

  if (elements.partnerLabel) {
    elements.partnerLabel.textContent = `Send to ${state.config.partner_name}`;
  }
  if (elements.sendPlan) {
    elements.sendPlan.textContent = `Send to ${state.config.partner_name}`;
    elements.sendPlan.disabled = !state.config.can_send_plan;
  }
  if (elements.timezoneLabel) {
    elements.timezoneLabel.textContent = state.config.timezone || "Asia/Colombo";
  }
  if (elements.prompt) {
    elements.prompt.placeholder =
    `Example: Plan my day around client work from 9 to 4, gym at 6, and dinner with ${partnerName()} at 8.`;
  }
  if (elements.diaryContent) {
    elements.diaryContent.placeholder =
    `Write freely. This stays as diary content and is not part of the plan email to ${partnerName()}.`;
  }
  if (elements.bookContent) {
    elements.bookContent.placeholder =
    "Keep your longer writing here. It will save separately from the day plan.";
  }

  renderPlan(state.plan);
  renderDocuments("diary");
  renderDocuments("book");
}

elements.tabs.forEach((tab) => {
  tab.addEventListener("click", () => switchTab(tab.dataset.tab));
});

elements.generatePlan.addEventListener("click", async () => {
  try {
    setStatus("plan", "Generating...");
    const data = await request("/api/plan/generate", { prompt: elements.prompt.value.trim() });
    state.plan = data.plan;
    renderPlan(state.plan);
    setStatus("plan", "Generated. Edit anything before saving.");
  } catch (error) {
    setStatus("plan", error.message, true);
  }
});

elements.clearPlan.addEventListener("click", () => {
  renderPlan(null);
  setStatus("plan", "Cleared.");
});

elements.addRow.addEventListener("click", () => {
  elements.scheduleList.appendChild(createRow());
});

elements.savePlan.addEventListener("click", async () => {
  try {
    const plan = collectPlan();
    const data = await request("/api/plan/save", { plan });
    state.plan = data.plan;
    renderPlan(state.plan);
    setStatus("plan", data.message || "Day plan saved.");
  } catch (error) {
    setStatus("plan", error.message, true);
  }
});

elements.sendPlan.addEventListener("click", async () => {
  try {
    const plan = collectPlan();
    const data = await request("/api/plan/send", { plan });
    state.plan = data.plan;
    renderPlan(state.plan);
    setStatus("plan", data.message || "Plan sent.");
  } catch (error) {
    setStatus("plan", error.message, true);
  }
});

elements.saveDiary.addEventListener("click", async () => {
  try {
    const data = await request("/api/document/save", {
      kind: "diary",
      title: elements.diaryTitle.value.trim(),
      content: elements.diaryContent.value.trim(),
    });
    state.documents = [
      ...state.documents.filter((item) => item.id !== data.document.id),
      data.document,
    ].sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1));
    renderDocuments("diary");
    setStatus("diary", data.message || "Diary saved.");
    elements.diaryTitle.value = "";
    elements.diaryContent.value = "";
  } catch (error) {
    setStatus("diary", error.message, true);
  }
});

elements.saveBook.addEventListener("click", async () => {
  try {
    const data = await request("/api/document/save", {
      kind: "book",
      title: elements.bookTitle.value.trim(),
      content: elements.bookContent.value.trim(),
    });
    state.documents = [
      ...state.documents.filter((item) => item.id !== data.document.id),
      data.document,
    ].sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1));
    renderDocuments("book");
    setStatus("book", data.message || "Book note saved.");
    elements.bookTitle.value = "";
    elements.bookContent.value = "";
  } catch (error) {
    setStatus("book", error.message, true);
  }
});

loadState().catch((error) => {
  setStatus("plan", error.message, true);
});

initializeImageCards();
