import { SchoolData, School, SchoolStats, SchoolRanking, FLIGHT_WEIGHTS } from './types';

export function calculateSchoolStats(
  schoolData: SchoolData[],
  schoolMap: Map<string, School>
): Map<string, SchoolStats> {
  const statsMap = new Map<string, SchoolStats>();

  for (const data of schoolData) {
    const schoolInfo = schoolMap.get(data.schoolId);
    if (!schoolInfo) continue;

    let totalWeightedWins = 0;
    let totalWeightedPlayed = 0;
    const opponents = new Set<string>();
    let wins = 0;
    let losses = 0;

    for (const collection of data.matchCollections || []) {
      for (const match of collection.matches || []) {
        const weight = FLIGHT_WEIGHTS[match.matchTypeId] || 0;
        if (weight === 0) continue;

        totalWeightedPlayed += weight;

        const isHome = match.homeTeamId === data.schoolId;
        const opponentId = isHome ? match.awayTeamId : match.homeTeamId;
        const schoolScore = isHome ? match.homeTeamScore : match.awayTeamScore;
        const opponentScore = isHome ? match.awayTeamScore : match.homeTeamScore;

        if (opponentId) {
          opponents.add(opponentId);
        }

        if (schoolScore > opponentScore) {
          totalWeightedWins += weight;
          wins++;
        } else if (schoolScore < opponentScore) {
          losses++;
        }
      }
    }

    const wwp = totalWeightedPlayed > 0 ? totalWeightedWins / totalWeightedPlayed : 0;

    statsMap.set(data.schoolId, {
      schoolId: data.schoolId,
      schoolName: schoolInfo.name,
      classification: schoolInfo.classification,
      league: schoolInfo.league,
      totalFlightsWon: totalWeightedWins,
      totalFlightsPlayed: totalWeightedPlayed,
      wwp,
      opponents: Array.from(opponents),
      wins,
      losses,
    });
  }

  return statsMap;
}

export function calculateRankings(statsMap: Map<string, SchoolStats>): SchoolRanking[] {
  const rankings: SchoolRanking[] = [];

  for (const stats of statsMap.values()) {
    let opponentWWPSum = 0;
    let opponentCount = 0;

    for (const opponentId of stats.opponents) {
      const opponentStats = statsMap.get(opponentId);
      if (opponentStats) {
        opponentWWPSum += opponentStats.wwp;
        opponentCount++;
      }
    }

    const owp = opponentCount > 0 ? opponentWWPSum / opponentCount : 0;
    const apr = (stats.wwp * 0.35) + (owp * 0.65);

    rankings.push({
      ...stats,
      owp,
      apr,
      rank: 0,
    });
  }

  rankings.sort((a, b) => b.apr - a.apr);

  rankings.forEach((ranking, index) => {
    ranking.rank = index + 1;
  });

  return rankings;
}

export function filterRankingsByClassification(
  rankings: SchoolRanking[],
  classification: string
): SchoolRanking[] {
  if (classification === 'All') {
    return rankings;
  }

  const filtered = rankings.filter(r => r.classification === classification);

  filtered.forEach((ranking, index) => {
    ranking.rank = index + 1;
  });

  return filtered;
}
