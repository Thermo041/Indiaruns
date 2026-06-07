export type RankingPayload = {
  generated_at?: string;
  summary: {
    scanned_candidates: number;
    top_k: number;
    reference_date: string;
    max_raw_score: number;
    min_raw_score: number;
  };
  records: CandidateRecord[];
};

export type CandidateRecord = {
  candidate_id: string;
  rank: number;
  score: number;
  raw_score: number;
  reasoning: string;
  profile: {
    name: string;
    headline: string;
    current_title: string;
    current_company: string;
    location: string;
    country: string;
    years_of_experience: number;
    industry: string;
  };
  top_skills: {
    name: string;
    proficiency: string;
    endorsements: number;
    duration_months: number;
  }[];
  signals: {
    open_to_work: boolean;
    last_active_date: string;
    days_inactive: number | null;
    recruiter_response_rate: number;
    avg_response_time_hours: number;
    notice_period_days: number;
    preferred_work_mode: string;
    willing_to_relocate: boolean;
    github_activity_score: number;
    interview_completion_rate: number;
    offer_acceptance_rate: number;
    saved_by_recruiters_30d: number;
    profile_views_received_30d: number;
    salary_min_lpa: number;
    salary_max_lpa: number;
  };
  components: Record<string, number>;
  technical_components: Record<string, number>;
  behavior_components: Record<string, number>;
  penalties: Record<string, number>;
};

