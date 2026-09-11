---
title: IMD radiosondes
---

```js
import {feature, merge} from "npm:topojson-client@3.1.0";
```

```js
// Arrow returns row proxies and epoch milliseconds; make both plain JavaScript.
function rows(table) {
  return table.toArray().map((row) => {
    const d = row.toJSON();
    if (d.month != null) d.month = new Date(d.month);
    return d;
  });
}

const monthly = rows(await FileAttachment("data/monthly.parquet").parquet());
const reasons = rows(await FileAttachment("data/reasons.parquet").parquet());
const stationMonthly = rows(await FileAttachment("data/station-monthly.parquet").parquet());
const supplies = rows(await FileAttachment("data/supplies.parquet").parquet());
const stations = await FileAttachment("data/stations.json").json();
const topology = await FileAttachment("data/india-states.topo.json").json();
const states = feature(topology, topology.objects.states);
const outline = merge(topology, topology.objects.states.geometries);
```

```js
const slots = d3.sum(monthly, (d) => d.slots);
const returned = d3.sum(monthly, (d) => d.returned);
const latest = d3.max(stations, (d) => d.last_date);
const span = [d3.min(monthly, (d) => d.month), d3.max(monthly, (d) => d.month)];

const integer = d3.format(",");
const percent = d3.format(".0%");
const metres = d3.format(",.0f");
const rate = (d) => (d.slots_recent ? d.returned_recent / d.slots_recent : null);

const DATA = "var(--theme-foreground-focus)";
const NODATA = "var(--theme-foreground-faintest)";

// Observable10 stops at ten hues and the portal uses thirteen codes.
const reasonColors = [...d3.schemeObservable10, "#8c6d31", "#7b4173", "#a3a3a3"];
const reasonOrder = d3
  .rollups(reasons, (v) => d3.sum(v, (d) => d.slots), (d) => d.misda_reason)
  .sort((a, b) => d3.descending(a[1], b[1]))
  .map(([name]) => name);

const outcomeColor = {domain: ["Returned data", "No data"], range: [DATA, NODATA], legend: true};

function split(d) {
  return [
    {month: d.month, outcome: "Returned data", slots: d.returned},
    {month: d.month, outcome: "No data", slots: d.slots - d.returned}
  ];
}
```

# IMD radiosondes

<div class="lede">
  Every balloon launch window at an India Meteorological Department upper air station since 2009,
  as reported by the department's monitoring portal.
</div>

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Stations</h2>
    <p class="big">${stations.length}</p>
  </div>
  <div class="card">
    <h2>Launch windows</h2>
    <p class="big">${integer(slots)}</p>
  </div>
  <div class="card">
    <h2>Returned data</h2>
    <p class="big">${percent(returned / slots)}</p>
  </div>
  <div class="card">
    <h2>Latest window</h2>
    <p class="big">${latest}</p>
  </div>
</div>

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Stations</h2>
    ${resize((width) => Plot.plot({
      width,
      height: 400,
      projection: {type: "mercator", domain: outline, inset: 6},
      marks: [
        Plot.geo(states, {fill: "var(--theme-foreground-faintest)", stroke: "var(--theme-background)", strokeWidth: 0.5}),
        Plot.geo(outline, {stroke: "var(--theme-foreground-fainter)", strokeWidth: 0.75}),
        Plot.dot(stations.filter((d) => d.latitude != null), {
          x: "longitude",
          y: "latitude",
          r: 3.5,
          fill: DATA,
          channels: {Station: "station_name", WMO: "wmo_id"},
          tip: {format: {x: null, y: null}}
        })
      ]
    }))}
  </div>
  <div class="card">
    <h2>Launch windows per month</h2>
    ${resize((width) => Plot.plot({
      width,
      height: 400,
      marginLeft: 48,
      x: {label: null},
      y: {label: null, grid: true, nice: true},
      color: outcomeColor,
      marks: [
        Plot.areaY(monthly.flatMap(split), {
          x: "month",
          y: "slots",
          fill: "outcome",
          order: ["Returned data", "No data"],
          curve: "step",
          tip: true
        }),
        Plot.ruleY([0])
      ]
    }))}
  </div>
</div>

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Height reached</h2>
    <h3>Median geopotential metres, with the 10th to 90th percentile</h3>
    ${resize((width) => Plot.plot({
      width,
      height: 230,
      marginLeft: 48,
      x: {label: null},
      y: {label: null, grid: true, nice: true, zero: true},
      marks: [
        Plot.areaY(monthly, {x: "month", y1: "height_p10", y2: "height_p90", fill: DATA, fillOpacity: 0.2}),
        Plot.lineY(monthly, {x: "month", y: "height_median", stroke: DATA, tip: true}),
        Plot.ruleY([0])
      ]
    }))}
  </div>
  <div class="card">
    <h2>Flight duration</h2>
    <h3>Median minutes from release to the last report</h3>
    ${resize((width) => Plot.plot({
      width,
      height: 230,
      marginLeft: 48,
      x: {label: null},
      y: {label: null, grid: true, nice: true, zero: true},
      marks: [
        Plot.lineY(monthly, {x: "month", y: "duration_median", stroke: DATA, tip: true}),
        Plot.ruleY([0])
      ]
    }))}
  </div>
</div>

<div class="card">
  <h2>Reason reported for a launch window without data</h2>
  <h3>Codes as the portal writes them. IMD publishes no definitions.</h3>
  ${resize((width) => Plot.plot({
    width,
    height: 300,
    marginLeft: 48,
    x: {label: null},
    y: {label: null, grid: true, nice: true},
    color: {domain: reasonOrder, range: reasonColors, legend: true, columns: "150px"},
    marks: [
      Plot.areaY(reasons, {x: "month", y: "slots", fill: "misda_reason", order: reasonOrder, curve: "step", tip: true}),
      Plot.ruleY([0])
    ]
  }))}
</div>

<div class="controls">${picker}</div>

```js
const picker = Inputs.select(stations.map((d) => d.station_name).sort(d3.ascending), {
  label: "Station",
  value: "DELHI"
});
const picked = Generators.input(picker);
```

```js
const meta = stations.find((d) => d.station_name === picked);
const stationRows = stationMonthly.filter((d) => d.station_name === picked);
const stationStock = supplies.filter((d) => d.station_name === picked);
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Launch windows</h2>
    <p class="big">${integer(meta.slots)}</p>
  </div>
  <div class="card">
    <h2>Returned data</h2>
    <p class="big">${meta.slots ? percent(meta.returned / meta.slots) : "n/a"}</p>
  </div>
  <div class="card">
    <h2>Median height</h2>
    <p class="big">${meta.height_median ? metres(meta.height_median) : "n/a"}</p>
  </div>
  <div class="card">
    <h2>Record</h2>
    <p class="big small">${meta.first_date ?? "none"} to ${meta.last_date ?? ""}</p>
  </div>
</div>

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Launch windows per month</h2>
    ${resize((width) => Plot.plot({
      width,
      height: 230,
      marginLeft: 48,
      x: {label: null, domain: span},
      y: {label: null, grid: true, nice: true},
      color: outcomeColor,
      marks: [
        Plot.rectY(stationRows.flatMap(split), {
          x: "month",
          y: "slots",
          fill: "outcome",
          interval: "month",
          tip: true
        }),
        Plot.ruleY([0])
      ]
    }))}
  </div>
  <div class="card">
    <h2>Stock held</h2>
    <h3>Monthly average of the station's daily reports</h3>
    ${resize((width) => Plot.plot({
      width,
      height: 230,
      marginLeft: 48,
      x: {label: null, domain: span},
      y: {label: null, grid: true, nice: true, zero: true},
      color: {domain: ["Radiosondes", "Balloons"], scheme: "Observable10", legend: true},
      marks: [
        Plot.lineY(
          stationStock.flatMap((d) => [
            {month: d.month, kind: "Radiosondes", units: d.instruments},
            {month: d.month, kind: "Balloons", units: d.balloons}
          ]),
          {x: "month", y: "units", stroke: "kind", tip: true}
        ),
        Plot.ruleY([0])
      ]
    }))}
  </div>
</div>

```js
const table = stations.map((d) => ({
  Station: d.station_name,
  WMO: d.wmo_id == null ? "" : String(d.wmo_id),
  First: d.first_date,
  Last: d.last_date,
  Windows: d.slots,
  "Returned data": d.slots ? d.returned / d.slots : null,
  "Last year": rate(d)
}));
```

<div class="card table-card">
  ${Inputs.table(table, {
    rows: 15,
    sort: "Station",
    format: {
      "Returned data": (d) => (d == null ? "" : percent(d)),
      "Last year": (d) => (d == null ? "" : percent(d))
    },
    align: {Windows: "right", "Returned data": "right", "Last year": "right"}
  })}
</div>
