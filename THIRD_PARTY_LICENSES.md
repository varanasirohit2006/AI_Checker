# Third-Party Licenses & Attribution

> Maintained per `AGENTS.md` Guardrail #2: study the cloned source in `research/<repo>`,
> rebuild behaviour in our own modules, and record every license + attribution here.
> Any direct code reuse must be explicitly permitted by the license below.

## Repositories (REA targets)

| # | Repo | URL | License | Commit (verified) | Verified On | How We Use It |
|---|------|-----|---------|-------------------|-------------|---------------|
| 1 | Binoculars | https://github.com/ahans30/Binoculars | BSD-3-Clause | `c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8` (2024-05-14) | 2026-11-23 | REA rebuild of observer/performer score → `detectors/binoculars.py` |
| 2 | fast-detect-gpt | https://github.com/baoguangsheng/fast-detect-gpt | MIT (© 2023 Bao Guangsheng, verified in `LICENSE`) | `971b05202bac2bb504d60c0ac0812fea7a8f7c82` (2026-02-07) | 2026-11-23 | REA rebuild → `detectors/fastdetect.py` |
| 3 | detecting-fake-text (GLTR) | https://github.com/HendrikStrobelt/detecting-fake-text | Apache-2.0 (to verify) | | | REA rebuild → `detectors/gltr_ranks.py` |
| 4 | copydetect | https://github.com/blingenf/copydetect | MIT | commit d364585 | 2026-11-23 | REA rebuild (word-token winnowing) → `similarity/winnow.py` |
| 5 | dolos | https://github.com/dodona-edu/dolos | MIT | | 2026-11-23 | REA UX & API contract spec (fragment schema) |
| 6 | chatgpt-comparison-detection (HC3) | https://github.com/Hello-SimpleAI/chatgpt-comparison-detection | Code: MIT / Data: CC-BY-SA | `1f8c15c28f87e09a5abfd86ee6e15005dc7d2119` | 2026-11-24 | REA rebuild (RoBERTa classifier) → `detectors/roberta_hc3.py` & 3-signal fusion |
| 7 | gpt-2-output-dataset | https://github.com/openai/gpt-2-output-dataset | MIT (to verify) | | | Iteration 2: baseline test harness |
| 8 | datasketch | https://github.com/ekzhu/datasketch | MIT (verified v2.0.0) | | 2026-11-23 | Direct install (MinHash LSH candidate search) → `similarity/lsh.py` |
| 9 | sentence-transformers | https://github.com/UKPLab/sentence-transformers | Apache-2.0 (verified v6.3.0) | | 2026-11-23 | Direct install (MiniLM embeddings) → `similarity/semantic.py` |
| 10 | semantic-plagiarism-detector | https://github.com/XYR05/semantic-plagiarism-detector | MIT (verified) | | 2026-11-23 | Architecture blueprint (parsing/chunking/FAISS thresholds) |

## Direct Libraries (not counted in the 10)

| Library | License | Purpose |
|---------|---------|---------|
| faiss-cpu | MIT (verified v1.16.0) | vector search for paraphrase detection → `similarity/semantic.py` |
| pdfplumber | MIT | PDF text + layout extraction |
| python-docx | MIT | DOCX text + formatting inspection |
| datasketch | MIT | MinHash + LSH candidate search |
| sentence-transformers | Apache-2.0 | multilingual MiniLM embeddings |
| confusable-homoglyphs | MIT | Unicode confusable mappings for Red Flags (verified 3.3.1, 2026-11-23) |
| reportlab | BSD | Synthetic PDF fixture generation only (tests/fixtures, verified 5.1.0) |
| scipy / scikit-learn / matplotlib / datasets | BSD / BSD / PSF-style / Apache-2.0 | Upstream fast-detect-gpt import chain only (installed 2026-11-23); not used by our scoring code except scipy.stats.norm in the Fast-DetectGPT probability mapping |
| fastapi / celery / rq / redis / psycopg2 | MIT/BSD | backend stack |
| next.js / tailwindcss / shadcn/ui | MIT | frontend stack |

## Model Weights

| Model | Hub ID | License | Used By |
|-------|--------|---------|---------|
| Falcon-7B (observer) | tiiuae/falcon-7b | Apache-2.0 (weights; TII Falcon License 1.0 historically — verify at download time) | Binoculars default observer |
| Falcon-7B-Instruct (performer) | tiiuae/falcon-7b-instruct | Apache-2.0 (verify at download time) | Binoculars default performer |

## Rules

1. Never copy source code verbatim into our modules unless the license explicitly
   permits it AND the notice is reproduced above the copied block.
2. Every new third-party dependency or weight download must be added to this file
   **before** it is used in committed code.
3. HC3 data (CC-BY-SA) may be used for calibration only; share-alike obligations apply.
4. Verify each license file inside `research/<repo>` — do not trust the README alone.


---

## Full License Texts & Copyright Notices

### 1. Binoculars (BSD-3-Clause)
Copyright (c) 2024, Abhimanyu Hans, Avi Schwarzschild, Chulin Xie, Saeed Mahloujifar, Bo Li, Tom Goldstein.
All rights reserved.
Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

### 2. Fast-DetectGPT (MIT)
Copyright (c) 2023 Bao Guangsheng.
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

### 3. Copydetect (MIT)
Copyright (c) 2020 Jonathan Bailey.
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

### 4. Dolos (MIT)
Copyright (c) 2020 Dodona, Ghent University.
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

### 5. Datasketch (MIT)
Copyright (c) 2016 Eric Zhu.
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

### 6. Sentence-Transformers (Apache 2.0)
Copyright (c) 2019 Ubiquitous Knowledge Processing (UKP) Lab, Technische Universität Darmstadt.
Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0.

### 7. FAISS (MIT)
Copyright (c) Meta Platforms, Inc. and affiliates.
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

### 8. ReportLab (BSD-3-Clause)
Copyright (c) 2000-2024, ReportLab Inc.
All rights reserved.
Redistribution and use in source and binary forms, with or without modification, are permitted provided that the copyright notices and conditions are met.
