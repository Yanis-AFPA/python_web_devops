// Global State
let calendar;
let quill;
let currentEventId = null;

// --- Helper Colors ---
async function updateTaskStatus(pageId, newStatus) {
    // Quick and dirty status update for Dashboard
    try {
        // 1. Fetch current to get other fields (required by PUT model if not partial)
        // Wait, our PUT requires all fields?
        // Let's check updateEventDate logic. It sends everything.
        // If we only send status, we might lose data if backend validation is strict on missing fields?
        // SQLModel with default=None and update logic usually merges.
        // But app logic in updateEventDate reconstructs the whole object.
        // Let's rely on a backend PATCH or just fetch-modify-save pattern if strict.
        // Given complexity, let's try a PATCH-like approach: fetching first.

        const getRes = await fetch(`/api/pages/${pageId}`);
        const currentData = await getRes.json();

        const payload = {
            title: currentData.title,
            content: currentData.content,
            start_time: currentData.start_time,
            end_time: currentData.end_time,
            category: currentData.category,
            priority: currentData.priority,
            assignee_id: currentData.assignee_id,
            status: newStatus // The change
        };

        const res = await fetch(`/api/pages/${pageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            // Visual feedback?
            // Maybe color change? Class manipulation is hard inline.
            // Reload dashboard metrics to reflect change
            initDashboard();
        } else {
            alert("Update failed.");
        }
    } catch (e) {
        console.error(e);
        alert("Network error");
    }
}

function getColorForStatus(status) {
    switch (status) {
        case 'todo': return '#6c757d'; // Gray
        case 'in_progress': return '#0d6efd'; // Blue
        case 'done': return '#198754'; // Green
        default: return '#3788d8';
    }
}

// --- Dashboard Functions ---

async function initDashboard() {
    try {
        const response = await fetch('/api/metrics');
        const data = await response.json();
        const role = data.role;
        const ctxData = data.context;

        // --- MEMBER ---
        if (role === 'member') {
            const stats = ctxData.my_stats || { todo: 0, in_progress: 0, done: 0 };

            // DOM Counters
            document.getElementById('stat-todo').innerText = stats.todo;
            document.getElementById('stat-inprogress').innerText = stats.in_progress;
            document.getElementById('stat-done').innerText = stats.done;

            // Simple Pie
            const ctx = document.getElementById('memberChart').getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['To Do', 'In Progress', 'Done'],
                    datasets: [{
                        data: [stats.todo, stats.in_progress, stats.done],
                        backgroundColor: ['#6c757d', '#0d6efd', '#198754'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { color: '#c9d1d9' } } }
                }
            });
        }

        // --- MANAGER ---
        else if (role === 'manager') {
            if (ctxData.error) {
                console.warn("Manager has no team.");
                return;
            }

            // Team Status Bar/Doughnut
            const teamStats = ctxData.team_stats;
            const ctxTeam = document.getElementById('teamStatusChart').getContext('2d');
            new Chart(ctxTeam, {
                type: 'bar', // or doughnut
                data: {
                    labels: ['To Do', 'In Progress', 'Done'],
                    datasets: [{
                        label: 'Tasks',
                        data: [teamStats.todo, teamStats.in_progress, teamStats.done],
                        backgroundColor: ['#6c757d', '#0d6efd', '#198754']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
                        x: { ticks: { color: '#8b949e' }, grid: { display: false } }
                    },
                    plugins: { legend: { display: false } }
                }
            });

            // Workload (Horizontal Bar)
            const workload = ctxData.workload; // {username: count}
            const workers = Object.keys(workload);
            const counts = Object.values(workload);

            const ctxWork = document.getElementById('workloadChart').getContext('2d');
            new Chart(ctxWork, {
                type: 'bar',
                indexAxis: 'y',
                data: {
                    labels: workers,
                    datasets: [{
                        label: 'Active Tasks',
                        data: counts,
                        backgroundColor: '#d29922'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { beginAtZero: true, ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
                        y: { ticks: { color: '#8b949e' }, grid: { display: false } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        // --- ADMIN ---
        else {
            const system = ctxData.system_stats;

            // Pages Chart
            const ctxPage = document.getElementById('adminPageChart').getContext('2d');
            new Chart(ctxPage, {
                type: 'line',
                data: {
                    labels: ['This Week'],
                    datasets: [{
                        label: 'New Pages',
                        data: [system.new_pages_week],
                        borderColor: '#238636',
                        backgroundColor: '#238636',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
                        x: { ticks: { color: '#8b949e' }, grid: { display: false } }
                    }
                }
            });

            // Cats
            const cats = system.categories;
            const ctxCat = document.getElementById('adminCatChart').getContext('2d');
            new Chart(ctxCat, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(cats),
                    datasets: [{
                        data: Object.values(cats),
                        backgroundColor: ['#8957e5', '#d29922', '#2da44e', '#a371f7'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { color: '#c9d1d9' } } }
                }
            });
        }

    } catch (e) {
        console.error("Error loading dashboard metrics:", e);
    }
}

// --- Global Users Cache for Assignee Dropdown ---
let usersCache = [];

async function loadUsersForDropdown() {
    try {
        const res = await fetch('/api/users');
        usersCache = await res.json();

        const sel = document.getElementById('pageAssignee');
        sel.innerHTML = '<option value="">-- Unassigned --</option>';

        const currentRole = window.currentUserRole;
        const currentId = window.currentUserId;
        const currentTeamId = window.currentTeamId; // Need to pass this from backend

        usersCache.forEach(u => {
            // FILTER LOGIC
            let shouldShow = true;

            if (currentRole === 'manager') {
                // Manager: Show Self + Team Members + Unassigned (maybe?)
                // Strict: Team Members only.
                // If u.team_id == currentTeamId
                if (currentTeamId) {
                    shouldShow = (u.team_id === currentTeamId);
                }
            } else if (currentRole === 'member') {
                // Member: Show Self only
                shouldShow = (u.id === currentId);
            }

            if (shouldShow || currentRole === 'admin') {
                const opt = document.createElement('option');
                opt.value = u.id;
                opt.innerText = u.username;
                sel.appendChild(opt);
            }
        });
    } catch (e) { console.error("Failed to load users for assignment", e); }
}

// --- Calendar Functions ---

function initCalendar() {
    loadUsersForDropdown(); // Load users first
    const calendarEl = document.getElementById('calendar');

    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'fr',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek'
        },
        editable: true, // Allow drag & drop
        selectable: true,
        events: '/api/pages', // Fetch events from API
        height: '100%',

        // Transform API data to matching colors of the theme
        eventDataTransform: function (eventData) {
            let assigneeName = "Unassigned";
            // Since we don't have user object joined in all list endpoint in standard call without depth, 
            // we rely on assignee_id. If we want names on calendar, backend should eager load or we map from cache.
            // For now, let's just use color codes for priority.

            return {
                id: eventData.id,
                title: eventData.title, // Add assignee prefix? e.g. "[Bob] Task"
                start: eventData.start_time,
                end: eventData.end_time || eventData.start_time,
                extendedProps: {
                    content: eventData.content,
                    category: eventData.category,
                    status: eventData.status,
                    author_id: eventData.author_id,
                    assignee_id: eventData.assignee_id,
                    priority: eventData.priority || 'medium'
                },
                backgroundColor: getColorForStatus(eventData.status || 'todo'),
                borderColor: getCategoryColor(eventData.category),
                textColor: '#ffffff'
            };
        },
        eventSourceSuccess: function (content, xhr) {
            console.log("Events fetched:", content);
            return content;
        },

        select: function (info) {
            // New Event
            openEditor({
                start: info.startStr,
                end: info.endStr
            });
        },

        eventClick: function (info) {
            // Existing Event
            openEditor(info.event, true);
        },

        eventDrop: async function (info) {
            await updateEventDate(info.event);
        },

        eventResize: async function (info) {
            await updateEventDate(info.event);
        }
    });

    calendar.render();
    initQuill();

    // Bind UI actions
    document.getElementById('closeEditor').addEventListener('click', closeEditor);
    document.getElementById('saveBtn').addEventListener('click', savePage);
    document.getElementById('deleteBtn').addEventListener('click', deletePage);

    // Auto-update tab title
    document.getElementById('pageTitle').addEventListener('input', (e) => {
        const val = e.target.value;
        document.getElementById('tabTitle').innerText = val ? val + ".md" : "untitled.md";
    });
}

function getCategoryColor(category) {
    switch (category) {
        case 'feature': return '#8957e5'; // Purple
        case 'bug': return '#d29922'; // Orange
        case 'devops': return '#2da44e'; // Green/Cyan
        case 'meeting': return '#a371f7'; // Lilac
        default: return '#58a6ff';
    }
}

function getPriorityColor(priority) {
    // Fill color based on priority
    switch (priority) {
        case 'critical': return '#b60205'; // Dark Red
        case 'high': return '#d29922';  // Orange/Gold
        case 'low': return '#21262d';   // Dark
        default: return '#30363d'; // Medium (Grey)
    }
}

async function updateEventDate(event) {
    const payload = {
        title: event.title,
        content: event.extendedProps.content || "",
        start_time: event.start,
        end_time: event.end, // might be null
        category: event.extendedProps.category || 'personal',
        status: event.extendedProps.status || 'draft',
        priority: event.extendedProps.priority || 'medium',
        assignee_id: event.extendedProps.assignee_id
    };

    // Re-format dates cause FC usage of Date objects
    // JSON.stringify handles generic ISO, but we need to be careful if API expects specific
    // SQLModel expects datetime, ISO is fine.

    try {
        const resp = await fetch(`/api/pages/${event.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) {
            alert("Update failed.");
            event.revert();
        }
    } catch (e) {
        console.error(e);
    }
}

// --- Editor Functions ---

function initQuill() {
    quill = new Quill('#editor-container', {
        modules: {
            toolbar: {
                container: '#toolbar-container',
                handlers: {
                    image: imageHandler
                }
            }
        },
        placeholder: '// Start documentation...',
        theme: 'snow'
    });
}

function imageHandler() {
    const input = document.createElement('input');
    input.setAttribute('type', 'file');
    input.setAttribute('accept', 'image/*');
    input.click();

    input.onchange = async () => {
        const file = input.files[0];
        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            // Insert image into editor
            const range = quill.getSelection();
            quill.insertEmbed(range.index, 'image', data.url);
        } catch (e) {
            console.error('Image upload failed', e);
        }
    };
}

function openEditor(data, isExisting = false) {
    const overlay = document.getElementById('editorOverlay');
    overlay.classList.remove('translate-x-full');

    // Reset Fields first to avoid stale data
    document.getElementById('saveBtn').style.display = 'block';
    document.getElementById('deleteBtn').style.display = 'none';

    if (isExisting) {
        // --- EXISTING EVENT ---
        currentEventId = data.id;
        document.getElementById('pageTitle').value = data.title;
        document.getElementById('tabTitle').innerText = data.title + ".md";

        // Pivot Fields
        document.getElementById('pageCategory').value = data.extendedProps.category || 'feature';
        document.getElementById('pagePriority').value = data.extendedProps.priority || 'medium';
        document.getElementById('pageAssignee').value = data.extendedProps.assignee_id || "";
        document.getElementById('pageStatus').value = data.extendedProps.status || 'todo';

        quill.root.innerHTML = data.extendedProps.content || "";

        // RBAC logic for existing
        const isMember = window.currentUserRole === 'member';
        const isAssignedToMe = (data.extendedProps.assignee_id === window.currentUserId);

        if (isMember) {
            // Member can only edit STATUS if assigned to them
            // All other fields read-only
            quill.disable();
            document.getElementById('pageTitle').disabled = true;
            document.getElementById('pageCategory').disabled = true;
            document.getElementById('pagePriority').disabled = true;
            document.getElementById('pageAssignee').disabled = true;

            if (isAssignedToMe) {
                document.getElementById('pageStatus').disabled = false;
                document.getElementById('saveBtn').style.display = 'block';
            } else {
                document.getElementById('pageStatus').disabled = true;
                document.getElementById('saveBtn').style.display = 'none'; // Cannot save anything
            }

            // Delete hidden for members
            document.getElementById('deleteBtn').style.display = 'none';
        } else {
            // Manager / Admin: Edit All
            quill.enable();
            document.getElementById('pageTitle').disabled = false;
            document.getElementById('pageCategory').disabled = false;
            document.getElementById('pagePriority').disabled = false;
            document.getElementById('pageAssignee').disabled = false;
            document.getElementById('pageStatus').disabled = false;
            document.getElementById('saveBtn').style.display = 'block';

            // Delete button logic
            document.getElementById('deleteBtn').style.display = 'inline-block';
        }

    } else {
        // --- NEW EVENT ---
        currentEventId = null;
        document.getElementById('pageTitle').value = "";
        document.getElementById('tabTitle').innerText = "untitled.md";
        document.getElementById('pageCategory').value = 'feature';
        document.getElementById('pagePriority').value = 'medium';
        document.getElementById('pageStatus').value = 'todo';
        quill.root.innerHTML = "";

        // Dates
        window.tempDates = { start: data.start, end: data.end };

        // RBAC logic for creation
        const isMember = window.currentUserRole === 'member';
        const assigneeSelect = document.getElementById('pageAssignee');

        quill.enable();
        document.getElementById('pageTitle').disabled = false;
        document.getElementById('pageCategory').disabled = false;
        document.getElementById('pagePriority').disabled = false;
        document.getElementById('pageStatus').disabled = false;

        if (isMember) {
            // Member creates -> Auto-assign to self, locked
            assigneeSelect.value = window.currentUserId;
            assigneeSelect.disabled = true;
        } else {
            // Manager/Admin -> Can assign to anyone (filtered by team if manager, handled by init)
            assigneeSelect.value = "";
            assigneeSelect.disabled = false;
        }
    }
}

function closeEditor() {
    document.getElementById('editorOverlay').classList.add('translate-x-full');
}

async function savePage() {
    const title = document.getElementById('pageTitle').value;
    const content = quill.root.innerHTML;
    const category = document.getElementById('pageCategory').value;
    const priority = document.getElementById('pagePriority').value;
    const status = document.getElementById('pageStatus').value;
    const assignee_id = document.getElementById('pageAssignee').value ? parseInt(document.getElementById('pageAssignee').value) : null;

    if (!title) {
        alert("Title Required");
        return;
    }

    const payload = {
        title, content, category, priority, assignee_id, status
    };

    let method = 'POST';
    let url = '/api/pages';

    if (currentEventId) {
        method = 'PUT';
        url = `/api/pages/${currentEventId}`;

        // Need to preserve dates if just editing content
        const eventObj = calendar.getEventById(currentEventId);
        payload.start_time = eventObj.start;
        payload.end_time = eventObj.end;
    } else {
        payload.start_time = window.tempDates.start;
        payload.end_time = window.tempDates.end;
    }

    try {
        const resp = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (resp.ok) {
            calendar.refetchEvents();
            showSaveStatus();
            setTimeout(closeEditor, 500); // Close after short delay for "Saved" check
        } else {
            const err = await resp.json();
            alert("Error: " + err.detail);
        }
    } catch (e) {
        console.error(e);
        alert("Erreur réseau: " + e.message);
    }
}

async function deletePage() {
    if (!currentEventId || !confirm("Confirm Deletion?")) return;

    try {
        const resp = await fetch(`/api/pages/${currentEventId}`, { method: 'DELETE' });
        if (resp.ok) {
            calendar.getEventById(currentEventId).remove();
            closeEditor();
        } else {
            alert("Impossible de supprimer.");
        }
    } catch (e) {
        console.error(e);
        alert("Erreur réseau: " + e.message);
    }
}

function showSaveStatus() {
    const el = document.getElementById('saveStatus');
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 2000);
}
