with ranked as (
  select
    employee_id,
    snapshot_date,
    engagement_score,
    sentiment_score,
    row_number() over (partition by employee_id order by snapshot_date desc) as rn
  from engagement_metrics
)
select
  employee_id,
  snapshot_date,
  engagement_score,
  sentiment_score
from ranked
where rn = 1
