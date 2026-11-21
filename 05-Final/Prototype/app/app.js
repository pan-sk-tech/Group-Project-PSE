"use strict";

const get = id => document.getElementById(id);
const searchForm = get("search-form");
const reportForm = get("report-form");
const visits = get("visits");
const results = get("results");
const originalEmpty = results.firstElementChild.cloneNode(true);
const originalReceipt = get("report-confirmation").firstElementChild.cloneNode(true);
let catalog;
const venues = new Map();
let searchRequest = null;
let saving = false;

function node(tag, className, content) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (content !== undefined) el.textContent = content;
  return el;
}

function message(id, content = "") {
  const el = get(id);
  el.textContent = content;
  el.hidden = !content;
}

async function api(path, body, signal) {
  const options = {signal, headers: {Accept: "application/json"}};
  if (body !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Cannot reach the campus service. Check that the local server is running.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok || !data) {
    const error = new Error(data?.error || "The campus service returned an unexpected response.");
    error.status = response.status;
    throw error;
  }
  return data;
}

// A retry after a lost receipt must refer to the same write, even after a tab refresh.
const pendingSubmissions = new Map();
function pendingKey(path) { return "campus-lost-found.pending.v1" + path; }
function readPending(path) {
  if (pendingSubmissions.has(path)) return pendingSubmissions.get(path);
  try {
    const saved = JSON.parse(sessionStorage.getItem(pendingKey(path)));
    if (saved && /^[a-f0-9]{64}$/.test(saved.key) && saved.payload && typeof saved.payload === "object") {
      pendingSubmissions.set(path, saved);
      return saved;
    }
  } catch { /* Storage can be disabled by the browser. */ }
  return null;
}
async function submitNewRecord(path, payload) {
  let pending = readPending(path);
  if (!pending || JSON.stringify(pending.payload) !== JSON.stringify(payload)) {
    const bytes = crypto.getRandomValues(new Uint8Array(32));
    const key = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
    pending = {key, payload};
    pendingSubmissions.set(path, pending);
    try { sessionStorage.setItem(pendingKey(path), JSON.stringify(pending)); } catch {}
  }
  return api(path, {...payload, submissionKey: pending.key});
}
function clearPending(path) {
  pendingSubmissions.delete(path);
  try { sessionStorage.removeItem(pendingKey(path)); } catch {}
}
function restoreDraft(path, prefix, fieldIds) {
  const pending = readPending(path);
  if (!pending) return;
  fillRecordForm(prefix, fieldIds, pending.payload);
}

function fillRecordForm(prefix, fieldIds, data) {
  const place = lookupPlace(data.location);
  if (place) {
    const building = get(prefix + "-building");
    building.value = place.building;
    building.dispatchEvent(new Event("change", {bubbles: true}));
    const venue = get(prefix === "urgent" ? "urgent-area" : prefix + "-location");
    const isManual = !venues.has(place.id);
    venue.value = isManual ? manualRoom : place.id;
    venue.dispatchEvent(new Event("change", {bubbles: true}));
    if (isManual) {
      const door = venue.closest(".place-picker").querySelector(".door-number");
      door.value = data.location.slice(5);
      door.dispatchEvent(new Event("input", {bubbles: true}));
    }
  }
  for (const [field, id] of Object.entries(fieldIds)) get(id).value = data[field] || "";
}

function populate(select, options, placeholder) {
  select.replaceChildren(new Option(placeholder, ""));
  for (const value of options) select.add(new Option(value, value));
}

const manualRoom = "__enter_room__";
let pickerSequence = 0;

function parseDoor(value, building) {
  const block = building.match(/^Block ([A-E])$/)?.[1];
  const text = value.normalize("NFKC").trim().toUpperCase();
  const formatError = "Enter the door number with its floor, for example " + block + "3.07 or 3.07.";
  if (!text || !block) return {error: formatError};
  const match = text.match(/^(?:([A-E])(?:\s*-\s*|\s*))?(LG[1-9]?|B[1-9]|G|[0-9]{1,2})(?:\s*[.-]\s*|\s+)([0-9]{1,3})([A-Z]?)$/);
  if (!match || !Number(match[3])) return {error: formatError};
  if (match[1] && match[1] !== block) {
    return {error: "This number starts with Block " + match[1] + ". Select that building or check the door number."};
  }
  let floor = match[2];
  if (/^[0-9]+$/.test(floor)) floor = Number(floor) ? String(Number(floor)) : "G";
  const door = String(Number(match[3])).padStart(2, "0") + match[4];
  const code = block + floor + "." + door;
  const id = catalog?.roomAliases?.[code] || "room:" + code;
  return {code, floor, id};
}

function lookupPlace(id) {
  const listed = venues.get(id);
  if (listed) return listed;
  if (!id?.startsWith("room:")) return null;
  const code = id.slice(5);
  const building = "Block " + code[0];
  const result = parseDoor(code, building);
  if (result.error) return null;
  const knownRoom = venues.get(result.id);
  if (knownRoom) return knownRoom;
  const level = "Level " + result.floor;
  return {id, name: "Room " + result.code, building, level, room: "", zone: building + " · " + level, userEntered: true};
}

function placeLabel(id) {
  const place = lookupPlace(id);
  if (!place) return "Campus venue";
  const room = place.room && !place.name.includes(place.room) ? place.room : "";
  return [place.name, place.building, place.level, room, place.userEntered ? "User-entered" : ""].filter(Boolean).join(" · ");
}

function nearbyZoneLabel(id) {
  const place = lookupPlace(id);
  return place ? (place.level ? place.building + " · " + place.level : place.name) : "this campus area";
}

function locationValue(venue) {
  return venue.value === manualRoom ? venue.dataset.roomLocation || "" : venue.value;
}

function floorRank(level) {
  const value = level.replace(/^Level /i, "").toUpperCase();
  if (/^B[1-9]$/.test(value)) return -10 - Number(value.slice(1));
  if (value.startsWith("LG")) return -(Number(value.slice(2)) || 1);
  return value === "G" ? 0 : Number(value) || 100;
}

function addVenueOptions(select, places) {
  const groups = new Map();
  for (const place of places) {
    if (!groups.has(place.level)) groups.set(place.level, []);
    groups.get(place.level).push(place);
  }
  const floors = [...groups.keys()].sort((a, b) => floorRank(a) - floorRank(b));
  for (const floor of floors) {
    const group = floor ? document.createElement("optgroup") : select;
    if (floor) {
      group.label = floor;
      select.append(group);
    }
    for (const place of groups.get(floor)) {
      const label = place.room && !place.name.includes(place.room) ? place.room + " · " + place.name : place.name;
      group.append(new Option(label, place.id));
    }
  }
}

function initialisePicker(venue, selected = "") {
  const picker = venue.closest(".place-picker");
  const building = picker.querySelector(".place-building");
  const note = picker.querySelector(".place-note");
  const doorField = get("door-field-template").content.firstElementChild.cloneNode(true);
  const door = doorField.querySelector(".door-number");
  const errorText = doorField.querySelector(".door-error");
  const prefix = venue.id || "visit-" + (++pickerSequence);
  door.id = prefix + "-door";
  errorText.id = prefix + "-door-error";
  door.setAttribute("aria-describedby", errorText.id);
  note.before(doorField);
  const buildings = [...new Set(catalog.places.map(place => place.building))];
  buildings.sort((left, right) => {
    if (left === right) return 0;
    if (left === "Earlier records") return 1;
    if (right === "Earlier records") return -1;
    return left.localeCompare(right, "en", {numeric: true});
  });
  populate(building, buildings, "Choose building");
  building.value = lookupPlace(selected)?.building || "";

  function syncDoor(showError = false) {
    const manual = venue.value === manualRoom;
    doorField.hidden = !manual;
    door.disabled = !manual;
    door.required = manual;
    const result = manual ? parseDoor(door.value, building.value) : {};
    const invalid = Boolean(showError && result.error);
    door.setCustomValidity(result.error || "");
    door.setAttribute("aria-invalid", String(invalid));
    errorText.textContent = invalid ? result.error : "";
    errorText.hidden = !invalid;
    venue.dataset.roomLocation = result.id || "";
    const place = lookupPlace(locationValue(venue));
    note.textContent = manual && place ? placeLabel(place.id) : "";
    note.hidden = !note.textContent;
  }

  function showBuilding(value = "") {
    const choices = catalog.places.filter(place => place.building === building.value);
    venue.replaceChildren(new Option(building.value ? "Choose a listed place" : "Select a building first", ""));
    if (/^Block [A-E]$/.test(building.value)) {
      venue.add(new Option("Enter a room number…", manualRoom));
      door.placeholder = "e.g. " + building.value.slice(-1) + "3.07 or 3.07";
    }
    addVenueOptions(venue, choices);
    door.value = value.startsWith("room:") && !venues.has(value) ? value.slice(5) : "";
    venue.value = door.value ? manualRoom : value;
    venue.disabled = !building.value;
    syncDoor();
  }
  showBuilding(selected);
  venue.addEventListener("change", event => {
    door.value = "";
    syncDoor();
    if (venue.value === manualRoom && event.isTrusted) door.focus();
    venue.dispatchEvent(new Event("venuechange", {bubbles: true}));
  });
  door.addEventListener("input", () => {
    syncDoor();
    venue.dispatchEvent(new Event("venuechange", {bubbles: true}));
  });
  door.addEventListener("blur", () => syncDoor(Boolean(door.value.trim())));
  door.addEventListener("invalid", () => syncDoor(true));
  building.addEventListener("change", () => {
    showBuilding();
    venue.dispatchEvent(new Event("change", {bubbles: true}));
  });
  return building;
}

function resetPlaceInForm(form) {
  form.reset();
  const building = form.querySelector(".place-building");
  building.dispatchEvent(new Event("change", {bubbles: true}));
}

function updateStops() {
  Array.from(visits.children).forEach((stop, i) => {
    stop.querySelector(".stop-number").textContent = String(i + 1);
    const remove = stop.querySelector(".remove");
    remove.hidden = visits.children.length === 1;
    remove.setAttribute("aria-label", "Remove stop " + (i + 1));
  });
}

function addStop(visit = {}, focus = false) {
  const stop = get("stop-template").content.firstElementChild.cloneNode(true);
  const location = stop.querySelector(".visit-location");
  const building = initialisePicker(location, visit.location);
  stop.querySelector(".visit-start").value = visit.start || "";
  stop.querySelector(".visit-end").value = visit.end || "";
  stop.querySelector(".remove").addEventListener("click", () => {
    const adjacent = stop.nextElementSibling || stop.previousElementSibling;
    stop.remove();
    updateStops();
    invalidateSearch();
    adjacent?.querySelector(".place-building").focus();
  });
  visits.append(stop);
  updateStops();
  if (focus) building.focus();
}

function campusNow() {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kuala_Lumpur", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23"
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return values.year + "-" + values.month + "-" + values.day + "T" + values.hour + ":" + values.minute;
}

const itemMenu = get("search-category");
const categoryShortcuts = Array.from(searchForm.querySelectorAll("button[data-item-type]"));
function showSelectedCategory() {
  const chosen = itemMenu.value;
  const hasShortcut = categoryShortcuts.some(button => button.dataset.itemType === chosen);
  for (const button of categoryShortcuts) {
    button.setAttribute("aria-pressed", String(button.dataset.itemType === chosen));
  }
  const selectedViaMenu = Boolean(chosen) && !hasShortcut;
  get("more-category").classList.toggle("selected", selectedViaMenu);
  get("more-caption").textContent = selectedViaMenu ? chosen : "More";
}
for (const button of categoryShortcuts) {
  button.addEventListener("click", () => {
    itemMenu.value = button.dataset.itemType;
    itemMenu.dispatchEvent(new Event("change", {bubbles: true}));
  });
}
itemMenu.addEventListener("change", showSelectedCategory);
itemMenu.addEventListener("invalid", () => message("search-error", "Choose the type of item you lost."));
function showSelectedColour() {
  const colour = get("search-colour").value;
  get("colour-summary").textContent = colour ? "Colour · " + colour : "Add a colour";
}
get("search-colour").addEventListener("change", showSelectedColour);

async function loadCatalog() {
  get("retry").hidden = true;
  message("catalog-status", "Loading campus locations…");
  try {
    catalog = await api("/api/catalog");
    for (const prefix of ["search", "found"]) {
      populate(get(prefix + "-category"), catalog.categories, "Select type");
      populate(get(prefix + "-colour"), catalog.colours, prefix === "found" ? "Unspecified" : "Any colour");
    }
    showSelectedCategory();
    showSelectedColour();
    populate(get("urgent-category"), catalog.categories, "Select type");
    populate(get("notice-category"), catalog.categories, "Select type");
    venues.clear();
    for (const place of catalog.places) venues.set(place.id, place);
    for (const id of ["urgent-area", "helper-area", "found-location", "notice-location"]) initialisePicker(get(id));
    renderOwned();
    visits.replaceChildren();
    addStop();
    get("found-at").value = campusNow();
    get("notice-at").value = campusNow();
    restoreDraft("/api/lost-notices", "notice", noticeFields);
    restoreDraft("/api/items", "found", {category:"found-category", colour:"found-colour", foundAt:"found-at",
      spot:"found-spot", description:"description", collectionPoint:"collection-point"});
    restoreDraft("/api/alerts", "urgent", {category:"urgent-category", spot:"urgent-spot", description:"urgent-description"});
    document.querySelectorAll(".form-fields").forEach(el => { el.disabled = false; });
    message("catalog-status");
    syncVisibleRecords();
  } catch (error) {
    message("catalog-status", error.message);
    get("retry").hidden = false;
  }
}

function invalidateSearch() {
  if (searchRequest) searchRequest.abort();
  searchRequest = null;
  get("search-button").disabled = false;
  get("match-count").hidden = true;
  get("result-status").textContent = "";
  results.setAttribute("aria-busy", "false");
  results.replaceChildren(originalEmpty.cloneNode(true));
  message("search-error");
}

function readVisits() {
  return Array.from(visits.children, stop => ({
    location: locationValue(stop.querySelector(".visit-location")),
    start: stop.querySelector(".visit-start").value,
    end: stop.querySelector(".visit-end").value
  }));
}

function describeTime(value) {
  // These are campus wall-clock times. Avoid converting them to the browser's time zone.
  const [day, time] = value.split("T");
  const [year, month, date] = day.split("-").map(Number);
  const label = new Intl.DateTimeFormat("en-GB", {
    year: "numeric", month: "short", day: "numeric", timeZone: "UTC"
  }).format(new Date(Date.UTC(year, month - 1, date)));
  return label + " · " + time;
}

function detailList(entries) {
  const list = node("dl");
  for (const [label, value] of entries) {
    list.append(node("dt", "", label), node("dd", "", value));
  }
  return list;
}

function matchCard(match) {
  const item = match.item;
  const card = node("article", "match-card");
  const header = node("div", "match-title");
  header.append(node("h3", "", item.category), node("span", "record-id", "#" + item.id));
  card.append(header, node("p", "description", item.description));
  card.append(detailList([
    ["Colour", item.colour || "Unspecified"], ["Found at", placeLabel(item.location)],
    ...(item.spot ? [["Specific spot", item.spot]] : []),
    ["Found on", describeTime(item.foundAt)], ["Collect from", item.collectionPoint]
  ]));
  const reasons = node("div", "reasons");
  const bullets = node("ul");
  for (const reason of match.reasons) bullets.append(node("li", "", reason));
  reasons.append(node("strong", "", "Why this matched"), bullets);
  card.append(reasons);
  return card;
}

function showMatches(matches) {
  const numberLabel = matches.length + (matches.length === 1 ? " match" : " matches");
  get("match-count").textContent = numberLabel;
  get("match-count").hidden = false;
  get("result-status").textContent = numberLabel + " found.";
  if (matches.length) {
    results.replaceChildren(...matches.map(matchCard));
  } else {
    const empty = node("div", "empty-state");
    const icon = node("span", "lens");
    icon.setAttribute("aria-hidden", "true");
    empty.append(icon, node("p", "", "No matching reports."));
    results.replaceChildren(empty);
  }
  focusFeedbackOnMobile("matches-title");
}

function focusFeedbackOnMobile(id) {
  if (window.matchMedia("(max-width: 700px)").matches && !get(id).closest("section").hidden) {
    const target = get(id);
    target.tabIndex = -1;
    target.focus({preventScroll: true});
    target.scrollIntoView({block: "start", behavior: "instant"});
  }
}

searchForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (searchRequest) return;
  invalidateSearch();
  const query = {category: get("search-category").value, colour: get("search-colour").value, visits: readVisits()};
  const request = new AbortController();
  searchRequest = request;
  get("search-button").disabled = true;
  results.setAttribute("aria-busy", "true");
  get("result-status").textContent = "Looking for matches.";
  results.replaceChildren(node("p", "description", "Looking for matches…"));
  try {
    const data = await api("/api/search", query, request.signal);
    if (searchRequest === request) showMatches(data.matches);
  } catch (error) {
    if (searchRequest === request) {
      results.replaceChildren(originalEmpty.cloneNode(true));
      get("result-status").textContent = "";
      message("search-error", error.message);
    }
  } finally {
    if (searchRequest === request) {
      searchRequest = null;
      get("search-button").disabled = false;
      results.setAttribute("aria-busy", "false");
    }
  }
});

function showReceipt(item, moveFocus = true) {
  lastReceiptId = item.id;
  const receipt = node("div", "receipt");
  receipt.append(node("p", "", "Report #" + item.id + " saved."),
    node("p", "description", item.description),
    detailList([["Item", item.category], ["Found at", placeLabel(item.location)], ...(item.spot ? [["Specific spot", item.spot]] : []),
      ["Found on", describeTime(item.foundAt)], ["Collect from", item.collectionPoint]]));
  if (item.status === "claimed") receipt.append(node("p", "record-state", "Claimed"));
  get("report-confirmation").replaceChildren(receipt);
  if (moveFocus) focusFeedbackOnMobile("report-title");
}

reportForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (saving) return;
  const report = {
    category: get("found-category").value, colour: get("found-colour").value,
    location: locationValue(get("found-location")), foundAt: get("found-at").value,
    spot: get("found-spot").value.trim(), description: get("description").value.trim(), collectionPoint: get("collection-point").value.trim()
  };
  saving = true;
  reportForm.querySelector(".form-fields").disabled = true;
  message("report-error");
  get("report-confirmation").replaceChildren(node("p", "description", "Saving your report…"));
  try {
    const data = await submitNewRecord("/api/items", report);
    rememberRecord("found", data.item.id, data.manageToken);
    clearPending("/api/items");
    resetPlaceInForm(reportForm);
    get("found-at").value = campusNow();
    invalidateSearch();
    showReceipt(data.item);
    refreshFoundReports();
  } catch (error) {
    get("report-confirmation").replaceChildren(originalReceipt.cloneNode(true));
    message("report-error", error.message);
  } finally {
    saving = false;
    reportForm.querySelector(".form-fields").disabled = false;
  }
});

function selectMode(name) {
  if (name !== "urgent" && receiving) stopReceiving();
  ["search", "report", "notices", "urgent"].forEach(mode => {
    const selected = mode === name;
    get(mode + "-panel").hidden = !selected;
    const button = get("show-" + mode);
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  if (name === "report") refreshFoundReports();
  if (name === "notices") refreshNotices();
  if (name === "search") refreshVisibleSearch();
}
get("show-notices").addEventListener("click", () => selectMode("notices"));
get("show-urgent").addEventListener("click", () => selectMode("urgent"));
get("show-search").addEventListener("click", () => selectMode("search"));
get("show-report").addEventListener("click", () => selectMode("report"));
get("retry").addEventListener("click", loadCatalog);
for (const type of ["input", "change"]) {
  searchForm.addEventListener(type, invalidateSearch);
  reportForm.addEventListener(type, () => {
    message("report-error");
    lastReceiptId = null;
    get("report-confirmation").replaceChildren(originalReceipt.cloneNode(true));
  });
}
get("add-stop").addEventListener("click", () => {
  invalidateSearch();
  addStop({}, true);
});
get("example").addEventListener("click", () => {
  invalidateSearch();
  get("search-category").value = "Umbrella";
  get("search-colour").value = "Black";
  showSelectedCategory();
  showSelectedColour();
  visits.replaceChildren();
  addStop({location: "library-study-room", start: "2026-11-08T10:00", end: "2026-11-08T11:00"});
  addStop({location: "grand-hall", start: "2026-11-08T11:15", end: "2026-11-08T12:00"});
  searchForm.requestSubmit();
});

const urgentForm = get("urgent-form");
const storageKey = "campus-lost-found.owned-alerts.v1";
let ownedRequests = [];
let expiryTimer;
let sendingUrgent = false;
let receiving = false;
let pollTimer;
let pollRequest = null;
let lastFeed = null;
const closing = new Set();

function isCurrent(alert) {
  return Date.parse(alert.expiresAt) > Date.now();
}

function persistOwned() {
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(ownedRequests));
  } catch {
    // Browsers with restricted storage can still manage requests until this page closes.
  }
}

function readOwned() {
  try {
    const entries = JSON.parse(sessionStorage.getItem(storageKey) || "[]");
    if (Array.isArray(entries)) {
      ownedRequests = entries.filter(entry => entry?.alert && typeof entry.manageToken === "string" && isCurrent(entry.alert));
    }
  } catch {
    ownedRequests = [];
  }
}

function expiryLabel(instant) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kuala_Lumpur", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"
  }).format(new Date(instant)) + " (UTC+8)";
}

function alertEntry(alert) {
  const entry = node("article", "urgent-entry");
  const heading = node("h4", "", alert.category);
  entry.append(heading, node("p", "description", alert.description),
    detailList([["Venue", placeLabel(alert.location)], ["Check", alert.spot], ["Expires", expiryLabel(alert.expiresAt)]]));
  return entry;
}

function renderOwned() {
  clearTimeout(expiryTimer);
  const activeRequests = ownedRequests.filter(entry => isCurrent(entry.alert));
  if (activeRequests.length < ownedRequests.length) {
    get("urgent-status").textContent = "An urgent request reached its 30-minute expiry.";
  }
  ownedRequests = activeRequests;
  persistOwned();
  const list = get("my-requests");
  list.replaceChildren();
  if (!ownedRequests.length) {
    list.append(node("p", "hint empty-note", "No active requests from this tab."));
    return;
  }
  for (const entry of ownedRequests) {
    const card = alertEntry(entry.alert);
    const button = node("button", "text-link", "Close request");
    button.type = "button";
    button.disabled = closing.has(entry.alert.id);
    button.setAttribute("aria-label", "Close request for " + entry.alert.category + " at " + entry.alert.spot);
    button.addEventListener("click", () => closeOwned(entry, button));
    card.append(button);
    list.append(card);
  }
  const earliest = Math.min(...ownedRequests.map(entry => Date.parse(entry.alert.expiresAt)));
  expiryTimer = setTimeout(renderOwned, Math.max(0, earliest - Date.now()) + 10);
}

async function closeOwned(entry, button) {
  if (closing.has(entry.alert.id)) return;
  closing.add(entry.alert.id);
  button.disabled = true;
  get("urgent-status").textContent = "Closing your request…";
  try {
    await api("/api/alerts/close", {id: entry.alert.id, manageToken: entry.manageToken});
    ownedRequests = ownedRequests.filter(saved => saved.alert.id !== entry.alert.id);
    get("urgent-status").textContent = "Request closed.";
    get("my-requests-title").tabIndex = -1;
    get("my-requests-title").focus();
  } catch (error) {
    get("urgent-status").textContent = error.message;
  } finally {
    closing.delete(entry.alert.id);
    renderOwned();
  }
}

urgentForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (sendingUrgent) return;
  const alert = {
    category: get("urgent-category").value, location: locationValue(get("urgent-area")),
    spot: get("urgent-spot").value.trim(), description: get("urgent-description").value.trim()
  };
  sendingUrgent = true;
  urgentForm.querySelector(".form-fields").disabled = true;
  message("urgent-error");
  get("urgent-status").textContent = "Sending your request…";
  try {
    const entry = await submitNewRecord("/api/alerts", alert);
    const active = !entry.closed && isCurrent(entry.alert);
    ownedRequests = ownedRequests.filter(saved => saved.alert.id !== entry.alert.id);
    if (active) ownedRequests.unshift({alert: entry.alert, manageToken: entry.manageToken});
    renderOwned();
    clearPending("/api/alerts");
    resetPlaceInForm(urgentForm);
    get("urgent-status").textContent = active
      ? "Request posted. Helpers listening in " + nearbyZoneLabel(entry.alert.location) + " can now see it."
      : "Your earlier request has already ended.";
    focusFeedbackOnMobile("my-requests-title");
  } catch (error) {
    get("urgent-status").textContent = "";
    message("urgent-error", error.message);
  } finally {
    sendingUrgent = false;
    urgentForm.querySelector(".form-fields").disabled = false;
  }
});

function resetFeed() {
  clearTimeout(pollTimer);
  if (pollRequest) pollRequest.abort();
  pollRequest = null;
  lastFeed = null;
  get("nearby-list").replaceChildren();
}

function stopReceiving() {
  receiving = false;
  resetFeed();
  const toggle = get("toggle-receiving");
  toggle.setAttribute("aria-pressed", "false");
  toggle.textContent = "Receive nearby requests";
  toggle.disabled = !locationValue(get("helper-area"));
  get("nearby-status").textContent = "Receiving is off.";
}

async function pollArea() {
  const area = locationValue(get("helper-area"));
  if (!receiving || !area || pollRequest) return;
  const request = new AbortController();
  pollRequest = request;
  try {
    const data = await api("/api/alerts?location=" + encodeURIComponent(area), undefined, request.signal);
    if (pollRequest !== request) return;
    const zone = lookupPlace(area)?.zone;
    const active = data.alerts.filter(alert => zone && lookupPlace(alert.location)?.zone === zone && isCurrent(alert));
    const signature = JSON.stringify(active);
    if (signature !== lastFeed) {
      lastFeed = signature;
      get("nearby-list").replaceChildren(...active.map(alertEntry));
      const label = active.length === 1 ? "active request" : "active requests";
      get("nearby-status").textContent = active.length
        ? active.length + " " + label + " in " + nearbyZoneLabel(area) + "."
        : "Listening in " + nearbyZoneLabel(area) + ". No active requests.";
    }
  } catch (error) {
    if (pollRequest !== request) return;
    lastFeed = null;
    get("nearby-list").replaceChildren();
    get("nearby-status").textContent = error.message + " Checking again shortly.";
  } finally {
    if (pollRequest === request) {
      pollRequest = null;
      if (receiving) pollTimer = setTimeout(pollArea, 3000);
    }
  }
}

function startReceiving() {
  const area = locationValue(get("helper-area"));
  if (!area) return;
  resetFeed();
  receiving = true;
  get("toggle-receiving").setAttribute("aria-pressed", "true");
  get("toggle-receiving").textContent = "Stop receiving";
  get("nearby-status").textContent = "Checking " + nearbyZoneLabel(area) + "…";
  pollArea();
}

get("toggle-receiving").addEventListener("click", () => {
  if (receiving) stopReceiving();
  else startReceiving();
});
get("helper-area").addEventListener("venuechange", () => {
  const valid = Boolean(locationValue(get("helper-area")));
  if (receiving && valid) {
    startReceiving();
  } else if (receiving) {
    resetFeed();
    get("nearby-status").textContent = "Receiving paused. Choose a venue to continue.";
  } else {
    stopReceiving();
  }
  get("toggle-receiving").disabled = !valid && !receiving;
});
get("receive-form").addEventListener("submit", event => event.preventDefault());

function selectUrgentRole(role) {
  for (const name of ["requester", "helper"]) {
    const active = role === name;
    get("urgent-" + name).setAttribute("aria-pressed", String(active));
    get(name + "-panel").hidden = !active;
  }
  if (role === "requester" && receiving) stopReceiving();
}
get("urgent-requester").addEventListener("click", () => selectUrgentRole("requester"));
get("urgent-helper").addEventListener("click", () => selectUrgentRole("helper"));
urgentForm.addEventListener("input", () => message("urgent-error"));
window.addEventListener("pagehide", stopReceiving);
const noticeForm = get("notice-form");
const noticeFields = {category: "notice-category", lostAt: "notice-at", description: "notice-description"};
const recordKeys = {found: "campus-lost-found.finder.", notice: "campus-lost-found.notice-owner."};
const volatileKeys = new Map();
let noticeView = "public";
let editingNotice = null;
let savingNotice = false;
let noticeRead = 0;
let foundRead = 0;
let lastReceiptId = null;

function rememberRecord(kind, id, token) {
  if (!Number.isSafeInteger(id) || !token) return;
  const key = recordKeys[kind] + id;
  try {
    localStorage.setItem(key, token);
    volatileKeys.delete(key);
  } catch {
    volatileKeys.set(key, token);
    const hint = kind === "found" ? get("my-finds").querySelector(".record-hint") : get("notice-mine-hint");
    hint.textContent = "Browser storage is unavailable. Keep this page open to manage your report.";
  }
}

function ownedKeys(kind) {
  const prefix = recordKeys[kind];
  const tokens = new Map();
  function add(key, token) {
    if (!key?.startsWith(prefix) || !token || !/^[1-9]\d*$/.test(key.slice(prefix.length))) return;
    const id = Number(key.slice(prefix.length));
    if (Number.isSafeInteger(id)) tokens.set(id, token);
  }
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith(prefix)) add(key, localStorage.getItem(key));
    }
  } catch { /* Management remains available in this tab while it is open. */ }
  volatileKeys.forEach((value, key) => add(key, value));
  return tokens;
}

async function ownedRecords(kind, path) {
  const keys = [...ownedKeys(kind).entries()].sort(([a], [b]) => b - a);
  const result = await Promise.all(keys.map(async ([id, token]) => {
    try {
      const row = await api(path + "/" + id);
      return {record: kind === "found" ? row.item : row.notice, token};
    } catch (error) {
      if (error.status === 404) return null;
      throw error;
    }
  }));
  return result.filter(Boolean);
}

function actionButton(action, label, handler, cls = "text-link") {
  const button = node("button", cls, label);
  button.type = "button";
  button.dataset.action = action;
  button.addEventListener("click", handler);
  return button;
}

function recordCard(record, kind) {
  const card = node("article", "record-card");
  card.dataset.recordId = String(record.id);
  const heading = node("div", "match-title");
  const status = {available: "Available", claimed: "Claimed", open: "Open", resolved: "Resolved"};
  heading.append(node("h3", "", record.category + " #" + record.id), node("span", "record-state", status[record.status]));
  const details = kind === "found"
    ? [["Found at", placeLabel(record.location)], ["Collect from", record.collectionPoint]]
    : [["Last seen", describeTime(record.lostAt)], ["Place", placeLabel(record.location)]];
  card.append(heading, node("p", "description", record.description), detailList(details));
  return card;
}

// Hide the final action until the reporter explicitly acknowledges the handover or resolution.
function confirmOnCard(card, opener, question, action, label, commit, onError) {
  if (card.querySelector(".record-confirmation")) return;
  const box = node("div", "record-confirmation");
  const actions = node("div", "record-actions");
  const cancel = actionButton("cancel", "Cancel", () => {
    box.remove();
    opener.hidden = false;
    opener.focus();
  });
  const confirm = actionButton(action, label, async () => {
    cancel.disabled = confirm.disabled = true;
    try {
      await commit();
    } catch (error) {
      cancel.disabled = confirm.disabled = false;
      onError(error);
    }
  }, "outline");
  box.append(node("p", "", question), actions);
  actions.append(confirm, cancel);
  opener.hidden = true;
  card.append(box);
  confirm.focus();
}

function foundCard({record, token}) {
  const card = recordCard(record, "found");
  if (record.status !== "available") return card;
  const actions = node("div", "record-actions");
  const handover = actionButton("handover", "Confirm handover", () => {
    confirmOnCard(card, handover, "Have you returned this item to its owner?", "confirm-handover", "Yes, mark claimed", async () => {
      const result = await api("/api/items/claim", {id: record.id, manageToken: token});
      if (lastReceiptId === record.id) showReceipt(result.item, false);
      invalidateSearch();
      message("my-finds-status", "Handover confirmed. This item is now claimed.");
      await refreshFoundReports();
    }, error => message("my-finds-status", error.message));
  });
  actions.append(handover);
  card.append(actions);
  return card;
}

async function refreshFoundReports() {
  const read = ++foundRead;
  if (!catalog || !ownedKeys("found").size) {
    get("my-finds").hidden = true;
    return;
  }
  get("my-finds").hidden = false;
  try {
    const entries = await ownedRecords("found", "/api/items");
    if (read !== foundRead) return;
    get("my-finds-list").replaceChildren(...entries.map(foundCard));
    get("my-finds").hidden = !entries.length;
    const receipt = entries.find(entry => entry.record.id === lastReceiptId);
    if (receipt?.record.status === "claimed") showReceipt(receipt.record, false);
  } catch (error) {
    if (read === foundRead) message("my-finds-status", error.message);
  }
}

function editNotice(record, token) {
  if (savingNotice || record.status !== "open") return;
  editingNotice = {id: record.id, token, revision: record.revision};
  fillRecordForm("notice", noticeFields, record);
  get("notice-form-title").textContent = "Edit notice #" + record.id;
  get("notice-save").textContent = "Save changes";
  get("notice-cancel").hidden = false;
  message("notice-error");
  get("notice-category").focus();
}

function resetNoticeEditor() {
  editingNotice = null;
  resetPlaceInForm(noticeForm);
  get("notice-at").value = campusNow();
  get("notice-form-title").textContent = "Post a lost notice";
  get("notice-save").textContent = "Post lost notice";
  get("notice-cancel").hidden = true;
  message("notice-error");
  restoreDraft("/api/lost-notices", "notice", noticeFields);
}

function noticeCard({record, token}) {
  const card = recordCard(record, "notice");
  if (record.status !== "open" || !token) return card;
  const actions = node("div", "record-actions");
  const edit = actionButton("edit-notice", "Edit notice", () => editNotice(record, token));
  const resolve = actionButton("resolve-notice", "Mark resolved", () => {
    confirmOnCard(card, resolve, "Has this lost notice been resolved? It will leave the open board.", "confirm-resolve", "Yes, mark resolved", async () => {
      await api("/api/lost-notices/resolve", {id: record.id, manageToken: token});
      if (editingNotice?.id === record.id) resetNoticeEditor();
      message("notice-status", "Notice #" + record.id + " resolved.");
      await refreshNotices();
    }, error => message("notice-list-error", error.message));
  });
  actions.append(edit, resolve);
  card.append(actions);
  return card;
}

function selectNoticeView(view) {
  noticeView = view;
  const mine = view === "mine";
  get("notice-public-tab").setAttribute("aria-pressed", String(!mine));
  get("notice-mine-tab").setAttribute("aria-pressed", String(mine));
  get("notice-board-list").hidden = mine;
  get("notice-mine-list").hidden = get("notice-mine-hint").hidden = !mine;
  return refreshNotices();
}

async function refreshNotices() {
  const read = ++noticeRead;
  if (!catalog) return;
  const mine = noticeView === "mine";
  const list = get(mine ? "notice-mine-list" : "notice-board-list");
  list.setAttribute("aria-busy", "true");
  message("notice-list-error");
  try {
    const entries = mine ? await ownedRecords("notice", "/api/lost-notices")
      : (await api("/api/lost-notices")).notices.map(record => ({record}));
    if (read !== noticeRead) return;
    if (mine && editingNotice && entries.some(e => e.record.id === editingNotice.id && e.record.status === "resolved")) {
      resetNoticeEditor();
    }
    if (entries.length) list.replaceChildren(...entries.map(noticeCard));
    else list.replaceChildren(node("p", "record-hint", mine ? "No notices from this browser yet." : "No open lost notices."));
  } catch (error) {
    if (read === noticeRead) {
      list.replaceChildren();
      message("notice-list-error", error.message);
    }
  } finally {
    if (read === noticeRead) list.removeAttribute("aria-busy");
  }
}

noticeForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (savingNotice) return;
  const payload = {
    category: get("notice-category").value, location: locationValue(get("notice-location")),
    lostAt: get("notice-at").value, description: get("notice-description").value.trim()
  };
  const editing = editingNotice;
  savingNotice = true;
  noticeForm.querySelector("fieldset").disabled = true;
  message("notice-error");
  try {
    const result = editing
      ? await api("/api/lost-notices/update", {...payload, id: editing.id, manageToken: editing.token, expectedRevision: editing.revision})
      : await submitNewRecord("/api/lost-notices", payload);
    if (!editing) {
      rememberRecord("notice", result.notice.id, result.manageToken);
      clearPending("/api/lost-notices");
    }
    resetNoticeEditor();
    message("notice-status", "Notice #" + result.notice.id + (editing ? " updated." : " posted."));
    await selectNoticeView("mine");
    focusFeedbackOnMobile("notice-board-title");
  } catch (error) {
    if (error.status === 409 && editing) {
      await selectNoticeView("mine");
      message("notice-error", editingNotice ? error.message + " Cancel this edit and reopen the notice to load the latest version." : error.message);
    } else {
      message("notice-error", error.message);
    }
  } finally {
    savingNotice = false;
    noticeForm.querySelector("fieldset").disabled = false;
  }
});
get("notice-cancel").addEventListener("click", resetNoticeEditor);
get("notice-refresh").addEventListener("click", refreshNotices);
get("notice-mine-tab").addEventListener("click", () => { message("notice-status"); selectNoticeView("mine"); });
get("notice-public-tab").addEventListener("click", () => { message("notice-status"); selectNoticeView("public"); });

function refreshVisibleSearch() {
  if (!get("search-panel").hidden && !get("match-count").hidden && !searchRequest) searchForm.requestSubmit();
}
function syncVisibleRecords() {
  if (!get("report-panel").hidden) refreshFoundReports();
  if (!get("notices-panel").hidden) refreshNotices();
  refreshVisibleSearch();
}
window.addEventListener("storage", event => {
  if (!event.key || Object.values(recordKeys).some(prefix => event.key.startsWith(prefix))) syncVisibleRecords();
});
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) syncVisibleRecords();
});
readOwned();
renderOwned();
loadCatalog();
