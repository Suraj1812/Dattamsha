with employees as (
  select * from {{ ref('stg_employees') }}
),
engagement as (
  select * from {{ ref('stg_latest_engagement') }}
),
workload as (
  select * from {{ ref('stg_latest_workload') }}
),
performance as (
  select * from {{ ref('stg_latest_performance') }}
)

select
  e.employee_id,
  e.full_name,
  e.department,
  e.role,
  g.engagement_score,
  g.sentiment_score,
  w.overtime_hours,
  w.meeting_hours,
  w.after_hours_messages,
  p.performance_rating,
  p.goal_completion_pct,
  least(
    greatest(
      ((1 - coalesce(g.engagement_score, 0.5)) * 0.45)
      + ((1 - coalesce(g.sentiment_score, 0.5)) * 0.20)
      + (least(coalesce(w.overtime_hours, 0) / 30.0, 1.0) * 0.20)
      + ((1 - coalesce(p.performance_rating, 0.5)) * 0.15),
      0.0
    ),
    1.0
  ) as attrition_risk,
  least(
    greatest(
      (least(coalesce(w.overtime_hours, 0) / 35.0, 1.0) * 0.40)
      + (least(coalesce(w.meeting_hours, 0) / 70.0, 1.0) * 0.20)
      + (least(coalesce(w.after_hours_messages, 0) / 180.0, 1.0) * 0.25)
      + ((1 - coalesce(g.engagement_score, 0.5)) * 0.15),
      0.0
    ),
    1.0
  ) as burnout_risk
from employees e
left join engagement g on e.employee_id = g.employee_id
left join workload w on e.employee_id = w.employee_id
left join performance p on e.employee_id = p.employee_id
