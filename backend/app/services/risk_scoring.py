from __future__ import annotations


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(value, maximum))


def score_attrition(
    engagement_score: float | None,
    sentiment_score: float | None,
    overtime_hours: float | None,
    performance_rating: float | None,
) -> float:
    engagement_score = 0.5 if engagement_score is None else engagement_score
    sentiment_score = 0.5 if sentiment_score is None else sentiment_score
    overtime_hours = 0 if overtime_hours is None else overtime_hours
    performance_rating = 0.5 if performance_rating is None else performance_rating

    risk = 0.0
    risk += (1 - engagement_score) * 0.45
    risk += (1 - sentiment_score) * 0.20
    risk += min(overtime_hours / 30, 1.0) * 0.20
    risk += (1 - performance_rating) * 0.15
    return round(clamp(risk), 3)


def score_burnout(
    engagement_score: float | None,
    overtime_hours: float | None,
    meeting_hours: float | None,
    after_hours_messages: int | None,
) -> float:
    engagement_score = 0.5 if engagement_score is None else engagement_score
    overtime_hours = 0 if overtime_hours is None else overtime_hours
    meeting_hours = 0 if meeting_hours is None else meeting_hours
    after_hours_messages = 0 if after_hours_messages is None else after_hours_messages

    risk = 0.0
    risk += min(overtime_hours / 35, 1.0) * 0.40
    risk += min(meeting_hours / 70, 1.0) * 0.20
    risk += min(after_hours_messages / 180, 1.0) * 0.25
    risk += (1 - engagement_score) * 0.15
    return round(clamp(risk), 3)
