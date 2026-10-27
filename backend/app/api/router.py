"""Aggregates all versioned API routers."""

from fastapi import APIRouter

from app.api import (
    admin,
    ai,
    auth,
    chatbot,
    complaints,
    dashboard,
    departments,
    feedback,
    health,
    notifications,
    reports,
    users,
)

api_router = APIRouter()
api_router.include_router(ai.router)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(complaints.router)
api_router.include_router(admin.router)
api_router.include_router(departments.router)
api_router.include_router(notifications.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(chatbot.router)
api_router.include_router(feedback.router)
