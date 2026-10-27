"""Load fictional DEMO data so every screen has something to show.

    python -m app.scripts.seed_demo            # add demo data (skips if demo complaints exist)
    python -m app.scripts.seed_demo --reset    # delete ALL complaints first, then reload the demo

Everything here is fictional: people, complaints and comments are invented for
demonstration and are clearly marked as demo data (accounts end in
"...demo@example.com"). The coordinates are approximate locality centres.
Complaints are created through the real services, so routing, AI predictions,
assignments, notifications and audit entries happen exactly as for real users;
afterwards the timestamps are spread over the past weeks so that charts,
trends and resolution times have realistic shapes.

Demo account password: DEMO_PASSWORD in backend/.env (generated on first run).
"""

import argparse
import os
import random
import secrets
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from dotenv import dotenv_values
from sqlalchemy import delete, select, text, update

from app.core.config import BACKEND_DIR, get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    AttachmentAnalysis,
    AuditLog,
    Category,
    Complaint,
    ComplaintAIPrediction,
    ComplaintAssignment,
    ComplaintAttachment,
    ComplaintComment,
    ComplaintFeedback,
    ComplaintPriority,
    ComplaintStatus,
    ComplaintStatusHistory,
    Department,
    Notification,
    PrioritySource,
    User,
    UserRole,
)
from app.repositories import user_repository
from app.schemas.complaint import AssignRequest, ComplaintCreate, StatusUpdate
from app.schemas.feedback import FeedbackCreate
from app.services import complaint_service, feedback_service

S = ComplaintStatus
RNG = random.Random(20261011)  # deterministic demo
NOW = datetime.now(UTC)

# --- People (fictional) -------------------------------------------------------------

CITIZENS = [
    ("Lakshmi Devi", "lakshmi.demo@example.com"),
    ("Arjun Reddy", "arjun.demo@example.com"),
    ("Fatima Begum", "fatima.demo@example.com"),
    ("Suresh Goud", "suresh.demo@example.com"),
    ("Priya Nair", "priya.demo@example.com"),
    ("Mohammed Irfan", "irfan.demo@example.com"),
]

STAFF = [
    ("Kiran Rao", "kiran.staff.demo@example.com", "Sewerage & Drainage Department"),
    ("Anitha Kumari", "anitha.staff.demo@example.com", "Sanitation Department"),
    ("Mahesh Yadav", "mahesh.staff.demo@example.com", "Roads & Engineering Department"),
    ("Srinivas Chary", "srinivas.staff.demo@example.com", "Street Lighting Department"),
    ("Padma Reddy", "padma.staff.demo@example.com", "Water Supply Department"),
    ("Venkat Naidu", "venkat.staff.demo@example.com", "Electricity Department"),
]

# Approximate locality centres (for map/demo purposes only).
LOCALITIES = {
    "Ameerpet": (17.4375, 78.4483),
    "Kukatpally": (17.4849, 78.4138),
    "Madhapur": (17.4483, 78.3915),
    "Secunderabad": (17.4399, 78.4983),
    "Begumpet": (17.4440, 78.4627),
    "Dilsukhnagar": (17.3688, 78.5247),
    "Mehdipatnam": (17.3959, 78.4331),
    "Gachibowli": (17.4401, 78.3489),
    "Banjara Hills": (17.4156, 78.4347),
    "LB Nagar": (17.3457, 78.5522),
    "Malkajgiri": (17.4534, 78.5279),
    "Tolichowki": (17.3984, 78.4126),
}


@dataclass
class DemoComplaint:
    slug: str
    subject: str
    description: str
    locality: str
    landmark: str
    final: S  # lifecycle stage to reach
    days_ago: float  # when it was filed
    comment: str | None = None  # citizen comment
    staff_note: str | None = None  # public staff reply
    internal: str | None = None  # internal staff note
    reopen: bool = False
    exact_spot: bool = False  # no random spread, so a near-duplicate pair shares the location


COMPLAINTS: list[DemoComplaint] = [
    # Drainage (incl. a near-duplicate pair in Ameerpet)
    DemoComplaint("drainage-sewerage", "Drain overflowing near Ameerpet metro bus stop",
                  "The roadside drain next to the metro bus stop has been overflowing for four days. Dirty water covers the footpath and commuters have to walk on the road.",
                  "Ameerpet", "near Metro Station bus stop", S.IN_PROGRESS, 9, staff_note="Desilting crew scheduled for tomorrow morning.",
                  exact_spot=True),
    DemoComplaint("drainage-sewerage", "Drain overflowing at Ameerpet metro bus stop again",
                  "The drain near the Ameerpet metro bus stop is overflowing. Dirty drain water is on the footpath and commuters walk on the road.",
                  "Ameerpet", "near Metro Station bus stop", S.SUBMITTED, 2, exact_spot=True),
    DemoComplaint("drainage-sewerage", "Open manhole without cover on internal road",
                  "A manhole on our colony road has been open without a cover for two days. It is very dangerous at night for children and two-wheelers.",
                  "Kukatpally", "KPHB Colony 4th Phase, Road No. 3", S.IN_PROGRESS, 4, internal="Cover ordered from stores; temporary barricade placed."),
    DemoComplaint("drainage-sewerage", "Waterlogging after every rain near school",
                  "Rainwater collects knee-deep in front of the government school after every rain because the stormwater drain is blocked with silt.",
                  "Dilsukhnagar", "near ZP High School", S.CLOSED, 30, comment="Thank you, the drain is flowing properly now."),
    DemoComplaint("drainage-sewerage", "Blocked drain causing mosquito breeding",
                  "The drain in our lane is completely blocked with plastic waste and stagnant water is breeding mosquitoes.",
                  "Mehdipatnam", "Humayun Nagar lane 2", S.ASSIGNED, 3),
    # Garbage
    DemoComplaint("garbage-sanitation", "Garbage not collected for a week",
                  "Garbage has not been collected from our street for a week. Bins are overflowing and stray dogs are spreading the waste.",
                  "Malkajgiri", "Vinayak Nagar main road", S.RESOLVED, 12, staff_note="Collection vehicle route has been corrected."),
    DemoComplaint("garbage-sanitation", "Garbage dumped on vacant plot",
                  "People are dumping household garbage on the vacant plot next to the park. It is burning sometimes and the smoke enters homes.",
                  "Tolichowki", "behind Galaxy Theatre", S.IN_PROGRESS, 6),
    DemoComplaint("garbage-sanitation", "Public toilet near market not cleaned",
                  "The public toilet near the vegetable market has not been cleaned for many days and is unusable.",
                  "Secunderabad", "near Monda Market", S.CLOSED, 25),
    DemoComplaint("garbage-sanitation", "Overflowing community bin at bus depot",
                  "The large community bin at the bus depot entrance is overflowing onto the road and blocking the footpath.",
                  "LB Nagar", "LB Nagar bus depot entrance", S.SUBMITTED, 1),
    # Roads
    DemoComplaint("roads-potholes", "Large potholes on service road",
                  "There are several large potholes on the service road. Two-wheeler riders are falling, especially at night when it rains.",
                  "Madhapur", "Hitech City service road near Cyber Towers", S.IN_PROGRESS, 8, comment="Another bike skidded here yesterday, please hurry."),
    DemoComplaint("roads-potholes", "Road dug up and left unfinished",
                  "The road was dug for pipeline work three weeks ago and has not been relaid. Traffic is jammed every evening.",
                  "Begumpet", "Prakash Nagar road", S.RESOLVED, 18, staff_note="Road restored after pipeline work."),
    DemoComplaint("roads-potholes", "Broken footpath tiles near hospital",
                  "Footpath tiles are broken and uneven outside the hospital. Elderly patients are tripping.",
                  "Banjara Hills", "Road No. 12 near the hospital", S.CLOSED, 35),
    DemoComplaint("roads-potholes", "Speed breaker without paint markings",
                  "A new speed breaker has no white paint markings and vehicles hit it hard at night.",
                  "Gachibowli", "near DLF gate", S.ASSIGNED, 5),
    DemoComplaint("roads-potholes", "Pothole filled with water near junction",
                  "A deep pothole near the junction is filled with water and not visible to drivers.",
                  "Kukatpally", "Y-junction", S.SUBMITTED, 0.5),
    # Street lights
    DemoComplaint("street-lights", "Street lights not working on entire lane",
                  "All street lights on our lane have been off for ten days. The lane is completely dark and women feel unsafe walking at night.",
                  "Malkajgiri", "Sai Nagar lane 5", S.RESOLVED, 14, staff_note="Faulty cable replaced; lights restored."),
    DemoComplaint("street-lights", "Street light flickering continuously",
                  "The street light pole in front of house no. 12 keeps flickering all night.",
                  "Dilsukhnagar", "Chaitanyapuri colony", S.CLOSED, 28),
    DemoComplaint("street-lights", "Street lights on during daytime",
                  "The street lights on the main road stay on during the daytime, wasting electricity.",
                  "Secunderabad", "SP Road", S.IN_PROGRESS, 7),
    DemoComplaint("street-lights", "Dark stretch near park entrance",
                  "Three poles near the park entrance have no working lights. Chain snatching incidents were reported here.",
                  "Banjara Hills", "near the park gate", S.SUBMITTED, 1.5),
    # Water
    DemoComplaint("water-supply", "No drinking water supply for three days",
                  "Our area has not received drinking water supply for three days. Families are buying water cans.",
                  "LB Nagar", "Mansoorabad", S.RESOLVED, 10, staff_note="Valve repaired; supply resumed on regular schedule."),
    DemoComplaint("water-supply", "Pipeline leakage wasting water",
                  "A pipeline is leaking on the main road and clean water is flowing into the drain all day.",
                  "Mehdipatnam", "near Rythu Bazar", S.CLOSED, 22, reopen=True, comment="The leak started again after two days."),
    DemoComplaint("water-supply", "Contaminated muddy water from taps",
                  "Tap water is coming muddy and smelly since yesterday. Children fell sick.",
                  "Tolichowki", "Paramount Colony", S.IN_PROGRESS, 3, internal="Sample sent for testing; check for sewage cross-connection."),
    DemoComplaint("water-supply", "Very low water pressure in mornings",
                  "Water pressure is so low in the morning supply hours that it does not reach the overhead tank.",
                  "Kukatpally", "Allwyn Colony", S.SUBMITTED, 2.5),
    # Electricity (incl. emergency example)
    DemoComplaint("electricity", "Live electric wire hanging over footpath",
                  "A live electric wire is hanging low over the footpath after last night's storm. Sparks are visible and children walk here to school. Danger.",
                  "Ameerpet", "near the school on SR Nagar road", S.RESOLVED, 6, staff_note="Line made safe and re-strung the same day."),
    DemoComplaint("electricity", "Frequent power cuts every evening",
                  "There are power cuts every evening between 7 and 9 pm for the last week.",
                  "Gachibowli", "Telecom Nagar", S.IN_PROGRESS, 5),
    DemoComplaint("electricity", "Transformer making loud noise",
                  "The transformer near our apartment is making loud buzzing noise and smoke was seen once.",
                  "Madhapur", "Ayyappa Society", S.ASSIGNED, 2),
    DemoComplaint("electricity", "Leaning electric pole after rain",
                  "An electric pole is leaning dangerously after heavy rain and may fall on parked vehicles.",
                  "Malkajgiri", "Anandbagh", S.CLOSED, 40),
    # Stray animals
    DemoComplaint("stray-animals", "Stray dogs chasing children in colony",
                  "A group of stray dogs is chasing children and two-wheelers in our colony every evening.",
                  "Kukatpally", "Vivekananda Nagar", S.IN_PROGRESS, 9),
    DemoComplaint("stray-animals", "Cattle sitting on main road",
                  "Cattle sit in the middle of the main road at night and cause accidents.",
                  "LB Nagar", "Sagar Ring Road", S.SUBMITTED, 4),
    DemoComplaint("stray-animals", "Dead animal on roadside not removed",
                  "A dead dog has been lying on the roadside for two days and is smelling badly.",
                  "Secunderabad", "near the railway quarters", S.CLOSED, 16),
    # Encroachment
    DemoComplaint("encroachment", "Shops encroaching footpath",
                  "Shopkeepers have occupied the entire footpath with goods and pedestrians are forced onto the road.",
                  "Dilsukhnagar", "main road near the bus stop", S.ASSIGNED, 11),
    DemoComplaint("encroachment", "Construction material blocking road",
                  "Sand and bricks for a private construction are dumped on the road for weeks, blocking half the lane.",
                  "Madhapur", "Kavuri Hills phase 2", S.RESOLVED, 20, staff_note="Owner instructed to clear the road; cleared."),
    # Public health
    DemoComplaint("public-health", "Mosquito menace, fogging needed",
                  "Mosquitoes have increased heavily in our area and two people have dengue. Please do fogging.",
                  "Tolichowki", "Nanal Nagar", S.RESOLVED, 13, staff_note="Fogging done in the area on two evenings."),
    DemoComplaint("public-health", "Stagnant water in construction pit",
                  "Rainwater is stagnant in an abandoned construction pit and breeding mosquitoes.",
                  "Gachibowli", "Indira Nagar", S.SUBMITTED, 3.5),
    # Pollution
    DemoComplaint("pollution", "Loudspeakers late at night",
                  "Loudspeakers are played at very high volume after 11 pm almost every night near our homes.",
                  "Mehdipatnam", "near the function hall", S.CLOSED, 27),
    DemoComplaint("pollution", "Burning of garbage every morning",
                  "Someone burns plastic garbage every morning and the smoke enters houses. Elderly people have breathing problems.",
                  "Begumpet", "Brahmanwadi", S.IN_PROGRESS, 4),
    # Parks & trees
    DemoComplaint("parks-trees", "Fallen tree blocking lane after storm",
                  "A big tree fell across the lane during the storm and is blocking vehicles.",
                  "Banjara Hills", "Road No. 3", S.CLOSED, 33),
    DemoComplaint("parks-trees", "Park play equipment broken",
                  "The swings and slide in the colony park are broken and have sharp edges.",
                  "Kukatpally", "KPHB 6th phase park", S.ASSIGNED, 6),
    DemoComplaint("parks-trees", "Tree branches touching electric wires",
                  "Tree branches are touching the overhead electric wires and spark during wind.",
                  "Secunderabad", "Bowenpally", S.SUBMITTED, 1),
    # Other
    DemoComplaint("other", "Bus shelter roof damaged",
                  "The roof of the bus shelter is broken and people get wet waiting for buses.",
                  "Ameerpet", "near Mythrivanam", S.SUBMITTED, 2),
    DemoComplaint("other", "Missing road name boards",
                  "Road name boards are missing in our colony and visitors and delivery agents get lost.",
                  "Malkajgiri", "Moula Ali", S.CLOSED, 38),
]

STAGE_ORDER = [S.SUBMITTED, S.ASSIGNED, S.IN_PROGRESS, S.RESOLVED, S.CLOSED]


# --- Helpers ---------------------------------------------------------------------------

def _demo_password() -> str:
    # Hosted servers set it as an environment variable; locally it lives in backend/.env.
    if os.environ.get("DEMO_PASSWORD"):
        return os.environ["DEMO_PASSWORD"]
    env_path = BACKEND_DIR / ".env"
    existing = dotenv_values(env_path).get("DEMO_PASSWORD")
    if existing:
        return existing
    password = secrets.token_urlsafe(9) + "d7"
    with env_path.open("a", encoding="utf-8") as fh:
        fh.write(f"\n# Shared password for the fictional demo accounts (development only)\nDEMO_PASSWORD={password}\n")
    return password


def _get_or_create_user(db, name: str, email: str, password_hash: str, role: UserRole, department_id: int | None = None) -> User:
    user = user_repository.get_by_email(db, email)
    if user is None:
        user = user_repository.create(db, full_name=name, email=email, hashed_password=password_hash, role=role)
    user.full_name, user.role, user.department_id, user.is_active = name, role, department_id, True
    db.commit()
    return user


def _reset(db) -> None:
    for model in (Notification, ComplaintFeedback, AttachmentAnalysis, ComplaintAIPrediction, ComplaintAttachment,
                  ComplaintComment, ComplaintAssignment, ComplaintStatusHistory, Complaint):
        db.execute(delete(model))
    db.execute(delete(AuditLog).where(AuditLog.action.like("complaint.%")))
    db.commit()
    db.execute(text("ALTER SEQUENCE complaints_id_seq RESTART WITH 1"))
    db.commit()
    uploads = get_settings().upload_path / "complaints"
    if uploads.exists():
        shutil.rmtree(uploads)
    print("Removed all complaints, their history, comments, notifications and uploaded photos.")


def _spread_timestamps(db, complaint_id: int, filed_at: datetime) -> None:
    """Move every event of a complaint from 'now' into a realistic past timeline."""
    complaint = db.get(Complaint, complaint_id)
    history = list(db.scalars(select(ComplaintStatusHistory).where(ComplaintStatusHistory.complaint_id == complaint_id)
                              .order_by(ComplaintStatusHistory.id)))
    moment = filed_at
    gaps = {S.ASSIGNED: (0.1, 1.0), S.IN_PROGRESS: (0.3, 2.0), S.RESOLVED: (0.5, 5.0), S.CLOSED: (0.2, 2.0)}
    resolved_at = closed_at = None
    for index, entry in enumerate(history):
        if index > 0:
            low, high = gaps.get(entry.to_status, (0.1, 0.5))
            moment = min(moment + timedelta(days=RNG.uniform(low, high)), NOW - timedelta(minutes=5))
        entry.created_at = moment
        if entry.to_status == S.RESOLVED:
            resolved_at = moment
        if entry.to_status == S.CLOSED:
            closed_at = moment
        if entry.to_status == S.IN_PROGRESS and entry.from_status == S.RESOLVED:
            resolved_at = None
    last = moment

    for assignment in db.scalars(select(ComplaintAssignment).where(ComplaintAssignment.complaint_id == complaint_id)):
        assigned = next((h.created_at for h in history if h.to_status == S.ASSIGNED), filed_at + timedelta(hours=3))
        assignment.created_at = assigned
    comments = list(db.scalars(select(ComplaintComment).where(ComplaintComment.complaint_id == complaint_id)
                               .order_by(ComplaintComment.id)))
    for i, comment in enumerate(comments):
        comment.created_at = min(filed_at + (last - filed_at) * ((i + 1) / (len(comments) + 1)) + timedelta(hours=2), NOW)
    for note in db.scalars(select(Notification).where(Notification.complaint_id == complaint_id)):
        note.created_at = last
        note.is_read = RNG.random() < 0.6
    prediction = db.scalar(select(ComplaintAIPrediction).where(ComplaintAIPrediction.complaint_id == complaint_id))
    if prediction:
        prediction.created_at = filed_at
        # Demo citizens "accepted" the suggestion exactly when it matched the category they chose.
        if prediction.predicted_category_id is not None:
            prediction.user_accepted_category = prediction.predicted_category_id == complaint.category_id
    feedback = db.scalar(select(ComplaintFeedback).where(ComplaintFeedback.complaint_id == complaint_id))
    if feedback:
        feedback.created_at = min(last + timedelta(hours=RNG.uniform(1, 20)), NOW)

    db.execute(
        update(Complaint).where(Complaint.id == complaint_id).values(
            created_at=filed_at, updated_at=max([last] + [c.created_at for c in comments]),
            incident_at=filed_at - timedelta(hours=RNG.uniform(2, 30)),
            resolved_at=resolved_at, closed_at=closed_at,
        )
    )
    db.commit()
    db.expire(complaint)


# --- Main --------------------------------------------------------------------------------

def run(reset: bool) -> int:
    with SessionLocal() as db:
        if reset:
            _reset(db)
        elif db.scalar(select(Complaint.id).limit(1)) is not None:
            print("Complaints already exist. Run with --reset to replace everything with the demo data.")
            return 1

        password = _demo_password()
        password_hash = hash_password(password)
        admin = db.scalar(select(User).where(User.role == UserRole.ADMIN, User.is_active.is_(True)).order_by(User.id))
        if admin is None:
            print("No administrator exists. Run `python -m app.scripts.create_admin` first.")
            return 1

        departments = {d.name: d for d in db.scalars(select(Department))}
        categories = {c.slug: c for c in db.scalars(select(Category)).unique()}
        citizens = [_get_or_create_user(db, n, e, password_hash, UserRole.USER) for n, e in CITIZENS]
        staff_by_dept: dict[int, User] = {}
        for name, email, dept_name in STAFF:
            dept = departments.get(dept_name)
            if dept is None:
                print(f"Department '{dept_name}' not found; skipping staff {name}.")
                continue
            staff_by_dept[dept.id] = _get_or_create_user(db, name, email, password_hash, UserRole.STAFF, dept.id)

        created = 0
        for index, demo in enumerate(COMPLAINTS):
            category = categories.get(demo.slug)
            if category is None:
                print(f"Category '{demo.slug}' not found; skipping.")
                continue
            citizen = citizens[index % len(citizens)]
            lat, lng = LOCALITIES[demo.locality]
            # Spread markers within the locality (about +/-200 m), except for exact-spot pairs.
            jitter = (lambda: 0.0) if demo.exact_spot else (lambda: RNG.uniform(-0.002, 0.002))  # noqa: E731
            complaint = complaint_service.create_complaint(
                db, user=citizen, files=[], ai_category_accepted=None,
                data=ComplaintCreate(
                    subject=demo.subject, description=demo.description, category_id=category.id,
                    location_text=f"{demo.landmark}, {demo.locality}, Hyderabad",
                    latitude=round(lat + jitter(), 6), longitude=round(lng + jitter(), 6),
                ),
            )
            cid = complaint.id
            target = STAGE_ORDER.index(demo.final)
            manager = staff_by_dept.get(category.department_id) or admin

            if target >= 1:
                if manager.role == UserRole.STAFF:
                    # Assigning a staff member moves the complaint to "assigned" automatically.
                    complaint_service.assign(
                        db, user=admin, complaint_id=cid,
                        request=AssignRequest(assignee_id=manager.id, note="Assigned to the area officer."),
                    )
                else:
                    complaint_service.change_status(db, user=admin, complaint_id=cid, change=StatusUpdate(status=S.ASSIGNED))
            if demo.staff_note and target >= 1:
                complaint_service.add_comment(db, user=manager, complaint_id=cid, body=demo.staff_note, is_internal=False)
            if target >= 2:
                complaint_service.change_status(db, user=manager, complaint_id=cid, change=StatusUpdate(status=S.IN_PROGRESS))
            if demo.internal:
                complaint_service.add_comment(db, user=manager, complaint_id=cid, body=demo.internal, is_internal=True)
            if demo.comment and not demo.reopen and target < 4:
                complaint_service.add_comment(db, user=citizen, complaint_id=cid, body=demo.comment, is_internal=False)
            if target >= 3:
                complaint_service.change_status(
                    db, user=manager, complaint_id=cid,
                    change=StatusUpdate(status=S.RESOLVED, note=demo.staff_note or "Work completed and verified on site."),
                )
            if demo.reopen and target >= 3:
                complaint_service.change_status(
                    db, user=citizen, complaint_id=cid,
                    change=StatusUpdate(status=S.IN_PROGRESS, note=demo.comment or "The problem is back."),
                )
                complaint_service.change_status(
                    db, user=manager, complaint_id=cid,
                    change=StatusUpdate(status=S.RESOLVED, note="Pipe joint replaced; checked again after 48 hours."),
                )
            if target >= 4:
                if demo.comment and not demo.reopen:
                    complaint_service.add_comment(db, user=citizen, complaint_id=cid, body=demo.comment, is_internal=False)
                complaint_service.change_status(db, user=citizen, complaint_id=cid, change=StatusUpdate(status=S.CLOSED))
            if target >= 3 and RNG.random() < 0.75:
                # Fictional feedback from the complainant, so ratings and the AI review page have data.
                rating = RNG.choice([3, 4, 4, 5, 5]) if not demo.reopen else 2
                feedback_service.submit_feedback(
                    db, user=citizen, complaint_id=cid,
                    data=FeedbackCreate(
                        rating=rating,
                        resolved_satisfactorily=rating >= 3,
                        ai_helpful=RNG.choice([True, True, True, False, None]),
                        comment=RNG.choice([None, "Quick response, thank you.", "Took longer than expected.", "Good follow-up from staff."]),
                    ),
                )

            filed_at = NOW - timedelta(days=demo.days_ago, hours=RNG.uniform(0, 8))
            _spread_timestamps(db, cid, filed_at)
            created += 1

        # One staff override of an AI-predicted priority, to show the "set by staff" label.
        first_roads = db.scalar(select(Complaint).join(Category).where(Category.slug == "roads-potholes").order_by(Complaint.id))
        if first_roads is not None:
            first_roads.priority = ComplaintPriority.HIGH
            first_roads.priority_source = PrioritySource.STAFF
            db.commit()

        print(f"Created {created} fictional demo complaints, {len(citizens)} demo citizens and {len(staff_by_dept)} demo staff.")
        print("Demo logins use DEMO_PASSWORD from backend/.env, e.g. lakshmi.demo@example.com (citizen),")
        print("kiran.staff.demo@example.com (Sewerage & Drainage staff). Admin login is unchanged.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Load fictional demo data.")
    parser.add_argument("--reset", action="store_true", help="delete ALL complaints before loading the demo")
    args = parser.parse_args()
    return run(args.reset)


if __name__ == "__main__":
    sys.exit(main())
