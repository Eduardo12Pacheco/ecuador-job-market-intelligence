# Zero-match taxonomy skills — development sample

- source: himalayas | attribution: https://himalayas.app
- dataset: development_sample | 20 records | one page (limit=20, offset=0) | complete: false
- snapshot: cap_0370798f7af4b0e3 | taxonomy: technical-skills-0.1.0 | matcher: keyword-baseline-0.1.0
- analysis: descriptive keyword evidence only (see `descriptive-development-sample-0.1.0.json` under `data/analytics/`)
- warning: bounded single-page development sample — NOT market coverage, NOT correlation, NOT causality, NOT representative
- streamlit: pending — the interactive Streamlit demo is not implemented; these offline artifacts are the baseline visualizations

A taxonomy skill with **zero matches in this sample** is **not evidence** that jobs lack the skill: it means the deterministic keyword baseline found no occurrence of the skill's terms in the searched fields of any of the 20 records. This is distinct from `no_evidence` records (records where the taxonomy found no keyword at all). This sample has 0 `no_evidence` records and 4 zero-match skills.

| skill_id | name | category | matched_records |
|---|---|---|---|
| skill.cpp | C++ | programming_language | 0 |
| skill.csharp | C# | programming_language | 0 |
| skill.git | Git | developer_tool | 0 |
| skill.java | Java | programming_language | 0 |

Summary: 4 of the 37 taxonomy skills have zero matches in this development sample.
