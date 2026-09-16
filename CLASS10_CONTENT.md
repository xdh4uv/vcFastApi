# Class 10 adaptive coursework coverage

Every chapter has five revision cards and 45 original MCQs. Each card provides a concept explanation, worked example, common mistake and checklist. Each question has a server-only answer and an explanation revealed after submission. Five-question focused sets use the existing chapter-scoped adaptive policy.

| Chapter | Revision concepts |
| --- | --- |
| 1. Real Numbers | Prime factorisation; HCF; LCM; irrational numbers; HCF–LCM relationship |
| 2. Polynomials | Zeroes; degree/graphs; sum of zeroes; product/coefficient relations; forming quadratics |
| 3. Pair of Linear Equations | Substitution; graphical solutions; consistency; elimination; modelling |
| 4. Quadratic Equations | Factorisation; discriminant; nature of roots; zero product/formula; word problems |
| 5. Arithmetic Progressions | Common difference; nth term; sum; term position; recovering an AP |
| 6. Triangles | Similarity criteria; scale; proportionality; three side ratios; similar subtriangles |
| 7. Coordinate Geometry | Distance; midpoint; internal section; equidistance; coordinate figures |
| 8. Introduction to Trigonometry | Standard angles; right-triangle ratios; identities; reciprocals; expressions |
| 9. Applications of Trigonometry | Elevation/depression; heights; horizontal distances; eye height; two observation points |
| 10. Circles | Radius/tangent; equal tangents; tangent count; tangent lengths; angles |
| 11. Areas Related to Circles | Circle/ring area; sectors; arcs; sector perimeter; segments |
| 12. Surface Areas and Volumes | Cylinders; cones; hemispheres; combined volume; exposed area |
| 13. Statistics | Class marks; cumulative frequency; grouped mean; median; mode |
| 14. Probability | Equally likely outcomes; complements; random draws; coin sample spaces; two dice |

Total adaptive content: **70 revision cards and 630 questions**. The original 70 fixed chapter-test questions and 14 final-test questions remain unchanged, for **714 questions across both assessment types**. Existing lesson notes, source links, read markers, levels and results are preserved.

## Source alignment and limits

The [NCERT Class X Mathematics contents, 2026–27 reprint](https://www.ncert.nic.in/textbook/pdf/jemh1ps.pdf) were checked on 17 September 2026 for the 14-chapter sequence and major headings. The [Statistics chapter](https://www.ncert.nic.in/textbook/pdf/jemh113.pdf) was available for checking grouped-data topics. Some other NCERT chapter PDF requests timed out; each existing lesson retains its official chapter link for the complete treatment. Questions, examples and explanations are newly authored, not copied textbook exercises.

This completes adaptive flow coverage of the current course. It is a finite starter bank, not exhaustive curriculum instruction or a board-exam simulator. Numerical variants reuse an authored problem pattern; they are fresh question IDs, not proof of independent psychometric evidence. Difficulty labels and score rules are product heuristics. Geometry and graph questions use text descriptions rather than diagrams or drawing tasks. There is no free-response proof grading, teacher review, timed exam, or LLM integration. Some questions apply prerequisite ideas to the chapter, such as quadratic formula, Pythagoras and volume conservation; they do not assert an exam-year syllabus requirement.

## Validation

Run `python -m unittest discover -s tests`. Chapters 1–2 keep their existing answer-key checks; `tests/class10_answer_keys.py` contains independently worked literal answers for all 540 new questions. Coverage tests check every baseline label, global question-ID uniqueness, 45 questions per chapter, three variants per concept/difficulty, matching generated artifacts and valid probability distractors.

End-to-end regressions cover each chapter's availability, answer redaction, draft recovery, backend grading, history isolation, repeat evidence, bank exhaustion and labeled revision. Adaptive submissions never count toward the final gate. All 14 official chapter tests are required; reset clears all results and derived evidence while retaining read markers. Publication is tested on an isolated Neon branch before the application database, using the runtime role to verify retrieval access.

## Publishing

On an environment with adaptive schema 002 already applied:

```text
python -m scripts.build_class10_banks
python -m unittest discover -s tests
python -m scripts.seed_adaptive --bank all --content-only
python -m scripts.verify_adaptive_db --bank all
```

Use the existing schema owner's direct connection for publication. All banks publish atomically and repeated publication is safe. No new table, index, API route or frontend component is needed. The existing UI discovers newly published chapters on the next request.

Published all 14 banks to the application's vchitr-main database on 17 September 2026 after isolated Neon validation. Runtime-role retrieval was verified. Existing course documents, attempts, preferences and read markers were unchanged.
