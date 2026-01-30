# Oregon High School Tennis Rankings

A comprehensive rankings system for Oregon high school tennis teams using a custom Adjusted Power Rating (APR) formula.

## Features

- **Automated Rankings Calculation**: Computes WWP, OWP, and APR scores for all schools
- **Multi-Year Support**: View rankings from 2022-2025
- **Classification Filtering**: Filter by 6A, 5A, or 4A/3A/2A/1A classifications
- **OSAA-Style Interface**: Clean, professional table design matching official OSAA rankings
- **Responsive Design**: Works on desktop and mobile devices

## Ranking Formula

### Flight Weights
- 1S/1D: 1.0
- 2S: 0.75
- 2D: 0.50
- 3S/3D: 0.25
- 4S/4D: 0.10

### Calculations
1. **WWP (Weighted Winning Percentage)**: Sum of flight weights won ÷ Sum of flight weights played
2. **OWP (Opponent Winning Percentage)**: Average WWP of all opponents faced
3. **APR (Adjusted Power Rating)**: (WWP × 0.35) + (OWP × 0.65)

Schools are ranked by APR score from highest to lowest.

## Setup Instructions

### 1. Configure GitHub Repository

In `src/dataFetcher.ts`, update the GitHub username:

```typescript
const GITHUB_OWNER = 'YOUR_GITHUB_USERNAME'; // Replace with your GitHub username
```

### 2. Repository Structure

Your `or-tennis-data` GitHub repository should be structured as follows:

```
or-tennis-data/
├── master_school_list.csv
├── 2025/
│   ├── school1.json
│   ├── school2.json
│   └── ...
├── 2024/
│   ├── school1.json
│   └── ...
├── 2023/
└── 2022/
```

### 3. Data Format

**master_school_list.csv**: Maps school IDs to classifications and leagues
```csv
schoolId,schoolName,classification,league
75097,Grants Pass,6A,Southwest (6A-7)
74728,Baker,4A/3A/2A/1A,Special District 5
```

**School JSON files**: Match data for each school
```json
{
  "schoolId": "75097",
  "schoolName": "Grants Pass",
  "matchCollections": [
    {
      "matches": [
        {
          "matchTypeId": 1,
          "homeTeamScore": 6,
          "awayTeamScore": 0,
          "homeTeamId": "75097",
          "awayTeamId": "75366"
        }
      ]
    }
  ]
}
```

**matchTypeId values**:
- 1: 1S (Singles 1)
- 2: 1D (Doubles 1)
- 3: 2S (Singles 2)
- 4: 2D (Doubles 2)
- 5: 3S (Singles 3)
- 6: 3D (Doubles 3)
- 7: 4S (Singles 4)
- 8: 4D (Doubles 4)

## Installation

```bash
npm install
```

## Development

```bash
npm run dev
```

## Build for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

## Usage

1. Select a year from the dropdown (2022-2025)
2. Select a classification filter (All, 6A, 5A, or 4A/3A/2A/1A)
3. View the rankings table with:
   - Rank
   - School name
   - Classification
   - League
   - Overall record (wins-losses)
   - WWP score
   - OWP score
   - APR score

## Technologies Used

- React 18 with TypeScript
- Vite for fast development and building
- GitHub as data source
- Responsive CSS for mobile and desktop
