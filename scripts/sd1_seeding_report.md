# Special District 1 Girls Tennis — 2026 Seeding Report

**Source:** 57 dual matches between SD1 schools (league play only), 2026 season.
SD1 schools: Blanchet, Catlin Gabel, Corbett, Oregon Episcopal (OES), Riverdale,
Riverside, Scappoose, St Helens, Tillamook, Trinity Academy, Valley Catholic,
Westside Christian.

**Per oregontennis.org/sd1-seeding:** coaches set the final seeds; this is the input
data. 1st-flight players/teams get preference for the top 8; 2nd-flight players are
only seeded into the top 8 if they played 1st-flight matches OR were particularly
stellar in their spot. Doubles eligibility requires 2+ league matches with the same
partner.

---

## Top 8 Singles — Recommended Seeds

Sorted by 1st-flight wins (volume of proven play at the top spot), then losses,
then total record. Head-to-head should be used by coaches to break ties.

| Seed | Player | School | Gr | F1 W-L | F2 W-L | Notes |
|---|---|---|---|---|---|---|
| 1 | **Ria Shah** | Catlin Gabel | 9 | 5-0 | 0-0 | Undefeated; beat #2 Rinard head-to-head (Apr 23) |
| 2 | **Nina Rinard** | Riverdale | 11 | 8-1 | 0-0 | Lone loss to Shah; beat #3 Thorne and #4 Nicholas |
| 3 | **Taylor Thorne** | Scappoose | 12 | 8-2 | 0-0 | Losses to Rinard and to #7 Sharan |
| 4 | **Margo Nicholas** | OES | 9 | 5-2 | 0-0 | Losses to Shah and Rinard |
| 5 | **Sanaya Sharan** | Catlin Gabel | 10 | 2-0 | 1-1 | Limited F1 sample but **beat Thorne** at F1 (Apr 28) |
| 6 | **Maria Felez** | Tillamook | 12 | 4-4 | 0-0 | Beat Koss; lost to Shah |
| 7 | **Kelsey Koss** | Westside Christian | 11 | 3-5 | 0-0 | Beat Felez head-to-head |
| 8 | **Emma Frias** | Valley Catholic | 9 | 2-2 | 1-0 | Lost to Shah and Thorne |

### Bubble / strong consideration

| Player | School | Record | Why |
|---|---|---|---|
| **Hailey Clayton** | OES | 1-0 F1, 5-0 F2, **7-0 total** | Undefeated across the season; only one F1 appearance but stellar at F2. Strongest "particularly stellar 2nd flight" candidate. |
| **Rachael Yang** | Valley Catholic | 2-2 F1 | Beat Koss at F1 |
| **Joyce My Nguyen** | Valley Catholic | 1-0 F1, 3-1 F2 | 5-2 overall, beat Felez at F1 |

### Head-to-head (top 8 flight-1 singles)

```
                  Nina R.  Taylor T.  Ria S.   Margo N.  Maria F.  Kelsey K.  Sanaya S.  Emma F.
Nina Rinard       —        W(F1)      L(F1)    W(F1)     .         .          .          .
Taylor Thorne     L(F1)    —          .        .         .         .          L(F1)      W(F1)
Ria Shah          W(F1)    .          —        W(F1)     W(F1)     W(F1)      .          W(F1)
Margo Nicholas    L(F1)    .          L(F1)    —         .         W(F1)      .          .
Maria Felez       .        .          L(F1)    .         —         L(F1)      .          .
Kelsey Koss       .        .          L(F1)    L(F1)     W(F1)     —          .          .
Sanaya Sharan     .        W(F1)      .        .         .         .          —          .
Emma Frias        .        L(F1)      L(F1)    .         .         .          .          —
```

---

## Top 8 Doubles — Recommended Seeds

| Seed | Team | School | F1 W-L | F2 W-L | Notes |
|---|---|---|---|---|---|
| 1 | **Lucy Bergland / Sadie Young** | OES | 3-0 | 3-0 | **6-0 overall**; F1 wins over #3 Kopetz/Sem, #4 Howard/Nelson, and #5 Raab/Saechao |
| 2 | **Amanda Perez / Jiya Mehta** | Catlin Gabel | 5-0 | 0-0 | Undefeated at F1; beat Cici Ji/Ella Li and Raab/Saechao |
| 3 | **Payton Scheidemantel / Maddie Olson** | Blanchet | 7-2 | 0-0 | Most F1 matches; losses to OES (Ji/Li) and CG (Shah/Tyner) |
| 4 | **Brooke Kopetz / Satya Semenchalam** | Valley Catholic | 4-1 | 0-0 | Lone loss to #1 Bergland/Young |
| 5 | **Natalie Howard / Violette Nelson** | Scappoose | 4-2 | 0-0 | Losses to #1 OES and #4 Valley Catholic |
| 6 | **Cici Ji / Ella Li** | OES | 3-1 | 0-0 | Beat Scheidemantel/Olson; lost to Perez/Mehta |
| 7 | **Addison Raab / Meuy Saechao** | St Helens | 4-5 | 1-0 | Tough F1 schedule; quality wins |
| 8 | **Sara Bernabe / Appollonia Munoz** | Riverside | 2-0 | 0-0 | Limited sample but undefeated at F1 |

### Bubble / strong consideration

| Team | School | Record | Why |
|---|---|---|---|
| **Rachael Yang / Satya Semenchalam** | Valley Catholic | 2-0 F1 | Beat Tillamook and St Helens at F1 (note: Semenchalam already paired w/ Kopetz above) |
| **Gracen Tummala / Kate Hawkins** | Westside Christian | 2-0 F1, 2-2 F2 | One F1 win over Riverside |
| **Jia Bhardwaj / Carlie Li** | OES | 3-0 F2, no F1 | Stellar 2nd-flight pair, undefeated |
| **Kyonna Picard / Vanessa Lao** | Scappoose | 3-0 F2, no F1 | Undefeated at F2 |

---

## Method notes

- Data scope: gender_2 (girls) varsity dual matches in `data/2026/` for the 12 SD1
  schools, filtered to meets where both teams are SD1 members.
- Singles record by flight is from `matchTeams` in each meet's `matches.Singles`
  list. A player's flight history is tracked as F1, F2, F3, etc.; only F1 and F2
  are surfaced in the top-8 view.
- Doubles records are keyed by the **player pair** (frozenset of two player IDs on
  the same school), so partner changes generate distinct records.
- Eligibility: doubles teams need 2+ league matches with the same partner (per
  SD1 rules); single-match doubles teams are filtered out.
- Final seeds remain a coach decision per the SD1 page; this report shows inputs.

Generated by `scripts/sd1_seeding_report.py`.
