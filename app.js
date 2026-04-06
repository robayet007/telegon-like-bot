const STORAGE_KEY = "ff-like-dashboard-data";

const demoData = {
  generatedAt: "2026-04-06 16:40",
  month: "2026-04",
  summary: {
    totalSuperAdmins: 3,
    totalAdmins: 7,
    totalUsers: 19,
    totalUidRequests: 86,
    totalDistributed100: 2550,
    totalDistributed200: 1680
  },
  superAdmins: [
    {
      id: 6385648689,
      username: "@UNIPIN_SUPPLYAR_NILOY",
      name: "Niloy Supplyar",
      limit100: 1000,
      used100: 460,
      distributed100: 920,
      limit200: 500,
      used200: 180,
      distributed200: 420,
      admins: [
        {
          id: 72110001,
          username: "@rifat_topup",
          name: "Rifat",
          role: "Admin",
          limit100: 350,
          used100: 160,
          limit200: 140,
          used200: 52,
          users: [
            { id: 880001, username: "@sabbir_uid", name: "Sabbir", role: "User", limit100: 80, used100: 34, limit200: 30, used200: 11 },
            { id: 880002, username: "@tanvirx", name: "Tanvir", role: "User", limit100: 70, used100: 22, limit200: 20, used200: 6 }
          ]
        },
        {
          id: 72110002,
          username: "@mim_store",
          name: "Mim Store",
          role: "Admin",
          limit100: 280,
          used100: 112,
          limit200: 130,
          used200: 41,
          users: [
            { id: 880003, username: "@rakibff", name: "Rakib", role: "User", limit100: 90, used100: 45, limit200: 35, used200: 14 }
          ]
        }
      ],
      directUsers: [
        { id: 990001, username: "@nahid_direct", name: "Nahid", role: "User", limit100: 140, used100: 54, limit200: 60, used200: 17 }
      ]
    },
    {
      id: 6385648690,
      username: "@saad_supply",
      name: "Saad Enterprise",
      limit100: 900,
      used100: 370,
      distributed100: 830,
      limit200: 650,
      used200: 240,
      distributed200: 500,
      admins: [
        {
          id: 72110003,
          username: "@anik_panel",
          name: "Anik",
          role: "Admin",
          limit100: 300,
          used100: 146,
          limit200: 180,
          used200: 72,
          users: [
            { id: 880004, username: "@lamiya_uid", name: "Lamiya", role: "User", limit100: 110, used100: 64, limit200: 60, used200: 21 }
          ]
        }
      ],
      directUsers: [
        { id: 990002, username: "@tahmid_live", name: "Tahmid", role: "User", limit100: 120, used100: 46, limit200: 70, used200: 18 },
        { id: 990003, username: "@forhad_uid", name: "Forhad", role: "User", limit100: 150, used100: 62, limit200: 55, used200: 20 }
      ]
    },
    {
      id: 6385648691,
      username: "@nafi_ops",
      name: "Nafi Ops",
      limit100: 650,
      used100: 220,
      distributed100: 500,
      limit200: 420,
      used200: 150,
      distributed200: 330,
      admins: [
        {
          id: 72110004,
          username: "@salman_grid",
          name: "Salman",
          role: "Admin",
          limit100: 180,
          used100: 88,
          limit200: 90,
          used200: 36,
          users: [
            { id: 880005, username: "@tamim_ff", name: "Tamim", role: "User", limit100: 70, used100: 27, limit200: 36, used200: 13 }
          ]
        }
      ],
      directUsers: [
        { id: 990004, username: "@ashik_uid", name: "Ashik", role: "User", limit100: 90, used100: 31, limit200: 42, used200: 16 }
      ]
    }
  ],
  recentActivity: [
    { at: "2026-04-06 16:31", actor: "Sabbir", actorRole: "User", manager: "Rifat", uid: "1711537287", packageType: 100, likesAdded: 95 },
    { at: "2026-04-06 16:24", actor: "Nahid", actorRole: "User", manager: "Niloy Supplyar", uid: "1988123366", packageType: 200, likesAdded: 180 },
    { at: "2026-04-06 16:15", actor: "Lamiya", actorRole: "User", manager: "Anik", uid: "1477001112", packageType: 100, likesAdded: 82 },
    { at: "2026-04-06 15:59", actor: "Forhad", actorRole: "User", manager: "Saad Enterprise", uid: "1880027217", packageType: 200, likesAdded: 166 },
    { at: "2026-04-06 15:44", actor: "Tamim", actorRole: "User", manager: "Salman", uid: "998822114", packageType: 100, likesAdded: 74 },
    { at: "2026-04-06 15:35", actor: "Rakib", actorRole: "User", manager: "Mim Store", uid: "777200118", packageType: 200, likesAdded: 155 }
  ]
};

const els = {
  statsGrid: document.getElementById("stats-grid"),
  superAdminCards: document.getElementById("super-admin-cards"),
  hierarchyTree: document.getElementById("hierarchy-tree"),
  usersTableBody: document.getElementById("users-table-body"),
  activityList: document.getElementById("activity-list"),
  generatedAt: document.getElementById("generated-at"),
  activeMonth: document.getElementById("active-month"),
  dataStatusText: document.getElementById("data-status-text"),
  quickInfoList: document.getElementById("quick-info-list"),
  userSearchInput: document.getElementById("user-search-input"),
  loadDemoBtn: document.getElementById("load-demo-btn"),
  clearStorageBtn: document.getElementById("clear-storage-btn"),
  jsonFileInput: document.getElementById("json-file-input")
};

let dashboardData = null;

function formatNumber(value) {
  return new Intl.NumberFormat().format(value ?? 0);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function roleClass(role) {
  return `role-${String(role).toLowerCase().replace(/\s+/g, "-")}`;
}

function normalizeData(raw) {
  const safe = raw && typeof raw === "object" ? raw : demoData;
  const superAdmins = Array.isArray(safe.superAdmins) ? safe.superAdmins : [];
  const recentActivity = Array.isArray(safe.recentActivity) ? safe.recentActivity : [];

  const computedSummary = {
    totalSuperAdmins: superAdmins.length,
    totalAdmins: superAdmins.reduce((sum, sa) => sum + (sa.admins?.length || 0), 0),
    totalUsers: superAdmins.reduce((sum, sa) => {
      const direct = sa.directUsers?.length || 0;
      const nested = (sa.admins || []).reduce((sub, admin) => sub + (admin.users?.length || 0), 0);
      return sum + direct + nested;
    }, 0),
    totalUidRequests: recentActivity.length,
    totalDistributed100: superAdmins.reduce((sum, sa) => sum + (sa.distributed100 || 0), 0),
    totalDistributed200: superAdmins.reduce((sum, sa) => sum + (sa.distributed200 || 0), 0)
  };

  return {
    generatedAt: safe.generatedAt || new Date().toLocaleString(),
    month: safe.month || new Date().toISOString().slice(0, 7),
    summary: { ...computedSummary, ...(safe.summary || {}) },
    superAdmins,
    recentActivity
  };
}

function flattenUsers(data) {
  const rows = [];

  for (const superAdmin of data.superAdmins) {
    rows.push({
      id: superAdmin.id,
      username: superAdmin.username,
      name: superAdmin.name,
      role: "Super Admin",
      manager: "Main Admin",
      limit100: superAdmin.limit100,
      used100: superAdmin.used100,
      limit200: superAdmin.limit200,
      used200: superAdmin.used200
    });

    for (const directUser of superAdmin.directUsers || []) {
      rows.push({
        id: directUser.id,
        username: directUser.username,
        name: directUser.name,
        role: "User",
        manager: superAdmin.name,
        limit100: directUser.limit100,
        used100: directUser.used100,
        limit200: directUser.limit200,
        used200: directUser.used200
      });
    }

    for (const admin of superAdmin.admins || []) {
      rows.push({
        id: admin.id,
        username: admin.username,
        name: admin.name,
        role: "Admin",
        manager: superAdmin.name,
        limit100: admin.limit100,
        used100: admin.used100,
        limit200: admin.limit200,
        used200: admin.used200
      });

      for (const user of admin.users || []) {
        rows.push({
          id: user.id,
          username: user.username,
          name: user.name,
          role: "User",
          manager: admin.name,
          limit100: user.limit100,
          used100: user.used100,
          limit200: user.limit200,
          used200: user.used200
        });
      }
    }
  }

  return rows;
}

function renderStats(data) {
  const items = [
    ["Super Admin", data.summary.totalSuperAdmins],
    ["Normal Admin", data.summary.totalAdmins],
    ["Managed User", data.summary.totalUsers],
    ["UID Requests", data.summary.totalUidRequests],
    ["Distributed Total", data.summary.totalDistributed100 + data.summary.totalDistributed200]
  ];

  els.statsGrid.innerHTML = items.map(([label, value]) => `
    <div class="stat-card">
      <p>${escapeHtml(label)}</p>
      <strong>${formatNumber(value)}</strong>
    </div>
  `).join("");
}

function renderSuperAdminCards(data) {
  if (!data.superAdmins.length) {
    els.superAdminCards.innerHTML = '<div class="empty-state">No super admin data available.</div>';
    return;
  }

  els.superAdminCards.innerHTML = data.superAdmins.map((item) => {
    const fill100 = item.limit100 ? Math.min((item.distributed100 / item.limit100) * 100, 100) : 0;
    const fill200 = item.limit200 ? Math.min((item.distributed200 / item.limit200) * 100, 100) : 0;
    const remaining100 = Math.max((item.limit100 || 0) - (item.distributed100 || 0), 0);
    const remaining200 = Math.max((item.limit200 || 0) - (item.distributed200 || 0), 0);

    return `
      <div class="super-admin-card">
        <div class="super-admin-top">
          <div>
            <p class="super-admin-name">${escapeHtml(item.name)}</p>
            <div class="super-admin-id mono">${escapeHtml(item.username)} · ${escapeHtml(item.id)}</div>
          </div>
          <span class="tag">${(item.admins?.length || 0) + (item.directUsers?.length || 0)} direct nodes</span>
        </div>
        <div class="metric-grid">
          <div class="mini-metric">
            <span class="muted">100 Package</span>
            <strong>${formatNumber(item.distributed100)} / ${formatNumber(item.limit100)}</strong>
            <small class="muted">remaining ${formatNumber(remaining100)}</small>
          </div>
          <div class="mini-metric">
            <span class="muted">200 Package</span>
            <strong>${formatNumber(item.distributed200)} / ${formatNumber(item.limit200)}</strong>
            <small class="muted">remaining ${formatNumber(remaining200)}</small>
          </div>
        </div>
        <div class="bar"><div class="bar-fill" style="width:${fill100}%"></div></div>
        <div class="muted">100 limit distributed</div>
        <div class="bar"><div class="bar-fill" style="width:${fill200}%"></div></div>
        <div class="muted">200 limit distributed</div>
      </div>
    `;
  }).join("");
}

function createTreeNode(label, sublabel, role, childrenHtml = "") {
  return `
    <div class="tree-node">
      <div class="tree-node-head">
        <div>
          <strong>${escapeHtml(label)}</strong>
          <div class="muted">${escapeHtml(sublabel)}</div>
        </div>
        <span class="role-badge ${roleClass(role)}">${escapeHtml(role)}</span>
      </div>
      ${childrenHtml ? `<div class="tree-children">${childrenHtml}</div>` : ""}
    </div>
  `;
}

function renderHierarchy(data) {
  if (!data.superAdmins.length) {
    els.hierarchyTree.innerHTML = '<div class="empty-state">No hierarchy data available.</div>';
    return;
  }

  const html = createTreeNode(
    "Main Admin",
    "Top level owner view",
    "Main Admin",
    data.superAdmins.map((superAdmin) => {
      const adminNodes = (superAdmin.admins || []).map((admin) => {
        const userNodes = (admin.users || []).map((user) =>
          createTreeNode(`${user.name} ${user.username || ""}`.trim(), `100 ${user.used100}/${user.limit100} · 200 ${user.used200}/${user.limit200}`, user.role || "User")
        ).join("");

        return createTreeNode(`${admin.name} ${admin.username || ""}`.trim(), `100 ${admin.used100}/${admin.limit100} · 200 ${admin.used200}/${admin.limit200}`, admin.role || "Admin", userNodes);
      }).join("");

      const directUserNodes = (superAdmin.directUsers || []).map((user) =>
        createTreeNode(`${user.name} ${user.username || ""}`.trim(), `100 ${user.used100}/${user.limit100} · 200 ${user.used200}/${user.limit200}`, user.role || "User")
      ).join("");

      return createTreeNode(`${superAdmin.name} ${superAdmin.username || ""}`.trim(), `100 ${superAdmin.used100}/${superAdmin.limit100} · 200 ${superAdmin.used200}/${superAdmin.limit200}`, "Super Admin", adminNodes + directUserNodes);
    }).join("")
  );

  els.hierarchyTree.innerHTML = html;
}

function renderUsersTable(data, searchTerm = "") {
  const rows = flattenUsers(data).filter((row) => {
    const haystack = `${row.name} ${row.username} ${row.manager} ${row.role} ${row.id}`.toLowerCase();
    return haystack.includes(searchTerm.toLowerCase());
  });

  if (!rows.length) {
    els.usersTableBody.innerHTML = `
      <tr>
        <td colspan="7"><div class="empty-state">No matching users found.</div></td>
      </tr>
    `;
    return;
  }

  els.usersTableBody.innerHTML = rows.map((row) => `
    <tr>
      <td><strong>${escapeHtml(row.name)}</strong><br><span class="muted">${escapeHtml(row.username || "No username")} · ${escapeHtml(row.id)}</span></td>
      <td><span class="role-badge ${roleClass(row.role)}">${escapeHtml(row.role)}</span></td>
      <td>${escapeHtml(row.manager)}</td>
      <td>${formatNumber(row.limit100)}</td>
      <td>${formatNumber(row.used100)}</td>
      <td>${formatNumber(row.limit200)}</td>
      <td>${formatNumber(row.used200)}</td>
    </tr>
  `).join("");
}

function renderActivity(data) {
  if (!data.recentActivity.length) {
    els.activityList.innerHTML = '<div class="empty-state">No UID activity found yet. Connect a safe activity feed later to see live request history.</div>';
    return;
  }

  els.activityList.innerHTML = data.recentActivity.map((item) => `
    <div class="activity-item">
      <div class="activity-item-head">
        <strong>${escapeHtml(item.actor)}</strong>
        <span class="tag">${escapeHtml(item.packageType)} package</span>
      </div>
      <p>
        <span class="mono">UID ${escapeHtml(item.uid)}</span> received <strong>${formatNumber(item.likesAdded)}</strong> likes.<br>
        Role: ${escapeHtml(item.actorRole)} · Manager: ${escapeHtml(item.manager)}<br>
        Time: ${escapeHtml(item.at)}
      </p>
    </div>
  `).join("");
}

function renderMeta(data, sourceLabel) {
  els.generatedAt.textContent = data.generatedAt;
  els.activeMonth.textContent = data.month;
  els.dataStatusText.textContent = sourceLabel;
  els.quickInfoList.innerHTML = `
    <li>${formatNumber(data.summary.totalSuperAdmins)} super admins monitored</li>
    <li>${formatNumber(data.summary.totalAdmins)} normal admins under management</li>
    <li>${formatNumber(data.summary.totalUsers)} users mapped in dashboard</li>
  `;
}

function renderAll(sourceLabel = "Demo mode") {
  if (!dashboardData) {
    dashboardData = normalizeData(demoData);
  }

  renderMeta(dashboardData, sourceLabel);
  renderStats(dashboardData);
  renderSuperAdminCards(dashboardData);
  renderHierarchy(dashboardData);
  renderUsersTable(dashboardData, els.userSearchInput.value || "");
  renderActivity(dashboardData);
}

async function fetchDashboardFromServer() {
  const response = await fetch("/api/dashboard", {
    headers: {
      "Accept": "application/json"
    },
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Dashboard API failed with status ${response.status}`);
  }

  return normalizeData(await response.json());
}

function saveData(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function loadSavedData() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;

  try {
    return normalizeData(JSON.parse(raw));
  } catch (error) {
    console.error("Saved dashboard data parse failed:", error);
    return null;
  }
}

function tryLoadInjectedData() {
  return window.dashboardData ? normalizeData(window.dashboardData) : null;
}

function handleImportedJson(text) {
  const parsed = JSON.parse(text);
  dashboardData = normalizeData(parsed);
  saveData(dashboardData);
  renderAll("Imported JSON");
}

els.userSearchInput.addEventListener("input", () => {
  renderUsersTable(dashboardData, els.userSearchInput.value || "");
});

els.loadDemoBtn.addEventListener("click", () => {
  dashboardData = normalizeData(demoData);
  saveData(dashboardData);
  renderAll("Demo mode");
});

els.clearStorageBtn.addEventListener("click", () => {
  localStorage.removeItem(STORAGE_KEY);
  initializeDashboard(true);
});

els.jsonFileInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;

  try {
    const text = await file.text();
    handleImportedJson(text);
  } catch (error) {
    console.error(error);
    alert("Could not import JSON. Please use a sanitized dashboard export.");
  } finally {
    event.target.value = "";
  }
});

async function initializeDashboard(ignoreSaved = false) {
  try {
    dashboardData = await fetchDashboardFromServer();
    renderAll("Live server data");
    return;
  } catch (error) {
    console.warn("Live dashboard fetch failed:", error);
  }

  const saved = ignoreSaved ? null : loadSavedData();
  const injected = tryLoadInjectedData();
  dashboardData = saved || injected || normalizeData(demoData);
  const source = saved ? "Saved local data" : (injected ? "Injected secure data" : "Demo fallback");
  renderAll(source);
}

initializeDashboard();
