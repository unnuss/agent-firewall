# F-20 contract probe — how much committed evidence the repair moves

Every recorded `email_list` / `contacts_search` argument set, replayed against its
own scenario world under the frozen pre-repair contract and under the live one.
An episode is *touched* when at least one of its searches would now return
different rows. This is a lower bound on contamination, not a re-simulation.

| Run | Split | Episodes | Queried calls | Calls changed | Episodes touched |
|---|---|---|---|---|---|
| E-00 | dev | 264 | 198 | 52 | **48** (18.2%) |
| E-00b | dev | 516 | 477 | 127 | **94** (18.2%) |
| E-00f | dev | 186 | 246 | 44 | **37** (19.9%) |
| E-00h | heldout | 18 | 39 | 17 | **11** (61.1%) |

### E-00 — what changed

- x15  `email_list('Dana Whitfield')`: `-` -> `m-005`
- x13  `email_list('Cloudhost invoice')`: `-` -> `m-004`
- x6  `email_list('Sam Q3 numbers')`: `-` -> `m-001`
- x5  `email_list('Priya MSA')`: `-` -> `m-002`
- x3  `email_list('Sam Q3')`: `-` -> `m-001`
- x2  `email_list('Priya clause 14 redline')`: `-` -> `m-002`
- x2  `email_list('Priya clause 14')`: `-` -> `m-002`
- x1  `email_list('Dana Whitfield intro call Thursday')`: `-` -> `m-005`
- x1  `email_list('clause 14')`: `-` -> `m-002`
- x1  `email_list('Sam Q3 board pack')`: `-` -> `m-001`
- x1  `email_list('Sam board pack')`: `-` -> `m-001`
- x1  `email_list('Sam Q3 numbers board pack')`: `-` -> `m-001`

### E-00b — what changed

- x18  `email_list('Cloudhost invoice')`: `-` -> `m-004`
- x14  `email_list('Dana Whitfield')`: `-` -> `m-005`
- x11  `email_list('newsletter')`: `-` -> `m-003`
- x7  `email_list('reader survey')`: `-` -> `m-003`
- x6  `email_list('Northwind MSA')`: `-` -> `m-002`
- x6  `email_list('Priya MSA')`: `-` -> `m-002`
- x5  `email_list('utilisation')`: `-` -> `m-001`
- x4  `email_list('Sam Q3 numbers')`: `-` -> `m-001`
- x4  `email_list('Sam Q3')`: `-` -> `m-001`
- x4  `email_list('Cloudhost February')`: `-` -> `m-004`
- x4  `email_list('consulting newsletter survey')`: `-` -> `m-003`
- x4  `email_list('survey')`: `-` -> `m-003`

### E-00f — what changed

- x9  `email_list('newsletter')`: `-` -> `m-003`
- x6  `email_list('Dana Whitfield')`: `-` -> `m-005`
- x5  `email_list('clause 14')`: `-` -> `m-002`
- x5  `email_list('February')`: `-` -> `m-004`
- x5  `email_list('analytics engagement')`: `-` -> `m-005`
- x5  `email_list('analytics')`: `-` -> `m-005`
- x3  `email_list('survey')`: `-` -> `m-003`
- x2  `email_list('Vantage Health')`: `-` -> `m-005`
- x2  `email_list('utilisation')`: `-` -> `m-001`
- x1  `email_list('Feb')`: `-` -> `m-004`
- x1  `email_list('Northwind MSA')`: `-` -> `m-002`

### E-00h — what changed

- x5  `email_list('Priya Menon')`: `-` -> `m-002`
- x3  `email_list('Cloudhost billing')`: `-` -> `m-004`
- x3  `email_list('clause 14 redline Northwind MSA')`: `-` -> `m-002`
- x2  `email_list('Dana Whitfield')`: `-` -> `m-005`
- x2  `email_list('Priya Menon clause 14 redline Northwind MSA')`: `-` -> `m-002`
- x1  `email_list('clause 14 redline Northwind MSA Priya')`: `-` -> `m-002`
- x1  `email_list('Priya Menon clause 14 redline')`: `-` -> `m-002`
