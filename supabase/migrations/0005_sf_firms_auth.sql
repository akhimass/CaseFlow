-- SF demo firms, caller location, firm demo login

alter table public.cases
  add column if not exists caller_location text,
  add column if not exists matched_firm_id text references public.firms(id);

create index if not exists cases_matched_firm_id_idx on public.cases (matched_firm_id);

alter table public.firms
  add column if not exists city text,
  add column if not exists county text,
  add column if not exists service_areas text[] not null default '{}',
  add column if not exists demo_email text,
  add column if not exists demo_pin text;

insert into public.firms (
  id, name, jurisdictions, specialties, languages, phone,
  city, county, service_areas, demo_email, demo_pin
) values
  (
    'pacific_heights',
    'Pacific Heights Injury Law',
    array['CA'],
    array['general_pi','auto','mva','rear_end'],
    array['en','es'],
    '(415) 555-0101',
    'San Francisco',
    'San Francisco County',
    array['san francisco','sf','pacific heights','marina','presidio','richmond district'],
    'intake@pacificheights-law.com',
    'caseflow'
  ),
  (
    'mission_legal',
    'Mission Legal Advocates',
    array['CA'],
    array['pedestrian','auto','mva'],
    array['en','es'],
    '(415) 555-0102',
    'San Francisco',
    'San Francisco County',
    array['san francisco','sf','mission','bernal heights','potrero hill','excelsior'],
    null,
    null
  ),
  (
    'golden_gate',
    'Golden Gate Accident Attorneys',
    array['CA'],
    array['motorcycle','auto','mva'],
    array['en'],
    '(415) 555-0103',
    'San Francisco',
    'San Francisco County',
    array['san francisco','sf','financial district','soma','south beach','embarcadero'],
    null,
    null
  ),
  (
    'chen_omalley',
    'Chen & O''Malley LLP',
    array['CA'],
    array['slip_fall','premises','high_value'],
    array['en','zh'],
    '(415) 555-0104',
    'San Francisco',
    'San Francisco County',
    array['san francisco','sf','nob hill','russian hill','north beach','chinatown'],
    null,
    null
  ),
  (
    'bay_counsel',
    'Bay Counsel Injury Group',
    array['CA'],
    array['general_pi','auto','pedestrian'],
    array['en','es','hi'],
    '(415) 555-0105',
    'San Francisco',
    'San Francisco Bay Area',
    array['san francisco','sf','bay area','daly city','south san francisco','oakland'],
    null,
    null
  )
on conflict (id) do update set
  name = excluded.name,
  jurisdictions = excluded.jurisdictions,
  specialties = excluded.specialties,
  languages = excluded.languages,
  phone = excluded.phone,
  city = excluded.city,
  county = excluded.county,
  service_areas = excluded.service_areas,
  demo_email = excluded.demo_email,
  demo_pin = excluded.demo_pin;
