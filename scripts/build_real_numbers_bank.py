"""Reproducible, original starter questions. Arithmetic checked during construction."""
import json
from math import gcd, lcm
from pathlib import Path

COURSE = "ncert-maths-10-v1"
concepts = [
    dict(id="prime-factorisation", title="Prime factorisation", legacyLabels=["prime factors"],
         explanation="Break a positive integer into prime factors. A perfect square has even prime exponents; a perfect cube has exponents divisible by three.",
         example=dict(problem="Find the least multiplier that makes 72 a square.", steps=["72 = 2³ × 3².", "The exponent of 2 is odd. Multiply by 2.", "72 × 2 = 144 = 12²."]),
         commonMistake="Adding to the number does not repair prime exponents in its factorisation.", checklist=["Factor completely into primes.", "Inspect each exponent.", "Multiply or divide as the question requests."]),
    dict(id="hcf", title="Highest common factor", legacyLabels=["HCF"],
         explanation="HCF uses only shared prime factors, each with its smaller exponent. It divides both numbers exactly.",
         example=dict(problem="Find the HCF of 48 and 72.", steps=["48 = 2⁴ × 3; 72 = 2³ × 3².", "Take 2³ × 3 = 24.", "Both 48/24 = 2 and 72/24 = 3 are integers."]),
         commonMistake="Choosing the larger exponents gives the LCM, not the HCF.", checklist=["Identify common primes.", "Take their smaller exponents.", "Check that the result divides both numbers."]),
    dict(id="lcm", title="Lowest common multiple", legacyLabels=["LCM"],
         explanation="LCM uses every prime present, each with its largest exponent. It is the first positive time that repeating integer cycles align.",
         example=dict(problem="Two bells ring every 6 and 8 minutes. When do they next ring together?", steps=["6 = 2 × 3; 8 = 2³.", "LCM = 2³ × 3 = 24.", "They next ring together after 24 minutes."]),
         commonMistake="The product is a common multiple, but may not be the least common multiple.", checklist=["List all prime factors.", "Use their largest exponents.", "Check divisibility by each given number."]),
    dict(id="irrational-numbers", title="Irrational numbers", legacyLabels=["irrational numbers"],
         explanation="A rational number is p/q for integers p and q ≠ 0. The square root of a prime is irrational. Rational operations can sometimes cancel an irrational term.",
         example=dict(problem="Why is √3 + 2 irrational?", steps=["Assume √3 + 2 is rational.", "Subtracting rational 2 would make √3 rational.", "But √3 is irrational. This contradiction proves the claim."]),
         commonMistake="Two irrational numbers can have a rational product: √3 × √3 = 3.", checklist=["Simplify the expression first.", "Check whether irrational terms cancel.", "In a contradiction proof, start with a fraction in lowest terms."]),
    dict(id="hcf-lcm-relation", title="HCF–LCM relationship", legacyLabels=["HCF–LCM relation"],
         explanation="For two positive integers a and b, HCF(a,b) × LCM(a,b) = a × b. Check the HCF and LCM as well as the product when verifying a proposed pair.",
         example=dict(problem="HCF is 6, LCM is 72, and one integer is 18. Find the other.", steps=["a × b = 6 × 72 = 432.", "b = 432/18 = 24.", "HCF(18,24) = 6 and LCM(18,24) = 72."]),
         commonMistake="The product identity alone does not guarantee that a proposed pair has the required HCF.", checklist=["Multiply HCF by LCM.", "Divide by the known integer when appropriate.", "Verify the resulting pair."]),
]


def build():
    questions = []
    titles = {c["id"]: c["title"] for c in concepts}
    def add(concept, difficulty, prompt, correct, wrong, explanation):
        values = [str(correct), *map(str, wrong)]
        assert len(values) == len(set(values)) == 4
        # Rotate the answer to avoid a fixed answer-position pattern.
        shift = len(questions) % 4
        options = values[shift:] + values[:shift]
        questions.append(dict(id=f"rn-v1-{len(questions)+1:02d}", conceptId=concept, concept=titles[concept],
            difficulty=difficulty, prompt=prompt, options=options, answer=options.index(str(correct)), explanation=explanation))
    def numeric(concept, difficulty, prompt, correct, explanation):
        candidates = list(dict.fromkeys([max(1, correct//2), max(1, correct-1), correct+1, correct*2, correct+3]))
        wrong = [n for n in candidates if n != correct]
        add(concept, difficulty, prompt, correct, wrong[:2] + [wrong[-1]], explanation)

    for n, factors, wrong in [(72, "2³ × 3²", ["2² × 3²", "2³ × 3", "2² × 3³"]),
                              (108, "2² × 3³", ["2³ × 3²", "2² × 3²", "2 × 3³"]),
                              (200, "2³ × 5²", ["2² × 5²", "2³ × 5", "2² × 5³"])]:
        add("prime-factorisation", "foundation", f"Which is the prime factorisation of {n}?", factors, wrong, f"{n} = {factors}. Each base is prime.")
    for n, divisor in [(72, 2), (108, 3), (200, 2)]:
        numeric("prime-factorisation", "standard", f"What is the least positive integer by which {n} must be divided to give a perfect square?", divisor,
                f"Remove the prime factor with an odd exponent: {n}/{divisor} = {n//divisor}, a perfect square.")
    for n, multiplier in [(72, 3), (108, 2), (200, 5)]:
        numeric("prime-factorisation", "challenge", f"What is the least positive integer by which {n} must be multiplied to give a perfect cube?", multiplier,
                f"Complete prime exponents to multiples of three: {n} × {multiplier} = {n*multiplier}, a perfect cube.")
    for a, b in [(36, 60), (54, 90), (80, 120)]:
        numeric("hcf", "foundation", f"Which is the greatest positive integer that divides both {a} and {b}?", gcd(a,b), f"HCF({a}, {b}) = {gcd(a,b)}. It divides both numbers exactly.")
    for a, b in [(84, 144), (96, 160), (105, 175)]:
        h = gcd(a,b)
        numeric("hcf", "standard", f"Two ribbons measure {a} cm and {b} cm. What is the greatest equal piece length (cm) that leaves no waste?", h, f"The piece length must divide both lengths. HCF({a}, {b}) = {h} cm.")
    for a, b in [(96, 144), (126, 180), (168, 252)]:
        h = gcd(a,b)
        numeric("hcf", "challenge", f"A teacher has {a} pencils and {b} erasers. All are split into the greatest possible number of identical packs. How many packs can be made?", h,
                f"The number of packs divides both counts: HCF = {h}. Each pack has {a//h} pencils and {b//h} erasers.")
    for a, b in [(8, 12), (9, 15), (14, 21)]:
        numeric("lcm", "foundation", f"Find the LCM of {a} and {b}.", lcm(a,b), f"The least positive multiple of both {a} and {b} is {lcm(a,b)}.")
    for a, b in [(12, 18), (15, 20), (16, 24)]:
        numeric("lcm", "standard", f"Two bells ring together now and repeat every {a} and {b} minutes. After how many minutes do they next ring together?", lcm(a,b), f"Find the first shared cycle: LCM({a}, {b}) = {lcm(a,b)} minutes.")
    for numbers in [(8,12,18), (6,15,20), (9,12,30)]:
        numeric("lcm", "challenge", f"What is the smallest positive integer divisible by each of {numbers[0]}, {numbers[1]} and {numbers[2]}?", lcm(*numbers), f"Use the greatest exponent of every prime in all three factorisations. Their LCM is {lcm(*numbers)}.")
    for p in [2, 3, 7]:
        add("irrational-numbers", "foundation", f"Which number is irrational? (Consider √{p}.)", f"√{p}", ["√81", "0.75", "13/5"], f"{p} is prime, so √{p} is irrational. √81 = 9; the decimal and fraction are rational.")
    for p in [2, 3, 7]:
        add("irrational-numbers", "standard", f"Which expression involving √{p} is irrational?", f"√{p} + 1", [f"√{p} × √{p}", f"√{p} - √{p}", f"√{p} / √{p}"], f"The other expressions equal {p}, 0 and 1. Adding rational 1 to irrational √{p} stays irrational.")
    for p in [2, 3, 7]:
        add("irrational-numbers", "challenge", f"Suppose √{p} = a/b in lowest terms. Squaring gives a² = {p}b². Which argument completes the contradiction?",
            f"Prime {p} divides a, and substitution then shows it divides b, contradicting lowest terms.",
            ["Both a and b must equal zero.", "Squaring a fraction always makes it an integer.", f"The equation proves {p} is not prime."],
            f"If prime {p} divides a², it divides a. Write a = {p}k; substitution gives b² = {p}k², so {p} also divides b. This contradicts coprimality.")
    for h, multiple, a in [(12,72,24), (6,120,30), (8,120,24)]:
        b = h*multiple//a
        assert gcd(a,b) == h and lcm(a,b) == multiple
        numeric("hcf-lcm-relation", "foundation", f"Two positive integers have HCF {h} and LCM {multiple}. One integer is {a}. Find the other.", b, f"The other integer is ({h} × {multiple})/{a} = {b}.")
    for a,b in [(18,30), (24,40), (28,42)]:
        numeric("hcf-lcm-relation", "standard", f"Two positive integers have product {a*b} and HCF {gcd(a,b)}. What is their LCM?", lcm(a,b), f"LCM = product/HCF = {a*b}/{gcd(a,b)} = {lcm(a,b)}.")
    for h,x,y in [(6,3,5), (4,3,7), (5,4,9)]:
        pair = lambda a,b: f"{a} and {b}"
        add("hcf-lcm-relation", "challenge", f"Which pair has HCF {h} and LCM {h*x*y}?", pair(h*x,h*y),
            [pair(h,h*y), pair(h*2,h*y), pair(h*x,h*y*2)],
            f"{h*x} = {h} × {x}, {h*y} = {h} × {y}; {x} and {y} are coprime. Their HCF is {h} and LCM is {h*x*y}.")
    assert len(questions) == 45
    return dict(courseId=COURSE, chapterId="ch-01", concepts=concepts, questions=questions)


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1] / "data/real-numbers-practice-v1.json"
    destination.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built 5 revision cards and 45 questions.")
