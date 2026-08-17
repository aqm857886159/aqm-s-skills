#!/usr/bin/env python3
"""Render a weekly group-operations report from verified insight JSON.

The Skill (LLM) writes semantic judgments to an insights file following
references/insights-contract.md. This script verifies every cited evidence ID
against the actual export files, derives all times and quotes from the export
data (never from the model), and renders a fixed, self-contained HTML report.
Unknown evidence IDs abort the render: no citation, no claim.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WEEKDAYS = "一二三四五六日"
CATEGORY_LABELS = {"intent": "意向", "question": "提问", "risk": "风险"}


class RenderError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _fail(exc: RenderError) -> int:
    print(json.dumps({"status": "error", "error": {"code": exc.code, "message": exc.message, **exc.details}}, ensure_ascii=False))
    return 2


def _parse_offset(value: str) -> timezone:
    sign = 1 if value.startswith("+") else -1
    hours, _, minutes = value[1:].partition(":")
    return timezone(sign * timedelta(hours=int(hours), minutes=int(minutes or 0)))


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RenderError(f"unreadable_{label}", f"Could not read {label} file: {path.name} ({type(exc).__name__}).")


def _git_root_for(path: Path) -> Path | None:
    current = path.resolve().parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def fmt_time(dt: datetime, offset: timezone) -> str:
    local = dt.astimezone(offset)
    return f"{local.month}月{local.day}日 周{WEEKDAYS[local.weekday()]} {local:%H:%M}"


def fmt_day(dt: datetime, offset: timezone) -> str:
    local = dt.astimezone(offset)
    return f"{local.month}/{local.day}"


def build_evidence_map(exports: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for export in exports:
        group = (export.get("conversation") or {}).get("name", "unknown")
        messages = export.get("messages") or []
        for position, message in enumerate(messages):
            catalog[str(message.get("id"))] = {
                "group": group,
                "message": message,
                "position": position,
                "messages": messages,
            }
    return catalog


def collect_citations(insights: dict[str, Any]) -> list[str]:
    cited: list[str] = []
    for section in ("followups", "unansweredQuestions", "buyingSignals", "risks"):
        for item in insights.get(section) or []:
            cited.extend(str(eid) for eid in item.get("evidence") or [])
    return cited


def earliest_evidence(item: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> datetime | None:
    stamps = []
    for eid in item.get("evidence") or []:
        found = catalog.get(str(eid))
        if found:
            parsed = _parse_dt(found["message"].get("createdAt"))
            if parsed:
                stamps.append(parsed)
    return min(stamps) if stamps else None


def waiting_label(item: dict[str, Any], catalog: dict[str, dict[str, Any]], generated_at: datetime) -> str:
    first = earliest_evidence(item, catalog)
    if not first:
        return ""
    days = max(0, round((generated_at - first).total_seconds() / 86400))
    return "今天提出" if days == 0 else f"已等 {days} 天"


def evidence_html(evidence_ids: list[str], catalog: dict[str, dict[str, Any]], offset: timezone, accent: str) -> str:
    blocks: list[str] = []
    for eid in evidence_ids:
        found = catalog[str(eid)]
        message = found["message"]
        neighbors = found["messages"][max(0, found["position"] - 2): found["position"] + 3]
        context_rows = []
        for neighbor in neighbors:
            stamp = _parse_dt(neighbor.get("createdAt"))
            mark = " ctx-hit" if neighbor.get("id") == message.get("id") else ""
            context_rows.append(
                f'<div class="ctx-row{mark}"><span class="ctx-time">{esc(fmt_time(stamp, offset) if stamp else "—")}</span>'
                f'<span class="ctx-author">{esc(neighbor.get("author"))}</span>'
                f'<span class="ctx-text">{esc(neighbor.get("text"))}</span></div>'
            )
        stamp = _parse_dt(message.get("createdAt"))
        blocks.append(
            f'<figure class="evidence evidence-{accent}">'
            f'<blockquote>{esc(message.get("text"))}</blockquote>'
            f'<figcaption><span class="ev-who">{esc(message.get("author"))}</span>'
            f'<span class="ev-sep">·</span><span class="ev-time">{esc(fmt_time(stamp, offset) if stamp else "—")}</span>'
            f'<span class="ev-sep">·</span><span class="ev-group">{esc(found["group"])}</span>'
            f'<code class="ev-id">{esc(eid)}</code>'
            f'<button type="button" class="ctx-toggle" aria-expanded="false">上下文</button></figcaption>'
            f'<div class="ctx" hidden>{"".join(context_rows)}</div>'
            f"</figure>"
        )
    return "".join(blocks)


def sparkline_svg(per_day: list[dict[str, Any]], axis: list[date], global_max: int) -> str:
    counts = {entry["date"]: entry["count"] for entry in per_day}
    width_step, chart_height = 22, 40
    width = width_step * len(axis)
    bars: list[str] = []
    for column, day in enumerate(axis):
        count = counts.get(day.isoformat(), 0)
        bar_height = 0 if global_max == 0 else round(count / global_max * (chart_height - 4))
        bar_height = max(2, bar_height) if count else 1
        x = column * width_step + 4
        y = chart_height - bar_height
        shade = "#0E7A45" if count == max(counts.values(), default=0) and count else "#9CC9AE"
        bars.append(
            f'<rect x="{x}" y="{y}" width="{width_step - 8}" height="{bar_height}" rx="1.5" fill="{shade}">'
            f"<title>{day.month}/{day.day}：{count} 条</title></rect>"
        )
        bars.append(
            f'<text x="{x + (width_step - 8) / 2}" y="{chart_height + 11}" text-anchor="middle" class="axis">{WEEKDAYS[day.weekday()]}</text>'
        )
    return (
        f'<svg class="spark" viewBox="0 0 {width} {chart_height + 14}" width="{width}" height="{chart_height + 14}" '
        f'role="img" aria-label="每日消息量">{"".join(bars)}</svg>'
    )


CSS = """
:root {
  --paper: #FDFDFB; --ink: #1F2823; --muted: #66716A; --line: #E3E6E1; --soft: #F4F6F3;
  --green: #0E7A45; --green-bright: #07C160; --green-bg: #EDF6F0;
  --amber: #A9741B; --amber-bg: #FBF4E4;
  --red: #B8402C; --red-bg: #F9EDE9;
  --serif: "Noto Serif SC", "Songti SC", "STSong", serif;
  --sans: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  --mono: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font-family: var(--sans); font-size: 15px; line-height: 1.7;
  -webkit-font-smoothing: antialiased;
}
.sheet { max-width: 860px; margin: 0 auto; padding: 40px 48px 64px; }
a { color: var(--green); }
button { font-family: var(--sans); }
:focus-visible { outline: 2px solid var(--green); outline-offset: 2px; }

/* ---- masthead ---- */
.mast-top { display: flex; justify-content: space-between; align-items: baseline; gap: 16px;
  font-size: 12.5px; color: var(--muted); letter-spacing: .04em; }
.mast-top .shop { font-weight: 600; color: var(--ink); }
.badge-local { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
.badge-local::before { content: ""; width: 7px; height: 7px; border-radius: 50%;
  background: var(--green-bright); box-shadow: 0 0 0 3px var(--green-bg); }
h1 { font-family: var(--serif); font-weight: 900; font-size: 42px; letter-spacing: .06em;
  margin: 18px 0 4px; }
.mast-sub { display: flex; justify-content: space-between; align-items: baseline; gap: 16px;
  color: var(--muted); font-size: 13.5px; }
.mast-sub .period { font-family: var(--mono); letter-spacing: .02em; }
.rule-double { border: 0; border-top: 3px solid var(--ink); margin: 18px 0 0; }
.rule-double + hr { border: 0; border-top: 1px solid var(--ink); margin: 3px 0 0; }

/* ---- headline ---- */
.headline { margin: 34px 0 0; }
.eyebrow { font-size: 12px; letter-spacing: .18em; color: var(--muted); margin-bottom: 8px; }
.eyebrow b { color: var(--green); font-weight: 600; }
.headline p { font-family: var(--serif); font-size: 21px; line-height: 1.75; margin: 0;
  font-weight: 600; }

/* ---- KPI ---- */
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); margin: 34px 0 0;
  border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.kpi { padding: 18px 18px 16px; border-left: 1px solid var(--line); }
.kpi:first-child { border-left: 0; padding-left: 0; }
.kpi .num { font-family: var(--serif); font-size: 40px; font-weight: 900; line-height: 1;
  font-variant-numeric: tabular-nums; }
.kpi .lbl { font-size: 13.5px; font-weight: 600; margin-top: 6px; }
.kpi .note { font-size: 12px; color: var(--muted); margin-top: 2px; }
.kpi-amber .num { color: var(--amber); } .kpi-green .num { color: var(--green); }
.kpi-red .num { color: var(--red); } .kpi-ink .num { color: var(--ink); }

/* ---- sections ---- */
section { margin-top: 44px; }
.sec-head { display: flex; align-items: baseline; gap: 10px; border-bottom: 1px solid var(--line);
  padding-bottom: 8px; margin-bottom: 4px; }
.sec-no { font-family: var(--serif); font-size: 13px; color: var(--muted); letter-spacing: .1em; }
.sec-head h2 { font-family: var(--serif); font-size: 20px; font-weight: 900; margin: 0; letter-spacing: .04em; }
.sec-head .count { margin-left: auto; font-family: var(--mono); font-size: 12.5px; color: var(--muted); }
.sec-mark { width: 9px; height: 9px; border-radius: 2px; align-self: center; }
.mark-amber { background: var(--amber); } .mark-green { background: var(--green); } .mark-red { background: var(--red); }

/* ---- followup cards ---- */
.card { display: grid; grid-template-columns: 44px 1fr; gap: 0 16px;
  padding: 22px 0 24px; border-bottom: 1px solid var(--line); }
.card:last-child { border-bottom: 0; }
.card .rank { font-family: var(--serif); font-size: 30px; font-weight: 900; color: #B9C2BA;
  line-height: 1.15; text-align: center; }
.card.is-done { opacity: .45; }
.card.is-done .card-title { text-decoration: line-through; }
.card-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.card-title { font-size: 16.5px; font-weight: 700; }
.chip { font-size: 11.5px; font-weight: 600; padding: 1.5px 8px; border-radius: 100px; white-space: nowrap; }
.chip-intent { color: var(--green); background: var(--green-bg); }
.chip-question { color: var(--amber); background: var(--amber-bg); }
.chip-risk { color: var(--red); background: var(--red-bg); }
.chip-wait { font-family: var(--mono); font-size: 11.5px; color: var(--muted);
  border: 1px solid var(--line); padding: 1px 7px; border-radius: 100px; white-space: nowrap; }
.done-toggle { margin-left: auto; display: inline-flex; align-items: center; gap: 6px;
  font-size: 12.5px; color: var(--muted); cursor: pointer; user-select: none; white-space: nowrap; }
.card-meta { font-size: 13px; color: var(--muted); margin-top: 2px; }
.card-meta b { color: var(--ink); font-weight: 600; }
.card-reason { margin: 8px 0 0; }

/* ---- evidence ---- */
.evidence { margin: 12px 0 0; padding: 10px 14px 9px; border-left: 3px solid var(--line);
  background: var(--soft); border-radius: 0 6px 6px 0; }
.evidence-amber { border-left-color: var(--amber); }
.evidence-green { border-left-color: var(--green); }
.evidence-red { border-left-color: var(--red); }
.evidence blockquote { margin: 0; font-size: 14px; white-space: pre-line; }
.evidence blockquote::before { content: "“"; color: var(--muted); }
.evidence blockquote::after { content: "”"; color: var(--muted); }
.evidence figcaption { display: flex; align-items: center; gap: 7px; flex-wrap: wrap;
  margin-top: 6px; font-size: 12px; color: var(--muted); }
.ev-who { font-weight: 600; color: var(--ink); }
.ev-time, .ev-id { font-family: var(--mono); }
.ev-id { font-size: 10.5px; opacity: .55; }
.ev-sep { opacity: .5; }
.ctx-toggle { margin-left: auto; border: 0; background: none; color: var(--green);
  font-size: 12px; cursor: pointer; padding: 0; }
.ctx { margin-top: 8px; border-top: 1px dashed var(--line); padding-top: 8px; }
.ctx-row { display: flex; gap: 8px; font-size: 12.5px; padding: 2.5px 6px; border-radius: 4px; }
.ctx-row.ctx-hit { background: rgba(7,193,96,.10); }
.ctx-time { font-family: var(--mono); color: var(--muted); white-space: nowrap; font-size: 11px; padding-top: 2px; }
.ctx-author { font-weight: 600; white-space: nowrap; }
.ctx-text { color: var(--ink); white-space: pre-line; overflow-wrap: anywhere; }

/* ---- suggested reply ---- */
.reply { display: flex; gap: 12px; align-items: flex-start; margin-top: 12px;
  padding: 12px 14px; background: var(--green-bg); border-radius: 8px; }
.reply .r-label { font-size: 11.5px; font-weight: 600; color: var(--green); white-space: nowrap;
  letter-spacing: .08em; padding-top: 2px; }
.reply .r-text { flex: 1; font-size: 14px; }
.copy-btn { border: 1px solid rgba(14,122,69,.35); color: var(--green); background: #fff;
  font-size: 12.5px; padding: 4px 12px; border-radius: 6px; cursor: pointer; white-space: nowrap; }
.copy-btn:hover { background: var(--green); color: #fff; }
.copy-btn.copied { background: var(--green); color: #fff; }

/* ---- list rows ---- */
.rows { margin: 0; }
.row { display: grid; grid-template-columns: 1fr auto; gap: 2px 14px; padding: 13px 0 14px;
  border-bottom: 1px solid var(--line); }
.row:last-child { border-bottom: 0; }
.row-main { font-size: 14.5px; }
.row-main b { font-weight: 700; }
.row-meta { font-size: 12.5px; color: var(--muted); }
.row-side { text-align: right; align-self: start; }
.row .evidence { grid-column: 1 / -1; }
.row-empty { padding: 14px 16px; background: var(--soft); border-radius: 8px;
  color: var(--muted); font-size: 13.5px; }
.sev { font-size: 11.5px; font-weight: 600; padding: 1.5px 8px; border-radius: 100px; }
.sev-high { color: var(--red); background: var(--red-bg); }
.sev-low { color: var(--muted); background: var(--soft); }
.sev-medium { color: var(--amber); background: var(--amber-bg); }
.estimate { font-family: var(--mono); font-size: 12px; color: var(--green); white-space: nowrap; }

/* ---- groups ---- */
.group-row { display: grid; grid-template-columns: 1fr auto; gap: 4px 20px;
  padding: 15px 0; border-bottom: 1px solid var(--line); align-items: center; }
.group-row:last-child { border-bottom: 0; }
.group-name { font-weight: 700; font-size: 15px; }
.group-stats { font-size: 12.5px; color: var(--muted); font-variant-numeric: tabular-nums; }
.group-note { grid-column: 1; font-size: 13.5px; color: var(--ink); margin: 0; }
.spark { grid-column: 2; grid-row: 1 / span 2; align-self: center; }
.spark .axis { font-size: 8.5px; fill: var(--muted); font-family: var(--sans); }

/* ---- coverage ---- */
.coverage { background: var(--soft); border-radius: 10px; padding: 20px 24px; font-size: 13.5px; }
.coverage dl { display: grid; grid-template-columns: 108px 1fr; gap: 5px 16px; margin: 0; }
.coverage dt { color: var(--muted); }
.coverage dd { margin: 0; }
.coverage ul { margin: 4px 0 0; padding-left: 18px; }
.coverage li { margin-top: 3px; }

/* ---- footer ---- */
footer { margin-top: 44px; border-top: 1px solid var(--line); padding-top: 14px;
  display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap;
  font-size: 12.5px; color: var(--muted); }
.ev-check { display: inline-flex; align-items: center; gap: 6px; }
.ev-check::before { content: "✓"; color: var(--green); font-weight: 700; }

@media (max-width: 700px) {
  .sheet { padding: 24px 20px 48px; }
  h1 { font-size: 30px; }
  .kpis { grid-template-columns: 1fr 1fr; }
  .kpi { padding: 14px; border-top: 1px solid var(--line); }
  .kpi:nth-child(-n+2) { border-top: 0; }
  .kpi:nth-child(odd) { border-left: 0; padding-left: 0; }
  .card { grid-template-columns: 1fr; }
  .card .rank { display: none; }
}
@media print {
  .ctx-toggle, .copy-btn, .done-toggle { display: none !important; }
  .sheet { max-width: none; padding: 0; }
  body { font-size: 12.5px; }
  section, .card { break-inside: avoid; }
}
@media (prefers-reduced-motion: no-preference) {
  .copy-btn { transition: background .15s ease, color .15s ease; }
}
"""

JS = """
document.addEventListener('click', function (event) {
  var toggle = event.target.closest('.ctx-toggle');
  if (toggle) {
    var ctx = toggle.closest('.evidence').querySelector('.ctx');
    var open = ctx.hasAttribute('hidden');
    if (open) { ctx.removeAttribute('hidden'); } else { ctx.setAttribute('hidden', ''); }
    toggle.setAttribute('aria-expanded', String(open));
    toggle.textContent = open ? '收起' : '上下文';
    return;
  }
  var copy = event.target.closest('.copy-btn');
  if (copy) {
    var text = copy.getAttribute('data-copy') || '';
    var done = function () {
      copy.classList.add('copied');
      copy.textContent = '已复制';
      setTimeout(function () { copy.classList.remove('copied'); copy.textContent = '复制话术'; }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done);
    } else {
      var area = document.createElement('textarea');
      area.value = text; document.body.appendChild(area); area.select();
      try { document.execCommand('copy'); } catch (ignored) {}
      document.body.removeChild(area); done();
    }
  }
});
var reportKey = document.body.getAttribute('data-report-key') || 'wechat-weekly';
document.querySelectorAll('.done-toggle input').forEach(function (box) {
  var key = reportKey + ':' + box.getAttribute('data-key');
  var saved = null;
  try { saved = localStorage.getItem(key); } catch (ignored) {}
  if (saved === '1') { box.checked = true; box.closest('.card').classList.add('is-done'); }
  box.addEventListener('change', function () {
    box.closest('.card').classList.toggle('is-done', box.checked);
    try { localStorage.setItem(key, box.checked ? '1' : '0'); } catch (ignored) {}
  });
});
"""


def render(insights: dict[str, Any], stats: dict[str, Any], catalog: dict[str, dict[str, Any]],
           offset: timezone, generated_at: datetime, evidence_total: int) -> str:
    period = insights.get("period") or {}
    followups = insights.get("followups") or []
    unanswered = insights.get("unansweredQuestions") or []
    signals = insights.get("buyingSignals") or []
    risks = insights.get("risks") or []
    totals = stats.get("totals") or {}
    group_notes = {entry.get("group"): entry.get("note") for entry in insights.get("groupNotes") or []}

    waits = [waiting_label(item, catalog, generated_at) for item in unanswered]
    wait_days = [int(w.split(" ")[1]) for w in waits if w.startswith("已等")]
    unanswered_note = f"最久已等 {max(wait_days)} 天" if wait_days else "本周提出"
    high_risks = sum(1 for risk in risks if risk.get("severity") == "high")
    risk_note = f"{high_risks} 条未处理" if high_risks else "均已处理"
    estimated = sum(1 for signal in signals if signal.get("estimate"))
    signal_note = f"{estimated} 条备注了金额" if estimated else "按证据时间排列"

    followup_cards: list[str] = []
    for rank, item in enumerate(followups, start=1):
        category = str(item.get("category") or "question")
        accent = {"intent": "green", "risk": "red"}.get(category, "amber")
        wait = waiting_label(item, catalog, generated_at)
        reply = str(item.get("suggestedReply") or "")
        reply_html = (
            f'<div class="reply"><span class="r-label">建议回复</span>'
            f'<span class="r-text">{esc(reply)}</span>'
            f'<button type="button" class="copy-btn" data-copy="{esc(reply)}">复制话术</button></div>'
            if reply else ""
        )
        followup_cards.append(
            f'<article class="card">'
            f'<div class="rank">{rank}</div>'
            f"<div>"
            f'<div class="card-head"><span class="card-title">{esc(item.get("title"))}</span>'
            f'<span class="chip chip-{esc(category)}">{CATEGORY_LABELS.get(category, esc(category))}</span>'
            + (f'<span class="chip-wait">{esc(wait)}</span>' if wait else "")
            + f'<label class="done-toggle"><input type="checkbox" data-key="followup-{rank}">已跟进</label></div>'
            f'<div class="card-meta"><b>{esc(item.get("who"))}</b> · {esc(item.get("group"))}</div>'
            f'<p class="card-reason">{esc(item.get("reason"))}</p>'
            f'{evidence_html([str(e) for e in item.get("evidence") or []], catalog, offset, accent)}'
            f"{reply_html}"
            f"</div></article>"
        )

    def list_rows(items: list[dict[str, Any]], accent: str, side: str, empty: str = "本周没有相关记录。") -> str:
        if not items:
            return f'<div class="row-empty">{esc(empty)}</div>'
        rows: list[str] = []
        for item in items:
            if side == "wait":
                label = waiting_label(item, catalog, generated_at)
                side_html = f'<span class="chip-wait">{esc(label)}</span>' if label else ""
            elif side == "estimate":
                side_html = f'<span class="estimate">{esc(item.get("estimate"))}</span>' if item.get("estimate") else ""
            else:
                severity = str(item.get("severity") or "medium")
                side_html = f'<span class="sev sev-{esc(severity)}">{ {"high": "高", "medium": "中", "low": "低"}.get(severity, esc(severity)) }风险 · {esc(item.get("status"))}</span>'
            rows.append(
                f'<div class="row">'
                f'<div><div class="row-main"><b>{esc(item.get("who"))}</b>　{esc(item.get("summary"))}</div>'
                f'<div class="row-meta">{esc(item.get("group"))}</div></div>'
                f'<div class="row-side">{side_html}</div>'
                f'{evidence_html([str(e) for e in item.get("evidence") or []], catalog, offset, accent)}'
                f"</div>"
            )
        return "".join(rows)

    axis: list[date] = []
    date_range = totals.get("dateRange") or {}
    first_day, last_day = date_range.get("first"), date_range.get("last")
    if first_day and last_day:
        cursor, end = date.fromisoformat(first_day), date.fromisoformat(last_day)
        while cursor <= end and len(axis) <= 31:
            axis.append(cursor)
            cursor += timedelta(days=1)
    global_max = max((entry["count"] for group in stats.get("groups") or [] for entry in group.get("perDay") or []), default=0)

    group_rows: list[str] = []
    for group in stats.get("groups") or []:
        note = group_notes.get(group.get("group"), "")
        group_rows.append(
            f'<div class="group-row">'
            f'<div><span class="group-name">{esc(group.get("group"))}</span>　'
            f'<span class="group-stats">{group.get("messageCount")} 条 · {group.get("participantCount")} 人参与 · {group.get("questionLikeCount")} 条疑问句</span></div>'
            f'{sparkline_svg(group.get("perDay") or [], axis, global_max) if axis else ""}'
            + (f'<p class="group-note">{esc(note)}</p>' if note else "")
            + "</div>"
        )

    truncation = "有截断，见下方说明" if totals.get("anyTruncated") else "无截断"
    decode_failures = totals.get("decodeFailures") or 0
    gaps = insights.get("gaps") or []
    gaps_html = "".join(f"<li>{esc(gap)}</li>" for gap in gaps)
    headline = esc(insights.get("headline"))

    generated_local = generated_at.astimezone(offset)
    generated_label = f"{generated_local.year}年{generated_local.month}月{generated_local.day}日 {generated_local:%H:%M}"
    report_key = f"{period.get('since', '')}~{period.get('until', '')}"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>客户群经营周报 · {esc(period.get("label"))}</title>
<style>{CSS}</style>
</head>
<body data-report-key="{esc(report_key)}">
<div class="sheet">

<header>
  <div class="mast-top">
    <span class="shop">{esc(insights.get("merchant") or "我的店铺")}</span>
    <span class="badge-local">本地生成 · 数据未离开这台电脑</span>
  </div>
  <h1>客户群经营周报</h1>
  <div class="mast-sub">
    <span>覆盖 {totals.get("groupCount", 0)} 个群 · {totals.get("messageCount", 0)} 条消息</span>
    <span class="period">{esc(period.get("label"))}</span>
  </div>
  <hr class="rule-double"><hr>
</header>

<div class="headline">
  <div class="eyebrow"><b>壹</b> ｜ 本周结论</div>
  <p>{headline}</p>
</div>

<div class="kpis">
  <div class="kpi kpi-amber"><div class="num">{len(unanswered)}</div><div class="lbl">未回复的客户提问</div><div class="note">{esc(unanswered_note)}</div></div>
  <div class="kpi kpi-green"><div class="num">{len(signals)}</div><div class="lbl">购买意向线索</div><div class="note">{esc(signal_note)}</div></div>
  <div class="kpi kpi-red"><div class="num">{len(risks)}</div><div class="lbl">风险与投诉</div><div class="note">{esc(risk_note)}</div></div>
  <div class="kpi kpi-ink"><div class="num">{len(followups)}</div><div class="lbl">建议今天跟进</div><div class="note">每条附建议话术</div></div>
</div>

<section>
  <div class="sec-head"><span class="sec-no">贰</span><h2>本周最该做的 {len(followups)} 件事</h2><span class="count">按优先级排列</span></div>
  {"".join(followup_cards)}
</section>

<section>
  <div class="sec-head"><span class="sec-mark mark-amber"></span><span class="sec-no">叁</span><h2>没人回复的客户提问</h2><span class="count">{len(unanswered)} 条</span></div>
  <div class="rows">{list_rows(unanswered, "amber", "wait", "本周没有无人回复的客户提问 —— 群里的问题都接住了。")}</div>
</section>

<section>
  <div class="sec-head"><span class="sec-mark mark-green"></span><span class="sec-no">肆</span><h2>购买意向线索</h2><span class="count">{len(signals)} 条</span></div>
  <div class="rows">{list_rows(signals, "green", "estimate", "本周群聊里没有可识别的购买意向 —— 若订单走群外渠道（小程序 / 私聊），这里自然为空。")}</div>
</section>

<section>
  <div class="sec-head"><span class="sec-mark mark-red"></span><span class="sec-no">伍</span><h2>风险与投诉</h2><span class="count">{len(risks)} 条</span></div>
  <div class="rows">{list_rows(risks, "red", "severity", "本周没有发现风险或投诉。")}</div>
</section>

<section>
  <div class="sec-head"><span class="sec-no">陆</span><h2>群活跃概览</h2><span class="count">周{WEEKDAYS[axis[0].weekday()] if axis else ""} — 周{WEEKDAYS[axis[-1].weekday()] if axis else ""}</span></div>
  {"".join(group_rows)}
</section>

<section>
  <div class="sec-head"><span class="sec-no">柒</span><h2>数据范围与边界</h2></div>
  <div class="coverage">
    <dl>
      <dt>数据来源</dt><dd>本机微信群聊导出（只读），共 {totals.get("groupCount", 0)} 个群、{totals.get("messageCount", 0)} 条消息</dd>
      <dt>完整性</dt><dd>{truncation}；解码失败 {decode_failures} 条</dd>
      <dt>隐私</dt><dd>报告在本机生成，聊天数据与报告均未上传；发送与跟进由你决定</dd>
      <dt>盲区</dt><dd><ul>{gaps_html}</ul></dd>
    </dl>
  </div>
</section>

<footer>
  <span class="ev-check">证据校验 {evidence_total}/{evidence_total} 通过 — 每条结论都能点开群里的原话</span>
  <span>生成于 {esc(generated_label)} · wechat-group-insights · <a href="https://github.com/aqm857886159/aqm-s-skills">开源</a></span>
</footer>

</div>
<script>{JS}</script>
</body>
</html>
"""


def write_private_html(path: Path, content: str, force: bool, allow_inside_git: bool) -> Path:
    destination = path.expanduser().resolve()
    if _git_root_for(destination) and not allow_inside_git:
        raise RenderError("unsafe_output", "Refusing to write a report derived from chat records inside a Git worktree. Choose a private path, or pass --allow-inside-git only for synthetic demo data.")
    if destination.exists() and not force:
        raise RenderError("output_exists", "The output file exists. Use --force to replace it explicitly.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(content)
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the weekly group report from verified insights.")
    parser.add_argument("--insights", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--exports", required=True, nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timezone", default="+08:00")
    parser.add_argument("--generated-at", help="ISO timestamp override for reproducible output")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-inside-git", action="store_true", help="Only for synthetic demo fixtures")
    args = parser.parse_args(argv)

    try:
        offset = _parse_offset(args.timezone)
        insights = _load_json(args.insights, "insights")
        stats = _load_json(args.stats, "stats")
        exports = [_load_json(path, "export") for path in args.exports]
        if insights.get("schemaVersion") != 1:
            raise RenderError("unsupported_insights_schema", "insights schemaVersion must be 1.")
        for export in exports:
            if export.get("source") != "wechat-local":
                raise RenderError("not_an_export", "Every --exports file must be a wechat-chat-export JSON.")

        catalog = build_evidence_map(exports)
        cited = collect_citations(insights)
        if not cited:
            raise RenderError("no_evidence", "The insights file cites no evidence IDs; refusing to render an unverifiable report.")
        unknown = sorted({eid for eid in cited if eid not in catalog})
        if unknown:
            raise RenderError("unknown_evidence", "Insights cite evidence IDs that do not exist in the exports. Remove or fix these claims.", {"unknownIds": unknown[:20], "unknownCount": len(unknown)})

        generated_at = _parse_dt(args.generated_at) if args.generated_at else datetime.now(timezone.utc)
        if generated_at is None:
            raise RenderError("invalid_generated_at", "--generated-at must be an ISO 8601 timestamp.")

        content = render(insights, stats, catalog, offset, generated_at, len(cited))
        destination = write_private_html(args.output, content, args.force, args.allow_inside_git)
        print(json.dumps({
            "status": "ok",
            "output": str(destination),
            "evidenceCited": len(cited),
            "evidenceVerified": len(cited),
            "followups": len(insights.get("followups") or []),
            "unansweredQuestions": len(insights.get("unansweredQuestions") or []),
            "buyingSignals": len(insights.get("buyingSignals") or []),
            "risks": len(insights.get("risks") or []),
        }, ensure_ascii=False))
        return 0
    except RenderError as exc:
        return _fail(exc)
    except OSError as exc:
        return _fail(RenderError("render_failed", f"Report rendering failed: {type(exc).__name__}."))


if __name__ == "__main__":
    raise SystemExit(main())
