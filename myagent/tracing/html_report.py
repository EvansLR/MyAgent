"""Generate local HTML trace inspection pages."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from myagent.tracing.inspect import (
    latest_context_event,
    latest_turn_summary,
    read_trace_events,
)


DEFAULT_REPORT_PATH = Path("data/traces/report.html")
DEFAULT_VIEWER_PATH = Path("data/traces/viewer.html")


def write_trace_report(
    output_path: str | Path = DEFAULT_REPORT_PATH,
    trace_root: str | Path = "data/traces",
    session_key: str = "cli:default",
) -> Path:
    """Write a static HTML report for common trace streams."""
    root = Path(trace_root)
    output = Path(output_path)
    events = read_trace_events(session_key, root)
    skill_events = read_trace_events("runtime:skills", root)
    startup_events = read_trace_events("runtime:startup", root)
    html = build_trace_report_html(
        events=events,
        skill_events=skill_events,
        startup_events=startup_events,
        session_key=session_key,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


def write_trace_viewer(output_path: str | Path = DEFAULT_VIEWER_PATH) -> Path:
    """Write an interactive local trace viewer HTML file."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_trace_viewer_html(), encoding="utf-8")
    return output


def build_trace_viewer_html() -> str:
    """Return a self-contained browser-side JSONL trace viewer."""
    return _TRACE_VIEWER_HTML


def build_trace_report_html(
    events: list[dict[str, Any]],
    skill_events: list[dict[str, Any]],
    startup_events: list[dict[str, Any]],
    session_key: str = "cli:default",
) -> str:
    """Return a self-contained trace report HTML document."""
    latest_context = latest_context_event(events)
    context = (latest_context or {}).get("data", {}).get("context", {})
    sections = context.get("sections") or []
    history = context.get("history") or {}
    summary = latest_turn_summary(events)
    recent_events = events[-40:]
    max_tokens = max([int(section.get("estimated_tokens") or 0) for section in sections] or [1])
    title = f"MyAgent Trace Report - {session_key}"
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{escape(title)}</title>",
            "<style>",
            _REPORT_CSS,
            "</style>",
            "</head>",
            "<body>",
            '<main class="shell">',
            '<section class="hero">',
            '<div class="hero-copy">',
            "<p>Local Runtime</p>",
            f"<h1>{escape(title)}</h1>",
            "<span>Context, skills, startup, and recent turn signals in one static report.</span>",
            "</div>",
            '<div class="signal-grid" aria-label="Trace metrics">',
            _metric("Events", len(events)),
            _metric("Skill Events", len(skill_events)),
            _metric("Startup Events", len(startup_events)),
            _metric("Context Tokens", context.get("estimated_tokens") or 0),
            "</div>",
            "</section>",
            '<section class="band summary-band">',
            "<h2>Latest Turn</h2>",
            _latest_turn_html(summary),
            "</section>",
            '<section class="band">',
            "<h2>Context Assembly</h2>",
            _context_overview_html(context, history),
            '<div class="section-table">',
            _section_header(),
            *[_section_row(section, max_tokens) for section in sections],
            "</div>",
            "</section>",
            '<section class="two-col">',
            '<div class="band">',
            "<h2>Skills</h2>",
            _event_list_html(skill_events[-20:], empty="No skill events found."),
            "</div>",
            '<div class="band">',
            "<h2>Startup</h2>",
            _event_list_html(startup_events[-20:], empty="No startup events found."),
            "</div>",
            "</section>",
            '<section class="band">',
            "<h2>Recent Session Events</h2>",
            _event_list_html(recent_events, empty="No session events found."),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _metric(label: str, value: object) -> str:
    return (
        '<div class="metric">'
        f"<strong>{escape(str(value))}</strong>"
        f"<span>{escape(label)}</span>"
        "</div>"
    )


def _latest_turn_html(summary: object | None) -> str:
    if summary is None:
        return '<p class="empty">No completed turn found.</p>'
    return (
        '<div class="turn-grid">'
        f"{_metric('Turn ID', getattr(summary, 'turn_id', ''))}"
        f"{_metric('Stop Reason', getattr(summary, 'stop_reason', '') or 'unknown')}"
        f"{_metric('Tool Calls', getattr(summary, 'tool_call_count', 0))}"
        f"{_metric('Warnings', getattr(summary, 'warning_count', 0))}"
        "</div>"
    )


def _context_overview_html(context: dict[str, Any], history: dict[str, Any]) -> str:
    warnings = context.get("warnings") or []
    warning_text = ", ".join(str(warning) for warning in warnings) if warnings else "none"
    history_text = f"{history.get('included_messages') or 0}/{history.get('total_messages') or 0}"
    return (
        '<div class="context-strip">'
        f"{_metric('Messages', context.get('message_count') or 0)}"
        f"{_metric('Estimated Tokens', context.get('estimated_tokens') or 0)}"
        f"{_metric('Total Chars', context.get('total_chars') or 0)}"
        f"{_metric('History', history_text)}"
        f"{_metric('Warnings', warning_text)}"
        "</div>"
    )


def _section_header() -> str:
    return (
        '<div class="section-row section-head">'
        "<span>Section</span><span>Tier</span><span>Source</span><span>Tokens</span><span>Size</span>"
        "</div>"
    )


def _section_row(section: dict[str, Any], max_tokens: int) -> str:
    tokens = int(section.get("estimated_tokens") or 0)
    width = min(max((tokens / max(max_tokens, 1)) * 100, 2), 100)
    included = "included" if section.get("included") else "dropped"
    return (
        '<div class="section-row">'
        f"<span><b>{escape(str(section.get('name') or ''))}</b><em>{included}</em></span>"
        f"<span>{escape(str(section.get('tier') or ''))}</span>"
        f"<span>{escape(str(section.get('source') or ''))}</span>"
        f"<span>{tokens}</span>"
        '<span class="bar-cell">'
        f'<i style="width:{width:.1f}%"></i>'
        f"<small>{int(section.get('chars') or 0)} chars</small>"
        "</span>"
        "</div>"
    )


def _event_list_html(events: list[dict[str, Any]], empty: str) -> str:
    if not events:
        return f'<p class="empty">{escape(empty)}</p>'
    return '<ol class="event-list">' + "".join(_event_item(event) for event in events) + "</ol>"


def _event_item(event: dict[str, Any]) -> str:
    data = event.get("data") or {}
    event_name = str(event.get("event") or "")
    preview = _preview_for_event(event_name, data)
    return (
        "<li>"
        f"<time>{escape(str(event.get('turn_id') or ''))}</time>"
        f"<strong>{escape(event_name)}</strong>"
        f"<span>{escape(preview)}</span>"
        "</li>"
    )


def _preview_for_event(event_name: str, data: dict[str, Any]) -> str:
    if event_name == "context_built":
        context = data.get("context") or {}
        return f"tokens={context.get('estimated_tokens') or 0}, messages={context.get('message_count') or 0}"
    if event_name == "llm_response":
        return f"tools={data.get('tool_names') or []}"
    if event_name in {"tool_call", "tool_result"}:
        return str(data.get("tool_name") or "")
    if event_name == "skill_loaded":
        return f"{data.get('skill_id') or ''} len={data.get('content_length') or 0}"
    if event_name == "active_skill_set":
        return f"{data.get('skill_id') or ''} scope={data.get('scope') or ''}"
    if event_name == "subagent_start":
        return f"{data.get('agent_type') or ''} skills={data.get('inherited_active_skills') or []}"
    if event_name == "mcp_server_registered":
        return (
            f"{data.get('server_name') or ''} {data.get('transport') or ''} "
            f"tools={data.get('tool_count') or 0}/{data.get('discovered_tool_count') or 0}"
        )
    if event_name == "turn_completed":
        return str(data.get("stop_reason") or "")
    return str(data.get("content_preview") or data.get("error") or "")


_REPORT_CSS = """
:root {
  --ink: #111314;
  --muted: #65706a;
  --paper: #f6f3ea;
  --panel: #fffdf5;
  --line: #d7d0bf;
  --green: #1f7a57;
  --red: #c94f3d;
  --gold: #d9a441;
  --coal: #202622;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    linear-gradient(90deg, rgba(32,38,34,.05) 1px, transparent 1px),
    linear-gradient(rgba(32,38,34,.05) 1px, transparent 1px),
    var(--paper);
  background-size: 32px 32px;
  color: var(--ink);
  font-family: "Aptos", "Segoe UI", sans-serif;
}
.shell { width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 56px; }
.hero {
  min-height: 240px;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(340px, .8fr);
  gap: 24px;
  align-items: stretch;
  border-bottom: 3px solid var(--coal);
  padding-bottom: 24px;
}
.hero-copy {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  background: var(--coal);
  color: var(--panel);
  padding: 28px;
}
.hero-copy p { margin: 0 0 12px; color: var(--gold); text-transform: uppercase; letter-spacing: .08em; }
.hero-copy h1 { margin: 0; font-size: clamp(34px, 6vw, 72px); line-height: .95; letter-spacing: 0; }
.hero-copy span { margin-top: 14px; color: #d6dbc9; font-size: 16px; max-width: 720px; }
.signal-grid, .turn-grid, .context-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}
.metric {
  min-height: 92px;
  border: 1px solid var(--line);
  background: var(--panel);
  padding: 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.metric strong { font-size: 26px; line-height: 1; overflow-wrap: anywhere; }
.metric span { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
.band { margin-top: 24px; border-top: 3px solid var(--coal); padding-top: 16px; }
h2 { margin: 0 0 14px; font-size: 22px; letter-spacing: 0; }
.section-table { border: 1px solid var(--line); background: var(--panel); }
.section-row {
  display: grid;
  grid-template-columns: 1.2fr .55fr 1fr .4fr 1.1fr;
  gap: 12px;
  align-items: center;
  min-height: 54px;
  padding: 10px 14px;
  border-top: 1px solid var(--line);
}
.section-row:first-child { border-top: 0; }
.section-head { min-height: 38px; background: #ebe4d1; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
.section-row b { display: block; font-weight: 800; }
.section-row em { display: block; margin-top: 3px; color: var(--green); font-style: normal; font-size: 12px; }
.bar-cell i { display: block; height: 10px; background: linear-gradient(90deg, var(--green), var(--gold)); }
.bar-cell small { display: block; color: var(--muted); margin-top: 5px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.event-list { list-style: none; padding: 0; margin: 0; border: 1px solid var(--line); background: var(--panel); }
.event-list li {
  display: grid;
  grid-template-columns: minmax(110px, .6fr) minmax(160px, .7fr) minmax(0, 1.7fr);
  gap: 12px;
  padding: 11px 14px;
  border-top: 1px solid var(--line);
}
.event-list li:first-child { border-top: 0; }
.event-list time { color: var(--muted); overflow-wrap: anywhere; }
.event-list strong { color: var(--coal); }
.event-list span { color: #39433d; overflow-wrap: anywhere; }
.empty { color: var(--muted); border: 1px dashed var(--line); padding: 18px; background: rgba(255,253,245,.68); }
@media (max-width: 820px) {
  .hero, .two-col { grid-template-columns: 1fr; }
  .section-row, .event-list li { grid-template-columns: 1fr; }
  .hero-copy h1 { font-size: 38px; }
}
"""


_TRACE_VIEWER_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MyAgent Trace Viewer</title>
<style>
:root {
  --ink: #161817;
  --muted: #66706b;
  --paper: #f2efe6;
  --panel: #fffdf7;
  --line: #d8d0be;
  --coal: #202622;
  --green: #207657;
  --gold: #d8a13f;
  --red: #b74d43;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    linear-gradient(90deg, rgba(32,38,34,.045) 1px, transparent 1px),
    linear-gradient(rgba(32,38,34,.045) 1px, transparent 1px),
    var(--paper);
  background-size: 28px 28px;
  color: var(--ink);
  font-family: "Aptos", "Segoe UI", sans-serif;
}
.shell { width: min(1240px, calc(100% - 28px)); margin: 0 auto; padding: 26px 0 48px; }
.top {
  min-height: 220px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, .55fr);
  gap: 18px;
  border-bottom: 3px solid var(--coal);
  padding-bottom: 18px;
}
.headline { background: var(--coal); color: var(--panel); padding: 24px; display: flex; flex-direction: column; justify-content: flex-end; }
.headline p { margin: 0 0 10px; color: var(--gold); text-transform: uppercase; letter-spacing: .08em; font-size: 12px; }
.headline h1 { margin: 0; font-size: clamp(38px, 6vw, 76px); line-height: .92; letter-spacing: 0; }
.headline span { color: #d6dbc9; max-width: 720px; margin-top: 14px; }
.loader { background: var(--panel); border: 1px solid var(--line); padding: 18px; display: flex; flex-direction: column; gap: 12px; }
.loader label { font-weight: 800; }
input[type=file] {
  width: 100%;
  border: 1px dashed var(--coal);
  background: #f9f6ed;
  padding: 16px;
}
.hint { color: var(--muted); font-size: 13px; line-height: 1.45; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 18px; }
.metric { background: var(--panel); border: 1px solid var(--line); min-height: 82px; padding: 14px; display: flex; flex-direction: column; justify-content: space-between; }
.metric strong { font-size: 28px; line-height: 1; overflow-wrap: anywhere; }
.metric span { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }
.tabs { display: flex; gap: 8px; flex-wrap: wrap; margin: 22px 0 12px; }
.tabs button {
  border: 1px solid var(--coal);
  background: transparent;
  color: var(--coal);
  padding: 9px 12px;
  font-weight: 800;
  cursor: pointer;
}
.tabs button.active { background: var(--coal); color: var(--panel); }
.panel { display: none; border-top: 3px solid var(--coal); padding-top: 16px; }
.panel.active { display: block; }
.band { background: rgba(255,253,247,.72); border: 1px solid var(--line); padding: 14px; margin-bottom: 16px; }
h2 { margin: 0 0 12px; font-size: 22px; letter-spacing: 0; }
.table { border: 1px solid var(--line); background: var(--panel); overflow: auto; }
.row { display: grid; grid-template-columns: 1.15fr .55fr .95fr .45fr 1.1fr; gap: 12px; align-items: center; min-height: 50px; padding: 10px 12px; border-top: 1px solid var(--line); }
.row:first-child { border-top: 0; }
.head { min-height: 36px; background: #e9e1ce; color: var(--muted); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
.row b { display: block; }
.row em { display: block; font-style: normal; color: var(--green); font-size: 12px; margin-top: 3px; }
.bar i { display: block; height: 9px; background: linear-gradient(90deg, var(--green), var(--gold)); }
.bar small { display: block; margin-top: 5px; color: var(--muted); }
.events { list-style: none; padding: 0; margin: 0; border: 1px solid var(--line); background: var(--panel); max-height: 620px; overflow: auto; }
.events li { display: grid; grid-template-columns: minmax(120px,.55fr) minmax(170px,.65fr) minmax(0,1.8fr); gap: 12px; padding: 10px 12px; border-top: 1px solid var(--line); }
.events li:first-child { border-top: 0; }
.events time { color: var(--muted); overflow-wrap: anywhere; }
.events strong { color: var(--coal); }
.events span { color: #3b443f; overflow-wrap: anywhere; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.empty { color: var(--muted); border: 1px dashed var(--line); padding: 16px; background: rgba(255,253,247,.65); }
.file-list { color: var(--muted); font-size: 13px; }
.raw pre { margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 1.5; }
@media (max-width: 880px) {
  .top, .two, .grid { grid-template-columns: 1fr; }
  .row, .events li { grid-template-columns: 1fr; }
  .headline h1 { font-size: 40px; }
}
</style>
</head>
<body>
<main class="shell">
  <section class="top">
    <div class="headline">
      <p>Local JSONL Inspector</p>
      <h1>MyAgent Trace Viewer</h1>
      <span>Select one or more saved trace JSONL files. Everything is parsed in your browser; no upload, no server.</span>
    </div>
    <div class="loader">
      <label for="files">Load trace files</label>
      <input id="files" type="file" multiple accept=".json,.jsonl,.txt">
      <div class="hint">Recommended: choose <b>cli_default.jsonl</b>, <b>runtime_skills.jsonl</b>, and <b>runtime_startup.jsonl</b> from <code>data/traces</code>.</div>
      <div id="fileList" class="file-list">No files loaded yet.</div>
    </div>
  </section>

  <section class="grid" aria-label="summary metrics">
    <div class="metric"><strong id="metricEvents">0</strong><span>Total Events</span></div>
    <div class="metric"><strong id="metricTurns">0</strong><span>Turns</span></div>
    <div class="metric"><strong id="metricContext">0</strong><span>Context Tokens</span></div>
    <div class="metric"><strong id="metricSkills">0</strong><span>Skill Events</span></div>
  </section>

  <nav class="tabs" aria-label="Trace views">
    <button class="active" data-tab="context">Context</button>
    <button data-tab="events">Events</button>
    <button data-tab="skills">Skills</button>
    <button data-tab="startup">Startup</button>
    <button data-tab="raw">Raw</button>
  </nav>

  <section id="context" class="panel active">
    <div class="band">
      <h2>Context Assembly</h2>
      <div id="contextSummary" class="grid"></div>
    </div>
    <div class="table" id="sectionsTable"></div>
  </section>

  <section id="events" class="panel">
    <div class="band"><h2>Session Events</h2><ol id="eventList" class="events"></ol></div>
  </section>

  <section id="skills" class="panel">
    <div class="band"><h2>Skill Runtime</h2><ol id="skillList" class="events"></ol></div>
  </section>

  <section id="startup" class="panel">
    <div class="band"><h2>Startup Runtime</h2><ol id="startupList" class="events"></ol></div>
  </section>

  <section id="raw" class="panel raw">
    <div class="band"><h2>Parsed JSON</h2><pre id="rawJson">[]</pre></div>
  </section>
</main>

<script>
const state = { events: [] };

document.querySelectorAll('.tabs button').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tabs button').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(item => item.classList.remove('active'));
    button.classList.add('active');
    document.getElementById(button.dataset.tab).classList.add('active');
  });
});

document.getElementById('files').addEventListener('change', async event => {
  const files = Array.from(event.target.files || []);
  const batches = await Promise.all(files.map(readTraceFile));
  state.events = batches.flat().sort((a, b) => String(a.timestamp || '').localeCompare(String(b.timestamp || '')));
  document.getElementById('fileList').textContent = files.length ? files.map(file => file.name).join(', ') : 'No files loaded yet.';
  render();
});

function readTraceFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => {
      const text = String(reader.result || '');
      const events = [];
      text.split(/\r?\n/).forEach((line, index) => {
        const trimmed = line.trim();
        if (!trimmed) return;
        try {
          const parsed = JSON.parse(trimmed);
          parsed.__file = file.name;
          events.push(parsed);
        } catch (error) {
          events.push({ event: 'parse_error', turn_id: file.name, data: { line: index + 1, error: String(error) }, __file: file.name });
        }
      });
      resolve(events);
    };
    reader.readAsText(file, 'utf-8');
  });
}

function render() {
  const events = state.events;
  const contextEvent = latest(events.filter(item => item.event === 'context_built'));
  const context = contextEvent?.data?.context || {};
  const sections = context.sections || [];
  const skillEvents = events.filter(item => ['skill_loaded', 'active_skill_set'].includes(item.event));
  const startupEvents = events.filter(item => String(item.session_key || '').includes('runtime:startup') || String(item.turn_id || '') === 'startup' || String(item.event || '').startsWith('mcp_'));
  const turnIds = new Set(events.map(item => item.turn_id).filter(Boolean));

  text('metricEvents', events.length);
  text('metricTurns', turnIds.size);
  text('metricContext', context.estimated_tokens || 0);
  text('metricSkills', skillEvents.length);

  renderContext(context, sections);
  renderEvents('eventList', events.filter(item => !['skill_loaded', 'active_skill_set'].includes(item.event)).slice(-200));
  renderEvents('skillList', skillEvents.slice(-100));
  renderEvents('startupList', startupEvents.slice(-100));
  document.getElementById('rawJson').textContent = JSON.stringify(events.slice(-80), null, 2);
}

function renderContext(context, sections) {
  const history = context.history || {};
  const warnings = context.warnings || [];
  document.getElementById('contextSummary').innerHTML = [
    metric('Messages', context.message_count || 0),
    metric('Estimated Tokens', context.estimated_tokens || 0),
    metric('Total Chars', context.total_chars || 0),
    metric('History', `${history.included_messages || 0}/${history.total_messages || 0}`),
    metric('Dropped', history.dropped_messages || 0),
    metric('Warnings', warnings.length ? warnings.join(', ') : 'none')
  ].join('');

  if (!sections.length) {
    document.getElementById('sectionsTable').innerHTML = '<p class="empty">No context_built event loaded.</p>';
    return;
  }
  const maxTokens = Math.max(...sections.map(section => Number(section.estimated_tokens || 0)), 1);
  const rows = sections.map(section => sectionRow(section, maxTokens)).join('');
  document.getElementById('sectionsTable').innerHTML = `
    <div class="row head"><span>Section</span><span>Tier</span><span>Source</span><span>Tokens</span><span>Size</span></div>
    ${rows}
  `;
}

function sectionRow(section, maxTokens) {
  const tokens = Number(section.estimated_tokens || 0);
  const width = Math.min(Math.max(tokens / maxTokens * 100, 2), 100);
  return `
    <div class="row">
      <span><b>${escapeHtml(section.name || '')}</b><em>${section.included ? 'included' : 'dropped'}</em></span>
      <span>${escapeHtml(section.tier || '')}</span>
      <span>${escapeHtml(section.source || '')}</span>
      <span>${tokens}</span>
      <span class="bar"><i style="width:${width}%"></i><small>${Number(section.chars || 0)} chars</small></span>
    </div>
  `;
}

function renderEvents(id, events) {
  const target = document.getElementById(id);
  if (!events.length) {
    target.innerHTML = '<li><span class="empty">No events loaded for this view.</span></li>';
    return;
  }
  target.innerHTML = events.map(event => `
    <li>
      <time>${escapeHtml(event.turn_id || event.__file || '')}</time>
      <strong>${escapeHtml(event.event || '')}</strong>
      <span>${escapeHtml(preview(event))}</span>
    </li>
  `).join('');
}

function preview(event) {
  const data = event.data || {};
  if (event.event === 'context_built') return `tokens=${data.context?.estimated_tokens || 0}, messages=${data.context?.message_count || 0}`;
  if (event.event === 'llm_response') return `tools=${JSON.stringify(data.tool_names || [])}`;
  if (['tool_call', 'tool_result'].includes(event.event)) return data.tool_name || '';
  if (event.event === 'skill_loaded') return `${data.skill_id || ''} len=${data.content_length || 0}`;
  if (event.event === 'active_skill_set') return `${data.skill_id || ''} scope=${data.scope || ''} reason=${data.reason || ''}`;
  if (event.event === 'subagent_start') return `${data.agent_type || ''} skills=${JSON.stringify(data.inherited_active_skills || [])}`;
  if (event.event === 'mcp_server_registered') return `${data.server_name || ''} ${data.transport || ''} tools=${data.tool_count || 0}/${data.discovered_tool_count || 0}`;
  if (event.event === 'parse_error') return `line=${data.line}, ${data.error}`;
  return data.content_preview || data.result_preview || data.stop_reason || data.error || event.__file || '';
}

function metric(label, value) {
  return `<div class="metric"><strong>${escapeHtml(String(value))}</strong><span>${escapeHtml(label)}</span></div>`;
}

function latest(items) {
  return items.length ? items[items.length - 1] : null;
}

function text(id, value) {
  document.getElementById(id).textContent = value;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[char]));
}

render();
</script>
</body>
</html>
"""
