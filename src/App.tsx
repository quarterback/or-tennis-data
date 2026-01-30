import { useState, useEffect } from 'react';
import RankingsTable from './RankingsTable';
import { SchoolRanking } from './types';
import {
  fetchSchoolClassifications,
  fetchAllSchoolData,
} from './dataFetcher';
import {
  calculateSchoolStats,
  calculateRankings,
  filterRankingsByClassification,
} from './rankingCalculator';
import './App.css';

function App() {
  const [year, setYear] = useState('2025');
  const [classification, setClassification] = useState('All');
  const [rankings, setRankings] = useState<SchoolRanking[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadRankings();
  }, [year]);

  useEffect(() => {
    if (rankings.length > 0) {
      const filtered = filterRankingsByClassification(rankings, classification);
      setRankings(filtered);
    }
  }, [classification]);

  const loadRankings = async () => {
    setLoading(true);
    setError(null);

    try {
      const schoolMap = await fetchSchoolClassifications();
      const schoolData = await fetchAllSchoolData(year);

      if (schoolData.length === 0) {
        setError(`No data found for ${year}`);
        setRankings([]);
        setLoading(false);
        return;
      }

      const statsMap = calculateSchoolStats(schoolData, schoolMap);
      const allRankings = calculateRankings(statsMap);
      const filtered = filterRankingsByClassification(allRankings, classification);

      setRankings(filtered);
    } catch (err) {
      setError('Failed to load rankings data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <h1>Oregon High School Tennis Rankings</h1>
        <p className="subtitle">Ranked by Adjusted Power Rating (APR)</p>
      </header>

      <div className="filters">
        <div className="filter-group">
          <label htmlFor="year-select">Year:</label>
          <select
            id="year-select"
            value={year}
            onChange={(e) => setYear(e.target.value)}
            disabled={loading}
          >
            <option value="2025">2025</option>
            <option value="2024">2024</option>
            <option value="2023">2023</option>
            <option value="2022">2022</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="classification-select">Classification:</label>
          <select
            id="classification-select"
            value={classification}
            onChange={(e) => setClassification(e.target.value)}
            disabled={loading}
          >
            <option value="All">All</option>
            <option value="6A">6A</option>
            <option value="5A">5A</option>
            <option value="4A/3A/2A/1A">4A/3A/2A/1A</option>
          </select>
        </div>
      </div>

      {loading && <div className="loading">Loading rankings...</div>}
      {error && <div className="error">{error}</div>}
      {!loading && !error && <RankingsTable rankings={rankings} />}

      <div className="legend">
        <h3>Legend</h3>
        <ul>
          <li><strong>WWP:</strong> Weighted Winning Percentage</li>
          <li><strong>OWP:</strong> Opponent Winning Percentage</li>
          <li><strong>APR:</strong> Adjusted Power Rating = (WWP × 0.35) + (OWP × 0.65)</li>
        </ul>
        <h3>Flight Weights</h3>
        <ul>
          <li>1S/1D: 1.0</li>
          <li>2S: 0.75</li>
          <li>2D: 0.50</li>
          <li>3S/3D: 0.25</li>
          <li>4S/4D: 0.10</li>
        </ul>
      </div>
    </div>
  );
}

export default App;
