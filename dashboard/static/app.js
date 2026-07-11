const POLL_MS = 4000;
let lastComputedAt = {}; // slug -> computed_at string, to detect real changes for the flash effect

function renderCard(p) {
  const dimsHtml = Object.entries(p.dimensions).map(([name, d]) => `
    <div class="dim ${d.status}">
      <span class="label">${name}</span>
      ${d.status}
    </div>
  `).join("");

  const reasonsHtml = Object.entries(p.dimensions).map(([name, d]) =>
    `<strong style="text-transform:capitalize">${name}:</strong> ${d.reason || "—"}`
  ).join("<br>");

  const overrideHtml = (p.override_reasons && p.override_reasons.length)
    ? `<div class="reasons" style="margin-top:8px; border-color:${p.overall_label === 'Red' ? '#f2c4c4' : '#f2ddb0'}">
         ${p.override_reasons.map(r => `⚠️ ${r}`).join("<br>")}
       </div>`
    : "";

  const dqHtml = (p.data_quality_notes && p.data_quality_notes.length)
    ? `<div class="dq-notes">Data quality: ${p.data_quality_notes.join(" · ")}</div>`
    : "";

  return `
    <div class="card ${p.overall_label}" id="card-${p.slug}">
      <div class="card-header">
        <h2>${p.project_name}</h2>
        <span class="badge ${p.overall_label}">${p.overall_label}</span>
      </div>
      <div class="meta">${p.row_count} tasks in source data &middot; last recalculated ${p.computed_at}</div>
      <div class="dims">${dimsHtml}</div>
      <div class="reasons">${reasonsHtml}</div>
      ${overrideHtml}
      ${dqHtml}
    </div>
  `;
}

async function poll() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    document.getElementById("server-time").textContent = "· " + data.server_time;

    const container = document.getElementById("cards");
    container.innerHTML = data.projects.map(renderCard).join("");

    // Briefly flash any card whose underlying data actually changed this poll
    data.projects.forEach(p => {
      if (p.just_recomputed && lastComputedAt[p.slug] && lastComputedAt[p.slug] !== p.computed_at) {
        const el = document.getElementById(`card-${p.slug}`);
        if (el) {
          el.classList.add("flash");
          setTimeout(() => el.classList.remove("flash"), 1500);
        }
      }
      lastComputedAt[p.slug] = p.computed_at;
    });
  } catch (e) {
    console.error("Poll failed:", e);
  }
}

poll();
setInterval(poll, POLL_MS);
