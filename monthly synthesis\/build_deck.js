const pptxgen = require("pptxgenjs");
const fs = require("fs");

const inputPath = process.argv[2] || "./monthly_summary.json";
const outputFileName = process.argv[3] || "Monthly_Executive_Presentation.pptx";
const data = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const portfolio = data.portfolio;
const projects = data.projects;
const deck = data.deck;

// Derive the reporting period from the actual week-ending dates in the data
// (fixed after review: this used to be a hardcoded date string).
const allWeekEndings = Object.values(projects).flatMap((p) => p.week_endings || []);
const sortedWeeks = [...new Set(allWeekEndings)].sort();
const periodStart = sortedWeeks[0];
const periodEnd = sortedWeeks[sortedWeeks.length - 1];
const fmtDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
};

// Palette: "Midnight Executive" + semantic RAG accents
const NAVY = "1E2761";
const ICE = "CADCFC";
const WHITE = "FFFFFF";
const RED = "C0392B";
const AMBER = "D68910";
const GREEN = "1E8449";
const SLATE = "4A4E69";

const ragColor = { Red: RED, Amber: AMBER, Green: GREEN };
const ragNum = { Red: 0, Amber: 1, Green: 2 };

let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "Professional Services PMO";
pres.title = "Monthly Portfolio Health Review";

// ---------- Slide 1: Title ----------
{
  let s = pres.addSlide();
  s.background = { color: NAVY };
  s.addShape(pres.shapes.OVAL, { x: 10.6, y: -1.5, w: 5, h: 5, fill: { color: "2B3A80" }, line: { type: "none" } });
  s.addText("Monthly Portfolio Health Review", {
    x: 0.7, y: 2.5, w: 10.5, h: 1.2, fontSize: 40, bold: true, color: WHITE, fontFace: "Cambria",
  });
  s.addText("Professional Services — Client Program Portfolio", {
    x: 0.7, y: 3.6, w: 10, h: 0.6, fontSize: 20, color: ICE, fontFace: "Calibri",
  });
  s.addText(`Reporting Period: ${fmtDate(periodStart)} – ${fmtDate(periodEnd)}   |   Prepared for: Executive Sponsor Review`, {
    x: 0.7, y: 6.6, w: 11, h: 0.4, fontSize: 13, color: ICE, italic: true, fontFace: "Calibri",
  });
  if (inputPath.includes("demo")) {
    s.addText("ILLUSTRATIVE — SYNTHETIC 4-WEEK DATASET (real client engagements below were single-snapshot exports; see README)", {
      x: 0.7, y: 0.4, w: 11.9, h: 0.35, fontSize: 11, bold: true, color: "F4D03F", fontFace: "Calibri",
    });
  }
}

// ---------- Slide 2: Portfolio Snapshot ----------
{
  let s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("Portfolio Snapshot", { x: 0.5, y: 0.35, w: 8, h: 0.7, fontSize: 30, bold: true, color: NAVY, fontFace: "Cambria" });
  s.addText("Where the portfolio stands as of the latest reporting week", { x: 0.5, y: 0.95, w: 9, h: 0.4, fontSize: 14, color: SLATE, italic: true });

  // RAG mix pie
  const mix = portfolio.current_rag_mix;
  s.addChart(pres.charts.PIE, [{
    name: "Projects", labels: ["Red", "Amber", "Green"], values: [mix.Red, mix.Amber, mix.Green],
  }], {
    x: 0.6, y: 1.6, w: 4.6, h: 4.6, showPercent: true, showLegend: true, legendPos: "b",
    chartColors: [RED, AMBER, GREEN], dataLabelColor: WHITE, dataLabelFontSize: 12,
  });

  // Big stat callouts on the right
  const cardX = 5.7, cardW = 6.9;
  const totalProjectWeeks = allWeekEndings.length;
  const fmtProjectList = (names) => (names.length ? ` (${names.join(", ")})` : "");
  const stats = [
    { label: "Projects in Portfolio", value: String(portfolio.total_projects) },
    { label: "Declining This Month", value: String(portfolio.projects_declining.length) + fmtProjectList(portfolio.projects_declining) },
    { label: "Recovering This Month", value: String(portfolio.projects_improving.length) + fmtProjectList(portfolio.projects_improving) },
    { label: "Weeks w/ Negative Client Sentiment", value: `${portfolio.weeks_with_negative_sentiment} of ${totalProjectWeeks} project-weeks` },
  ];
  let y = 1.6;
  stats.forEach((st) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: cardX, y, w: cardW, h: 1.05, rectRadius: 0.08, fill: { color: "F4F6FB" }, line: { type: "none" },
      shadow: { type: "outer", color: "000000", blur: 4, offset: 2, angle: 90, opacity: 0.12 },
    });
    s.addText(st.value, { x: cardX + 0.25, y: y + 0.08, w: cardW - 0.5, h: 0.55, fontSize: 22, bold: true, color: NAVY, fontFace: "Calibri" });
    s.addText(st.label, { x: cardX + 0.25, y: y + 0.62, w: cardW - 0.5, h: 0.35, fontSize: 12, color: SLATE, fontFace: "Calibri" });
    y += 1.25;
  });
}

// ---------- Slide 3: Trend Analysis (the "so what" over time) ----------
{
  let s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("Trend Analysis: Direction Matters More Than a Snapshot", { x: 0.5, y: 0.35, w: 12, h: 0.7, fontSize: 26, bold: true, color: NAVY, fontFace: "Cambria" });
  s.addText(`RAG trajectory across the last ${sortedWeeks.length} weekly reporting cycles (2 = Green, 1 = Amber, 0 = Red)`, { x: 0.5, y: 0.95, w: 11, h: 0.4, fontSize: 13, color: SLATE, italic: true });

  const weekLabels = sortedWeeks.map((iso, i) => `Wk ${i + 1} (${fmtDate(iso).replace(/, \d{4}$/, "")})`);
  const series = Object.keys(projects).map((name) => ({
    name,
    labels: weekLabels,
    values: projects[name].trajectory.map((s) => ragNum[s]),
  }));

  s.addChart(pres.charts.LINE, series, {
    x: 0.6, y: 1.55, w: 7.4, h: 4.6, lineSize: 3, lineSmooth: false,
    showLegend: true, legendPos: "b",
    valAxisMinVal: 0, valAxisMaxVal: 2, valAxisMajorUnit: 1,
    catAxisLabelColor: SLATE, valAxisLabelColor: SLATE,
    chartColors: [RED, GREEN, AMBER],
    lineDataSymbol: "circle", lineDataSymbolSize: 8,
  });

  // Right-side interpretation cards — generated from data.deck.trend_notes
  // (fixed after review: these used to be hardcoded per-project strings in
  // this file, so re-running the pipeline on different data wouldn't change
  // the deck's narrative).
  const colorMap = { red: RED, amber: AMBER, green: GREEN };
  let ny = 1.55;
  deck.trend_notes.forEach((n) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.25, y: ny, w: 4.5, h: 1.45, rectRadius: 0.08, fill: { color: "F4F6FB" }, line: { type: "none" } });
    s.addShape(pres.shapes.OVAL, { x: 8.45, y: ny + 0.18, w: 0.18, h: 0.18, fill: { color: colorMap[n.color_key] || SLATE }, line: { type: "none" } });
    s.addText(n.title, { x: 8.75, y: ny + 0.1, w: 3.9, h: 0.3, fontSize: 13, bold: true, color: NAVY, margin: 0 });
    s.addText(n.body, { x: 8.45, y: ny + 0.45, w: 4.15, h: 0.95, fontSize: 10.5, color: SLATE, margin: 0 });
    ny += 1.6;
  });
}

// ---------- Slide 4: Emerging Risks ----------
{
  let s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("Emerging Risks Across the Portfolio", { x: 0.5, y: 0.35, w: 10, h: 0.7, fontSize: 28, bold: true, color: NAVY, fontFace: "Cambria" });
  s.addText("Patterns that would be missed by reviewing each project in isolation", { x: 0.5, y: 0.95, w: 11, h: 0.4, fontSize: 14, color: SLATE, italic: true });

  // Generated from data.deck.risks (fixed after review: previously hardcoded).
  // Card height and spacing adapt to however many risks were actually detected.
  const risks = deck.risks;
  const cardH = risks.length <= 3 ? 1.55 : 1.15;
  const gap = risks.length <= 3 ? 1.75 : 1.3;
  let y = 1.65;
  risks.forEach((r, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y, w: 12.3, h: cardH, rectRadius: 0.08, fill: { color: i === 1 ? "FBEFEA" : "F4F6FB" }, line: { type: "none" } });
    s.addText(String(i + 1), { x: 0.75, y: y + cardH / 2 - 0.45, w: 0.9, h: 0.9, fontSize: 30, bold: true, color: NAVY, align: "center", valign: "middle" });
    s.addText(r.title, { x: 1.8, y: y + 0.15, w: 10.7, h: 0.4, fontSize: 15, bold: true, color: NAVY, margin: 0 });
    s.addText(r.body, { x: 1.8, y: y + 0.55, w: 10.7, h: cardH - 0.6, fontSize: 12.5, color: SLATE, margin: 0 });
    y += gap;
  });
}

// ---------- Slide 5: Spotlight on the project needing the most attention ----------
{
  let s = pres.addSlide();
  s.background = { color: NAVY };
  const spotlightName = deck.spotlight_project;
  const spot = projects[spotlightName];
  const statusColor = { Red: RED, Amber: AMBER, Green: GREEN }[spot.latest_status] || SLATE;

  s.addText(`Spotlight: ${spotlightName}`, { x: 0.6, y: 0.4, w: 8, h: 0.7, fontSize: 28, bold: true, color: WHITE, fontFace: "Cambria" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 9.9, y: 0.45, w: 2.9, h: 0.55, rectRadius: 0.08, fill: { color: statusColor }, line: { type: "none" } });
  s.addText(`STATUS: ${spot.latest_status.toUpperCase()}`, { x: 9.9, y: 0.45, w: 2.9, h: 0.55, fontSize: 15, bold: true, color: WHITE, align: "center", valign: "middle" });

  const reasons = spot.latest_reasons;
  const dimLabels = spot.latest_dimension_labels;
  const dimColorMap = { Red: RED, Amber: AMBER, Green: GREEN };
  let y = 1.4;
  Object.keys(reasons).forEach((d) => {
    s.addShape(pres.shapes.OVAL, { x: 0.7, y: y + 0.05, w: 0.22, h: 0.22, fill: { color: dimColorMap[dimLabels[d]] || SLATE }, line: { type: "none" } });
    s.addText(d.charAt(0).toUpperCase() + d.slice(1), { x: 1.1, y: y - 0.03, w: 2, h: 0.35, fontSize: 13, bold: true, color: ICE, margin: 0 });
    s.addText(reasons[d], { x: 3.2, y: y - 0.06, w: 9.5, h: 0.5, fontSize: 12.5, color: WHITE, margin: 0 });
    y += 0.68;
  });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: y + 0.15, w: 12.1, h: 1.5, rectRadius: 0.08, fill: { color: "2B3A80" }, line: { type: "none" } });
  s.addText("Bottom line for the client conversation", { x: 0.9, y: y + 0.3, w: 11.5, h: 0.35, fontSize: 14, bold: true, color: ICE, margin: 0 });
  // Generated from data.deck.spotlight_bottom_line (fixed after review:
  // previously a hardcoded paragraph naming "Project Alpha" specifically).
  s.addText(deck.spotlight_bottom_line, {
    x: 0.9, y: y + 0.65, w: 11.5, h: 0.9, fontSize: 12.5, color: WHITE, margin: 0,
  });
}

// ---------- Slide 6: Recommendations ----------
{
  let s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("Executive Recommendations", { x: 0.5, y: 0.35, w: 10, h: 0.7, fontSize: 30, bold: true, color: NAVY, fontFace: "Cambria" });
  s.addText("Actions for this coming month, in priority order", { x: 0.5, y: 0.95, w: 10, h: 0.4, fontSize: 14, color: SLATE, italic: true });

  // Generated from data.deck.recommendations (fixed after review: previously hardcoded).
  const recs = deck.recommendations;
  let y = 1.65;
  const gap = recs.length > 4 ? 1.05 : 1.25;
  recs.forEach((r, i) => {
    s.addShape(pres.shapes.OVAL, { x: 0.6, y: y + 0.05, w: 0.55, h: 0.55, fill: { color: NAVY }, line: { type: "none" } });
    s.addText(String(i + 1), { x: 0.6, y: y + 0.05, w: 0.55, h: 0.55, fontSize: 20, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(r.title, { x: 1.4, y: y, w: 11.2, h: 0.4, fontSize: 15, bold: true, color: NAVY, margin: 0 });
    s.addText(r.body, { x: 1.4, y: y + 0.4, w: 11.2, h: gap - 0.45, fontSize: 12.5, color: SLATE, margin: 0 });
    y += gap;
  });
}

// ---------- Slide 7: Appendix - methodology at a glance ----------
{
  let s = pres.addSlide();
  s.background = { color: "F4F6FB" };
  s.addText("Appendix: How RAG Status Is Determined", { x: 0.5, y: 0.35, w: 11, h: 0.7, fontSize: 26, bold: true, color: NAVY, fontFace: "Cambria" });
  s.addText("Automated weekly scoring across five weighted signals, with escalation overrides", { x: 0.5, y: 0.95, w: 11, h: 0.4, fontSize: 13, color: SLATE, italic: true });

  const cols = [
    { title: "Schedule (25%)", body: "% of tasks past their planned date; any late critical milestone forces Red." },
    { title: "Budget (20%)", body: "Actual vs. planned spend-to-date. Green 90–110%, Amber 70–90% / 110–130%, Red beyond that." },
    { title: "Milestones (25%)", body: "Overdue milestones and those due within 2 weeks flagged at risk." },
    { title: "Blockers (20%)", body: "Count, severity, and age of open blockers; any critical or 14+ day blocker escalates." },
    { title: "Sentiment (10%)", body: "PM/client narrative tone and week-over-week trend, classified automatically." },
  ];
  let x = 0.5;
  const w = 2.42;
  cols.forEach((c) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.65, w, h: 3.0, rectRadius: 0.08, fill: { color: WHITE }, line: { type: "none" },
      shadow: { type: "outer", color: "000000", blur: 4, offset: 2, angle: 90, opacity: 0.1 } });
    s.addText(c.title, { x: x + 0.15, y: 1.85, w: w - 0.3, h: 0.6, fontSize: 13, bold: true, color: NAVY, margin: 0 });
    s.addText(c.body, { x: x + 0.15, y: 2.45, w: w - 0.3, h: 2.1, fontSize: 11, color: SLATE, margin: 0 });
    x += w + 0.14;
  });

  s.addText("Missing data is never treated as automatically Green — it is scored Amber and flagged for follow-up. Critical blockers or 2+ overdue milestones override the weighted score and force Red regardless of other signals.", {
    x: 0.5, y: 4.9, w: 12.3, h: 0.8, fontSize: 12, italic: true, color: SLATE,
  });
  const weeklyReportsPath = inputPath.includes("demo") ? "/outputs/weekly_demo" : "/outputs/weekly";
  s.addText(`Full methodology: RAG_METHODOLOGY.md  |  Agent source: /agent  |  Weekly reports: ${weeklyReportsPath}`, {
    x: 0.5, y: 6.9, w: 12.3, h: 0.4, fontSize: 10, color: SLATE,
  });
}

pres.writeFile({ fileName: outputFileName }).then(() => console.log("done"));
