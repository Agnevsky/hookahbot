"use strict";

/* ════════════════════════════════════════════════════════════════
   Telegram
   ════════════════════════════════════════════════════════════════ */
const tg = window.Telegram && window.Telegram.WebApp;
const supports = (v) => !!(tg && tg.isVersionAtLeast && tg.isVersionAtLeast(v));

if (tg) {
  tg.ready();
  tg.expand();
  if (supports("7.7")) tg.disableVerticalSwipes();   // не закрывать приложение при прокрутке
  // У приложения своя тёмная тема — красим под неё шапку и фон Telegram
  try {
    if (supports("6.1")) { tg.setHeaderColor("#0a0812"); tg.setBackgroundColor("#0a0812"); }
    if (supports("7.10")) tg.setBottomBarColor("#0a0812");
  } catch { /* старый клиент */ }
}

const haptic = {
  tap()     { tg?.HapticFeedback?.selectionChanged(); },
  ok()      { tg?.HapticFeedback?.notificationOccurred("success"); },
  warn()    { tg?.HapticFeedback?.notificationOccurred("warning"); },
  error()   { tg?.HapticFeedback?.notificationOccurred("error"); },
};

function confirmDialog(text) {
  return new Promise((resolve) => {
    if (supports("6.2")) tg.showConfirm(text, (ok) => resolve(!!ok));
    else resolve(window.confirm(text));
  });
}

/* ════════════════════════════════════════════════════════════════
   API
   ════════════════════════════════════════════════════════════════ */
async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: {
      "Authorization": `tma ${tg?.initData || ""}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* пустой ответ */ }
  if (!res.ok) {
    let msg = data?.detail;
    if (Array.isArray(msg)) msg = msg.map((d) => d.msg).join("; ");
    const err = new Error(msg || `Ошибка ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

/* ════════════════════════════════════════════════════════════════
   Состояние
   ════════════════════════════════════════════════════════════════ */
const CAT_COLOR = { tobacco: "var(--tobacco)", bar: "var(--bar)", other: "var(--other)" };

const S = {
  data: null,
  tab: "list",
  listCat: "tobacco",
  editCat: "tobacco",
  addCat: null,
  addSub: null,
  search: "",
  brandSearch: "",
  selecting: false,
  selected: new Set(),
  recent: [],
  sheetItem: null,
  sheetSub: null,
  busy: false,
};

const $ = (id) => document.getElementById(id);

/** Маленький помощник для DOM: h("div", {class: "x", onclick}, ...children) */
function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style") el.style.cssText = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;      // только для своих SVG-констант
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

const ICON = {
  pencil: '<svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zm17.71-10.21a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>',
  trash:  '<svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>',
  check:  '<svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>',
};

/* ════════════════════════════════════════════════════════════════
   Утилиты
   ════════════════════════════════════════════════════════════════ */
function plural(n, one, few, many) {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
}
const positionsWord = (n) => `${n} ${plural(n, "позиция", "позиции", "позиций")}`;

function ago(iso) {
  const d = new Date(iso);
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return "только что";
  if (s < 3600) return `${Math.floor(s / 60)} мин назад`;
  if (s < 86400) return `${Math.floor(s / 3600)} ч назад`;
  if (s < 172800) return "вчера";
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

function lines(text) {
  return text.split("\n").map((l) => l.trim()).filter(Boolean);
}

function levelColor(pool) {
  if (pool.level >= 100) return "var(--full)";
  if (pool.level >= 80) return "var(--hot)";
  if (pool.level > 0) return "var(--warn)";
  return "var(--ok)";
}

function toast(text, kind = "") {
  const el = h("div", { class: `toast ${kind ? "toast--" + kind : ""}` }, text);
  $("toasts").append(el);
  setTimeout(() => { el.classList.add("is-leaving"); setTimeout(() => el.remove(), 260); }, kind === "error" ? 4200 : 2600);
}

function alertText(a) {
  if (a.level >= 100) return `${a.title}: список заполнен (${a.count} из ${a.capacity}) — пора заказывать!`;
  return `${a.title}: заполнено на ${a.percent}% (${a.count} из ${a.capacity})`;
}

function showAlerts(alerts) {
  for (const a of alerts || []) toast(alertText(a), a.level >= 80 ? "warn" : "");
}

function cat(key) { return S.data.categories.find((c) => c.key === key); }

/** Позиции категории, сгруппированные по подкатегории (в порядке марок/разделов). */
function groupItems(category) {
  const order = category.key === "tobacco"
    ? S.data.brands.map((b) => b.name)
    : category.key === "bar" ? S.data.bar_subs.map((s) => s.value) : [];
  const groups = new Map();
  for (const item of category.items) {
    const k = item.subcategory || "";
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(item);
  }
  const rank = (k) => { const i = order.indexOf(k); return i === -1 ? 1e6 : i; };
  return [...groups.entries()].sort((a, b) => rank(a[0]) - rank(b[0]) || a[0].localeCompare(b[0], "ru"));
}

function subEmoji(categoryKey, sub) {
  if (categoryKey === "bar") return (S.data.bar_subs.find((s) => s.value === sub) || {}).emoji || "";
  return "";
}

function highlight(text, q) {
  if (!q) return text;
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i === -1) return text;
  return [text.slice(0, i), h("mark", null, text.slice(i, i + q.length)), text.slice(i + q.length)];
}

/* ════════════════════════════════════════════════════════════════
   Загрузка
   ════════════════════════════════════════════════════════════════ */
async function load({ quiet = false } = {}) {
  const btn = $("refresh");
  btn.classList.add("is-spinning");
  try {
    S.data = await api("GET", "/api/state");
    // выбранные позиции, которых больше нет, — убираем
    const ids = new Set(S.data.categories.flatMap((c) => c.items.map((i) => i.id)));
    for (const id of [...S.selected]) if (!ids.has(id)) S.selected.delete(id);
    render();
  } catch (e) {
    if (e.status === 401) return block(e.message);
    if (!quiet) toast(e.message || "Нет связи с сервером", "error");
  } finally {
    btn.classList.remove("is-spinning");
  }
}

function block(text) {
  $("blocker").hidden = false;
  if (text) $("blocker-text").textContent = text;
}

/* ════════════════════════════════════════════════════════════════
   Рендер
   ════════════════════════════════════════════════════════════════ */
function render() {
  if (!S.data) return;
  const total = S.data.categories.reduce((s, c) => s + c.count, 0);
  $("hello").textContent = `Привет, ${S.data.me.name || "друг"} · ${total ? positionsWord(total) + " в заказе" : "заказ пуст"}`;
  const badge = $("badge-total");
  badge.hidden = !total;
  badge.textContent = total;

  renderSegmented($("list-cats"), S.listCat, (k) => { S.listCat = k; render(); });
  renderSegmented($("edit-cats"), S.editCat, (k) => { S.editCat = k; S.selected.clear(); render(); });
  renderList();
  renderAdd();
  renderEdit();
  renderActionBar();
}

function renderSegmented(root, active, onPick) {
  root.replaceChildren(...S.data.categories.map((c) =>
    h("button", {
      class: c.key === active ? "is-active" : "",
      style: `--cat:${CAT_COLOR[c.key]}`,
      onclick: () => { if (c.key !== active) { haptic.tap(); onPick(c.key); } },
    }, `${c.emoji} ${c.title}`, c.count ? h("span", { class: "count" }, c.count) : null)
  ));
}

/* ─── Вкладка «Список» ─────────────────────────────────────────── */
function renderPools(categoryKey) {
  return S.data.pools.filter((p) => p.category === categoryKey).map((p) => {
    const pct = Math.min(100, p.count * 100 / p.capacity);
    const note = p.level >= 100 ? "Пора делать заказ!" : p.level >= 80 ? "Скоро пора заказывать" : "";
    return h("div", { class: "pool", style: `--lvl:${levelColor(p)}` },
      h("div", { class: "pool__row" },
        h("span", { class: "pool__title" }, p.title),
        h("span", { class: "pool__stat" }, h("b", null, p.count), ` из ${p.capacity} · ${p.percent}%`),
      ),
      h("div", { class: "bar" },
        h("div", { class: "bar__fill", style: `width:${pct}%` }),
        ...S.data.thresholds.filter((t) => t < 100).map((t) => h("span", { class: "bar__tick", style: `left:${t}%` })),
      ),
      note ? h("div", { class: "pool__note" }, note) : null,
    );
  });
}

function renderList() {
  const c = cat(S.listCat);
  $("list-pools").replaceChildren(...renderPools(c.key));

  const q = S.search.trim();
  const body = $("list-body");
  if (!c.items.length) {
    body.replaceChildren(h("div", { class: "empty" },
      h("div", { class: "empty__emoji" }, c.emoji),
      h("div", { class: "empty__title" }, "Список пуст"),
      h("div", null, "Добавьте то, что закончилось"),
      h("button", { class: "btn btn--primary", onclick: () => { S.addCat = c.key; S.addSub = null; switchTab("add"); } }, "➕ Добавить"),
    ));
  } else {
    const groups = groupItems(c)
      .map(([sub, items]) => [sub, q ? items.filter((i) => i.content.toLowerCase().includes(q.toLowerCase()) || sub.toLowerCase().includes(q.toLowerCase())) : items])
      .filter(([, items]) => items.length);
    body.replaceChildren(...(groups.length ? groups.map(([sub, items]) =>
      h("div", { class: "group", style: `--cat:${CAT_COLOR[c.key]}` },
        h("div", { class: "group__head" },
          h("span", null, sub ? `${subEmoji(c.key, sub)} ${sub}`.trim() : "Без раздела"),
          h("span", { class: "count" }, items.length)),
        ...items.map((i) => h("div", { class: "item" },
          h("span", { class: "item__dot" }),
          h("div", { class: "item__body" },
            h("div", { class: "item__text" }, highlight(i.content, q)),
            h("div", { class: "item__meta" }, [i.added_by, ago(i.added_at)].filter(Boolean).join(" · ")),
          ),
        )),
      )) : [h("div", { class: "empty" }, h("div", { class: "empty__emoji" }, "🔍"), h("div", null, "Ничего не найдено"))]));
  }

  // Администратору — «Отправить ответственному»
  const admin = $("list-admin");
  const people = S.data.responsible || [];
  admin.replaceChildren(...(people.length ? [
    h("div", { class: "section-title" }, "Отправить список"),
    h("div", { class: "send-row" }, ...people.map((p) =>
      h("button", { class: "btn btn--outline", onclick: (e) => sendTo(p, e.currentTarget) }, `📤 ${p.name}`))),
  ] : []));
}

/* ─── Вкладка «Добавить» ───────────────────────────────────────── */
function renderAdd() {
  $("add-cats").replaceChildren(...S.data.categories.map((c) =>
    h("button", {
      class: `tile ${S.addCat === c.key ? "is-active" : ""}`,
      style: `--cat:${CAT_COLOR[c.key]}`,
      onclick: () => {
        haptic.tap();
        if (S.addCat !== c.key) { S.addCat = c.key; S.addSub = null; S.brandSearch = ""; $("brand-search").value = ""; }
        renderAdd();
        if (c.key === "other") focusText();
      },
    },
      c.count ? h("span", { class: "count" }, c.count) : null,
      h("div", { class: "tile__emoji" }, c.emoji),
      h("div", { class: "tile__title" }, c.title),
    )
  ));

  const needsSub = S.addCat === "tobacco" || S.addCat === "bar";
  $("add-sub-wrap").hidden = !needsSub;
  if (needsSub) {
    $("add-sub-title").textContent = S.addCat === "tobacco" ? "2. Марка" : "2. Раздел";
    $("brand-search-wrap").hidden = S.addCat !== "tobacco" || S.data.brands.length < 8;
    const color = CAT_COLOR[S.addCat];
    let options;
    if (S.addCat === "tobacco") {
      const q = S.brandSearch.trim().toLowerCase();
      options = S.data.brands.filter((b) => !q || b.name.toLowerCase().includes(q)).map((b) => ({ value: b.name, label: b.name }));
    } else {
      options = S.data.bar_subs.map((s) => ({ value: s.value, label: `${s.emoji} ${s.value}` }));
    }
    const counts = {};
    for (const i of cat(S.addCat).items) counts[i.subcategory] = (counts[i.subcategory] || 0) + 1;
    $("add-subs").replaceChildren(...(options.length ? options.map((o) =>
      h("button", {
        class: `chip ${S.addSub === o.value ? "is-active" : ""}`,
        style: `--cat:${color}`,
        onclick: () => { haptic.tap(); S.addSub = o.value; renderAdd(); focusText(); },
      }, o.label, counts[o.value] ? ` · ${counts[o.value]}` : "")
    ) : [h("span", { class: "hint" }, S.data.brands.length ? "Марка не найдена" : "Марок пока нет — добавьте во вкладке «Правка»")]));
  }

  const ready = S.addCat && (!needsSub || S.addSub);
  $("add-input-wrap").hidden = !ready;
  if (ready) {
    $("add-input-title").textContent = needsSub ? `3. Позиции — ${S.addSub}` : "2. Позиции";
    updateAddButton();
  }
  $("add-recent").replaceChildren(...(S.recent.length ? [
    h("div", { class: "section-title" }, "Только что добавлено"),
    h("div", { class: "card" }, ...S.recent.slice(0, 8).map((r) => h("div", { class: "recent__item" }, r))),
  ] : []));
}

function focusText() {
  // На телефоне клавиатура вылезает сама — только если поле уже видно
  setTimeout(() => { const t = $("add-text"); if (!t.closest("[hidden]")) t.focus({ preventScroll: false }); }, 50);
}

function updateAddButton() {
  const n = lines($("add-text").value).length;
  const btn = $("add-submit");
  btn.disabled = !n || S.busy;
  btn.textContent = n > 1 ? `Добавить ${positionsWord(n)}` : "Добавить";
  $("add-hint").textContent = n > 1 ? `${positionsWord(n)} — каждая строка отдельно` : "Каждая строка — отдельная позиция";
}

async function submitAdd() {
  const text = $("add-text").value;
  const items = lines(text);
  if (!items.length || S.busy) return;
  S.busy = true; updateAddButton();
  try {
    const res = await api("POST", "/api/items", { category: S.addCat, subcategory: S.addSub, content: text });
    haptic.ok();
    const where = S.addSub ? ` · ${S.addSub}` : "";
    toast(`✅ Добавлено: ${positionsWord(res.added)}${where}`);
    showAlerts(res.alerts);
    S.recent = [...items.map((i) => (S.addSub ? `${S.addSub}: ${i}` : i)), ...S.recent].slice(0, 20);
    $("add-text").value = "";
    await load({ quiet: true });
  } catch (e) {
    haptic.error();
    toast(e.message, "error");
  } finally {
    S.busy = false; updateAddButton();
  }
}

/* ─── Вкладка «Правка» ─────────────────────────────────────────── */
function renderEdit() {
  const c = cat(S.editCat);
  $("edit-select-toggle").textContent = S.selecting ? "Готово" : "Выбрать";
  $("edit-select-toggle").classList.toggle("is-on", S.selecting);
  $("edit-select-toggle").hidden = !c.items.length;
  $("edit-hint").textContent = S.selecting
    ? (S.selected.size ? `Выбрано: ${S.selected.size}` : "Отметьте позиции для удаления")
    : (c.items.length ? "Нажмите на позицию, чтобы изменить" : "");

  const body = $("edit-body");
  if (!c.items.length) {
    body.replaceChildren(h("div", { class: "empty" },
      h("div", { class: "empty__emoji" }, "✨"),
      h("div", { class: "empty__title" }, "Здесь пока пусто"),
      h("div", null, `В списке «${c.title}» нет позиций`),
    ));
  } else {
    body.replaceChildren(...groupItems(c).map(([sub, items]) =>
      h("div", { class: "group", style: `--cat:${CAT_COLOR[c.key]}` },
        h("div", { class: "group__head" },
          h("span", null, sub ? `${subEmoji(c.key, sub)} ${sub}`.trim() : "Без раздела"),
          h("span", { class: "count" }, items.length)),
        ...items.map((i) => editRow(c, i)),
      )));
  }

  // Заказ сделан — очистить категорию
  $("edit-danger").replaceChildren(...(c.items.length ? [
    h("div", { class: "section-title" }, "Заказ сделан?"),
    h("div", { class: "card danger-card" },
      h("div", { class: "danger-card__text" },
        h("div", { class: "danger-card__title" }, `Очистить «${c.title}»`),
        h("div", { class: "hint" }, `Удалит все ${positionsWord(c.count)} и оповестит команду`)),
      h("button", { class: "btn btn--danger-ghost", onclick: () => clearCategory(c) }, "🗑 Очистить"),
    ),
  ] : []));

  renderBrands();
}

function editRow(c, i) {
  const selected = S.selected.has(i.id);
  if (S.selecting) {
    return h("button", {
      class: `item ${selected ? "is-selected" : ""}`,
      onclick: () => { haptic.tap(); selected ? S.selected.delete(i.id) : S.selected.add(i.id); renderEdit(); renderActionBar(); },
    },
      h("span", { class: "check", html: ICON.check }),
      h("div", { class: "item__body" },
        h("div", { class: "item__text" }, i.content),
        h("div", { class: "item__meta" }, [i.added_by, ago(i.added_at)].filter(Boolean).join(" · "))),
    );
  }
  return h("div", { class: "item" },
    h("button", { class: "item__body", style: "text-align:left", onclick: () => openSheet(c, i) },
      h("div", { class: "item__text" }, i.content),
      h("div", { class: "item__meta" }, [i.added_by, ago(i.added_at)].filter(Boolean).join(" · "))),
    h("button", { class: "item__act", "aria-label": "Изменить", html: ICON.pencil, onclick: () => openSheet(c, i) }),
    h("button", { class: "item__act item__act--danger", "aria-label": "Удалить", html: ICON.trash, onclick: () => deleteItems([i.id], `Удалить «${i.content}»?`) }),
  );
}

function renderActionBar() {
  const show = S.tab === "edit" && S.selecting;
  $("action-bar").hidden = !show;
  if (!show) return;
  const n = S.selected.size;
  const all = cat(S.editCat).items;
  const btn = $("delete-selected");
  btn.disabled = !n;
  btn.textContent = n ? `Удалить ${positionsWord(n)}` : "Удалить";
  $("select-all").textContent = n === all.length && n ? "Снять все" : "Выбрать все";
}

function renderBrands() {
  const root = $("edit-brands");
  if (!S.data.me.is_admin || S.editCat !== "tobacco") return root.replaceChildren();
  const input = h("input", { class: "input", placeholder: "Новая марка", maxlength: "40", enterkeyhint: "done" });
  const add = async () => {
    const name = input.value.trim();
    if (!name) return;
    try {
      await api("POST", "/api/brands", { name });
      haptic.ok(); toast(`Марка «${name}» добавлена`);
      await load({ quiet: true });
    } catch (e) { haptic.error(); toast(e.message, "error"); }
  };
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") add(); });
  root.replaceChildren(
    h("div", { class: "section-title" }, `Марки табака · ${S.data.brands.length}`),
    h("div", { class: "card" },
      h("div", { class: "chips chips--compact", style: "margin:0" }, ...S.data.brands.map((b) =>
        h("span", { class: "chip chip--removable" }, b.name,
          h("button", { class: "chip__x", "aria-label": `Убрать ${b.name}`, onclick: () => removeBrand(b) }, "✕")))),
      h("div", { class: "brand-add" }, input, h("button", { class: "btn btn--primary", onclick: add }, "Добавить")),
    ),
  );
}

/* ─── Действия ─────────────────────────────────────────────────── */
async function deleteItems(ids, question) {
  if (!ids.length) return;
  haptic.warn();
  if (!(await confirmDialog(question))) return;
  try {
    const res = await api("POST", "/api/items/delete", { ids });
    haptic.ok();
    toast(`🗑 Удалено: ${positionsWord(res.deleted)}`);
    ids.forEach((id) => S.selected.delete(id));
    if (!S.selected.size) S.selecting = false;
    closeSheet();
    await load({ quiet: true });
  } catch (e) { haptic.error(); toast(e.message, "error"); }
}

async function clearCategory(c) {
  haptic.warn();
  if (!(await confirmDialog(`Заказ «${c.title}» сделан?\n\nСписок будет очищен (${positionsWord(c.count)}), команда получит оповещение.`))) return;
  try {
    await api("POST", `/api/categories/${c.key}/clear`);
    haptic.ok();
    toast(`✅ Список «${c.title}» очищен`);
    S.selected.clear(); S.selecting = false;
    await load({ quiet: true });
  } catch (e) { haptic.error(); toast(e.message, "error"); }
}

async function removeBrand(b) {
  if (!(await confirmDialog(`Убрать марку «${b.name}» из списка?\n\nУже добавленные позиции останутся.`))) return;
  try {
    await api("DELETE", `/api/brands/${b.id}`);
    haptic.ok(); toast(`Марка «${b.name}» убрана`);
    if (S.addSub === b.name && S.addCat === "tobacco") S.addSub = null;
    await load({ quiet: true });
  } catch (e) { haptic.error(); toast(e.message, "error"); }
}

async function sendTo(person, btn) {
  if (!(await confirmDialog(`Отправить ${person.name} список и заполненность?`))) return;
  btn.disabled = true;
  try {
    await api("POST", `/api/send/${person.id}`);
    haptic.ok(); toast(`📤 Отправлено ${person.name}`);
  } catch (e) { haptic.error(); toast(e.message, "error"); }
  finally { btn.disabled = false; }
}

function copyList() {
  const c = cat(S.listCat);
  if (!c.items.length) return toast("Список пуст");
  const parts = [`${c.emoji} ${c.title} — ${positionsWord(c.count)}`];
  for (const [sub, items] of groupItems(c)) {
    parts.push("", sub ? `${sub}:` : "");
    for (const i of items) parts.push(`• ${i.content}`);
  }
  const text = parts.join("\n").replace(/\n{3,}/g, "\n\n");
  const done = () => { haptic.ok(); toast("Список скопирован"); };
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text) && done());
  } else if (fallbackCopy(text)) done();
}

function fallbackCopy(text) {
  const t = h("textarea", { style: "position:fixed;opacity:0" });
  t.value = text; document.body.append(t); t.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { /* нет доступа */ }
  t.remove();
  if (!ok) toast("Не удалось скопировать", "error");
  return ok;
}

/* ─── Шторка редактирования ───────────────────────────────────── */
function openSheet(c, item) {
  haptic.tap();
  S.sheetItem = { ...item, category: c.key };
  S.sheetSub = item.subcategory;
  $("sheet-text").value = item.content;
  $("sheet-meta").textContent = [item.added_by && `Добавил(а): ${item.added_by}`, ago(item.added_at)].filter(Boolean).join(" · ");
  renderSheetSubs();
  $("sheet").hidden = false;
  $("sheet-backdrop").hidden = false;
  if (tg?.BackButton) { tg.BackButton.show(); }
}

function renderSheetSubs() {
  const item = S.sheetItem;
  const label = $("sheet-sub-label"), root = $("sheet-subs");
  if (item.category === "other") { label.hidden = true; root.replaceChildren(); return; }
  label.hidden = false;
  label.textContent = item.category === "tobacco" ? "Марка" : "Раздел";
  let options = item.category === "tobacco"
    ? S.data.brands.map((b) => ({ value: b.name, label: b.name }))
    : S.data.bar_subs.map((s) => ({ value: s.value, label: `${s.emoji} ${s.value}` }));
  if (item.subcategory && !options.some((o) => o.value === item.subcategory)) {
    options = [{ value: item.subcategory, label: item.subcategory }, ...options];   // марку убрали из списка
  }
  root.replaceChildren(...options.map((o) => h("button", {
    class: `chip ${S.sheetSub === o.value ? "is-active" : ""}`,
    style: `--cat:${CAT_COLOR[item.category]}`,
    onclick: () => { haptic.tap(); S.sheetSub = o.value; renderSheetSubs(); },
  }, o.label)));
}

function closeSheet() {
  $("sheet").hidden = true;
  $("sheet-backdrop").hidden = true;
  S.sheetItem = null;
  tg?.BackButton?.hide();
}

async function saveSheet() {
  const item = S.sheetItem;
  const content = $("sheet-text").value.trim();
  if (!item || !content) return toast("Напишите название позиции", "error");
  try {
    const res = await api("PATCH", `/api/items/${item.id}`, { content, subcategory: S.sheetSub });
    haptic.ok(); toast("Сохранено");
    showAlerts(res.alerts);
    closeSheet();
    await load({ quiet: true });
  } catch (e) { haptic.error(); toast(e.message, "error"); }
}

/* ════════════════════════════════════════════════════════════════
   Вкладки и события
   ════════════════════════════════════════════════════════════════ */
function switchTab(tab) {
  if (S.tab !== tab) haptic.tap();
  S.tab = tab;
  if (tab !== "edit") { S.selecting = false; S.selected.clear(); }
  document.querySelectorAll(".view").forEach((v) => { v.hidden = v.dataset.view !== tab; });
  const tabs = [...document.querySelectorAll(".tab")];
  tabs.forEach((t) => t.classList.toggle("is-active", t.dataset.tab === tab));
  $("tab-glider").style.setProperty("--i", tabs.findIndex((t) => t.dataset.tab === tab));
  // Список и правка показывают одну и ту же категорию — так удобнее переходить
  if (tab === "edit") S.editCat = S.listCat;
  if (tab === "list") S.listCat = S.editCat;
  window.scrollTo({ top: 0 });
  render();
}

document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));
$("refresh").addEventListener("click", () => { haptic.tap(); load(); });
$("list-search").addEventListener("input", (e) => { S.search = e.target.value; renderList(); });
$("list-copy").addEventListener("click", copyList);
$("brand-search").addEventListener("input", (e) => { S.brandSearch = e.target.value; renderAdd(); });
$("add-text").addEventListener("input", updateAddButton);
$("add-text").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submitAdd(); });
$("add-submit").addEventListener("click", submitAdd);
$("edit-select-toggle").addEventListener("click", () => {
  haptic.tap(); S.selecting = !S.selecting; S.selected.clear(); renderEdit(); renderActionBar();
});
$("select-all").addEventListener("click", () => {
  haptic.tap();
  const all = cat(S.editCat).items.map((i) => i.id);
  if (S.selected.size === all.length) S.selected.clear(); else all.forEach((id) => S.selected.add(id));
  renderEdit(); renderActionBar();
});
$("delete-selected").addEventListener("click", () =>
  deleteItems([...S.selected], `Удалить ${positionsWord(S.selected.size)}?`));
$("sheet-backdrop").addEventListener("click", closeSheet);
$("sheet-save").addEventListener("click", saveSheet);
$("sheet-text").addEventListener("keydown", (e) => { if (e.key === "Enter") saveSheet(); });
$("sheet-delete").addEventListener("click", () => {
  const i = S.sheetItem; if (i) deleteItems([i.id], `Удалить «${i.content}»?`);
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && S.sheetItem) closeSheet(); });
tg?.BackButton?.onClick(closeSheet);

// Свежие данные: при возврате в приложение и раз в 20 секунд
document.addEventListener("visibilitychange", () => { if (!document.hidden) load({ quiet: true }); });
setInterval(() => { if (!document.hidden && !S.sheetItem && !S.busy) load({ quiet: true }); }, 20000);

/* ─── Старт ───────────────────────────────────────────────────── */
if (!tg || !tg.initData) {
  block();
} else {
  $("list-body").replaceChildren(h("div", { class: "skeleton" }), h("div", { class: "skeleton" }), h("div", { class: "skeleton" }));
  load();
}
