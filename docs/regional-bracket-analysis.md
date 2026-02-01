# Oregon Tennis Regional Bracket Analysis

## Executive Summary

Regional bracket optimization for Oregon high school tennis could reduce first-round travel by **44.8% in 4A/3A/2A/1A** and **33-37% in 5A/6A**—comparable to findings from baseball/softball analysis.

| Classification | Strict Seeding | Regional Optimal | Savings |
|----------------|----------------|------------------|---------|
| 4A/3A/2A/1A    | 11,531 mi      | 6,369 mi         | **44.8%** |
| 5A             | 4,756 mi       | 3,156 mi         | **33.6%** |
| 6A             | 3,058 mi       | 1,921 mi         | **37.2%** |

---

## The Problem: Extreme Travel in Combined Classifications

The 4A/3A/2A/1A combined classification creates the worst travel scenarios because it spans schools from Baker City to Brookings, Nyssa to Astoria.

### Worst Strict-Seeding Matchups (2022-2025)

| Distance | Matchup | Year |
|----------|---------|------|
| 331 mi | #4 Baker vs #13 North Bend | 2025 Girls |
| 320 mi | #3 St Mary's (Medford) vs #14 Four Rivers (Ontario) | 2023 Boys |
| 319 mi | #3 Philomath vs #14 Ontario | 2024 Girls |
| 308 mi | #5 St Mary's (Medford) vs #12 Pendleton | 2024 Girls |
| 306 mi | #4 Sutherlin vs #13 Vale | 2023 Girls |
| 304 mi | #2 St Mary's (Medford) vs #15 Baker | 2024 Boys |
| 304 mi | #1 St Mary's (Medford) vs #16 Baker | 2025 Boys |

These are one-way distances. Round-trip with team travel means 600+ miles for a single match.

---

## Comparison to Baseball/Softball Findings

| Metric | Baseball/Softball | Tennis 4A-1A | Tennis 5A |
|--------|-------------------|--------------|-----------|
| Travel reduction potential | 39.3% | **44.8%** | 33.6% |
| Worst single matchup | 387 mi | 331 mi | 229 mi |
| Seeds 9-16 QF rate | 11.5% | N/A* | N/A* |

*Tennis uses individual tournaments, not team brackets. If OSAA adopted team playoffs, similar patterns would likely emerge.

**Key insight:** Tennis travel burden is WORSE than baseball/softball due to combined classifications spanning the entire state.

---

## Year-by-Year Analysis: 4A/3A/2A/1A

### 2023 Boys: Most Dramatic Savings

| Mode | Total Miles |
|------|-------------|
| Strict seeding | 1,914 mi |
| Regional optimal | 516 mi |
| **Savings** | **1,398 mi (73.1%)** |

**What changed:**
- Marist Catholic plays nearby Creswell instead of distant Riverside
- St Mary's plays Klamath Union (56 mi) instead of Four Rivers/Ontario (320 mi)
- Nyssa plays Four Rivers (10 mi) instead of Klamath Union (267 mi)

### 2022 Girls: Second-Best Improvement

| Mode | Total Miles |
|------|-------------|
| Strict seeding | 1,034 mi |
| Regional optimal | 375 mi |
| **Savings** | **659 mi (63.7%)** |

---

## Geographic Reality

Oregon's tennis-playing schools cluster into distinct regions:

**Portland Metro:** Catlin Gabel, OES, Valley Catholic, Riverdale, Parkrose
**Willamette Valley:** Philomath, Stayton, Cascade, Creswell, Marist
**Southern Oregon:** St Mary's, Cascade Christian, Sutherlin, Ashland, Klamath Union
**Eastern Oregon:** Nyssa, Ontario, Vale, Baker, Pendleton, Weston-McEwen, Irrigon

Strict seeding regularly forces cross-state matchups (Portland to Eastern Oregon, Southern Oregon to Eastern Oregon) when same-region alternatives exist.

---

## The Competitive Argument

From baseball/softball analysis:
- Seeds 1-4 advance to semifinals **76%** of the time
- Seeds 13-16 reach quarterfinals only **3%** of the time
- No seed 13-16 has reached a final

**Implication:** Swapping opponents within the 9-16 seed range has minimal competitive impact. The cream rises regardless of first-round matchup.

Tennis is arguably MORE predictable than team sports (less randomness in individual performance), making the case for regional swapping even stronger.

---

## Proposed Format for Tennis

### Option A: Flex Tier Regional Swapping (Recommended for 5A, 4A-1A)

1. **Seeds 1-4:** Protected positioning (play seeds 13-16)
2. **Seeds 5-8:** Flexible matching with seeds 9-12 based on geography
3. **Seeds 9-16:** Treated as "peer group" for assignment purposes
4. **Constraint:** No same-league first-round matchups

### Option B: Regional Pods (More Aggressive)

1. **East Pod:** Schools east of Cascades
2. **West Pod:** Willamette Valley and Coast
3. **South Pod:** Southern Oregon
4. **Metro Pod:** Portland area

First round within pods, bracket merges for quarterfinals.

---

## Why 6A Needs This Less

6A schools are concentrated in Portland metro and larger cities:
- Shorter average distances between ranked teams
- Fewer extreme outliers (Grants Pass, Roseburg are the exceptions)
- 37% savings still meaningful but less urgent

---

## Implementation Considerations

### What Changes for Coaches/ADs

1. Bracket announcement includes "regional assignment" note
2. First-round opponent determined by geography, not strict seed pairing
3. Competitive seeding preserved (top 4 still have easiest paths)

### What Stays the Same

1. Power Index determines seeding order
2. Auto-bids for league champions
3. Bracket position 1-4 protected
4. All matches count equally for advancement

---

## Appendix: Sample Regional Brackets

### 2023 Boys 4A-1A: Strict vs Regional

**Strict Seeding (1,914 miles total):**
```
#1 Marist Catholic (Eugene) vs #16 Riverside (Boardman)    207 mi
#2 OES (Portland) vs #15 Ontario                          299 mi
#3 St Mary's (Medford) vs #14 Four Rivers (Ontario)       320 mi
#4 Nyssa vs #13 Klamath Union                             267 mi
#5 Catlin Gabel (Portland) vs #12 Baker                   242 mi
#6 The Dalles vs #11 Philomath                            129 mi
#7 Weston-McEwen (Athena) vs #10 Creswell                 258 mi
#8 Stanfield vs #9 Cascade (Turner)                       193 mi
```

**Regional Optimized (516 miles total):**
```
#1 Marist Catholic vs Creswell                             10 mi
#2 OES vs Cascade                                          48 mi
#3 St Mary's vs Klamath Union                              56 mi
#4 Nyssa vs Four Rivers                                    10 mi
#5 Catlin Gabel vs Philomath                               75 mi
#6 The Dalles vs Riverside                                 73 mi
#7 Weston-McEwen vs Baker                                  78 mi
#8 Stanfield vs Ontario                                   164 mi
```

**Savings: 1,398 miles (73%)**

---

## Data Sources

- School coordinates: OpenStreetMap/Nominatim geocoding
- Rankings: Oregon Tennis Power Index (2022-2025)
- Distance calculation: Haversine formula (great-circle distance)
- Analysis period: 8 tournaments (4 years × 2 genders) per classification
