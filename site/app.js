const format = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });

function total(rows, field) {
  return rows.reduce((sum, row) => sum + row[field], 0);
}

function renderMetrics(rows) {
  const plans = total(rows, "plans");
  const matched = total(rows, "matched");
  const delayed = total(rows, "delayed");
  const cancelled = total(rows, "cancelled");
  const weightedDelay = delayed ? rows.reduce((sum, row) => sum + (row.meanDelay ?? 0) * row.delayed, 0) / delayed : null;
  const metrics = [
    ["Planned events", format.format(plans), "saved timetable slice"],
    ["Matched changes", format.format(matched), plans ? `${format.format(matched / plans * 100)}% of plans` : "n.a."],
    ["Positive delays", format.format(delayed), weightedDelay === null ? "mean unavailable" : `${format.format(weightedDelay)} min mean`],
    ["Cancellations", format.format(cancelled), "matched events only"],
  ];
  document.querySelector("#metrics").innerHTML = metrics.map(([label, value, note]) =>
    `<article class="metric"><span>${label}</span><strong>${value}</strong><small>${note}</small></article>`
  ).join("");
}

function renderCities(rows) {
  const maxShare = Math.max(...rows.map(row => row.plans ? row.delayed / row.plans : 0), 0.01);
  document.querySelector("#delay-chart").innerHTML = rows.map((row, index) => {
    const share = row.plans ? row.delayed / row.plans : 0;
    return `<div class="bar-row"><span>${row.name}</span><div class="bar-track"><div class="bar-fill" style="width:${share / maxShare * 100}%;animation-delay:${index * 90}ms"></div></div><b>${format.format(share * 100)}%</b></div>`;
  }).join("");
  document.querySelector("#city-table").innerHTML = rows.map(row =>
    `<tr><td>${row.name}</td><td>${row.plans}</td><td>${row.matched}</td><td>${row.meanDelay === null ? "n.a." : `${format.format(row.meanDelay)} min`}</td><td>${row.maxDelay === null ? "n.a." : `${row.maxDelay} min`}</td></tr>`
  ).join("");
}

async function start() {
  const response = await fetch("data/summary.json");
  if (!response.ok) throw new Error("Dashboard data could not be loaded");
  const data = await response.json();
  document.querySelector("#generated").textContent = new Date(data.generatedAt).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC";
  document.querySelector("#project-status").textContent = data.status;
  document.querySelector("#paired-hours").textContent = data.pairedHours;
  document.querySelector("#notice-text").textContent = data.notice;
  document.querySelector("#source-list").innerHTML = data.sources.map(source =>
    `<article class="source"><div><b>${source.name}</b><small>${source.detail}</small></div><span class="source-state ${source.state.toLowerCase()}">${source.state}</span></article>`
  ).join("");

  const select = document.querySelector("#city-select");
  data.cities.forEach(city => select.add(new Option(city.name, city.key)));
  const render = () => {
    const rows = select.value === "all" ? data.cities : data.cities.filter(city => city.key === select.value);
    renderMetrics(rows);
    renderCities(rows);
  };
  select.addEventListener("change", render);
  render();
}

start().catch(error => {
  document.querySelector("#notice-text").textContent = error.message;
  document.querySelector("#project-status").textContent = "DATA ERROR";
});
