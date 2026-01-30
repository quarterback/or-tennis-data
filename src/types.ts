export interface School {
  id: string;
  name: string;
  classification: string;
  league: string;
}

export interface Match {
  matchTypeId: number;
  homeTeamScore: number;
  awayTeamScore: number;
  homeTeamId: string;
  awayTeamId: string;
}

export interface MatchCollection {
  matches: Match[];
}

export interface SchoolData {
  schoolId: string;
  schoolName: string;
  matchCollections: MatchCollection[];
}

export interface FlightResult {
  matchTypeId: number;
  won: boolean;
  played: boolean;
}

export interface SchoolStats {
  schoolId: string;
  schoolName: string;
  classification: string;
  league: string;
  totalFlightsWon: number;
  totalFlightsPlayed: number;
  wwp: number;
  opponents: string[];
  wins: number;
  losses: number;
}

export interface SchoolRanking extends SchoolStats {
  owp: number;
  apr: number;
  rank: number;
}

export const FLIGHT_WEIGHTS: Record<number, number> = {
  1: 1.0,   // 1S
  2: 1.0,   // 1D
  3: 0.75,  // 2S
  4: 0.50,  // 2D
  5: 0.25,  // 3S
  6: 0.25,  // 3D
  7: 0.10,  // 4S
  8: 0.10,  // 4D
};
