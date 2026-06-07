/**
 * Seed demo cases for the firm dashboard.
 *
 * These mirror the shape the live agent broadcasts (see `useCaseflowEvents` +
 * the firm panels), so every firm has realistic, fully-populated leads to show
 * during the demo without running a live intake. They are seeded into the
 * server-side case store (`case-store.ts`), so the SSE feed, the single-case
 * GET endpoint, and the voice-briefing agent all see identical data.
 *
 * Plain data only — no imports — so it is safe to load on the server.
 */

type Json = Record<string, unknown>;

const T = Math.floor(Date.now() / 1000) - 420;

type FirmMeta = {
  name: string;
  phone: string;
  specialties: string[];
  rating: string;
  years: string;
  response: string;
};

const FIRMS: Record<string, FirmMeta> = {
  pacific_heights: {
    name: 'Pacific Heights Injury Law',
    phone: '(415) 555-0101',
    specialties: ['auto', 'rear_end', 'general_pi'],
    rating: '4.9',
    years: '18',
    response: '2',
  },
  mission_legal: {
    name: 'Mission Legal Advocates',
    phone: '(415) 555-0102',
    specialties: ['pedestrian', 'auto', 'mva'],
    rating: '4.7',
    years: '12',
    response: '3',
  },
  golden_gate: {
    name: 'Golden Gate Accident Attorneys',
    phone: '(415) 555-0103',
    specialties: ['motorcycle', 'auto', 'mva'],
    rating: '4.8',
    years: '15',
    response: '2',
  },
  chen_omalley: {
    name: "Chen & O'Malley LLP",
    phone: '(415) 555-0104',
    specialties: ['slip_fall', 'premises', 'high_value'],
    rating: '4.9',
    years: '22',
    response: '4',
  },
  bay_counsel: {
    name: 'Bay Counsel Injury Group',
    phone: '(415) 555-0105',
    specialties: ['general_pi', 'auto', 'pedestrian'],
    rating: '4.6',
    years: '10',
    response: '2',
  },
};

// Build the Moss firm-lead cards (matched firm + two alternatives), each carrying
// its own grounding evidence — mirrors what retrieval.firm_leads emits live.
function firmLeads(c: CaseInput): Json[] {
  const top = c.firm_id;
  const alts = Object.keys(FIRMS)
    .filter((id) => id !== top)
    .slice(0, 2);
  const solNote = c.streams.law.text.slice(0, 130);
  const range = c.streams.settlement.amount_range;
  const langs = c.language === 'es' ? ['es', 'en'] : ['en', 'es'];
  return [top, ...alts].map((id, i) => {
    const f = FIRMS[id];
    const isTop = i === 0;
    return {
      firm_id: id,
      name: f.name,
      phone: f.phone,
      languages: langs,
      specialties: f.specialties,
      score: isTop ? c.match_score : Math.max(58, c.match_score - 9 - i * 6),
      match_reasons: isTop
        ? c.streams.firm.reasons
        : ['Jurisdiction match (CA)', `Bilingual ${langs.join('/')} intake`],
      rating: f.rating,
      years_experience: f.years,
      response_time_hours: f.response,
      comparable_range: range,
      jurisdiction_note: solNote,
      profile_excerpt: `${f.name} — ${f.specialties.join(', ').replace(/_/g, ' ')}.`,
    };
  });
}

// The citation trail: which retrieval IDs the agent cited, in order.
function citationTrail(c: CaseInput): Json[] {
  return c.citations.map((id, i) => ({
    citation_id: id,
    timestamp: T + 40 + i * 6,
    turn: 3 + i,
  }));
}

type StreamInput = {
  law: {
    id: string;
    title: string;
    subtitle: string;
    text: string;
    citation: string;
    score: number;
  };
  settlement: { id: string; title: string; amount_range: string; text: string; score: number };
  firm: { firm_id: string; reasons: string[]; score: number };
  procedure: { id: string; title: string; text: string; score: number };
};

function mossStreams(input: StreamInput): Json[] {
  const firmMeta = FIRMS[input.firm.firm_id];
  return [
    {
      namespace: 'state-law',
      query: 'CA personal injury statute of limitations and liability',
      results_count: 1,
      time_taken_ms: 142,
      timestamp: T + 12,
      seq: 1,
      cached: false,
      snippets: [{ ...input.law, subtitle: input.law.subtitle }],
    },
    {
      namespace: 'settlements',
      query: 'comparable settlement outcomes',
      results_count: 2,
      time_taken_ms: 168,
      timestamp: T + 18,
      seq: 2,
      cached: false,
      snippets: [input.settlement],
    },
    {
      namespace: 'firms',
      query: 'best firm match for jurisdiction + specialty',
      results_count: 1,
      time_taken_ms: 121,
      timestamp: T + 24,
      seq: 3,
      cached: false,
      snippets: [
        {
          id: `firms:${input.firm.firm_id}`,
          title: firmMeta.name,
          reasons: input.firm.reasons,
          phone: firmMeta.phone,
          score: input.firm.score,
        },
      ],
    },
    {
      namespace: 'procedures',
      query: 'post-accident procedural guidance',
      results_count: 1,
      time_taken_ms: 109,
      timestamp: T + 30,
      seq: 4,
      cached: false,
      snippets: [input.procedure],
    },
  ];
}

type CaseInput = {
  case_id: string;
  caller: string;
  accident_type: string;
  location: string;
  injuries: string;
  fault_claim: string;
  language: string;
  score: number;
  status: string;
  last_event: string;
  est_value: number;
  firm_id: string;
  match_score: number;
  match_reason: string;
  streams: StreamInput;
  synthesis: string;
  citations: string[];
  verbal_summary: string;
  firm_brief: string;
  documents?: Json;
  consistency?: Json;
  redactions: number;
  redaction_categories: Record<string, number>;
};

function buildCase(c: CaseInput): Json {
  const firmMeta = FIRMS[c.firm_id];
  return {
    case_id: c.case_id,
    caller_id: c.caller,
    accident_type: c.accident_type,
    state: 'CA',
    jurisdiction: 'CA',
    caller_location: c.location,
    location: c.location,
    injuries: c.injuries,
    fault_claim: c.fault_claim,
    language: c.language,
    score: c.score,
    case_strength: c.score,
    est_value: c.est_value,
    status: c.status,
    last_event: c.last_event,
    case_completeness: 0.92,
    consent_given_at: new Date((T - 600) * 1000).toISOString(),
    pii_redacted: true,
    updated_at: (T + 60) * 1000,
    matched_firm_id: c.firm_id,
    matches: [
      {
        firm_id: c.firm_id,
        name: firmMeta.name,
        score: c.match_score,
        reasoning: c.match_reason,
      },
    ],
    moss_retrievals: mossStreams(c.streams),
    moss_firm_leads: firmLeads(c),
    moss_citations: citationTrail(c),
    caseflow_decision: {
      synthesis: c.synthesis,
      confidence: Math.min(0.97, c.score / 100 + 0.08),
      language: c.language,
      citations: c.citations,
      source: 'qwen-max via TrueFoundry',
      status: 'ready',
      seq: 1,
    },
    verbal_summary: c.verbal_summary,
    firm_brief: c.firm_brief,
    // Generated case-file PDFs — real artifacts written to S3 at
    // {case_id}/docs/{doc_type}.{md,pdf} and grounded in this case's stored
    // evidence; the firm Documents panel previews/downloads them via presigned URL.
    generated_documents: [
      {
        doc_type: 'intake_summary',
        title: 'Intake Summary',
        audit_status: 'verified',
        audit_confidence: 0.94,
        page_count: 2,
        generated_at: new Date((T + 80) * 1000).toISOString(),
      },
      {
        doc_type: 'demand_letter',
        title: 'Demand Letter Draft',
        audit_status: 'verified',
        audit_confidence: 0.92,
        page_count: 2,
        generated_at: new Date((T + 95) * 1000).toISOString(),
      },
      {
        doc_type: 'action_sheet',
        title: '24-Hour Action Sheet',
        audit_status: 'verified',
        audit_confidence: 0.95,
        page_count: 1,
        generated_at: new Date((T + 100) * 1000).toISOString(),
      },
    ],
    ...(c.documents
      ? {
          documents: c.documents,
          document_parsing: {
            status: 'parsed',
            doc_type: Object.keys(c.documents)[0],
            provider: 'Unsiloed',
            source: 'Unsiloed Vision API',
            field_count: 6,
            latency_ms: 2140,
            timestamp: T + 40,
          },
        }
      : {}),
    ...(c.consistency ? { consistency_audit: c.consistency } : {}),
    privacy_stats: {
      redaction_count: c.redactions,
      categories: c.redaction_categories,
      encryption: 'SSE-KMS (aws:kms)',
      sensitive_bucket: 'caseflow-sensitive',
      consent_given_at: new Date((T - 600) * 1000).toISOString(),
      stt_note: 'Deepgram STT → MiniMax TTS; transcripts redacted before gateway calls.',
    },
    voice_bridge: {
      stt_provider: 'Deepgram',
      stt_model: 'nova-3',
      detected_language: c.language,
      tts_provider: 'MiniMax',
      tts_model: 'speech-2.8-hd',
      tts_voice: c.language === 'es' ? 'Spanish_SereneWoman' : 'English_SereneWoman',
      timestamp: T + 5,
    },
  };
}

export const DEMO_CASES: Json[] = [
  buildCase({
    case_id: 'demo-maria-delgado',
    caller: 'Maria Delgado',
    accident_type: 'rear_end',
    location: 'San Francisco, CA',
    injuries: 'Whiplash, neck pain; MRI ordered',
    fault_claim: 'Other driver ran the red light',
    language: 'es',
    score: 78,
    status: 'matched',
    last_event: 'discrepancy_found',
    est_value: 72000,
    firm_id: 'pacific_heights',
    match_score: 91,
    match_reason: 'CA auto/rear-end specialty, bilingual EN/ES intake, serves San Francisco.',
    streams: {
      law: {
        id: 'state-law:ca-sol',
        title: 'CA Statute of Limitations — personal injury',
        subtitle: 'Cal. Civ. Proc. Code § 335.1',
        text: 'Two years from the date of injury to file a personal-injury claim. Claims against a government entity require a notice of claim within six months.',
        citation: 'Cal. Civ. Proc. Code § 335.1',
        score: 0.95,
      },
      settlement: {
        id: 'settlements:ca-rear-end-moderate-contested',
        title: 'Rear-end · moderate severity · contested fault',
        amount_range: '$45,000 – $95,000',
        text: 'Soft-tissue neck injury with imaging and contested liability in CA urban venues; settlements cluster mid-five figures when treatment is documented.',
        score: 0.88,
      },
      firm: {
        firm_id: 'pacific_heights',
        reasons: ['CA rear-end/auto specialty', 'Bilingual EN/ES', 'Serves San Francisco'],
        score: 0.91,
      },
      procedure: {
        id: 'procedures:post_accident_72h',
        title: 'First 72 hours after a collision',
        text: 'Document injuries with imaging, preserve the police report, and avoid recorded statements to the other insurer until represented.',
        score: 0.82,
      },
    },
    synthesis:
      'Strong rear-end claim with documented whiplash and an MRI order. The caller states the other driver ran a red light, but the police report lists fault as undetermined — resolving that conflict materially affects liability. CA two-year SoL is comfortably open.',
    citations: ['state-law:ca-sol', 'settlements:ca-rear-end-moderate-contested'],
    verbal_summary:
      'Maria Delgado was rear-ended in San Francisco and reports whiplash with an MRI ordered. She says the other driver ran the red light, though the police report marks fault undetermined — a discrepancy worth clarifying. The two-year California filing window is open and comparable settlements range from forty-five to ninety-five thousand dollars.',
    firm_brief:
      'Rear-end, Spanish-speaking claimant, San Francisco. Whiplash + MRI ordered. Liability conflict: caller says red-light, police report undetermined. SoL open (2 yr). Comparable range $45K–$95K.',
    documents: {
      police_report: {
        report_number: 'SFPD-2026-04412',
        incident_date: '2026-06-01',
        location: 'Van Ness Ave & Geary Blvd, San Francisco',
        fault_determination: 'Undetermined',
        other_driver_claim: 'Claimed right of way',
        _meta: {
          confidence: {
            report_number: 0.97,
            incident_date: 0.95,
            location: 0.9,
            fault_determination: 0.71,
            other_driver_claim: 0.68,
          },
          source: 'Unsiloed Vision API',
          latency_ms: 2140,
        },
      },
      er_discharge: {
        visit_date: '2026-06-01',
        primary_diagnosis: 'Cervical strain (whiplash)',
        imaging_ordered: 'MRI cervical spine',
        treatment: 'NSAIDs, soft collar, PT referral',
        _meta: {
          confidence: {
            visit_date: 0.96,
            primary_diagnosis: 0.9,
            imaging_ordered: 0.88,
            treatment: 0.84,
          },
          source: 'Unsiloed Vision API',
          latency_ms: 1980,
        },
      },
    },
    consistency: {
      conflict: true,
      conflict_type: 'fault_attribution',
      reason:
        'Caller states the other driver ran the red light, but the police report records fault as undetermined and notes the other driver claimed right of way.',
      clarifying_question:
        '¿Recuerda si había testigos o cámaras en el cruce que puedan confirmar quién tenía la luz verde?',
      source: 'qwen-max via TrueFoundry',
      llm_model: 'qwen-max',
      failover: false,
    },
    redactions: 14,
    redaction_categories: {
      name: 4,
      phone: 2,
      address: 3,
      dob: 1,
      ssn_partial: 1,
      email: 1,
      plate: 2,
    },
  }),
  buildCase({
    case_id: 'demo-james-okafor',
    caller: 'James Okafor',
    accident_type: 'pedestrian',
    location: 'Mission District, San Francisco, CA',
    injuries: 'Fractured wrist, contusions',
    fault_claim: 'Driver failed to yield in crosswalk',
    language: 'en',
    score: 84,
    status: 'booked',
    last_event: 'outbound_call',
    est_value: 130000,
    firm_id: 'mission_legal',
    match_score: 89,
    match_reason: 'Pedestrian-injury specialty, Mission District local counsel.',
    streams: {
      law: {
        id: 'state-law:ca-comparative-negligence',
        title: 'CA pure comparative negligence',
        subtitle: 'Li v. Yellow Cab Co. (1975)',
        text: 'Damages are reduced by the plaintiff’s share of fault but never barred — even a mostly-at-fault plaintiff may recover a proportional amount.',
        citation: 'Li v. Yellow Cab Co., 13 Cal.3d 804',
        score: 0.92,
      },
      settlement: {
        id: 'settlements:ca-pedestrian-fracture-clear',
        title: 'Pedestrian · fracture · clear fault',
        amount_range: '$90,000 – $180,000',
        text: 'Crosswalk pedestrian strikes with documented fractures and clear driver fault settle in the low-to-mid six figures in SF.',
        score: 0.9,
      },
      firm: {
        firm_id: 'mission_legal',
        reasons: ['Pedestrian specialty', 'Serves Mission District', 'Bilingual EN/ES'],
        score: 0.89,
      },
      procedure: {
        id: 'procedures:evidence_preservation',
        title: 'Crosswalk evidence preservation',
        text: 'Request nearby business and traffic-camera footage quickly; signal-timing data and witness contacts are time-sensitive.',
        score: 0.8,
      },
    },
    synthesis:
      'High-value pedestrian claim with a documented wrist fracture and a failure-to-yield in a marked crosswalk. Clear fault and CA comparative-negligence rules favor strong recovery; comparable outcomes reach the low six figures.',
    citations: ['state-law:ca-comparative-negligence', 'settlements:ca-pedestrian-fracture-clear'],
    verbal_summary:
      'James Okafor was struck in a Mission District crosswalk and suffered a fractured wrist. The driver failed to yield, fault appears clear, and comparable pedestrian-fracture settlements range from ninety thousand to one hundred eighty thousand dollars. The consult is booked.',
    firm_brief:
      'Pedestrian, English, Mission District. Fractured wrist, clear fault (failure to yield in crosswalk). Comparable range $90K–$180K. Consult booked via outbound call.',
    redactions: 9,
    redaction_categories: { name: 3, phone: 2, address: 2, dob: 1, email: 1 },
  }),
  buildCase({
    case_id: 'demo-wei-zhang',
    caller: 'Wei Zhang',
    accident_type: 'slip_fall',
    location: 'Nob Hill, San Francisco, CA',
    injuries: 'Herniated disc; surgery consult pending',
    fault_claim: 'Wet floor, no warning signage',
    language: 'en',
    score: 81,
    status: 'matched',
    last_event: 'firms_matched',
    est_value: 165000,
    firm_id: 'chen_omalley',
    match_score: 93,
    match_reason: 'Premises-liability / high-value specialty; serves Nob Hill & Chinatown.',
    streams: {
      law: {
        id: 'state-law:ca-premises-liability',
        title: 'CA premises liability — duty of care',
        subtitle: 'Rowland v. Christian (1968)',
        text: 'Property owners owe a duty of ordinary care; liability turns on foreseeability of harm and whether the hazard was known or should have been known.',
        citation: 'Rowland v. Christian, 69 Cal.2d 108',
        score: 0.93,
      },
      settlement: {
        id: 'settlements:ca-slip-fall-disc-clear',
        title: 'Slip & fall · disc injury · clear hazard',
        amount_range: '$120,000 – $250,000',
        text: 'Documented herniated-disc injuries from unmarked wet-floor hazards in commercial premises reach the mid-six figures with surgical recommendations.',
        score: 0.9,
      },
      firm: {
        firm_id: 'chen_omalley',
        reasons: ['Premises liability', 'High-value cases', 'Serves Nob Hill / Chinatown'],
        score: 0.93,
      },
      procedure: {
        id: 'procedures:premises_incident_report',
        title: 'Premises incident documentation',
        text: 'Secure the incident report, photograph the hazard and absence of signage, and identify staff who knew of the spill.',
        score: 0.83,
      },
    },
    synthesis:
      'High-value premises claim: a herniated disc from an unmarked wet floor with a pending surgical consult. CA premises-liability duty and the lack of warning signage support strong liability; comparable settlements reach the mid-six figures.',
    citations: ['state-law:ca-premises-liability', 'settlements:ca-slip-fall-disc-clear'],
    verbal_summary:
      'Wei Zhang slipped on an unmarked wet floor in a Nob Hill building and has a herniated disc with a surgery consult pending. The absence of warning signage strengthens premises liability, and comparable disc-injury cases settle between one hundred twenty and two hundred fifty thousand dollars.',
    firm_brief:
      'Slip & fall, English, Nob Hill. Herniated disc, surgery consult pending. Hazard: unmarked wet floor, no signage. Comparable range $120K–$250K. High-value — routed to Chen & O’Malley.',
    documents: {
      incident_report: {
        report_number: 'PROP-INC-7781',
        incident_date: '2026-05-28',
        location: 'Lobby, 1200 California St, San Francisco',
        fault_determination: 'Hazard noted; no signage present',
        _meta: {
          confidence: {
            report_number: 0.94,
            incident_date: 0.93,
            location: 0.91,
            fault_determination: 0.76,
          },
          source: 'Unsiloed Vision API',
          latency_ms: 2010,
        },
      },
    },
    redactions: 8,
    redaction_categories: { name: 3, phone: 1, address: 2, dob: 1, email: 1 },
  }),
  buildCase({
    case_id: 'demo-robert-hayes',
    caller: 'Robert Hayes',
    accident_type: 'motorcycle',
    location: 'Financial District, San Francisco, CA',
    injuries: 'Road rash, possible fractured rib',
    fault_claim: 'Car merged into lane without signaling',
    language: 'en',
    score: 69,
    status: 'matched',
    last_event: 'case_strength',
    est_value: 88000,
    firm_id: 'golden_gate',
    match_score: 87,
    match_reason: 'Motorcycle-injury specialty; serves Financial District / SoMa.',
    streams: {
      law: {
        id: 'state-law:ca-lane-change',
        title: 'CA unsafe lane change',
        subtitle: 'Cal. Veh. Code § 22107',
        text: 'A driver may not change lanes until the movement can be made with reasonable safety and after an appropriate signal — relevant to merge-fault disputes.',
        citation: 'Cal. Veh. Code § 22107',
        score: 0.89,
      },
      settlement: {
        id: 'settlements:ca-motorcycle-moderate-contested',
        title: 'Motorcycle · moderate · contested fault',
        amount_range: '$55,000 – $120,000',
        text: 'Motorcycle merge-collision injuries with contested fault settle mid-five to low-six figures when injuries are documented.',
        score: 0.85,
      },
      firm: {
        firm_id: 'golden_gate',
        reasons: ['Motorcycle specialty', 'Serves Financial District', 'Trial-ready'],
        score: 0.87,
      },
      procedure: {
        id: 'procedures:motorcycle_gear_evidence',
        title: 'Preserve gear & damage evidence',
        text: 'Keep damaged helmet and gear, photograph the bike and road, and obtain the merging vehicle’s insurance details.',
        score: 0.78,
      },
    },
    synthesis:
      'Motorcycle merge-collision with road rash and a possible rib fracture. Liability hinges on the unsignaled lane change (Veh. Code § 22107); fault is contested, putting comparable outcomes in the mid-five to low-six figures.',
    citations: ['state-law:ca-lane-change', 'settlements:ca-motorcycle-moderate-contested'],
    verbal_summary:
      'Robert Hayes was injured when a car merged into his lane without signaling in the Financial District. He has road rash and a possible fractured rib. Fault is contested under California’s unsafe-lane-change rule, and comparable settlements range from fifty-five to one hundred twenty thousand dollars.',
    firm_brief:
      'Motorcycle, English, Financial District. Road rash + possible rib fracture. Contested fault (unsignaled merge). Comparable range $55K–$120K. Routed to Golden Gate.',
    redactions: 7,
    redaction_categories: { name: 3, phone: 2, address: 1, plate: 1 },
  }),
  buildCase({
    case_id: 'demo-sofia-reyes',
    caller: 'Sofia Reyes',
    accident_type: 'rear_end',
    location: 'Daly City, CA (Bay Area)',
    injuries: 'Lower back strain',
    fault_claim: 'Stopped at light, hit from behind',
    language: 'es',
    score: 63,
    status: 'matched',
    last_event: 'firms_matched',
    est_value: 41000,
    firm_id: 'bay_counsel',
    match_score: 84,
    match_reason: 'General PI / auto specialty; trilingual intake; serves the Bay Area.',
    streams: {
      law: {
        id: 'state-law:ca-sol',
        title: 'CA Statute of Limitations — personal injury',
        subtitle: 'Cal. Civ. Proc. Code § 335.1',
        text: 'Two years from the date of injury to file a personal-injury claim in California.',
        citation: 'Cal. Civ. Proc. Code § 335.1',
        score: 0.95,
      },
      settlement: {
        id: 'settlements:ca-rear-end-low-clear',
        title: 'Rear-end · low severity · clear fault',
        amount_range: '$20,000 – $50,000',
        text: 'Clear-fault rear-end with soft-tissue back strain and conservative treatment settles in the low-to-mid five figures.',
        score: 0.86,
      },
      firm: {
        firm_id: 'bay_counsel',
        reasons: ['General PI / auto', 'Trilingual EN/ES/HI', 'Serves Bay Area'],
        score: 0.84,
      },
      procedure: {
        id: 'procedures:post_accident_72h',
        title: 'First 72 hours after a collision',
        text: 'Seek a medical evaluation, keep treatment records, and document vehicle damage and the other driver’s details.',
        score: 0.81,
      },
    },
    synthesis:
      'Straightforward clear-fault rear-end with a lower-back strain and conservative treatment. Liability is strong; value is modest given soft-tissue-only injuries, with comparable outcomes in the low-to-mid five figures.',
    citations: ['state-law:ca-sol', 'settlements:ca-rear-end-low-clear'],
    verbal_summary:
      'Sofia Reyes was stopped at a light and rear-ended in Daly City, with a lower-back strain. Fault is clear and the two-year filing window is open. Comparable soft-tissue rear-end cases settle between twenty and fifty thousand dollars.',
    firm_brief:
      'Rear-end, Spanish, Daly City. Lower-back strain, clear fault. SoL open. Comparable range $20K–$50K. Routed to Bay Counsel.',
    redactions: 6,
    redaction_categories: { name: 2, phone: 2, address: 1, email: 1 },
  }),
  buildCase({
    case_id: 'demo-linda-park',
    caller: 'Linda Park',
    accident_type: 'auto',
    location: 'Marina District, San Francisco, CA',
    injuries: 'Concussion, shoulder sprain',
    fault_claim: 'T-boned at intersection',
    language: 'en',
    score: 74,
    status: 'matched',
    last_event: 'firms_matched',
    est_value: 86000,
    firm_id: 'pacific_heights',
    match_score: 88,
    match_reason: 'CA auto specialty; serves Marina / Pacific Heights.',
    streams: {
      law: {
        id: 'state-law:ca-right-of-way',
        title: 'CA intersection right-of-way',
        subtitle: 'Cal. Veh. Code § 21800',
        text: 'Right-of-way rules govern intersection collisions; the driver who unlawfully enters or fails to yield bears liability.',
        citation: 'Cal. Veh. Code § 21800',
        score: 0.9,
      },
      settlement: {
        id: 'settlements:ca-tbone-moderate-clear',
        title: 'T-bone · moderate · clear fault',
        amount_range: '$60,000 – $130,000',
        text: 'Intersection T-bone collisions with concussion and orthopedic injury and clear fault settle in the mid-five to low-six figures.',
        score: 0.88,
      },
      firm: {
        firm_id: 'pacific_heights',
        reasons: ['CA auto specialty', 'Serves Marina', 'Bilingual EN/ES'],
        score: 0.88,
      },
      procedure: {
        id: 'procedures:concussion_followup',
        title: 'Concussion follow-up care',
        text: 'Recommend neurology follow-up and symptom logging; concussion documentation strengthens general-damages valuation.',
        score: 0.8,
      },
    },
    synthesis:
      'Intersection T-bone with a concussion and shoulder sprain. Right-of-way rules and clear fault support strong liability; concussion documentation should lift general damages into the mid-five to low-six figures.',
    citations: ['state-law:ca-right-of-way', 'settlements:ca-tbone-moderate-clear'],
    verbal_summary:
      'Linda Park was T-boned at a Marina District intersection, suffering a concussion and shoulder sprain. Fault appears clear under California right-of-way rules, and comparable T-bone settlements range from sixty to one hundred thirty thousand dollars.',
    firm_brief:
      'Auto T-bone, English, Marina District. Concussion + shoulder sprain, clear fault. Comparable range $60K–$130K. Routed to Pacific Heights.',
    redactions: 8,
    redaction_categories: { name: 3, phone: 2, address: 2, dob: 1 },
  }),
];

// --------------------------------------------------------------------------- #
// Bulk caseload — gives EVERY partner firm a full pipeline of varied cases so
// the home queue, Cases view, KPIs, and Moss overview/metrics are populated for
// the demo (live intakes merge over these by case_id).
// --------------------------------------------------------------------------- #
const NAMES = [
  'Carlos Ramirez',
  'Aisha Khan',
  'Daniel Cohen',
  'Lucia Torres',
  'Marcus Webb',
  'Priya Nair',
  'Sofia Marin',
  'Andre Dubois',
  'Hana Kim',
  'Ethan Brooks',
  'Valeria Cruz',
  'Omar Haddad',
  'Grace Liu',
  'Diego Salas',
  'Nora Bishop',
  'Tomas Vega',
  'Renee Adams',
  'Ivan Rios',
  'Mei Chen',
  'Jamal Carter',
  'Paola Mendez',
  'Kevin Olsen',
  'Rosa Iglesias',
  'Sam Patel',
  'Beatriz Lima',
  'Noah Fischer',
  'Camila Reyes',
  'Tariq Aziz',
  'Elena Sokol',
  'Marco Bellini',
];

type Tmpl = {
  type: string;
  injuries: string;
  fault: string;
  lawId: string;
  lawTitle: string;
  lawText: string;
  setId: string;
  setTitle: string;
  range: string;
  procId: string;
  procTitle: string;
  procText: string;
};

const TEMPLATES: Tmpl[] = [
  {
    type: 'rear_end',
    injuries: 'Whiplash, neck and back pain',
    fault: 'Other driver hit me from behind',
    lawId: 'state-law:ca-sol',
    lawTitle: 'CA filing window — personal injury',
    lawText:
      'Two years from the date of injury to file a personal-injury claim in California (CCP §335.1).',
    setId: 'settlements:ca-rear-end-moderate-contested',
    setTitle: 'Rear-end · moderate',
    range: '$45,000 – $95,000',
    procId: 'procedures:post_accident_72h',
    procTitle: 'First 72 hours',
    procText:
      'Document injuries, preserve the police report, avoid recorded statements until represented.',
  },
  {
    type: 't_bone',
    injuries: 'Concussion and shoulder sprain',
    fault: 'They ran the intersection',
    lawId: 'state-law:ca-negligence',
    lawTitle: 'CA comparative negligence',
    lawText: 'California pure comparative negligence — recovery reduced by your share of fault.',
    setId: 'settlements:ca-tbone-high-clear',
    setTitle: 'T-bone · high',
    range: '$120,000 – $250,000',
    procId: 'procedures:documenting_injuries',
    procTitle: 'Documenting injuries',
    procText: 'Photograph injuries and keep all imaging and treatment records.',
  },
  {
    type: 'slip_fall',
    injuries: 'Sprained ankle, ongoing PT',
    fault: 'Wet floor, no warning sign',
    lawId: 'state-law:ca-premises',
    lawTitle: 'CA premises liability',
    lawText: 'Owners owe reasonable care; liability needs notice of the hazard (Civ. Code §1714).',
    setId: 'settlements:ca-slip-fall-med-clear',
    setTitle: 'Slip & fall · moderate',
    range: '$25,000 – $60,000',
    procId: 'procedures:post_slip_fall_48h',
    procTitle: 'First 48 hours after a fall',
    procText: 'Photograph the hazard, request an incident report, see a doctor, keep your shoes.',
  },
  {
    type: 'dog_bite',
    injuries: 'Hand laceration, possible scarring',
    fault: 'Unleashed dog bit me',
    lawId: 'state-law:ca-dog-bite',
    lawTitle: 'CA dog-bite strict liability',
    lawText:
      'California imposes strict liability on dog owners regardless of prior behavior (Civ. Code §3342).',
    setId: 'settlements:ca-dog-bite-med-clear',
    setTitle: 'Dog bite · moderate',
    range: '$35,000 – $90,000',
    procId: 'procedures:post_dog_bite_24h',
    procTitle: 'First 24 hours after a bite',
    procText:
      'Get medical care, report to animal control, identify the owner, photograph injuries.',
  },
  {
    type: 'motorcycle',
    injuries: 'Road rash, wrist fracture',
    fault: 'Car turned left into me',
    lawId: 'state-law:ca-damages',
    lawTitle: 'CA damages',
    lawText: 'Economic and non-economic damages recoverable; no MICRA cap outside med-mal.',
    setId: 'settlements:ca-motorcycle-high-clear',
    setTitle: 'Motorcycle · high',
    range: '$150,000 – $400,000',
    procId: 'procedures:finding_doctor',
    procTitle: 'Finding the right doctor',
    procText: 'See a specialist promptly; consistent treatment supports the claim.',
  },
  {
    type: 'pedestrian',
    injuries: 'Leg fracture, hospitalized',
    fault: 'Hit in the crosswalk',
    lawId: 'state-law:ca-sol',
    lawTitle: 'CA filing window',
    lawText:
      'Two years to file; claims against a public entity require a 6-month government claim.',
    setId: 'settlements:ca-pedestrian-high-clear',
    setTitle: 'Pedestrian · high',
    range: '$200,000 – $500,000',
    procId: 'procedures:post_accident_72h',
    procTitle: 'First 72 hours',
    procText: 'Get imaging, preserve the report, do not give a recorded statement.',
  },
];

const STATUSES = ['matched', 'booked', 'intake', 'matched', 'booked', 'declined'];

function generateCaseload(): Json[] {
  const firms = Object.keys(FIRMS);
  const out: Json[] = [];
  let n = 0;
  for (const firm of firms) {
    for (let i = 0; i < 6; i++) {
      const t = TEMPLATES[n % TEMPLATES.length];
      const caller = NAMES[n % NAMES.length];
      const lang = n % 3 === 0 ? 'es' : 'en';
      const score = 52 + ((n * 17) % 44); // 52–95
      const est =
        score >= 78
          ? 90000 + (n % 5) * 35000
          : score >= 62
            ? 45000 + (n % 4) * 12000
            : 18000 + (n % 4) * 6000;
      const status = STATUSES[n % STATUSES.length];
      out.push(
        buildCase({
          case_id: `demo-${firm}-${i}`,
          caller,
          accident_type: t.type,
          location: 'San Francisco, CA',
          injuries: t.injuries,
          fault_claim: t.fault,
          language: lang,
          score: status === 'declined' ? Math.min(score, 38) : score,
          status,
          last_event: status === 'booked' ? 'booked' : 'firms_matched',
          est_value: est,
          firm_id: firm,
          match_score: Math.min(97, score + 5),
          match_reason: `CA ${t.type.replace('_', ' ')} fit, serves San Francisco${lang === 'es' ? ', bilingual EN/ES' : ''}.`,
          streams: {
            law: {
              id: t.lawId,
              title: t.lawTitle,
              subtitle: 'California',
              text: t.lawText,
              citation: t.lawTitle,
              score: 0.93,
            },
            settlement: {
              id: t.setId,
              title: t.setTitle,
              amount_range: t.range,
              text: `Comparable ${t.type.replace('_', ' ')} outcomes in California.`,
              score: 0.88,
            },
            firm: {
              firm_id: firm,
              reasons: [
                `CA ${t.type.replace('_', ' ')} specialty`,
                'Serves San Francisco',
                lang === 'es' ? 'Bilingual EN/ES' : 'English intake',
              ],
              score: 0.9,
            },
            procedure: { id: t.procId, title: t.procTitle, text: t.procText, score: 0.82 },
          },
          synthesis: `${t.type.replace('_', ' ')} case in San Francisco. ${t.lawText} Comparable settlements ${t.range}.`,
          citations: [t.lawId, t.setId],
          verbal_summary: `${caller} reports a ${t.type.replace('_', ' ')} in San Francisco — ${t.injuries.toLowerCase()}. Comparable settlements range ${t.range}.`,
          firm_brief: `${t.type.replace('_', ' ')}, ${lang === 'es' ? 'Spanish' : 'English'}, San Francisco. ${t.injuries}. Range ${t.range}.`,
          redactions: 4 + (n % 6),
          redaction_categories: { name: 2, phone: 1, address: n % 2 },
        })
      );
      n++;
    }
  }
  return out;
}

DEMO_CASES.push(...generateCaseload());
