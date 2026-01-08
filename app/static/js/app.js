// Global State
let calendar;
let quill;
let currentEventId = null;

// --- Helper Colors ---
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

        // Pages per Week Chart
        const ctxPages = document.getElementById('pagesChart').getContext('2d');
        new Chart(ctxPages, {
            type: 'bar',
            data: {
                labels: ['Cette semaine'],
                datasets: [{
                    label: 'Commits (Pages)',
                    data: [data.new_pages_week],
                    backgroundColor: '#238636', // GitHub Green
                    borderColor: '#2ea043',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#8b949e', font: { family: "'JetBrains Mono'" } },
                        grid: { color: '#30363d' }
                    },
                    x: {
                        ticks: { color: '#8b949e', font: { family: "'JetBrains Mono'" } },
                        grid: { display: false }
                    }
                }
            }
        });

        // Categories Chart
        const ctxCat = document.getElementById('categoryChart').getContext('2d');
        const catLabels = Object.keys(data.categories);
        const catData = Object.values(data.categories);

        new Chart(ctxCat, {
            type: 'doughnut',
            data: {
                labels: catLabels,
                datasets: [{
                    data: catData,
                    // Colors: Info(Blue), Success(Green), Error(Red), Warning(Purple->Gold for project)
                    backgroundColor: ['#58a6ff', '#238636', '#da3633', '#d29922'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: { position: 'right', labels: { color: '#c9d1d9', font: { family: "'JetBrains Mono'" } } }
                }
            }
        });

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
        usersCache.forEach(u => {
            const opt = document.createElement('option');
            opt.value = u.id;
            opt.innerText = u.username;
            sel.appendChild(opt);
        });
    } catch (e) { console.error("Failed to load users for assignment"); }
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
        case 'meeting': return '#58a6ff'; // blue
        case 'project': return '#238636'; // green
        case 'incident': return '#da3633'; // red
        default: return '#30363d'; // grey (personal/other)
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

    if (isExisting) {
        currentEventId = data.id;
        document.getElementById('pageTitle').value = data.title;
        document.getElementById('tabTitle').innerText = data.title + ".md";
        document.getElementById('pageCategory').value = data.extendedProps.category;

        // Pivot Fields
        document.getElementById('pagePriority').value = data.extendedProps.priority || 'medium';
        document.getElementById('pageAssignee').value = data.extendedProps.assignee_id || "";
        document.getElementById('pageStatus').value = data.extendedProps.status || 'todo';

        // Load content
        // IMPORTANT: data.extendedProps.content might be stale if we didn't refetch. 
        // For production apps, fetch full details here. For MVP, we use the props from calendar load.
        // Assuming the calendar 'events' feed returns full content.
        quill.root.innerHTML = data.extendedProps.content || "";

        // RBAC Check for Delete button
        const canDelete = (window.currentUserRole === 'admin') || (window.currentUserRole === 'manager');

        document.getElementById('deleteBtn').style.display = canDelete ? 'inline-block' : 'none';

    } else {
        // New
        currentEventId = null;
        document.getElementById('pageTitle').value = "";
        document.getElementById('tabTitle').innerText = "untitled.md";
        document.getElementById('pagePriority').value = "medium";
        document.getElementById('pagePriority').value = "medium";
        document.getElementById('pageAssignee').value = "";
        document.getElementById('pageStatus').value = "todo";
        quill.root.innerHTML = "";

        // Temporary holding dates
        window.tempDates = { start: data.start, end: data.end };

        document.getElementById('deleteBtn').style.display = 'none';
    }

    // RBAC: Read-only logic
    const isMember = window.currentUserRole === 'member';

    if (isMember) {
        // Members can ONLY change status (if existing task)
        // If creating new task: they can edit everything. (Assuming they can create self-tasks)
        // Let's refine based on user request "ne voit que leur tache mais peuvent change le status"

        if (isExisting) {
            quill.disable();
            document.getElementById('pageTitle').disabled = true;
            document.getElementById('pageCategory').disabled = true;
            document.getElementById('pagePriority').disabled = true;
            document.getElementById('pageAssignee').disabled = true;
            // Status is ENABLED for Members
            document.getElementById('pageStatus').disabled = false;
        } else {
            // Creation mode: Enable all
            quill.enable();
            document.getElementById('pageTitle').disabled = false;
        }
        document.getElementById('saveBtn').style.display = 'block';
    } else {
        // Admin / Manager
        quill.enable();
        document.getElementById('pageTitle').disabled = false;
        document.getElementById('pageCategory').disabled = false;
        document.getElementById('pagePriority').disabled = false;
        document.getElementById('pageAssignee').disabled = false;
        document.getElementById('pageStatus').disabled = false;
        document.getElementById('saveBtn').style.display = 'block';
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
