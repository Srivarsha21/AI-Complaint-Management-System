from datetime import date

import pytest

from tests import analytics_fixtures
from tests.conftest import auth_header, login, make_user

SUMMARY = "/api/v1/dashboard/summary"
ANALYTICS = "/api/v1/dashboard/analytics"
OCTOBER = {"date_from": "2026-10-01", "date_to": "2026-10-05"}


@pytest.fixture
def data(db):
    return analytics_fixtures.build(db)


def _get(client, email, url, **params):
    response = client.get(url, params=params, headers=auth_header(login(client, email)))
    assert response.status_code == 200, response.text
    return response.json()


# --- Access control --------------------------------------------------------------

def test_analytics_requires_admin(client, data):
    tokens = login(client, "alice@example.com")
    assert client.get(ANALYTICS, headers=auth_header(tokens)).status_code == 403
    assert client.get(ANALYTICS).status_code == 401
    assert client.get(SUMMARY).status_code == 401


def test_invalid_date_range_is_rejected(client, data):
    tokens = login(client, "admin@example.com")
    response = client.get(ANALYTICS, params={"date_from": "2026-10-05", "date_to": "2026-10-01"},
                          headers=auth_header(tokens))
    assert response.status_code == 400


# --- User summary ----------------------------------------------------------------

def test_user_summary_counts_only_own_complaints(client, data):
    body = _get(client, "alice@example.com", SUMMARY)
    assert body["total"] == 3
    assert body["by_status"] == {"submitted": 1, "assigned": 0, "in_progress": 0, "resolved": 2, "closed": 0}
    assert body["pending"] == 1

    refs = {u["reference_number"] for u in body["recent_updates"]}
    assert refs == {data.ref(1), data.ref(2), data.ref(6)}
    # Newest first: the submission of #2 (01 Oct 23:30 IST) is the latest event.
    first = body["recent_updates"][0]
    assert (first["reference_number"], first["from_status"], first["to_status"]) == (data.ref(2), None, "submitted")
    assert body["recent_updates"][1]["to_status"] == "resolved"
    assert body["recent_updates"][1]["note"] == "Moved to resolved"
    assert len(body["recent_updates"]) == 5

    bob = _get(client, "bob@example.com", SUMMARY)
    assert bob["total"] == 3
    assert bob["pending"] == 1  # assigned #5
    assert all(u["reference_number"] in {data.ref(3), data.ref(4), data.ref(5)} for u in bob["recent_updates"])


def test_user_summary_for_new_user_is_all_zero(client, db):
    make_user(db, email="new@example.com")
    body = _get(client, "new@example.com", SUMMARY)
    assert body == {
        "total": 0, "pending": 0,
        "by_status": {"submitted": 0, "assigned": 0, "in_progress": 0, "resolved": 0, "closed": 0},
        "recent_updates": [],
    }


def test_recent_updates_are_capped_at_ten(client, data, db):
    from app.models import ComplaintStatus, ComplaintStatusHistory

    complaint = data.complaints[data.ref(2)]
    for i in range(12):
        db.add(ComplaintStatusHistory(complaint_id=complaint.id, from_status=ComplaintStatus.SUBMITTED,
                                      to_status=ComplaintStatus.SUBMITTED, note=f"n{i}"))
    db.commit()
    assert len(_get(client, "alice@example.com", SUMMARY)["recent_updates"]) == 10


# --- Analytics aggregation -----------------------------------------------------

def test_analytics_totals_and_distributions(client, data):
    body = _get(client, "admin@example.com", ANALYTICS, **OCTOBER)

    assert body["filters"]["timezone"] == "Asia/Kolkata"
    assert body["totals"] == {"total": 5, "open": 3, "pending": 2, "in_progress": 1, "resolved": 1, "closed": 1}
    assert {s["status"]: s["count"] for s in body["by_status"]} == {
        "submitted": 1, "assigned": 1, "in_progress": 1, "resolved": 1, "closed": 1,
    }
    assert {p["priority"]: p["count"] for p in body["by_priority"]} == {
        "low": 1, "medium": 0, "high": 1, "critical": 1, "not_assessed": 2,
    }
    assert [(c["name"], c["count"]) for c in body["by_category"]] == [("Drainage", 3), ("Potholes", 2)]
    departments = {d["name"]: (d["id"], d["count"]) for d in body["by_department"]}
    assert departments["Roads Dept"][1] == 2
    assert departments["Sewerage Dept"][1] == 2
    assert departments["Unassigned"] == (None, 1)


def test_analytics_daily_trend_uses_ist_days(client, data):
    body = _get(client, "admin@example.com", ANALYTICS, **OCTOBER)
    assert body["trend"]["granularity"] == "day"
    points = [(p["period_start"], p["created"], p["resolved"]) for p in body["trend"]["points"]]
    assert points == [
        ("2026-10-01", 2, 1),  # #1 and #2 created; #1 resolved 20:00 IST
        ("2026-10-02", 1, 1),  # #3 (00:30 IST); #6 resolved (filed in September)
        ("2026-10-03", 1, 0),
        ("2026-10-04", 0, 1),  # #4 resolved 15:00 IST
        ("2026-10-05", 1, 0),
    ]


def test_date_to_is_inclusive_in_ist(client, data):
    # #3 was created at 2026-10-01 19:00 UTC, which is already 2 October in IST.
    body = _get(client, "admin@example.com", ANALYTICS, date_from="2026-10-01", date_to="2026-10-01")
    assert body["totals"]["total"] == 2
    assert [p["period_start"] for p in body["trend"]["points"]] == ["2026-10-01"]


def test_analytics_weekly_trend_for_long_ranges(client, data):
    body = _get(client, "admin@example.com", ANALYTICS, date_from="2026-06-01", date_to="2026-10-05")
    trend = body["trend"]
    assert trend["granularity"] == "week"
    assert all(date.fromisoformat(p["period_start"]).weekday() == 0 for p in trend["points"])
    assert sum(p["created"] for p in trend["points"]) == 6
    assert sum(p["resolved"] for p in trend["points"]) == 3
    by_week = {p["period_start"]: (p["created"], p["resolved"]) for p in trend["points"]}
    assert by_week["2026-09-28"] == (4, 3)  # Mon 28 Sep - Sun 4 Oct
    assert by_week["2026-10-05"] == (1, 0)
    assert by_week["2026-09-14"] == (1, 0)  # #6 created Sun 20 Sep


def test_resolution_time_uses_only_resolved_complaints(client, data):
    everything = _get(client, "admin@example.com", ANALYTICS)["resolution"]
    # 10 h, 30 h and 288 h.
    assert everything["sample_size"] == 3
    assert everything["average_hours"] == pytest.approx((10 + 30 + 288) / 3, abs=0.01)
    assert everything["median_hours"] == pytest.approx(30)

    october = _get(client, "admin@example.com", ANALYTICS, **OCTOBER)["resolution"]
    assert october == {"average_hours": 20.0, "median_hours": 20.0, "sample_size": 2}


def test_oldest_open_complaints(client, data):
    body = _get(client, "admin@example.com", ANALYTICS)
    oldest = body["oldest_open"]
    assert [c["reference_number"] for c in oldest] == [data.ref(2), data.ref(3), data.ref(5)]
    assert oldest[2]["department"] is None
    assert oldest[0]["category"] == "Potholes"
    assert oldest[0]["age_days"] >= 0


def test_analytics_filters(client, data):
    admin = "admin@example.com"
    by_category = _get(client, admin, ANALYTICS, category_id=data.drainage.id)
    assert by_category["totals"]["total"] == 3
    assert [c["name"] for c in by_category["by_category"]] == ["Drainage"]

    by_department = _get(client, admin, ANALYTICS, department_id=data.potholes.department_id)
    assert by_department["totals"]["total"] == 3  # #2, #4, #6

    by_status = _get(client, admin, ANALYTICS, status="resolved")
    assert by_status["totals"] == {"total": 2, "open": 0, "pending": 0, "in_progress": 0, "resolved": 2, "closed": 0}
    assert by_status["oldest_open"] == []


def test_analytics_empty_result_is_zero_safe(client, data):
    body = _get(client, "admin@example.com", ANALYTICS, date_from="2025-01-01", date_to="2025-01-03")
    assert body["totals"]["total"] == 0
    assert body["by_category"] == [] and body["by_department"] == []
    assert all(p["count"] == 0 for p in body["by_priority"])
    assert body["resolution"] == {"average_hours": None, "median_hours": None, "sample_size": 0}
    assert [(p["created"], p["resolved"]) for p in body["trend"]["points"]] == [(0, 0)] * 3


def test_analytics_with_no_complaints_at_all(client, db):
    make_user(db, email="admin@example.com", role=analytics_fixtures.UserRole.ADMIN)
    body = _get(client, "admin@example.com", ANALYTICS)
    assert body["totals"]["total"] == 0
    assert body["trend"]["points"] == []
