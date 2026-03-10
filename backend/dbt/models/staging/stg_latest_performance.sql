with ranked as (
  select
    employee_id,
    snapshot_date,
    performance_rating,
    goal_completion_pct,
    row_number() over (partition by employee_id order by snapshot_date desc) as rn
  from performance_metrics
)
select
  employee_id,
  snapshot_date,
  performance_rating,
  goal_completion_pct
from ranked
where rn = 1
