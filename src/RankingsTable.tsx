import { SchoolRanking } from './types';

interface RankingsTableProps {
  rankings: SchoolRanking[];
}

export default function RankingsTable({ rankings }: RankingsTableProps) {
  return (
    <div className="table-container">
      <table className="rankings-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>School</th>
            <th>Classification</th>
            <th>League</th>
            <th>Overall Record</th>
            <th>WWP</th>
            <th>OWP</th>
            <th>APR</th>
          </tr>
        </thead>
        <tbody>
          {rankings.length === 0 ? (
            <tr>
              <td colSpan={8} className="no-data">No data available</td>
            </tr>
          ) : (
            rankings.map((ranking) => (
              <tr key={ranking.schoolId}>
                <td className="rank-cell">{ranking.rank}</td>
                <td className="school-cell">{ranking.schoolName}</td>
                <td className="classification-cell">{ranking.classification}</td>
                <td className="league-cell">{ranking.league}</td>
                <td className="record-cell">
                  {ranking.wins}-{ranking.losses}
                </td>
                <td className="stat-cell">{ranking.wwp.toFixed(3)}</td>
                <td className="stat-cell">{ranking.owp.toFixed(3)}</td>
                <td className="apr-cell">{ranking.apr.toFixed(3)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
