with ranked as (
  select
    employee_id,
    snapshot_date,
    overtime_hours,
    meeting_hours,
    after_hours_messages,
    row_number() over (partition by employee_id order by snapshot_date desc) as rn
  from workload_metrics
)
select
  employee_id,
  snapshot_date,
  overtime_hours,
  meeting_hours,
  after_hours_messages
from ranked
where rn = 1
