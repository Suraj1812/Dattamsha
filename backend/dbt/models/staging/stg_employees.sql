select
  id as employee_id,
  external_id,
  full_name,
  manager_id,
  department,
  role,
  location,
  employment_status,
  cast(base_salary as numeric) as base_salary,
  hire_date
from employees
where employment_status = 'active'
