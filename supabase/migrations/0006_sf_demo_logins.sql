-- Make all five San Francisco demo firms usable as demo law-firm logins, and
-- retire the stale non-SF seed firms from the demo login pool.
--
-- Background: migration 0001 seeded five non-SF firms (Orange County, LA, San
-- Diego, statewide), and 0005 added the five SF demo firms but only gave
-- pacific_heights a demo PIN. The Moss `firms` index, kb/firms.json routing, and
-- the firm dashboard all standardize on the five SF firms, so every SF firm
-- should be a selectable demo user, and the stale firms should never appear.

-- 1) Enable demo login for every SF demo firm (idempotent).
update public.firms
set
  demo_pin = 'caseflow',
  demo_email = case id
    when 'pacific_heights' then 'intake@pacificheights-law.com'
    when 'mission_legal' then 'intake@missionlegal.com'
    when 'golden_gate' then 'intake@goldengate-accident.com'
    when 'chen_omalley' then 'intake@chenomalley.com'
    when 'bay_counsel' then 'intake@baycounsel.com'
    else demo_email
  end
where id in (
  'pacific_heights', 'mission_legal', 'golden_gate', 'chen_omalley', 'bay_counsel'
);

-- 2) Ensure the stale non-SF seed firms can never appear as demo logins.
update public.firms
set demo_pin = null, demo_email = null
where id in ('martinez', 'brennan', 'reyes', 'patel', 'cohen');
