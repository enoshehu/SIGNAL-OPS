const format = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });
const cityColours = ["#ff4d24", "#397a9e", "#88a61b", "#a15b9a"];
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function total(rows, field) {
  return rows.reduce((sum, row) => sum + Number(row[field] ?? 0), 0);
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function colourFor(cityKey, cities) {
  const index = Math.max(cities.findIndex((city) => city.key === cityKey), 0);
  return cityColours[index % cityColours.length];
}

function renderMetrics(rows) {
  const plans = total(rows, "plans");
  const matched = total(rows, "matched");
  const delayed = total(rows, "delayed");
  const cancelled = total(rows, "cancelled");
  const weightedDelay = delayed
    ? rows.reduce((sum, row) => sum + Number(row.meanDelay ?? 0) * Number(row.delayed ?? 0), 0) / delayed
    : null;
  const metrics = [
    ["Planned events", format.format(plans), "Retained timetable slice", "#397a9e"],
    ["Matched changes", format.format(matched), plans ? `${format.format((matched / plans) * 100)}% of plans` : "Not available", "#88a61b"],
    ["Positive delays", format.format(delayed), weightedDelay === null ? "Mean unavailable" : `${format.format(weightedDelay)} min weighted mean`, "#ff4d24"],
    ["Cancellations", format.format(cancelled), matched ? `${format.format((cancelled / matched) * 100)}% of matched events` : "Not available", "#a15b9a"],
  ];

  document.querySelector("#metrics").innerHTML = metrics
    .map(
      ([label, value, note, colour], index) => `
        <article class="metric" data-index="0${index + 1}" style="--metric-color:${colour}">
          <span>${escapeHTML(label)}<i aria-hidden="true"></i></span>
          <strong>${escapeHTML(value)}</strong>
          <small>${escapeHTML(note)}</small>
        </article>`,
    )
    .join("");
}

function renderCities(rows, allCities) {
  const maxShare = Math.max(
    ...rows.map((row) => (row.plans ? row.delayed / row.plans : 0)),
    0.01,
  );

  document.querySelector("#delay-chart").innerHTML = rows
    .map((row, index) => {
      const share = row.plans ? row.delayed / row.plans : 0;
      const colour = colourFor(row.key, allCities);
      return `
        <div class="bar-row" style="--city-color:${colour}">
          <span class="bar-name"><i class="city-symbol" aria-hidden="true"></i>${escapeHTML(row.name)}</span>
          <div class="bar-track" role="img" aria-label="${escapeHTML(row.name)}: ${format.format(share * 100)} percent of planned events had a positive delay">
            <div class="bar-fill" style="width:${(share / maxShare) * 100}%;animation-delay:${index * 90}ms"></div>
          </div>
          <b>${format.format(share * 100)}%</b>
        </div>`;
    })
    .join("");

  document.querySelector("#city-table").innerHTML = rows
    .map((row) => {
      const colour = colourFor(row.key, allCities);
      return `
        <tr style="--city-color:${colour}">
          <td><span class="table-city"><i class="city-symbol" aria-hidden="true"></i>${escapeHTML(row.name)}</span></td>
          <td>${format.format(row.plans)}</td>
          <td>${format.format(row.matched)}</td>
          <td>${row.meanDelay === null ? "Not available" : `${format.format(row.meanDelay)} min`}</td>
          <td>${row.maxDelay === null ? "Not available" : `${format.format(row.maxDelay)} min`}</td>
        </tr>`;
    })
    .join("");
}

function renderRoute(cities, select) {
  const route = document.querySelector("#route-map");
  route.innerHTML = `<div class="route-track" aria-hidden="true"></div>${cities
      .map(
        (city, index) => `
          <button class="route-stop" type="button" data-city="${escapeHTML(city.key)}" aria-pressed="true" style="--route-color:${cityColours[index % cityColours.length]}">
            <span>${escapeHTML(city.name)}</span>
            <small>${format.format(city.plans)} plans</small>
          </button>`,
      )
      .join("")}`;

  route.querySelectorAll(".route-stop").forEach((button) => {
    button.addEventListener("click", () => {
      select.value = button.dataset.city;
      select.dispatchEvent(new Event("change"));
      document.querySelector("#cities").scrollIntoView({
        behavior: reduceMotion ? "auto" : "smooth",
        block: "start",
      });
    });
  });
}

function reading(value, unit, digits = 1) {
  return value === null || value === undefined
    ? "Not available"
    : `${Number(value).toFixed(digits)} ${unit}`;
}

function renderWeather(cities) {
  document.querySelector("#weather-grid").innerHTML = cities
    .map((city) => {
      const observed = city.latestWeatherAt ? new Date(city.latestWeatherAt) : null;
      const observedLabel = observed
        ? `${observed.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" })} UTC`
        : "No retained reading";
      return `
        <article class="weather-reading" style="--city-color:${colourFor(city.key, cities)}">
          <header><h3>${escapeHTML(city.name)}</h3><i aria-hidden="true"></i></header>
          <dl>
            <div><dt>Temperature</dt><dd>${escapeHTML(reading(city.temperature, "°C"))}</dd></div>
            <div><dt>Rain</dt><dd>${escapeHTML(reading(city.precipitation, "mm"))}</dd></div>
            <div><dt>Wind</dt><dd>${escapeHTML(reading(city.windSpeed, "m/s"))}</dd></div>
          </dl>
          <p>${escapeHTML(observedLabel)} · ${format.format(city.weatherHours ?? 0)} retained hours</p>
        </article>`;
    })
    .join("");
}

function updateRoute(selectedCity) {
  document.querySelectorAll(".route-stop").forEach((button) => {
    const active = selectedCity === "all" || button.dataset.city === selectedCity;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function renderSources(sources) {
  document.querySelector("#source-list").innerHTML = sources
    .map((source, index) => {
      const state = source.state === "READY" ? "ready" : "waiting";
      return `
        <article class="source">
          <div class="source-head">
            <span class="source-number">SRC 0${index + 1}</span>
            <span class="source-state ${state}">${escapeHTML(source.state)}</span>
          </div>
          <h3>${escapeHTML(source.name)}</h3>
          <small>${escapeHTML(source.detail)}</small>
        </article>`;
    })
    .join("");
}

function configureTheme() {
  const root = document.documentElement;
  const button = document.querySelector("#theme-toggle");
  const stored = localStorage.getItem("signalops-theme");
  const preferredNight = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initial = stored ?? (preferredNight ? "night" : "day");

  function setTheme(theme) {
    const night = theme === "night";
    root.dataset.theme = theme;
    button.setAttribute("aria-pressed", String(night));
    button.setAttribute("aria-label", `Switch to ${night ? "day" : "night"} shift`);
    button.querySelector("b").textContent = night ? "Day shift" : "Night shift";
    document.querySelector('meta[name="theme-color"]').content = night ? "#101512" : "#e8e3d6";
  }

  setTheme(initial);
  button.addEventListener("click", () => {
    const next = root.dataset.theme === "night" ? "day" : "night";
    localStorage.setItem("signalops-theme", next);
    setTheme(next);
  });
}

let dashboardData;
let selectedCity = "all";
let secondsUntilRefresh = 60;

async function loadData() {
  const refreshButton = document.querySelector("#data-refresh");
  refreshButton.disabled = true;
  refreshButton.textContent = "Refreshing…";
  const response = await fetch(`data/summary.json?checked=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Dashboard data could not be loaded");
  const data = await response.json();
  dashboardData = data;
  const generatedAt = new Date(data.generatedAt);

  document.querySelector("#generated").textContent =
    `${generatedAt.toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
    })} UTC`;
  document.querySelector("#project-status").textContent = data.status;
  document.querySelector("#paired-hours").textContent = format.format(data.pairedHours);
  document.querySelector("#notice-text").textContent = data.notice;
  document.querySelector("#checked").textContent = new Date().toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  const hasOverlap = Number(data.pairedHours) > 0;
  const joinCore = document.querySelector("#join-core");
  joinCore.classList.toggle("connected", hasOverlap);
  document.querySelector("#join-symbol").textContent = hasOverlap ? "✓" : "×";
  document.querySelector("#join-state").textContent = hasOverlap
    ? `${format.format(data.pairedHours)} paired hours available`
    : "Waiting for matching hours";

  renderSources(data.sources);
  renderWeather(data.cities);

  const select = document.querySelector("#city-select");
  select.replaceChildren(new Option("All four cities", "all"));
  data.cities.forEach((city) => select.add(new Option(city.name, city.key)));
  select.value = data.cities.some((city) => city.key === selectedCity) ? selectedCity : "all";
  renderRoute(data.cities, select);

  const render = () => {
    const rows =
      select.value === "all"
        ? dashboardData.cities
        : dashboardData.cities.filter((city) => city.key === select.value);
    renderMetrics(rows);
    renderCities(rows, dashboardData.cities);
    updateRoute(select.value);
    selectedCity = select.value;
  };

  select.onchange = render;
  render();
  secondsUntilRefresh = 60;
  refreshButton.disabled = false;
  refreshButton.textContent = "Refresh now";
}

async function start() {
  configureTheme();
  const refreshButton = document.querySelector("#data-refresh");
  refreshButton.addEventListener("click", () => loadData().catch(showError));
  await loadData();
  window.setInterval(() => {
    secondsUntilRefresh -= 1;
    if (secondsUntilRefresh <= 0) loadData().catch(showError);
    else if (!refreshButton.disabled) refreshButton.textContent = `Refresh now · ${secondsUntilRefresh}s`;
  }, 1000);
}

function showError(error) {
  document.querySelector("#notice-text").textContent = error.message;
  document.querySelector("#project-status").textContent = "DATA ERROR";
  document.querySelector("#join-state").textContent = "Data unavailable";
  const refreshButton = document.querySelector("#data-refresh");
  secondsUntilRefresh = 60;
  refreshButton.disabled = false;
  refreshButton.textContent = "Try again";
}

start().catch(showError);
