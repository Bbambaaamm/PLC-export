"""Read-only incident and BoxID lookup over the local observation archive."""
from datetime import datetime, timezone
import math
import sqlite3
import time

from flask import Blueprint, jsonify, render_template, request
from eventJournal import journal

history_blueprint = Blueprint("history", __name__)


def parse_filters():
    box = request.args.get("box_id", "").strip()
    if len(box) > 64:
        raise ValueError("BoxID je příliš dlouhé")
    def parse_time(name, default):
        value = request.args.get(name)
        if not value:
            return default
        # UI explicitly uses UTC, API accepts epoch or ISO8601 with timezone.
        try:
            result = float(value)
        except ValueError:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            result = date.timestamp()
        if not math.isfinite(result):
            raise ValueError("Neplatný čas")
        return result
    end = parse_time("until", time.time())
    start = parse_time("since", end - 86400)
    limit = int(request.args.get("limit", 200))
    if start > end or not 1 <= limit <= 200:
        raise ValueError("Neplatný interval nebo limit (1–200)")
    return dict(box_id=box, since=start, until=end, limit=limit)


@history_blueprint.route("/api/events")
def events_api():
    try:
        filters = parse_filters()
        events = journal.search(**filters)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except sqlite3.Error:
        return jsonify(error="Archiv není dostupný", archive=journal.health()), 503
    response = jsonify(events=events, archive=journal.health(), filters=filters,
                       completeness="observations_only", limit_reached=len(events) == filters["limit"])
    response.headers["Cache-Control"] = "no-store"
    return response


@history_blueprint.route("/history")
def history_page():
    events, error, status = [], None, 200
    try:
        events = journal.search(**parse_filters())
    except ValueError as exc:
        error, status = str(exc), 400
    except sqlite3.Error:
        error, status = "Archiv zatím není dostupný. Zkontrolujte stav zapisovacího vlákna.", 503
    for event in events:
        event["time_label"] = datetime.fromtimestamp(event["observed_at"], timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return render_template("history.html", events=events, error=error, health=journal.health(),
                           box_id=request.args.get("box_id", "")), status, {"Cache-Control": "no-store"}
