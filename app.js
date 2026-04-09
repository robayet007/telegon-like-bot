const STORAGE_KEY = "ff-like-dashboard-data";

const demoData = {
  generatedAt: "2026-04-09 10:30:00 UTC",
  month: "2026-04",
  summary: {
    totalSuperAdmins: 3,
    activeSuperAdmins: 2,
    expiredSuperAdmins: 1,
    inactiveSuperAdmins: 0,
    onlineSuperAdmins: 2,
    totalAdmins: 4,
    totalUsers: 11,
    totalUidRequests: 12,
    totalDistributed100: 1720,
    totalDistributed200: 960,
    totalUsed100: 520,
    totalUsed200: 210
  },
  superAdmins: [
    {
      id: 6385648689,
      username: "@niloy_ops",
      name: "Niloy Ops",
      accessStatus: "active",
      accessText: "Active until 2026-04-28 18:00 UTC",
      accessExpiresAt: "2026-04-28 18:00 UTC",
      clientOnline: true,
      branchStorageReady: true,
      requestCount: 5,
      lastActivityAt: "2026-04-09 09:40:00 UTC",
      adminCount: 2,
      userCount: 4,
      limit100: 900,
      used100: 220,
      remaining100: 680,
      distributed100: 560,
      distributable100: 120,
      availableSelf100: 340,
      limit200: 500,
      used200: 80,
      remaining200: 420,
      distributed200: 290,
      distributable200: 130,
      availableSelf200: 210,
      admins: [
        {
          id: 72110001,
          username: "@rifat_topup",
          name: "Rifat",
          role: "Admin",
          limit100: 220,
          used100: 90,
          remaining100: 130,
          limit200: 110,
          used200: 34,
          remaining200: 76,
          users: [
            {
              id: 880001,
              username: "@sabbir_uid",
              name: "Sabbir",
              role: "User",
              limit100: 70,
              used100: 20,
              remaining100: 50,
              limit200: 25,
              used200: 7,
              remaining200: 18
            }
          ]
        },
        {
          id: 72110002,
          username: "@mim_store",
          name: "Mim Store",
          role: "Admin",
          limit100: 180,
          used100: 60,
          remaining100: 120,
          limit200: 90,
          used200: 29,
          remaining200: 61,
          users: [
            {
              id: 880002,
              username: "@rakib_ff",
              name: "Rakib",
              role: "User",
              limit100: 60,
              used100: 24,
              remaining100: 36,
              limit200: 30,
              used200: 9,
              remaining200: 21
            }
          ]
        }
      ],
      directUsers: [
        {
          id: 990001,
          username: "@nahid_direct",
          name: "Nahid",
          role: "User",
          limit100: 160,
          used100: 26,
          remaining100: 134,
          limit200: 60,
          used200: 10,
          remaining200: 50
        },
        {
          id: 990002,
          username: "@ashik_direct",
          name: "Ashik",
          role: "User",
          limit100: 80,
          used100: 14,
          remaining100: 66,
          limit200: 30,
          used200: 5,
          remaining200: 25
        }
      ]
    },
    {
      id: 6385648690,
      username: "@saad_supply",
      name: "Saad Supply",
      accessStatus: "expired",
      accessText: "Expired on 2026-04-06 12:00 UTC",
      accessExpiresAt: "2026-04-06 12:00 UTC",
      clientOnline: false,
      branchStorageReady: true,
      requestCount: 0,
      lastActivityAt: "",
      adminCount: 1,
      userCount: 3,
      limit100: 700,
      used100: 150,
      remaining100: 550,
      distributed100: 400,
      distributable100: 150,
      availableSelf100: 300,
      limit200: 400,
      used200: 70,
      remaining200: 330,
      distributed200: 200,
      distributable200: 130,
      availableSelf200: 200,
      admins: [
        {
          id: 72110003,
          username: "@anik_panel",
          name: "Anik",
          role: "Admin",
          limit100: 200,
          used100: 55,
          remaining100: 145,
          limit200: 100,
          used200: 25,
          remaining200: 75,
          users: [
            {
              id: 880003,
              username: "@lamiya_uid",
              name: "Lamiya",
              role: "User",
              limit100: 90,
              used100: 32,
              remaining100: 58,
              limit200: 40,
              used200: 12,
              remaining200: 28
            }
          ]
        }
      ],
      directUsers: [
        {
          id: 990003,
          username: "@forhad_uid",
          name: "Forhad",
          role: "User",
          limit100: 110,
          used100: 38,
          remaining100: 72,
          limit200: 55,
          used200: 19,
          remaining200: 36
        },
        {
          id: 990004,
          username: "@tahmid_live",
          name: "Tahmid",
          role: "User",
          limit100: 90,
          used100: 25,
          remaining100: 65,
          limit200: 45,
          used200: 14,
          remaining200: 31
        }
      ]
    },
    {
      id: 6385648691,
      username: "@nafi_ops",
      name: "Nafi Ops",
      accessStatus: "active",
      accessText: "Active until 2026-04-22 09:00 UTC",
      accessExpiresAt: "2026-04-22 09:00 UTC",
      clientOnline: true,
      branchStorageReady: true,
      requestCount: 3,
      lastActivityAt: "2026-04-09 08:25:00 UTC",
      adminCount: 1,
      userCount: 2,
      limit100: 650,
      used100: 150,
      remaining100: 500,
      distributed100: 360,
      distributable100: 140,
      availableSelf100: 290,
      limit200: 320,
      used200: 60,
      remaining200: 260,
      distributed200: 150,
      distributable200: 110,
      availableSelf200: 170,
      admins: [
        {
          id: 72110004,
          username: "@salman_grid",
          name: "Salman",
          role: "Admin",
          limit100: 170,
          used100: 66,
          remaining100: 104,
          limit200: 75,
          used200: 21,
          remaining200: 54,
          users: [
            {
              id: 880004,
              username: "@tamim_ff",
              name: "Tamim",
              role: "User",
              limit100: 70,
              used100: 18,
              remaining100: 52,
              limit200: 32,
              used200: 8,
              remaining200: 24
            }
          ]
        }
      ],
      directUsers: [
        {
          id: 990005,
          username: "@ashraful_uid",
          name: "Ashraful",
          role: "User",
          limit100: 120,
          used100: 31,
          remaining100: 89,
          limit200: 43,
          used200: 12,
          remaining200: 31
        }
      ]
    }
  ],
  recentActivity: [
    {
      at: "2026-04-09 09:40:00 UTC",
      actor: "Nahid",
      actorRole: "User",
      manager: "Niloy Ops",
      uid: "1711537287",
      packageType: 100,
      likesAdded: 92,
      branchOwner: "Niloy Ops",
      branchOwnerUsername: "@niloy_ops",
      accessStatus: "active"
    },
    {
      at: "2026-04-09 09:14:00 UTC",
      actor: "Rifat",
      actorRole: "Admin",
      manager: "Niloy Ops",
      uid: "1888123366",
      packageType: 200,
      likesAdded: 180,
      branchOwner: "Niloy Ops",
      branchOwnerUsername: "@niloy_ops",
      accessStatus: "active"
    },
    {
      at: "2026-04-09 08:25:00 UTC",
      actor: "Tamim",
      actorRole: "User",
      manager: "Salman",
      uid: "1477001112",
      packageType: 100,
      likesAdded: 84,
      branchOwner: "Nafi Ops",
      branchOwnerUsername: "@nafi_ops",
      accessStatus: "active"
    }
  ]
};

const els = {
  statsGrid: document.getElementById("stats-grid"),
  superAdminTableBody: document.getElementById("super-admin-table-body"),
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
  return new Intl.NumberFormat().format(Number(value || 0));
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
  return `role-${String(role || "user").toLowerCase().replace(/\s+/g, "-")}`;
}

function accessClass(status) {
  return `status-${String(status || "missing").toLowerCase()}`;
}

function accessLabel(status) {
  const value = String(status || "missing").toLowerCase();
  if (value === "active") return "Active";
  if (value === "expired") return "Expired";
  if (value === "owner") return "Owner";
  return "No Grant";
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function normalizeUser(user, role = "User") {
  const safe = user && typeof user === "object" ? user : {};
  return {
    id: safe.id ?? 0,
    username: safe.username || "",
    name: safe.name || String(safe.id || "Unknown"),
    role: safe.role || role,
    managerId: safe.managerId ?? null,
    limit100: Number(safe.limit100 || 0),
    used100: Number(safe.used100 || 0),
    remaining100: Number(safe.remaining100 ?? Math.max((safe.limit100 || 0) - (safe.used100 || 0), 0)),
    limit200: Number(safe.limit200 || 0),
    used200: Number(safe.used200 || 0),
    remaining200: Number(safe.remaining200 ?? Math.max((safe.limit200 || 0) - (safe.used200 || 0), 0)),
    distributed100: Number(safe.distributed100 || 0),
    distributed200: Number(safe.distributed200 || 0),
    distributable100: Number(safe.distributable100 || 0),
    distributable200: Number(safe.distributable200 || 0),
    availableSelf100: Number(safe.availableSelf100 || 0),
    availableSelf200: Number(safe.availableSelf200 || 0),
    users: safeArray(safe.users).map((item) => normalizeUser(item, item.role || "User"))
  };
}

function normalizeSuperAdmin(item) {
  const safe = normalizeUser(item, "Super Admin");
  const admins = safeArray(item.admins).map((admin) => normalizeUser(admin, admin.role || "Admin"));
  const directUsers = safeArray(item.directUsers).map((user) => normalizeUser(user, user.role || "User"));
  const nestedUsers = admins.reduce((sum, admin) => sum + safeArray(admin.users).length, 0);

  return {
    ...safe,
    accessStatus: item.accessStatus || "missing",
    accessText: item.accessText || "No owner grant",
    accessGrantedAt: item.accessGrantedAt || "N/A",
    accessExpiresAt: item.accessExpiresAt || "N/A",
    clientOnline: Boolean(item.clientOnline),
    branchStorageReady: Boolean(item.branchStorageReady),
    requestCount: Number(item.requestCount || 0),
    lastActivityAt: item.lastActivityAt || "No activity",
    adminCount: Number(item.adminCount ?? admins.length),
    userCount: Number(item.userCount ?? (directUsers.length + nestedUsers)),
    admins,
    directUsers
  };
}

function normalizeData(raw) {
  const safe = raw && typeof raw === "object" ? raw : demoData;
  const superAdmins = safeArray(safe.superAdmins).map(normalizeSuperAdmin);
  const recentActivity = safeArray(safe.recentActivity).map((item) => ({
    at: item.at || "",
    actor: item.actor || "Unknown",
    actorRole: item.actorRole || "User",
    manager: item.manager || "Main Admin",
    uid: item.uid || "",
    packageType: Number(item.packageType || 0),
    likesAdded: Number(item.likesAdded || 0),
    branchOwner: item.branchOwner || "Main Admin",
    branchOwnerUsername: item.branchOwnerUsername || "",
    accessStatus: item.accessStatus || "owner"
  }));

  const computedSummary = {
    totalSuperAdmins: superAdmins.length,
    activeSuperAdmins: superAdmins.filter((item) => item.accessStatus === "active").length,
    expiredSuperAdmins: superAdmins.filter((item) => item.accessStatus === "expired").length,
    inactiveSuperAdmins: superAdmins.filter((item) => item.accessStatus === "missing").length,
    onlineSuperAdmins: superAdmins.filter((item) => item.clientOnline).length,
    totalAdmins: superAdmins.reduce((sum, item) => sum + item.adminCount, 0),
    totalUsers: superAdmins.reduce((sum, item) => sum + item.userCount, 0),
    totalUidRequests: recentActivity.length,
    totalDistributed100: superAdmins.reduce((sum, item) => sum + item.distributed100, 0),
    totalDistributed200: superAdmins.reduce((sum, item) => sum + item.distributed200, 0),
    totalUsed100: superAdmins.reduce((sum, item) => sum + item.used100, 0),
    totalUsed200: superAdmins.reduce((sum, item) => sum + item.used200, 0)
  };

  return {
    generatedAt: safe.generatedAt || new Date().toISOString(),
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
      branch: superAdmin.name,
      stats100: `${formatNumber(superAdmin.used100)} / ${formatNumber(superAdmin.limit100)} (left ${formatNumber(superAdmin.remaining100)})`,
      stats200: `${formatNumber(superAdmin.used200)} / ${formatNumber(superAdmin.limit200)} (left ${formatNumber(superAdmin.remaining200)})`
    });

    for (const directUser of superAdmin.directUsers) {
      rows.push({
        id: directUser.id,
        username: directUser.username,
        name: directUser.name,
        role: directUser.role || "User",
        manager: superAdmin.name,
        branch: superAdmin.name,
        stats100: `${formatNumber(directUser.used100)} / ${formatNumber(directUser.limit100)} (left ${formatNumber(directUser.remaining100)})`,
        stats200: `${formatNumber(directUser.used200)} / ${formatNumber(directUser.limit200)} (left ${formatNumber(directUser.remaining200)})`
      });
    }

    for (const admin of superAdmin.admins) {
      rows.push({
        id: admin.id,
        username: admin.username,
        name: admin.name,
        role: admin.role || "Admin",
        manager: superAdmin.name,
        branch: superAdmin.name,
        stats100: `${formatNumber(admin.used100)} / ${formatNumber(admin.limit100)} (left ${formatNumber(admin.remaining100)})`,
        stats200: `${formatNumber(admin.used200)} / ${formatNumber(admin.limit200)} (left ${formatNumber(admin.remaining200)})`
      });

      for (const user of admin.users) {
        rows.push({
          id: user.id,
          username: user.username,
          name: user.name,
          role: user.role || "User",
          manager: admin.name,
          branch: superAdmin.name,
          stats100: `${formatNumber(user.used100)} / ${formatNumber(user.limit100)} (left ${formatNumber(user.remaining100)})`,
          stats200: `${formatNumber(user.used200)} / ${formatNumber(user.limit200)} (left ${formatNumber(user.remaining200)})`
        });
      }
    }
  }

  return rows;
}

function renderStats(data) {
  const items = [
    ["Super Admins", data.summary.totalSuperAdmins],
    ["Active Access", data.summary.activeSuperAdmins],
    ["Expired Access", data.summary.expiredSuperAdmins],
    ["Online Clients", data.summary.onlineSuperAdmins],
    ["Branch Admins", data.summary.totalAdmins],
    ["Managed Users", data.summary.totalUsers],
    ["Recent Requests", data.summary.totalUidRequests],
    ["100 Used", data.summary.totalUsed100],
    ["200 Used", data.summary.totalUsed200]
  ];

  els.statsGrid.innerHTML = items.map(([label, value]) => `
    <div class="stat-card">
      <p>${escapeHtml(label)}</p>
      <strong>${formatNumber(value)}</strong>
    </div>
  `).join("");
}

function renderSuperAdminTable(data) {
  if (!data.superAdmins.length) {
    els.superAdminTableBody.innerHTML = `
      <tr>
        <td colspan="8"><div class="empty-state">No super admin data available.</div></td>
      </tr>
    `;
    return;
  }

  els.superAdminTableBody.innerHTML = data.superAdmins.map((item) => `
    <tr>
      <td>
        <strong>${escapeHtml(item.name)}</strong><br>
        <span class="muted">${escapeHtml(item.username || "No username")} | ${escapeHtml(item.id)}</span>
      </td>
      <td>
        <span class="status-badge ${accessClass(item.accessStatus)}">${escapeHtml(accessLabel(item.accessStatus))}</span><br>
        <span class="muted">${escapeHtml(item.accessText)}</span>
      </td>
      <td>
        <span class="status-badge ${item.clientOnline ? "status-active" : "status-expired"}">${item.clientOnline ? "Online" : "Offline"}</span><br>
        <span class="muted">${item.branchStorageReady ? "Storage ready" : "Storage missing"}</span>
      </td>
      <td>
        <strong>${formatNumber(item.requestCount)}</strong><br>
        <span class="muted">this month</span>
      </td>
      <td>
        Used ${formatNumber(item.used100)} / ${formatNumber(item.limit100)}<br>
        <span class="muted">Distributed ${formatNumber(item.distributed100)} | Left ${formatNumber(item.distributable100)}</span>
      </td>
      <td>
        Used ${formatNumber(item.used200)} / ${formatNumber(item.limit200)}<br>
        <span class="muted">Distributed ${formatNumber(item.distributed200)} | Left ${formatNumber(item.distributable200)}</span>
      </td>
      <td>
        ${formatNumber(item.adminCount)} admin(s)<br>
        <span class="muted">${formatNumber(item.userCount)} user(s)</span>
      </td>
      <td>${escapeHtml(item.lastActivityAt || "No activity")}</td>
    </tr>
  `).join("");
}

function metricBar(used, total) {
  const fill = total > 0 ? Math.min((used / total) * 100, 100) : 0;
  return `
    <div class="bar">
      <div class="bar-fill" style="width:${fill}%"></div>
    </div>
  `;
}

function renderSuperAdminCards(data) {
  if (!data.superAdmins.length) {
    els.superAdminCards.innerHTML = '<div class="empty-state">No branch cards available.</div>';
    return;
  }

  els.superAdminCards.innerHTML = data.superAdmins.map((item) => `
    <article class="super-admin-card">
      <div class="super-admin-top">
        <div>
          <p class="super-admin-name">${escapeHtml(item.name)}</p>
          <div class="super-admin-id mono">${escapeHtml(item.username || "No username")} | ${escapeHtml(item.id)}</div>
        </div>
        <span class="status-badge ${accessClass(item.accessStatus)}">${escapeHtml(accessLabel(item.accessStatus))}</span>
      </div>

      <div class="info-grid">
        <div class="info-chip">
          <span>Requests</span>
          <strong>${formatNumber(item.requestCount)}</strong>
        </div>
        <div class="info-chip">
          <span>Client</span>
          <strong>${item.clientOnline ? "Online" : "Offline"}</strong>
        </div>
        <div class="info-chip">
          <span>Admins</span>
          <strong>${formatNumber(item.adminCount)}</strong>
        </div>
        <div class="info-chip">
          <span>Users</span>
          <strong>${formatNumber(item.userCount)}</strong>
        </div>
      </div>

      <div class="metric-block">
        <div class="metric-row">
          <span>100 package</span>
          <strong>${formatNumber(item.used100)} / ${formatNumber(item.limit100)}</strong>
        </div>
        ${metricBar(item.used100 + item.distributed100, Math.max(item.limit100, 1))}
        <small class="muted">Self used ${formatNumber(item.used100)} | Distributed ${formatNumber(item.distributed100)} | Free to distribute ${formatNumber(item.distributable100)}</small>
      </div>

      <div class="metric-block">
        <div class="metric-row">
          <span>200 package</span>
          <strong>${formatNumber(item.used200)} / ${formatNumber(item.limit200)}</strong>
        </div>
        ${metricBar(item.used200 + item.distributed200, Math.max(item.limit200, 1))}
        <small class="muted">Self used ${formatNumber(item.used200)} | Distributed ${formatNumber(item.distributed200)} | Free to distribute ${formatNumber(item.distributable200)}</small>
      </div>

      <div class="card-footer">
        <div>
          <span class="muted">Access</span>
          <strong>${escapeHtml(item.accessText)}</strong>
        </div>
        <div>
          <span class="muted">Last activity</span>
          <strong>${escapeHtml(item.lastActivityAt || "No activity")}</strong>
        </div>
      </div>
    </article>
  `).join("");
}

function createTreeNode(label, sublabel, role, extra = "", childrenHtml = "") {
  return `
    <div class="tree-node">
      <div class="tree-node-head">
        <div>
          <strong>${escapeHtml(label)}</strong>
          <div class="muted">${escapeHtml(sublabel)}</div>
          ${extra ? `<div class="tiny-muted">${escapeHtml(extra)}</div>` : ""}
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
    "Owner branch view",
    "Main Admin",
    "All verified super admin branches",
    data.superAdmins.map((superAdmin) => {
      const adminNodes = superAdmin.admins.map((admin) => {
        const userNodes = admin.users.map((user) =>
          createTreeNode(
            `${user.name} ${user.username || ""}`.trim(),
            `100 ${user.used100}/${user.limit100} | 200 ${user.used200}/${user.limit200}`,
            user.role || "User"
          )
        ).join("");

        return createTreeNode(
          `${admin.name} ${admin.username || ""}`.trim(),
          `100 ${admin.used100}/${admin.limit100} | 200 ${admin.used200}/${admin.limit200}`,
          admin.role || "Admin",
          `Nested users: ${admin.users.length}`,
          userNodes
        );
      }).join("");

      const directUserNodes = superAdmin.directUsers.map((user) =>
        createTreeNode(
          `${user.name} ${user.username || ""}`.trim(),
          `100 ${user.used100}/${user.limit100} | 200 ${user.used200}/${user.limit200}`,
          user.role || "User"
        )
      ).join("");

      return createTreeNode(
        `${superAdmin.name} ${superAdmin.username || ""}`.trim(),
        `${accessLabel(superAdmin.accessStatus)} | Requests ${superAdmin.requestCount}`,
        "Super Admin",
        `${superAdmin.adminCount} admin(s), ${superAdmin.userCount} user(s), last ${superAdmin.lastActivityAt || "No activity"}`,
        adminNodes + directUserNodes
      );
    }).join("")
  );

  els.hierarchyTree.innerHTML = html;
}

function renderUsersTable(data, searchTerm = "") {
  const query = String(searchTerm || "").trim().toLowerCase();
  const rows = flattenUsers(data).filter((row) => {
    const haystack = `${row.name} ${row.username} ${row.manager} ${row.role} ${row.branch} ${row.id}`.toLowerCase();
    return haystack.includes(query);
  });

  if (!rows.length) {
    els.usersTableBody.innerHTML = `
      <tr>
        <td colspan="6"><div class="empty-state">No matching users found.</div></td>
      </tr>
    `;
    return;
  }

  els.usersTableBody.innerHTML = rows.map((row) => `
    <tr>
      <td>
        <strong>${escapeHtml(row.name)}</strong><br>
        <span class="muted">${escapeHtml(row.username || "No username")} | ${escapeHtml(row.id)}</span>
      </td>
      <td><span class="role-badge ${roleClass(row.role)}">${escapeHtml(row.role)}</span></td>
      <td>${escapeHtml(row.manager)}</td>
      <td>${escapeHtml(row.stats100)}</td>
      <td>${escapeHtml(row.stats200)}</td>
      <td>${escapeHtml(row.branch)}</td>
    </tr>
  `).join("");
}

function renderActivity(data) {
  if (!data.recentActivity.length) {
    els.activityList.innerHTML = '<div class="empty-state">No request activity found for the current dataset.</div>';
    return;
  }

  els.activityList.innerHTML = data.recentActivity.map((item) => `
    <div class="activity-item">
      <div class="activity-item-head">
        <div>
          <strong>${escapeHtml(item.actor)}</strong>
          <div class="muted">${escapeHtml(item.actorRole)} via ${escapeHtml(item.manager)}</div>
        </div>
        <span class="tag">${escapeHtml(String(item.packageType || "-"))}</span>
      </div>
      <p>
        Branch: <strong>${escapeHtml(item.branchOwner)}</strong> ${item.branchOwnerUsername ? `(${escapeHtml(item.branchOwnerUsername)})` : ""}<br>
        Access: <span class="status-inline ${accessClass(item.accessStatus)}">${escapeHtml(accessLabel(item.accessStatus))}</span><br>
        UID: <span class="mono">${escapeHtml(item.uid || "N/A")}</span><br>
        Likes Added: <strong>${formatNumber(item.likesAdded)}</strong><br>
        Time: ${escapeHtml(item.at || "N/A")}
      </p>
    </div>
  `).join("");
}

function renderMeta(data, sourceLabel) {
  els.generatedAt.textContent = data.generatedAt;
  els.activeMonth.textContent = data.month;
  els.dataStatusText.textContent = sourceLabel;
  els.quickInfoList.innerHTML = `
    <li>${formatNumber(data.summary.totalSuperAdmins)} super admin branches loaded</li>
    <li>${formatNumber(data.summary.activeSuperAdmins)} active access and ${formatNumber(data.summary.expiredSuperAdmins)} expired access</li>
    <li>${formatNumber(data.summary.onlineSuperAdmins)} online clients and ${formatNumber(data.summary.totalUidRequests)} recent requests</li>
    <li>${formatNumber(data.summary.totalAdmins)} admins and ${formatNumber(data.summary.totalUsers)} managed users across branches</li>
  `;
}

function renderAll(sourceLabel = "Demo mode") {
  if (!dashboardData) {
    dashboardData = normalizeData(demoData);
  }

  renderMeta(dashboardData, sourceLabel);
  renderStats(dashboardData);
  renderSuperAdminTable(dashboardData);
  renderSuperAdminCards(dashboardData);
  renderHierarchy(dashboardData);
  renderUsersTable(dashboardData, els.userSearchInput.value || "");
  renderActivity(dashboardData);
}

async function fetchDashboardFromServer() {
  const response = await fetch("/api/dashboard", {
    headers: { Accept: "application/json" },
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
  dashboardData = normalizeData(JSON.parse(text));
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
    alert("Could not import JSON. Please use a valid dashboard export.");
  } finally {
    event.target.value = "";
  }
});

async function initializeDashboard(ignoreSaved = false) {
  try {
    dashboardData = await fetchDashboardFromServer();
    saveData(dashboardData);
    renderAll("Live server data");
    return;
  } catch (error) {
    console.warn("Live dashboard fetch failed:", error);
  }

  const saved = ignoreSaved ? null : loadSavedData();
  const injected = tryLoadInjectedData();
  dashboardData = saved || injected || normalizeData(demoData);
  const source = saved ? "Saved local data" : (injected ? "Injected data" : "Demo fallback");
  renderAll(source);
}

initializeDashboard();
