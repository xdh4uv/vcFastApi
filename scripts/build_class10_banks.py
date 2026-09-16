"""Original adaptive starter banks for Class 10 chapters 3–14.

Each concept has three authored question patterns at increasing difficulty,
with three numerical variants per pattern. This is finite authored content,
not runtime generation. Published question IDs and snapshots are immutable.
"""
import json
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ['foundation', 'standard', 'challenge']
NAMES = {3:'linear-equations',4:'quadratic-equations',5:'arithmetic-progressions',6:'triangles',7:'coordinate-geometry',
         8:'trigonometry',9:'trigonometry-applications',10:'circles',11:'circle-areas',12:'surface-areas-volumes',13:'statistics',14:'probability'}


class ChapterBank:
    def __init__(self, chapter):
        self.chapter = chapter
        self.concepts, self.questions = [], []

    def concept(self, id_, title, labels, explanation, mistake, checklist):
        self.current = dict(id=id_,title=title,legacyLabels=labels,explanation=explanation,commonMistake=mistake,checklist=checklist)
        self.concepts.append(self.current)

    def q(self, tier, prompt, correct, steps, wrong=None):
        if wrong is None:
            value = F(correct)
            correct = str(value)
            wrong = [str(value-1), str(value+1), str(value+2)]
            if 0 < value < 1 or (self.chapter == 14 and 0 <= value <= 1):
                choices = [F(1,2),F(1,3),F(2,3),F(1,4),F(3,4),F(1,6),F(5,6),F(1,5),F(4,5),F(0),F(1)]
                wrong = [str(v) for v in sorted(choices,key=lambda v: abs(v-value)) if v != value][:3]
            elif value == 0:
                wrong = ['1','2','3']
        values = list(map(str, [correct, *wrong]))
        assert len(values) == len(set(values)) == 4, prompt
        # Stable rotation gives no fixed correct-option position.
        shift = len(self.questions) % 4
        options = values[shift:] + values[:shift]
        q = dict(id=f'c{self.chapter:02d}-v1-{len(self.questions)+1:02d}',conceptId=self.current['id'],concept=self.current['title'],
                 difficulty=LEVELS[tier],prompt=prompt,options=options,answer=options.index(str(correct)),explanation=' '.join(steps))
        self.questions.append(q)
        if tier == 1 and 'example' not in self.current:
            self.current['example'] = dict(problem=prompt,steps=[*steps, f'Answer: {correct}.'])

    def dump(self):
        return dict(courseId='ncert-maths-10-v1',chapterId=f'ch-{self.chapter:02d}',concepts=self.concepts,questions=self.questions)


def linear():
    b = ChapterBank(3)
    b.concept('substitution','Solving by substitution',['solution pairs'],
        'A solution pair satisfies both equations. Express one variable using the simpler equation, substitute into the other, solve, then recover and check the second variable.',
        'A pair that satisfies only one equation is not a common solution.', ['Isolate one variable.','Substitute with brackets.','Check both original equations.'])
    for t in range(3):
        for n in [2,3,4]:
            if t == 0: b.q(t,f'Given y = {n} and x + y = {3*n}, find x.',2*n,[f'Substitute y = {n}: x = {3*n} - {n} = {2*n}.'])
            elif t == 1: b.q(t,f'Solve y = x + {n} and x + y = {5*n}. What is x?',2*n,[f'Substitute: 2x + {n} = {5*n}.',f'Then x = {2*n} and y = {3*n}.'])
            else: b.q(t,f'Solve y = 2x - {n} and 3x + 2y = {12*n}. What is y?',3*n,[f'Substitute to get 7x = {14*n}, so x = {2*n}.',f'Thus y = {3*n}.'])
    b.concept('graphs','Graphical solutions',['graph interpretation'],
        'Each linear equation represents a line. Intersecting lines have one common point, distinct parallel lines have none, and coincident lines have infinitely many. The intersection coordinates satisfy both equations.',
        'Parallel and coincident lines are different cases.', ['Identify whether lines intersect.','Read both coordinates.','Verify by substitution.'])
    for t in range(3):
        for n in [2,3,4]:
            if t == 0: b.q(t,f'Two lines intersect only at ({n}, {n+1}). How many common solutions are there?',1,['Exactly one intersection means exactly one solution.'])
            elif t == 1: b.q(t,f'The lines x + y = {3*n} and x - y = {n} intersect at P. Find the x-coordinate of P.',2*n,[f'Adding the equations gives 2x = {4*n}.',f'P = ({2*n}, {n}).'])
            else: b.q(t,f'The lines y = 2x + {n} and y = -x + {7*n} intersect. Find the y-coordinate.',5*n,[f'At intersection, 3x = {6*n}, so x = {2*n}.',f'Substitute to obtain y = {5*n}.'])
    b.concept('consistency','Consistency of equations',['dependent equations'],
        'Proportional coefficients and constants represent the same line. Proportional x/y coefficients with incompatible constants represent parallel lines. Otherwise the pair has a unique solution. Comparing multiples avoids division by zero.',
        'Compare constants as well as x and y coefficients.', ['Write equations in the same form.','Compare all coefficients and constants.','Distinguish none, one and infinitely many.'])
    for t in range(3):
        for n in [2,3,4]:
            choices=['No solution','One solution','Infinitely many solutions','Exactly two solutions']
            if t == 0: b.q(t,f'How many solutions do x + y = {n} and 2x + 2y = {2*n} have?',choices[2],['The second equation is twice the first, so both describe the same line.'],[choices[0],choices[1],choices[3]])
            elif t == 1: b.q(t,f'How many solutions do x + 2y = {n} and 2x + 4y = {2*n+1} have?',choices[0],['Doubling the first gives a different constant from the second. The lines are distinct and parallel.'],choices[1:])
            else: b.q(t,f'For infinitely many solutions, find k: {n}x + 2y = {3*n}; {2*n}x + 4y = k.',6*n,['The entire first equation must be doubled.',f'Therefore k = 2 × {3*n} = {6*n}.'])
    b.concept('elimination','Solving by elimination',['elimination'],
        'Make one variable have matching or opposite coefficients by multiplying whole equations. Subtract or add to eliminate it, then substitute back.',
        'Multiply every term, including the constant, when scaling an equation.', ['Choose a variable to eliminate.','Scale entire equations.','Check the recovered pair.'])
    for t in range(3):
        for n in [2,3,4]:
            if t == 0: b.q(t,f'x + y = {5*n} and x - y = {n}. Find y.',2*n,[f'Subtract the second equation: 2y = {4*n}.',f'y = {2*n}.'])
            elif t == 1: b.q(t,f'2x + 3y = {12*n} and 2x + y = {8*n}. Find x.',3*n,[f'Subtract: 2y = {4*n}, so y = {2*n}.',f'Then 2x = {6*n}, so x = {3*n}.'])
            else: b.q(t,f'3x + 2y = {13*n} and 2x + 3y = {12*n}. Find y.',2*n,[f'Multiply equations by 2 and 3 respectively; subtract to get 5y = {10*n}.',f'Thus y = {2*n}, x = {3*n}.'])
    b.concept('modelling','Modelling with two variables',['modelling'],
        'Name both unknowns with units. Translate each independent condition into an equation, solve the pair, and interpret the solution in the original context.',
        'A total price is not the unit price; keep counts and prices separate.', ['Define variables and units.','Use two independent conditions.','Check the answer in the story.'])
    for t in range(3):
        for n in [2,3,4]:
            if t == 0: b.q(t,f'A pen and notebook cost ₹{10*n}. Two pens and a notebook cost ₹{13*n}. Find the pen price in rupees.',3*n,[f'Subtract the first total from the second: pen = {13*n} - {10*n} = {3*n}.'])
            elif t == 1: b.q(t,f'Two adult tickets and one child ticket cost ₹{20*n}; one adult and two child tickets cost ₹{16*n}. Find one child ticket price in rupees.',4*n,[f'Double the second condition and subtract the first: three child tickets cost ₹{12*n}.',f'One costs ₹{4*n}.'])
            else: b.q(t,f'A boat travels {6*n} km downstream in 2 hours and {4*n} km upstream in 2 hours. Find the current speed in km/h.',F(n,2),[f'Downstream speed = {3*n}; upstream speed = {2*n}.','Current speed is half their difference.',f'Current = {F(n,2)} km/h.'])
    return b.dump()


def quadratics():
    b = ChapterBank(4)
    b.concept('factorisation','Factorising quadratic equations',['factorisation'],
        'Write the equation with zero on one side. Factor the quadratic and set each factor equal to zero. Expanding the factors checks the coefficients.',
        'Factors must reproduce both the middle coefficient and the constant.', ['Move all terms to one side.','Factor and solve both factors.','Substitute both roots.'])
    for t in range(3):
        for n in [2,3,4]:
            if t == 0: b.q(t,f'Find the larger root of (x - {n})(x - {n+3}) = 0.',n+3,[f'The roots are {n} and {n+3}.'])
            elif t == 1: b.q(t,f'Find the positive root of x² - {n}x - {2*n*n} = 0.',2*n,[f'Factor as (x - {2*n})(x + {n}) = 0.',f'The positive root is {2*n}.'])
            else: b.q(t,f'Find the smaller root of 2x² - {3*n}x + {n*n} = 0.',F(n,2),[f'Factor as (2x - {n})(x - {n}) = 0.',f'The roots are {F(n,2)} and {n}.'])
    b.concept('discriminant','Calculating the discriminant',['discriminant'],
        'For ax² + bx + c = 0 with a ≠ 0, D = b² − 4ac. Use signed coefficients after collecting all terms on one side.',
        'Square the entire signed value of b; retain the sign of c in 4ac.', ['Identify a, b and c.','Compute b² and 4ac separately.','Subtract to find D.'])
    for t in range(3):
        for n in [2,3,4]:
            if t == 0: b.q(t,f'Find D for x² - {2*n}x + {n*n} = 0.',0,[f'D = ({-2*n})² - 4 × {n*n} = 0.'])
            elif t == 1: b.q(t,f'Find D for 2x² + {n}x - {n*n} = 0.',9*n*n,[f'D = {n*n} - 4 × 2 × ({-n*n}) = {9*n*n}.'])
            else: b.q(t,f'The equation x² - {2*n}x + k = 0 has equal roots. Find k.',n*n,[f'Equal roots require D = {4*n*n} - 4k = 0.',f'Thus k = {n*n}.'])
    b.concept('root-nature','Nature of roots',['nature of roots'],
        'The sign of D determines real-root behaviour: D > 0 gives two distinct real roots, D = 0 gives one repeated real root, and D < 0 gives no real roots.',
        'A negative discriminant does not give two negative real roots.', ['Calculate D.','Compare it with zero.','Distinguish repeated from distinct roots.'])
    for t in range(3):
        for n in [2,3,4]:
            if t == 0: b.q(t,f'A quadratic has discriminant {n*n}. How many distinct real roots does it have?',2,['The discriminant is positive, so there are two distinct real roots.'])
            elif t == 1: b.q(t,f'How many distinct real roots does x² + {2*n}x + {n*n+1} = 0 have?',0,[f'D = {4*n*n} - {4*(n*n+1)} = -4; there are no real roots.'])
            else: b.q(t,f'Find the greatest integer k for which x² - {2*n}x + k = 0 has two distinct real roots.',n*n-1,[f'D > 0 requires k < {n*n}.',f'The greatest integer satisfying this is {n*n-1}.'])
    b.concept('formula-and-zero-product','Zero product and quadratic formula',['zero product'],
        'If a product is zero, at least one factor is zero. For a general quadratic, x = (−b ± √D)/(2a). Keep both signs and the full denominator.',
        'Dividing by x can discard the valid root x = 0.', ['Check for a common factor first.','Use both ± branches if applying the formula.','Keep zero roots.'])
    for t in range(3):
        for n in [2,3,4]:
            if t == 0: b.q(t,f'In x(x - {n}) = 0, one root is {n}. What is the other root?',0,['The first factor x is zero when x = 0.'])
            elif t == 1: b.q(t,f'Find the nonzero root of 3x² - {6*n}x = 0.',2*n,[f'Factor as 3x(x - {2*n}) = 0.',f'Roots are 0 and {2*n}.'])
            else: b.q(t,f'Use the quadratic formula to find the larger root of 2x² - {5*n}x + {2*n*n} = 0.',2*n,[f'D = {9*n*n}, so √D = {3*n}.',f'The larger root is ({5*n} + {3*n})/4 = {2*n}.'])
    b.concept('quadratic-models','Quadratic word problems',['modelling'],
        'Products of unknown lengths or consecutive integers often lead to quadratic equations. Solve algebraically, then reject roots that violate the stated physical or positive-integer conditions.',
        'A negative algebraic root may be impossible for a length.', ['Define the unknown.','Form the product equation.','Check context and units after solving.'])
    for t in range(3):
        for n in [2,3,4]:
            if t == 0: b.q(t,f'A square has area {n*n} cm². Find its side length in cm.',n,[f'Side² = {n*n}; the positive side length is {n}.'])
            elif t == 1: b.q(t,f'A rectangle has width x cm, length x + 3 cm, and area {n*(n+3)} cm². Find the width in cm.',n,[f'x(x + 3) = {n*(n+3)}.',f'The roots are {n} and {-n-3}; only {n} is a valid width.'])
            else: b.q(t,f'Two consecutive positive integers have product {(n+4)*(n+5)}. Find their sum.',2*n+9,[f'Let the smaller be x: x(x + 1) = {(n+4)*(n+5)}.',f'The positive solution is {n+4}, so the sum is {2*n+9}.'])
    return b.dump()


def progressions():
    b = ChapterBank(5)
    cards = [
        ('difference','Common difference',['common difference'],'In an AP, subtract each term from the next: the same difference d must recur. For indexed terms, aⱼ − aᵢ = (j − i)d.','Do not reverse the subtraction or confuse index gaps with term values.',['Subtract in order.','Check another consecutive pair.','Divide an indexed term difference by the index gap.']),
        ('nth-term','Finding an nth term',['nth term'],'The nth term is aₙ = a + (n − 1)d, where a is the first term. There are n − 1 steps from the first term to the nth.','Using nd instead of (n − 1)d shifts the result by one term.',['Identify a and d.','Count n − 1 steps.','Add the change to a.']),
        ('sum','Sum of an AP',['sum'],'Sₙ = n[2a + (n − 1)d]/2, or n(a + l)/2 when the last term l is known. Pairing opposite-end terms explains the formula.','The nth term is not the sum of the first n terms.',['Find the term count.','Find the last term if useful.','Multiply count by average of first and last.']),
        ('position','Locating a term',['term position'],'Set the target equal to a + (n − 1)d and solve for n. A target is a term only if the resulting index is a positive integer.','A fractional index does not name a term in the AP.',['Write the target equation.','Solve for n.','Check positivity and integrality.']),
        ('recovering','Recovering an AP',['recovering an AP'],'Two indexed terms give the common difference by subtraction. Substitute d into either aₙ equation to recover the first term.','Subtract indices as well as values.',['Use the gap between indices.','Recover d first.','Substitute to obtain a.'])]
    for ci, card in enumerate(cards):
        b.concept(*card)
        for t in range(3):
            for n in [2,3,4]:
                if ci == 0:
                    if t == 0: b.q(t,f'Find the common difference of {5*n}, {4*n}, {3*n}, ….',-n,[f'd = {4*n} - {5*n} = {-n}.'])
                    elif t == 1: b.q(t,f'Three consecutive AP terms are {n}, k, {5*n}. Find k.',3*n,[f'The middle term is their average: ({n} + {5*n})/2 = {3*n}.'])
                    else: b.q(t,f'An AP has a₄ = {7*n} and a₉ = {17*n}. Find d.',2*n,[f'Five steps change the value by {10*n}.',f'd = {10*n}/5 = {2*n}.'])
                elif ci == 1:
                    if t == 0: b.q(t,f'For a = {n} and d = 3, find a₅.',n+12,[f'a₅ = {n} + 4 × 3 = {n+12}.'])
                    elif t == 1: b.q(t,f'Find a₁₂ for the AP {10*n}, {9*n}, {8*n}, ….',-n,[f'd = {-n}; a₁₂ = {10*n} - 11 × {n} = {-n}.'])
                    else: b.q(t,f'An AP has a₃ = {5*n}, a₇ = {13*n}. Find a₁₀.',19*n,[f'd = {8*n}/4 = {2*n}.',f'From a₇ take three steps: a₁₀ = {13*n} + {6*n} = {19*n}.'])
                elif ci == 2:
                    if t == 0: b.q(t,f'An AP has 6 terms, first {n} and last {n+10}. Find its sum.',6*n+30,[f'S = 6({n} + {n+10})/2 = {6*n+30}.'])
                    elif t == 1: b.q(t,f'Find the sum of the first 10 terms of {n}, {n+2}, {n+4}, ….',10*n+90,[f'The last term is {n+18}.',f'S₁₀ = 10({n} + {n+18})/2 = {10*n+90}.'])
                    else: b.q(t,f'Rows in a hall contain {n+10}, {n+12}, {n+14}, … seats. Find the total seats in the first 12 rows.',12*n+252,[f'The 12th row has {n+32} seats.',f'Total = 12({n+10} + {n+32})/2 = {12*n+252}.'])
                elif ci == 3:
                    if t == 0: b.q(t,f'Which term of {n}, {n+2}, {n+4}, … equals {n+8}?',5,[f'{n+8} = {n} + (k − 1)2 gives k = 5.'])
                    elif t == 1: b.q(t,f'Which term of {10*n}, {9*n}, {8*n}, … is zero?',11,[f'0 = {10*n} − (k − 1){n}, so k = 11.'])
                    else: b.q(t,f'How many positive terms are in {5*n+1}, {4*n+1}, {3*n+1}, …?',6,[f'aₖ = {5*n+1} − (k − 1){n} > 0.',f'The sixth term is 1 and the seventh is {1-n}, so there are 6 positive terms.'])
                else:
                    if t == 0: b.q(t,f'An AP has a₂ = {3*n}, d = {n}. Find a.',2*n,[f'a = a₂ − d = {3*n} − {n} = {2*n}.'])
                    elif t == 1: b.q(t,f'An AP has a₃ = {7*n}, a₆ = {13*n}. Find a.',3*n,[f'd = {6*n}/3 = {2*n}.',f'a = a₃ − 2d = {3*n}.'])
                    else: b.q(t,f'An AP has S₄ = {20*n} and d = {2*n}. Find a.',2*n,[f'{20*n} = 4[2a + 3({2*n})]/2.',f'4a = {8*n}; a = {2*n}.'])
    return b.dump()


def triangles():
    b = ChapterBank(6)
    cards = [
        ('criteria','Recognising similarity',['similarity criteria'],'AA compares two angles, SAS compares two proportional sides and the included angle, and SSS compares all three side ratios. Always match corresponding vertices.','Two sides and a non-included angle do not establish SAS similarity.',['Mark corresponding vertices.','Identify exactly what is given.','Apply the matching criterion.']),
        ('scale','Corresponding sides and scale',['scale factor'],'In similar triangles all corresponding lengths have the same scale factor. Their perimeters have this factor too.','Keep smaller-to-larger or larger-to-smaller ratios consistent.',['Pair corresponding lengths.','Find one scale factor.','Apply it to the required length.']),
        ('proportionality','Basic proportionality theorem',['proportionality'],'If DE is parallel to BC in triangle ABC, with D on AB and E on AC, then AD/DB = AE/EC. Conversely equal ratios with points on those sides establish parallelism.','Do not mix a part-to-part ratio with a part-to-whole ratio.',['Check the parallel-line condition.','Write ratios using matching segments.','Cross-multiply and check the result.']),
        ('side-ratios','Using three side ratios',['SSS similarity'],'SSS similarity requires one common ratio for all three corresponding sides. Sorting sides by length can help find the correspondence.','Matching just one or two side ratios is insufficient for SSS.',['Order or label corresponding sides.','Compare all three ratios.','Check the triangle inequality.']),
        ('part-whole','Similar subtriangles',['part and whole'],'When DE is parallel to BC, triangles ADE and ABC are similar. Therefore AD/AB = AE/AC = DE/BC. Whole sides include both component segments.','AB is AD + DB, not DB alone.',['Distinguish whole sides from parts.','Use one consistent similarity ratio.','Add or subtract segments only after solving.'])]
    for ci, card in enumerate(cards):
        b.concept(*card)
        for t in range(3):
            for n in [2,3,4]:
                if ci == 0:
                    criteria=['AA','SAS','SSS','No similarity criterion is established']
                    if t == 0: b.q(t,f'Two triangles each have angles {20*n}° and 40°. Which criterion proves similarity?',criteria[0],['Two corresponding angles agree; the third agrees because each angle sum is 180°.'],criteria[1:])
                    elif t == 1: b.q(t,f'Two triangles have sides {n}, {2*n} and {3*n}, {6*n}, with equal included angles of 50°. Which criterion applies?',criteria[1],['Both side ratios are 1:3 and the included angles agree.'],[criteria[0],criteria[2],criteria[3]])
                    else: b.q(t,f'Triangles have sides {n}, {n+1}, {n+2} and {2*n}, {2*n+2}, {2*n+4}. Which criterion proves similarity?',criteria[2],['Each corresponding side ratio is 1:2, so all three ratios agree.'],[criteria[0],criteria[1],criteria[3]])
                elif ci == 1:
                    if t == 0: b.q(t,f'Similar triangles have smaller:larger side ratio 2:3. A smaller side is {2*n} cm. Find its larger match in cm.',3*n,[f'Multiply by 3/2: {2*n} × 3/2 = {3*n}.'])
                    elif t == 1: b.q(t,f'Similar triangles have smaller:larger side ratio 3:5. A larger side is {5*n} cm. Find its smaller match in cm.',3*n,[f'Multiply by 3/5: {5*n} × 3/5 = {3*n}.'])
                    else: b.q(t,f'Similar triangles have perimeters {12*n} and {18*n} cm. A side in the first is {2*n} cm. Find the corresponding side in the second in cm.',3*n,['Perimeters and corresponding sides have the same ratio 2:3.',f'The side is {2*n} × 3/2 = {3*n}.'])
                elif ci == 2:
                    if t == 0: b.q(t,f'In triangle ABC, D is on AB, E on AC, DE ∥ BC. AD = {n}, DB = {2*n}, AE = {n} cm. Find EC in cm.',2*n,[f'AD/DB = AE/EC gives {n}/{2*n} = {n}/EC.',f'EC = {2*n}.'])
                    elif t == 1: b.q(t,f'In triangle ABC, DE ∥ BC, D on AB, E on AC. DB = {3*n}, AE = {2*n}, EC = {3*n} cm. Find AD in cm.',2*n,[f'AD/{3*n} = {2*n}/{3*n}, so AD = {2*n}.'])
                    else: b.q(t,f'In triangle ABC, DE ∥ BC, D on AB, E on AC. AD = {3*n}, AE = {2*n}, EC = {4*n} cm. Find AB in cm.',9*n,[f'AD/DB = 1/2, so DB = {6*n}.',f'AB = AD + DB = {9*n}.'])
                elif ci == 3:
                    if t == 0: b.q(t,f'A triangle with sides 3, 4, 5 cm is similar to one with corresponding sides {3*n}, {4*n}, x cm. Find x.',5*n,[f'The common scale factor is {n}; x = 5 × {n} = {5*n}.'])
                    elif t == 1: b.q(t,f'Similar triangles have ordered side lists (5, 12, 13) and ({5*n}, x, {13*n}). Find x.',12*n,[f'The first and third side ratios both give scale {n}.',f'The middle side is 12 × {n} = {12*n}.'])
                    else: b.q(t,f'A triangle similar to one with sides 5, 12, 13 cm has perimeter {30*n} cm. Find its shortest side in cm.',5*n,[f'The original perimeter is 30, so scale = {n}.',f'The shortest side is {5*n}.'])
                else:
                    if t == 0: b.q(t,f'In triangle ABC, DE ∥ BC, D on AB, E on AC. AD = {n}, AB = {3*n}, AC = {6*n} cm. Find AE in cm.',2*n,[f'AE/AC = AD/AB = 1/3.',f'AE = {6*n}/3 = {2*n}.'])
                    elif t == 1: b.q(t,f'In triangle ABC, DE ∥ BC, D on AB, E on AC. AD = {2*n}, AE = {3*n}, AC = {9*n} cm. Find AB in cm.',6*n,[f'AD/AB = AE/AC = 1/3.',f'AB = 3 × {2*n} = {6*n}.'])
                    else: b.q(t,f'In triangle ABC, DE ∥ BC, D on AB, E on AC. AD = {2*n}, AB = {5*n}, BC = {10*n} cm. Find DE in cm.',4*n,[f'DE/BC = AD/AB = 2/5.',f'DE = {10*n} × 2/5 = {4*n}.'])
    return b.dump()


def coordinates():
    b = ChapterBank(7)
    cards = [
        ('distance','Distance between points',['distance'],'Distance is √[(x₂ − x₁)² + (y₂ − y₁)²]. Horizontal or vertical distances are absolute coordinate differences.','A coordinate difference may be negative, but distance cannot be.',['Subtract matching coordinates.','Square and add.','Take the nonnegative square root.']),
        ('midpoint','Midpoints',['midpoint'],'The midpoint averages corresponding coordinates: ((x₁ + x₂)/2, (y₁ + y₂)/2). You can rearrange to find a missing endpoint.','Average x with x and y with y, not x with y.',['Write the two coordinate averages.','Solve missing coordinates separately.','Check the midpoint lies between endpoints.']),
        ('section','Internal division of a segment',['section formula'],'If AP:PB = m:n, then P = ((mxB + nxA)/(m+n), (myB + nyA)/(m+n)). The coordinate of the opposite endpoint receives each weight.','Reversing the weights generally places the point on the wrong side of the midpoint.',['Label A, B and the ratio order.','Use opposite endpoint weights.','Check P lies inside AB.']),
        ('equidistant','Equidistant points',['equal distances'],'Set the squared distances to the two given points equal. Squaring avoids unnecessary square roots; expand carefully to solve the remaining coordinate.','Equal distances do not mean equal x-coordinates.',['Write both squared distances.','Expand and cancel common terms.','Substitute the coordinate into both distances.']),
        ('coordinate-shapes','Lengths in coordinate figures',[],'Use the distance formula to find side lengths, compare squared lengths to recognise figures, and add lengths for perimeter.','A diagonal and a side are different lengths.',['Label which points are joined.','Compute all needed distances.','Use the geometry only after checking lengths.'])]
    for ci, card in enumerate(cards):
        b.concept(*card)
        for t in range(3):
            for n in [2,3,4]:
                if ci == 0:
                    if t == 0: b.q(t,f'Find the distance between ({n}, 2) and ({5*n}, 2).',4*n,[f'The y-coordinates agree, so distance = |{5*n} − {n}| = {4*n}.'])
                    elif t == 1: b.q(t,f'Find the distance between (0, 0) and ({3*n}, {4*n}).',5*n,[f'Distance² = {9*n*n} + {16*n*n} = {25*n*n}.',f'Distance = {5*n}.'])
                    else: b.q(t,f'Find the distance between ({-n}, {2*n}) and ({4*n}, {-10*n}).',13*n,[f'Coordinate differences are {5*n} and {-12*n}.',f'Distance = √({169*n*n}) = {13*n}.'])
                elif ci == 1:
                    if t == 0: b.q(t,f'Find the x-coordinate of the midpoint of ({n}, 0) and ({5*n}, 4).',3*n,[f'x = ({n} + {5*n})/2 = {3*n}.'])
                    elif t == 1: b.q(t,f'The midpoint of A({-n}, {n}) and B(x, {5*n}) has x-coordinate {2*n}. Find x.',5*n,[f'({-n} + x)/2 = {2*n}.',f'x = {5*n}.'])
                    else: b.q(t,f'A rectangle has diagonal endpoints ({-2*n}, {n}) and ({4*n}, {7*n}). Find the y-coordinate of the intersection of its diagonals.',4*n,['Rectangle diagonals bisect each other.',f'The intersection y-coordinate is ({n} + {7*n})/2 = {4*n}.'])
                elif ci == 2:
                    if t == 0: b.q(t,f'P divides A(0, 0), B({6*n}, 0) internally with AP:PB = 1:2. Find Px.',2*n,[f'Px = (1 × {6*n} + 2 × 0)/3 = {2*n}.'])
                    elif t == 1: b.q(t,f'P divides A({-n}, {n}), B({5*n}, {7*n}) internally with AP:PB = 2:1. Find Py.',5*n,[f'Py = (2 × {7*n} + {n})/3 = {5*n}.'])
                    else: b.q(t,f'P({n}, {2*n}) lies between A({-n}, 0) and B({5*n}, {6*n}). If AP:PB = m:1, find m.',F(1,2),[f'The x-displacements AP and PB are {2*n} and {4*n}; their ratio is 1:2.', 'Thus m = 1/2.'])
                elif ci == 3:
                    if t == 0: b.q(t,f'Point (x, 0) is equidistant from ({-n}, 0) and ({3*n}, 0). Find x.',n,[f'It is the midpoint on the x-axis: x = ({-n} + {3*n})/2 = {n}.'])
                    elif t == 1: b.q(t,f'Point (x, 0) is equidistant from ({-n}, {n}) and ({3*n}, {n}). Find x.',n,[f'(x + {n})² + {n*n} = (x − {3*n})² + {n*n}.',f'Expansion gives x = {n}.'])
                    else: b.q(t,f'Point (x, 0) is equidistant from ({-n}, {n}) and ({3*n}, {3*n}). Find x.',2*n,[f'(x + {n})² + {n*n} = (x − {3*n})² + {9*n*n}.',f'After cancellation, {8*n}x = {16*n*n}; x = {2*n}.'])
                else:
                    if t == 0: b.q(t,f'A rectangle has vertices (0,0), ({3*n},0), ({3*n},{4*n}), (0,{4*n}). Find its perimeter.',14*n,[f'Adjacent sides are {3*n} and {4*n}.',f'Perimeter = 2({3*n} + {4*n}) = {14*n}.'])
                    elif t == 1: b.q(t,f'A rhombus has vertices ({3*n},0), (0,{4*n}), ({-3*n},0), (0,{-4*n}). Find its perimeter.',20*n,[f'Each side has length √({9*n*n}+{16*n*n}) = {5*n}.',f'Perimeter = {20*n}.'])
                    else: b.q(t,f'For A(0,0), B({3*n},{4*n}), C({6*n},{8*n}), find AB + BC − AC.',0,[f'AB = BC = {5*n}; AC = {10*n}.','The difference is 0, consistent with B lying on AC.'])
    return b.dump()


def trig():
    b = ChapterBank(8)
    b.concept('standard-angles','Standard angle values',['standard angles'],
        'Recall exact values at 0°, 30°, 45°, 60° and 90°. For acute angles, sine increases and cosine decreases over these standard values. tan θ = sin θ/cos θ where cos θ is nonzero.',
        'tan 90° is undefined; it is not zero.', ['Identify the function and angle.','Use an exact value.','Check denominators before division.'])
    for n,(angle,sine,cosine) in enumerate([(30,'1/2','√3/2'),(45,'√2/2','√2/2'),(60,'√3/2','1/2')]):
        b.q(0,f'What is sin {angle}°?',sine,[f'The exact standard value is {sine}.'],[v for v in ['1/2','√2/2','√3/2','1'] if v != sine])
    for angle in [30,45,60]: b.q(1,f'Evaluate sin²{angle}° + cos²{angle}°.',1,['The identity sin²θ + cos²θ = 1 applies at this angle.'])
    for angle in [30,45,60]: b.q(2,f'Evaluate (sin²{angle}° + cos²{angle}°)/(tan²45° + 1).',F(1,2),['The numerator is 1 and tan45° = 1.','Thus the value is 1/(1 + 1) = 1/2.'])
    cards = [
        ('ratios','Ratios in right triangles',['ratios'],'For an acute angle, sin = opposite/hypotenuse, cos = adjacent/hypotenuse and tan = opposite/adjacent. Label sides relative to the chosen angle.','The opposite side changes when you choose the other acute angle.',['Mark the angle and hypotenuse.','Choose the correct side ratio.','Use Pythagoras if a side is missing.']),
        ('identities','Using trigonometric identities',['identities'],'The identities sin²θ + cos²θ = 1, sec²θ − tan²θ = 1 and cosec²θ − cot²θ = 1 relate squared ratios.','sin²θ means (sin θ)², not sin(θ²).',['Choose the matching identity.','Rearrange before substituting.','Square fractions carefully.']),
        ('reciprocals','Reciprocal ratios',[],'For acute angles, sec = 1/cos, cosec = 1/sin and cot = 1/tan. A reciprocal reverses numerator and denominator.','The reciprocal of a ratio is not one minus that ratio.',['Identify the reciprocal pair.','Invert the fraction.','Use a side triangle if needed.']),
        ('expressions','Evaluating trigonometric expressions',[],'Simplify expressions using exact ratios and identities before doing arithmetic. For acute angles all basic ratios are positive.','Do not cancel terms across addition; only common factors may be cancelled.',['Simplify using identities.','Substitute exact fractions.','Combine using a common denominator.'])]
    triples=[(3,4,5),(5,12,13),(8,15,17)]
    for ci,card in enumerate(cards):
        b.concept(*card)
        for t in range(3):
            for o,a,h in triples:
                if ci == 0:
                    if t == 0: b.q(t,f'For acute θ, opposite side = {o}, adjacent = {a}. Find tan θ.',F(o,a),[f'tan θ = opposite/adjacent = {o}/{a}.'])
                    elif t == 1: b.q(t,f'θ is acute and sin θ = {o}/{h}. Find cos θ.',F(a,h),[f'Take opposite {o}, hypotenuse {h}; adjacent = √({h*h} − {o*o}) = {a}.',f'cos θ = {a}/{h}.'])
                    else: b.q(t,f'θ is acute and tan θ = {o}/{a}. Find sin θ + cos θ.',F(o+a,h),[f'The hypotenuse for sides {o} and {a} is {h}.',f'The sum is ({o} + {a})/{h} = {F(o+a,h)}.'])
                elif ci == 1:
                    if t == 0: b.q(t,f'For acute θ with tan θ = {o}/{a}, find sec²θ − tan²θ.',1,['The difference equals 1 by the secant identity.'])
                    elif t == 1: b.q(t,f'If tan θ = {o}/{a}, find sec²θ.',F(h*h,a*a),[f'sec²θ = 1 + {o*o}/{a*a} = {F(h*h,a*a)}.'])
                    else: b.q(t,f'θ is acute and sin θ = {o}/{h}. Find cosec²θ − 1.',F(a*a,o*o),[f'cosec²θ = {h*h}/{o*o}.',f'Subtract 1 to obtain {F(a*a,o*o)}, which is cot²θ.'])
                elif ci == 2:
                    if t == 0: b.q(t,f'If cos θ = {a}/{h}, find sec θ.',F(h,a),[f'sec θ is the reciprocal of cos θ: {h}/{a}.'])
                    elif t == 1: b.q(t,f'θ is acute and tan θ = {o}/{a}. Find cot θ.',F(a,o),[f'cot θ = 1/tan θ = {a}/{o}.'])
                    else: b.q(t,f'θ is acute and cos θ = {a}/{h}. Find cosec θ.',F(h,o),[f'sin θ = √(1 − {a*a}/{h*h}) = {o}/{h}.',f'Invert to get cosec θ = {h}/{o}.'])
                else:
                    if t == 0: b.q(t,f'θ is acute and sin θ = {o}/{h}. Find sin θ × cosec θ.',1,['Sine and cosecant are reciprocals; their product is 1.'])
                    elif t == 1: b.q(t,f'θ is acute and tan θ = {o}/{a}. Find tan θ + cot θ.',F(o*o+a*a,o*a),[f'Add {o}/{a} + {a}/{o} using denominator {o*a}.',f'The result is {F(h*h,o*a)}.'])
                    else: b.q(t,f'θ is acute and cos θ = {a}/{h}. Evaluate (1 − sin²θ)/cos θ.',F(a,h),['The numerator equals cos²θ.',f'Division by nonzero cos θ leaves cos θ = {a}/{h}.'])
    return b.dump()


def applications():
    b = ChapterBank(9)
    cards = [
        ('angles','Elevation and depression',['elevation'],'Elevation is measured upward from the observer’s horizontal; depression is measured downward. Parallel horizontal lines make a depression angle equal to the corresponding elevation angle.','Measure from the horizontal, not from the vertical.',['Draw the observer’s horizontal.','Mark the line of sight.','Use parallel horizontals when transferring angles.']),
        ('heights','Finding heights',['height'],'On level ground, tan θ = height above eye level / horizontal distance. Include observer height only when the question gives it.','The line of sight is the hypotenuse, not the horizontal distance.',['Draw a right triangle.','Use h = d tan θ.','Add eye height when required.']),
        ('distances','Finding horizontal distances',['distance'],'Rearrange tan θ = h/d to obtain d = h/tan θ. Use the vertical height above the observation point.','Multiplying h by tan θ instead of dividing reverses the relation.',['Identify the relevant vertical height.','Rearrange before substitution.','Simplify exact radicals.']),
        ('eye-height','Accounting for eye height',['eye height'],'If the observer’s eyes are e metres above level ground, the right-triangle height is H − e, so total height H = e + d tan θ.','A computed height above the eyes is not yet the total height above ground.',['Separate eye height from triangle height.','Use the angle from eye level.','Recombine heights at the end.']),
        ('two-points','Two observation points',['two observation points'],'For two points on the same side of a vertical tower, use one common tower height and distances that differ by the movement. A larger elevation angle corresponds to the nearer point on level ground.','When moving away, add the movement to distance; do not subtract it.',['Label nearer and farther distances.','Write a tangent equation for each.','Eliminate the shared unknown.'])]
    for ci,card in enumerate(cards):
        b.concept(*card)
        for t in range(3):
            for n in [2,3,4]:
                if ci == 0:
                    if t == 0: b.q(t,f'An observer looks upward at a tower along a line {10*n}° above the horizontal. What is this angle called?','Angle of elevation',['An upward angle from the observer’s horizontal is an angle of elevation.'],['Angle of depression','Right angle','Straight angle'])
                    elif t == 1: b.q(t,f'From a tower top the angle of depression to a ground point is {10*n}°. Find the angle of elevation back to the tower top in degrees.',10*n,['The two horizontals are parallel, so the corresponding angles are equal.'])
                    else: b.q(t,f'A line of sight to a tower top is {10*n}° above horizontal. Find the acute angle between that line and the vertical tower in degrees.',90-10*n,['The horizontal and tower are perpendicular.',f'The two acute angles sum to 90°: {90-10*n}°.'])
                elif ci == 1:
                    if t == 0: b.q(t,f'From ground level {10*n} m from a vertical pole, elevation to its top is 45°. Find its height in m.',10*n,[f'H = {10*n} tan45° = {10*n}.'])
                    elif t == 1: b.q(t,f'A tower is viewed from ground level at horizontal distance {n}√3 m and elevation 30°. Find its height in m.',n,[f'H = {n}√3 × 1/√3 = {n}.'])
                    else: b.q(t,f'An observer’s eyes are 2 m above level ground, {n}√3 m from a tower. Elevation is 60°. Find the total height in m.',3*n+2,[f'Height above eyes = {n}√3 × √3 = {3*n}.',f'Total height = {3*n} + 2 = {3*n+2}.'])
                elif ci == 2:
                    if t == 0: b.q(t,f'A {5*n} m tower is seen at elevation 45° from ground level. Find horizontal distance in m.',5*n,[f'd = {5*n}/tan45° = {5*n}.'])
                    elif t == 1: b.q(t,f'A {3*n}√3 m tower is seen at elevation 60° from ground level. Find horizontal distance in m.',3*n,[f'd = {3*n}√3/√3 = {3*n}.'])
                    else: b.q(t,f'A {n}√3 m tower is seen at elevation 30° from ground level. Find horizontal distance in m.',3*n,[f'd = {n}√3/(1/√3) = {3*n}.'])
                elif ci == 3:
                    if t == 0: b.q(t,f'Eye height is 1.5 m. A pole is {5*n} m away on level ground at elevation 45°. Find total pole height in m.',F(3,2)+5*n,[f'Height above eyes = {5*n}; add 1.5 m.',f'H = {F(3,2)+5*n} m.'])
                    elif t == 1: b.q(t,f'Eye height is 1.5 m, ground distance to a tree is {2*n}√3 m and elevation is 30°. Find total tree height in m.',F(3,2)+2*n,[f'Triangle height = {2*n}√3/√3 = {2*n}.',f'Add 1.5: H = {F(3,2)+2*n}.'])
                    else: b.q(t,f'A {n+3} m tower is {n} m horizontally from an observer on a platform. Elevation from the eyes is 45°. Find eye height above the same level ground in m.',3,[f'The tower is {n} m above the eyes.',f'Eye height = {n+3} − {n} = 3 m.'])
                else:
                    if t == 0: b.q(t,f'A {3*n} m tower is viewed from ground level at 45°. The observer moves {n} m directly toward it. Find the new horizontal distance in m.',2*n,[f'The original distance equals the height, {3*n}.',f'New distance = {3*n} − {n} = {2*n}.'])
                    elif t == 1: b.q(t,f'From two ground points on the same side of a tower, elevations are 60° (near) and 30° (far). The points are {2*n}√3 m apart. Find tower height in m.',3*n,['For height H, far distance = H√3 and near distance = H/√3.',f'Their difference is 2H/√3 = {2*n}√3, hence H = {3*n}.'])
                    else: b.q(t,f'Elevation to a tower is 45° from ground level. Moving {n}(√3 − 1) m directly away makes it 30°. Find tower height in m.',n,['For height H, the distances are H and H√3.',f'The increase H(√3 − 1) equals {n}(√3 − 1), so H = {n}.'])
    return b.dump()


def circles():
    b = ChapterBank(10)
    cards = [
        ('radius','Radius and tangent',['tangent radius'],'The radius to the point of contact is perpendicular to a tangent. Centre, contact point and an external point form a right triangle.','The radius must end at the point of contact for the perpendicular rule.',['Join centre to contact point.','Mark the 90° angle.','Use triangle angle sums or Pythagoras.']),
        ('equal-tangents','Equal tangent segments',['equal tangents'],'Two tangent segments from the same external point to the same circle have equal lengths. Shared external points allow equal segments to be paired in larger figures.','Tangents from different external points need not have equal lengths.',['Identify the common external point.','Equate matching tangent lengths.','Check all lengths are positive.']),
        ('count','Number of tangents',['tangent count'],'A point inside a circle has no tangent through it, a point on it has one, and an external point has two. Compare its centre-distance with the radius.','A line through an interior point cuts the circle, so it is not a tangent.',['Compare OP with radius r.','Classify the point’s position.','Use the matching tangent count.']),
        ('length','Finding tangent lengths',['tangent length'],'In right triangle OAP, OA is radius r, OP is centre-distance d, and PA = √(d² − r²). OP is the hypotenuse.','Do not subtract lengths before squaring, or mistake the radius for the hypotenuse.',['Draw radius to contact.','Write d² = r² + PA².','Take a positive root.']),
        ('angles','Angles between tangents',['angles'],'For tangents PA and PB, the smaller angle APB and smaller central angle AOB sum to 180°. OP also bisects the angle between the tangent segments.','The two right angles occur at the contact points, not at P or O.',['Mark both tangent-radius right angles.','Use the quadrilateral angle sum.','Use the angle bisector only with the shared centre and point.'])]
    for ci,card in enumerate(cards):
        b.concept(*card)
        for t in range(3):
            for n in [2,3,4]:
                if ci == 0:
                    if t == 0: b.q(t,f'A tangent touches a circle of radius {n} cm at A. Find the angle between OA and the tangent in degrees.',90,['A radius to the contact point is perpendicular to the tangent.'])
                    elif t == 1: b.q(t,f'PA is tangent at A, O is the centre and ∠OPA = {20*n}°. Find ∠AOP in degrees.',90-20*n,[f'∠OAP = 90°, so ∠AOP = 90° − {20*n}° = {90-20*n}°.'])
                    else: b.q(t,f'Tangents PA and PB have smaller central angle AOB = {100+10*n}°. Find ∠APB in degrees.',80-10*n,['Angles at A and B are right angles.',f'∠APB = 360° − 180° − {100+10*n}° = {80-10*n}°.'])
                elif ci == 1:
                    if t == 0: b.q(t,f'PA and PB are tangents from P to one circle. PA = {7*n} cm. Find PB in cm.',7*n,['Tangent segments from the same external point are equal.'])
                    elif t == 1: b.q(t,f'PA and PB are tangents from P to one circle. PA = 2x + {n} and PB = {5*n} cm. Find x.',2*n,[f'2x + {n} = {5*n}, hence x = {2*n}.'])
                    else: b.q(t,f'A convex quadrilateral ABCD has a circle tangent to all four sides. AB = {3*n}, BC = {4*n}, CD = {5*n} cm. Find DA in cm.',4*n,['Equal tangent segments give AB + CD = BC + DA.',f'DA = {3*n} + {5*n} − {4*n} = {4*n}.'])
                elif ci == 2:
                    if t == 0: b.q(t,f'OP = {n} cm for a circle of radius {2*n} cm. How many tangents pass through P?',0,['OP < radius, so P is inside and has no tangents.'])
                    elif t == 1: b.q(t,f'OP = {3*n} cm for a circle of radius {3*n} cm. How many tangents pass through P?',1,['P lies on the circle, where there is exactly one tangent.'])
                    else: b.q(t,f'A circle has radius {2*n} cm. P is {n} cm outside its boundary along a radius extended. How many tangents pass through P?',2,[f'OP = {3*n} > radius {2*n}; P is external, so two tangents exist.'])
                elif ci == 3:
                    if t == 0: b.q(t,f'OP = {5*n} cm and radius OA = {3*n} cm. PA is tangent at A. Find PA in cm.',4*n,[f'PA² = {25*n*n} − {9*n*n} = {16*n*n}.',f'PA = {4*n}.'])
                    elif t == 1: b.q(t,f'PA is a tangent of length {12*n} cm; the circle radius is {5*n} cm. Find OP in cm.',13*n,[f'OP² = {144*n*n} + {25*n*n} = {169*n*n}.',f'OP = {13*n}.'])
                    else: b.q(t,f'An external point is {13*n} cm from the centre; its tangent length is {12*n} cm. Find the radius in cm.',5*n,[f'r² = {169*n*n} − {144*n*n} = {25*n*n}.',f'r = {5*n}.'])
                else:
                    if t == 0: b.q(t,f'Tangents PA and PB form angle {20*n}°. Find the smaller central angle AOB in degrees.',180-20*n,[f'∠AOB = 180° − {20*n}° = {180-20*n}°.'])
                    elif t == 1: b.q(t,f'Tangents PA and PB form angle {20*n}°. O is the centre. Find ∠APO in degrees.',10*n,['OP bisects the angle between the tangent segments.',f'∠APO = {20*n}°/2 = {10*n}°.'])
                    else: b.q(t,f'Tangents PA and PB touch at A and B. O is the centre and ∠APO = {10*n}°. Find the smaller central angle AOB in degrees.',180-20*n,[f'∠APB = 2 × {10*n}° = {20*n}°.',f'∠AOB = {180-20*n}°.'])
    return b.dump()


def areas():
    b = ChapterBank(11)
    cards = [
        ('circle-area','Circle and ring areas',['circle area'],'A circle has area πr². An annular ring has area π(R² − r²), the difference of two circle areas. Use the stated value of π.','Doubling radius multiplies area by four, not two.',['Convert diameter to radius if needed.','Square the radius.','Use square units.']),
        ('sector','Sector area',['sector area'],'A sector with central angle θ° has area (θ/360)πr². The angle fraction describes the fraction of the full circle.','Use 360 in the denominator, not 180.',['Identify radius and central angle.','Find the fraction of a full turn.','Multiply full area by that fraction.']),
        ('arc','Arc length',['arc length'],'Arc length for central angle θ° is (θ/360)2πr. It is a curved length, measured in linear units.','The sector area formula uses r²; arc length uses r.',['Find full circumference.','Multiply by the angle fraction.','Check linear units.']),
        ('perimeter','Sector perimeter',['sector perimeter'],'A sector perimeter is its arc plus two radii. A semicircle’s perimeter is πr + 2r. Boundaries shared inside a composite shape are not exposed perimeter.','Arc length alone omits the straight boundary pieces.',['Trace the actual boundary.','Add the arc and straight pieces.','Avoid counting internal edges.']),
        ('segment','Minor segment area',['segment area'],'A minor segment is the region between a chord and its minor arc. Its area equals minor-sector area minus the area of the triangle formed by the two radii.','Subtract triangle area from sector area, not from the full circle.',['Find the sector area.','Find the included triangle’s area.','Subtract and keep square units.'])]
    for ci,card in enumerate(cards):
        b.concept(*card)
        for t in range(3):
            for n in [2,3,4]:
                r=7*n
                pi=F(22,7)
                if ci == 0:
                    if t == 0: b.q(t,f'Find the area in cm² of a circle of radius {r} cm. Use π = 22/7.',pi*r*r,[f'A = (22/7) × {r}² = {pi*r*r}.'])
                    elif t == 1: b.q(t,f'A circular plate has diameter {2*r} cm. Find its area in cm². Use π = 22/7.',pi*r*r,[f'Radius = {2*r}/2 = {r}.',f'Area = {pi*r*r}.'])
                    else: b.q(t,f'A ring has outer radius {2*r} cm and inner radius {r} cm. Find its area in cm². Use π = 22/7.',3*pi*r*r,[f'Area = (22/7)({2*r}² − {r}²) = {3*pi*r*r}.'])
                elif ci == 1:
                    if t == 0: b.q(t,f'Find the area of a 90° sector of radius {r} cm in cm². Use π = 22/7.',pi*r*r/4,[f'Area = (90/360) × (22/7) × {r}² = {pi*r*r/4}.'])
                    elif t == 1: b.q(t,f'Find the area of a 120° sector of radius {r} cm in cm². Use π = 22/7.',pi*r*r/3,[f'The sector is one third of the circle: area = {pi*r*r/3}.'])
                    else: b.q(t,f'A sector of radius {r} cm has area {pi*r*r/6} cm². Find its central angle in degrees. Use π = 22/7.',60,[f'Its area is 1/6 of full area {pi*r*r}.','Angle = 360°/6 = 60°.'])
                elif ci == 2:
                    if t == 0: b.q(t,f'Find the length in cm of a 180° arc of radius {r} cm. Use π = 22/7.',pi*r,[f'Half the circumference is πr = {pi*r}.'])
                    elif t == 1: b.q(t,f'Find the length in cm of a 60° arc of radius {r} cm. Use π = 22/7.',pi*r/3,[f'Length = (60/360) × 2 × (22/7) × {r} = {pi*r/3}.'])
                    else: b.q(t,f'An arc of radius {r} cm has length {pi*r/2} cm. Find its central angle in degrees. Use π = 22/7.',90,[f'Full circumference is {2*pi*r}; the arc is one quarter.', 'Angle = 90°.'])
                elif ci == 3:
                    if t == 0: b.q(t,f'Find the perimeter in cm of a semicircle of radius {r} cm. Use π = 22/7.',pi*r+2*r,[f'Perimeter = πr + 2r = {pi*r} + {2*r} = {pi*r+2*r}.'])
                    elif t == 1: b.q(t,f'Find the perimeter in cm of a 90° sector of radius {r} cm. Use π = 22/7.',pi*r/2+2*r,[f'The arc is {pi*r/2}; add two radii {2*r}.',f'Total = {pi*r/2+2*r}.'])
                    else: b.q(t,f'A 120° sector has radius {r} cm. Find its perimeter in cm. Use π = 22/7.',2*pi*r/3+2*r,[f'Arc = {2*pi*r/3}.',f'Add the two radii: perimeter = {2*pi*r/3+2*r}.'])
                else:
                    if t == 0: b.q(t,f'A minor sector has area {10*n} cm² and its triangle has area {6*n} cm². Find the minor segment area in cm².',4*n,[f'Segment = sector − triangle = {10*n} − {6*n} = {4*n}.'])
                    elif t == 1: b.q(t,f'A chord subtends 90° at the centre of a radius-{r} cm circle. Find the minor segment area in cm². Use π = 22/7.',pi*r*r/4-F(r*r,2),[f'Sector = {pi*r*r/4}. The right triangle has area r²/2 = {F(r*r,2)}.',f'Difference = {pi*r*r/4-F(r*r,2)}.'])
                    else: b.q(t,f'For a chord subtending 90° in a circle of radius {r} cm, find the major segment area in cm². Use π = 22/7.',3*pi*r*r/4+F(r*r,2),[f'Minor segment = quarter circle minus right triangle = {pi*r*r/4-F(r*r,2)}.',f'Major segment = full circle minus minor segment = {3*pi*r*r/4+F(r*r,2)}.'])
    return b.dump()


def solids():
    b = ChapterBank(12)
    def piq(t,prompt,value,steps):
        b.q(t,prompt,f'{value}π',steps,[f'{value-1}π',f'{value+1}π',f'{value+2}π'])
    cards = [
        ('cylinder','Cylinder volume',['cylinder volume'],'A cylinder has volume πr²h, equal to circular base area times perpendicular height. Volume is measured in cubic units.','Use radius, not diameter, in r².',['Find the radius.','Multiply base area by height.','Check cubic units.']),
        ('cone','Cone volume and recasting',['cone volume'],'A cone has volume πr²h/3. Its perpendicular height differs from its slant height. When material is recast without loss, total volume stays constant.','Omitting the factor 1/3 makes the cone volume three times too large.',['Use perpendicular height.','Include the factor 1/3.','Equate volumes when material is conserved.']),
        ('hemisphere','Hemisphere surface area',['hemisphere area'],'A hemisphere has curved area 2πr² and total area 3πr² when its circular base is included. State which surfaces are exposed.','Curved area excludes the flat circular base.',['Identify whether the base counts.','Use curved or total area accordingly.','Keep square units.']),
        ('combined-volume','Combined solids and volume conservation',['combined volume'],'Add non-overlapping component volumes to find a composite solid’s volume. For recasting, divide total material volume by the volume of one new piece.','Do not add surface areas when the question asks for volume.',['Split into named solids.','Avoid overlapping volumes.','Use equal volumes if material is recast.']),
        ('exposed-area','Exposed surface area',['exposed area'],'Trace the surfaces visible outside a combined solid. Joined faces are internal and must be excluded; an exposed base must be included if requested.','Adding total areas of components double-counts their joined faces.',['List exposed curved surfaces.','List exposed flat surfaces.','Exclude internal joins.'])]
    for ci,card in enumerate(cards):
        b.concept(*card)
        for t in range(3):
            for n in [2,3,4]:
                if ci == 0:
                    if t == 0: piq(t,f'Find the volume in cm³ of a cylinder with radius {n} cm and height 5 cm.',5*n*n,[f'V = π × {n}² × 5 = {5*n*n}π cm³.'])
                    elif t == 1: piq(t,f'A cylinder has diameter {2*n} cm and height {3*n} cm. Find its volume in cm³.',3*n**3,[f'Radius = {n}.',f'V = π × {n}² × {3*n} = {3*n**3}π.'])
                    else: b.q(t,f'A cylindrical vessel has radius {n} cm and contains {4*n**3}π cm³ of water. Find water depth in cm.',4*n,[f'π × {n*n} × h = {4*n**3}π.',f'h = {4*n}.'])
                elif ci == 1:
                    if t == 0: piq(t,f'Find the volume in cm³ of a cone with radius 3 cm and perpendicular height {3*n} cm.',9*n,[f'V = π × 9 × {3*n}/3 = {9*n}π.'])
                    elif t == 1: b.q(t,f'A cone of radius 3 cm has volume {9*n}π cm³. Find its perpendicular height in cm.',3*n,[f'3πh = {9*n}π, so h = {3*n}.'])
                    else: b.q(t,f'A solid cylinder of radius 3 cm and height {4*n} cm is melted without loss into cones of radius 3 cm and height {n} cm. How many cones are formed?',12,[f'Cylinder volume = {36*n}π; each cone volume = {3*n}π.', 'Their ratio is 12.'])
                elif ci == 2:
                    if t == 0: piq(t,f'Find the curved surface area in cm² of a hemisphere of radius {n} cm.',2*n*n,[f'Curved area = 2π × {n}² = {2*n*n}π.'])
                    elif t == 1: piq(t,f'Find the total surface area in cm² of a hemisphere of radius {n} cm, including its base.',3*n*n,[f'Curved area plus base = (2 + 1)π × {n}² = {3*n*n}π.'])
                    else: b.q(t,f'A hemisphere has curved surface area {2*n*n}π cm². Find its radius in cm.',n,[f'2πr² = {2*n*n}π gives r² = {n*n}.',f'Take the positive root: r = {n}.'])
                elif ci == 3:
                    if t == 0: piq(t,f'A cylinder of radius {n} cm and height 3 cm is topped by a cone of the same radius and height 3 cm. Find total volume in cm³.',4*n*n,[f'Cylinder = {3*n*n}π and cone = {n*n}π.',f'Total = {4*n*n}π.'])
                    elif t == 1: piq(t,f'A solid cylinder of radius 3 cm and height {n} cm is topped by a hemisphere of radius 3 cm. Find total volume in cm³.',9*n+18,[f'Cylinder = {9*n}π; hemisphere = (2/3)π × 27 = 18π.',f'Total = {9*n+18}π.'])
                    else: b.q(t,f'A solid sphere of radius {3*n} cm is melted without loss into spheres of radius {n} cm. How many small spheres are formed?',27,['Sphere volume scales with the cube of the radius.',f'Count = ({3*n}/{n})³ = 27.'])
                else:
                    if t == 0: piq(t,f'Find the curved surface area in cm² of a cylinder of radius {n} cm and height 5 cm; exclude both ends.',10*n,[f'Curved area = 2πrh = 2π × {n} × 5 = {10*n}π.'])
                    elif t == 1: piq(t,f'A cone has radius {3*n} cm and perpendicular height {4*n} cm. Find total surface area in cm² including its base.',24*n*n,[f'Slant height = √({9*n*n}+{16*n*n}) = {5*n}.',f'Area = πr(l+r) = π × {3*n} × {8*n} = {24*n*n}π.'])
                    else: piq(t,f'A cylinder of radius {n} cm and height {3*n} cm has a same-radius hemisphere on top. Include the exposed bottom. Find total exposed area in cm².',9*n*n,[f'Cylinder curve = {6*n*n}π, hemisphere curve = {2*n*n}π, bottom = {n*n}π.',f'Total = {9*n*n}π; the joined circular faces are internal.'])
    return b.dump()


def statistics():
    b = ChapterBank(13)
    cards = [
        ('class-marks','Class marks and intervals',['class marks'],'The class mark is the midpoint of a class interval, (lower + upper)/2. In grouped-mean calculations this midpoint represents the values in that class.','The class width is upper minus lower; it is not the class mark.',['Read both class limits.','Average them for the class mark.','Keep width and midpoint distinct.']),
        ('cumulative','Cumulative frequencies',['cumulative frequency'],'A cumulative frequency adds all frequencies up to and including a class. Subtract successive cumulative totals to recover a class frequency.','A cumulative total includes earlier classes, not only the current one.',['Accumulate from the first class.','Subtract successive totals to recover a frequency.','Check the last total equals N.']),
        ('mean','Grouped mean',['grouped mean'],'The estimated grouped mean is Σfᵢxᵢ/Σfᵢ, where xᵢ are class marks. Frequencies supply the weights.','An unweighted average of class marks is wrong when frequencies differ.',['Multiply each midpoint by its frequency.','Add products and frequencies separately.','Divide the totals.']),
        ('median','Grouped median',['grouped median'],'Find the median class using N/2 and cumulative frequencies. The estimated median is l + [(N/2 − cf)/f]h, where cf is the cumulative frequency before that class.','Use cf before the median class, not the cumulative total including it.',['Locate the median class.','Identify l, cf, f and h.','Substitute into the interpolation formula.']),
        ('mode','Grouped mode',['grouped mode'],'For equal-width classes, the modal class has the greatest frequency. The estimated mode is l + [(f₁−f₀)/(2f₁−f₀−f₂)]h.','f₀ and f₂ are neighbouring class frequencies, not cumulative frequencies.',['Find the highest-frequency class.','Read both neighbours.','Use the mode formula with the class width.'])]
    for ci,card in enumerate(cards):
        b.concept(*card)
        for t in range(3):
            for n in [2,3,4]:
                if ci == 0:
                    if t == 0: b.q(t,f'Find the class mark of the interval {10*n}–{10*n+10}.',10*n+5,[f'Midpoint = ({10*n} + {10*n+10})/2 = {10*n+5}.'])
                    elif t == 1: b.q(t,f'A class has mark {10*n+5} and width 10. Find its lower limit.',10*n,[f'Lower limit = midpoint − half-width = {10*n+5} − 5 = {10*n}.'])
                    else: b.q(t,f'A class has lower limit {10*n} and mark {10*n+7}. Find its upper limit.',10*n+14,[f'(Lower + upper)/2 = {10*n+7}.',f'Upper = 2 × {10*n+7} − {10*n} = {10*n+14}.'])
                elif ci == 1:
                    if t == 0: b.q(t,f'The first three class frequencies are {n}, {2*n}, {3*n}. Find cumulative frequency through the second class.',3*n,[f'Add the first two frequencies: {n} + {2*n} = {3*n}.'])
                    elif t == 1: b.q(t,f'Cumulative frequency before a class is {3*n} and through that class is {8*n}. Find its frequency.',5*n,[f'Frequency = {8*n} − {3*n} = {5*n}.'])
                    else: b.q(t,f'A distribution has total frequency {12*n}. Cumulative frequency through the penultimate class is {7*n}. Find the last class frequency.',5*n,[f'Last frequency = {12*n} − {7*n} = {5*n}.'])
                elif ci == 2:
                    if t == 0: b.q(t,f'Class marks are {n}, {3*n}, {5*n}, with frequencies 1, 1, 1. Find the grouped mean.',3*n,[f'Mean = ({n} + {3*n} + {5*n})/3 = {3*n}.'])
                    elif t == 1: b.q(t,f'Class marks are {n}, {3*n}, {5*n}, with frequencies 1, 2, 3. Find the grouped mean.',F(11*n,3),[f'Weighted sum = {n} + {6*n} + {15*n} = {22*n}.','Total frequency is 6.',f'Mean = {F(11*n,3)}.'])
                    else: b.q(t,f'Two groups have {n} and {2*n} observations with means {10*n} and {16*n}. Find their combined mean.',14*n,[f'Total sum = {n} × {10*n} + {2*n} × {16*n} = {42*n*n}.',f'Divide by {3*n}: mean = {14*n}.'])
                elif ci == 3:
                    if t == 0: b.q(t,f'A median class has l = {10*n}, N = 20, cf = 6, f = 8, h = 10. Find the grouped median.',10*n+5,[f'Median = {10*n} + [(10 − 6)/8] × 10 = {10*n+5}.'])
                    elif t == 1: b.q(t,f'Continuous classes [{10*n},{10*n+10}), [{10*n+10},{10*n+20}), [{10*n+20},{10*n+30}) have frequencies 4, 12, 4. Find the grouped median.',10*n+15,['N = 20; the middle class contains N/2 = 10.',f'Median = {10*n+10} + [(10 − 4)/12] × 10 = {10*n+15}.'])
                    else: b.q(t,f'A median class has l = {10*n}, h = 10, f = 20, cf = 10. The median is {10*n+5}. Find total frequency N.',40,[f'{10*n+5} − {10*n} = [(N/2 − 10)/20] × 10.', 'Hence N/2 − 10 = 10 and N = 40.'])
                else:
                    if t == 0: b.q(t,f'Equal-width classes have lower limits {10*n}, {10*n+10}, {10*n+20} and frequencies 3, 9, 4. Find the modal class lower limit.',10*n+10,['The middle class has the greatest frequency, 9.',f'Its lower limit is {10*n+10}.'])
                    elif t == 1: b.q(t,f'A modal class has l = {10*n}, h = 10, f₀ = 4, f₁ = 10, f₂ = 6. Find the grouped mode.',10*n+6,[f'Mode = {10*n} + [(10 − 4)/(20 − 4 − 6)] × 10 = {10*n+6}.'])
                    else: b.q(t,f'Equal-width classes [{10*n},{10*n+10}), [{10*n+10},{10*n+20}), [{10*n+20},{10*n+30}) have frequencies 5, 15, 5. Find the grouped mode.',10*n+15,[f'The middle class is modal. Mode = {10*n+10} + [(15 − 5)/(30 − 5 − 5)] × 10 = {10*n+15}.'])
    return b.dump()


def probability():
    b = ChapterBank(14)
    cards = [
        ('equally-likely','Equally likely outcomes',['equally likely outcomes'],'When all elementary outcomes are equally likely, P(E) = favourable outcomes / total outcomes. List outcomes before counting.','The counting formula needs equally likely outcomes; not all verbal categories are equally likely.',['State the sample space.','Count favourable outcomes once each.','Reduce the fraction.']),
        ('complement','Complementary events',['complement'],'An event and its complement cover every outcome without overlap, so P(not E) = 1 − P(E). Probabilities lie between 0 and 1.','The complement of at least one is none, not exactly one.',['Describe the complement precisely.','Subtract its probability from 1.','Check the result is in [0,1].']),
        ('draws','Random draws',['random draw'],'For a uniformly chosen ball or numbered card, count the objects that satisfy the condition and divide by the total number of objects.','Objects are counted, not just the number of colour categories.',['Count the full collection.','Count objects meeting the condition.','Recount totals after additions.']),
        ('sample-space','Coin sample spaces',['sample space'],'Independent fair coin tosses have equally likely ordered H/T sequences. Enumerate them or count positions when calculating an event.','HH, HT, TH and TT are four outcomes; one-head is not a single elementary outcome.',['List ordered sequences.','Apply exactly, at least, or at most carefully.','Count favourable sequences.']),
        ('dice','Two-dice sample spaces',['two dice'],'Two independent fair six-sided dice have 36 equally likely ordered outcomes. Sums are not equally likely; count the ordered pairs that produce the event.','(2,5) and (5,2) are different ordered outcomes.',['Use ordered pairs.','Count pairs satisfying the condition.','Divide by 36 and simplify.'])]
    for ci,card in enumerate(cards):
        b.concept(*card)
        for t in range(3):
            for n in [2,3,4]:
                if ci == 0:
                    if t == 0: b.q(t,f'A fair six-sided die is rolled. Find P(score ≤ {n}).',F(n,6),[f'Favourable scores are 1 through {n}: {n} out of 6.',f'Probability = {F(n,6)}.'])
                    elif t == 1: b.q(t,f'Choose uniformly an integer from 1 to {6*n}, inclusive. Find P(a multiple of 3).',F(1,3),[f'There are {2*n} multiples of 3 among {6*n} integers.', 'Probability = 1/3.'])
                    else:
                        count=sum(k%2==0 or k%3==0 for k in range(1,6*n+1))
                        b.q(t,f'Choose uniformly an integer from 1 to {6*n}, inclusive. Find P(divisible by 2 or 3).',F(count,6*n),[f'Count multiples: {3*n} of 2, {2*n} of 3; subtract {n} multiples of 6 counted twice.',f'Probability = {4*n}/{6*n} = 2/3.'])
                elif ci == 1:
                    if t == 0: b.q(t,f'P(E) = {n}/10. Find P(not E).',1-F(n,10),[f'P(not E) = 1 − {n}/10 = {1-F(n,10)}.'])
                    elif t == 1: b.q(t,f'A bag has {n} red and {2*n+1} blue balls, all equally likely to be drawn. Find P(not red).',F(2*n+1,3*n+1),[f'There are {3*n+1} balls.',f'P(not red) = 1 − {n}/{3*n+1} = {F(2*n+1,3*n+1)}.'])
                    else: b.q(t,f'Toss {n} independent fair coins. Find P(at least one head).',1-F(1,2**n),[f'The complement is all tails: one sequence out of {2**n}.',f'Probability = 1 − 1/{2**n} = {1-F(1,2**n)}.'])
                elif ci == 2:
                    if t == 0: b.q(t,f'A bag has {n} white and {n+3} black balls. Draw one uniformly. Find P(black).',F(n+3,2*n+3),[f'Total = {2*n+3}; black = {n+3}.',f'P = {F(n+3,2*n+3)}.'])
                    elif t == 1: b.q(t,f'Cards numbered 1 to {5*n} are equally likely to be drawn. Find P(a number greater than {3*n}).',F(2,5),[f'There are {2*n} qualifying cards out of {5*n}.','Probability = 2/5.'])
                    else: b.q(t,f'A bag starts with {n} red and {2*n} blue balls. How many red balls must be added to make P(red) = 1/2 on a uniform draw?',n,['Red and blue counts must become equal.',f'Add {2*n} − {n} = {n} red balls.'])
                elif ci == 3:
                    if t == 0: b.q(t,f'Toss {n} independent fair coins. How many equally likely ordered sequences are possible?',2**n,[f'Two choices for each coin gives 2^{n} = {2**n}.'])
                    elif t == 1: b.q(t,f'Toss {n} independent fair coins. Find P(exactly one head).',F(n,2**n),[f'The head can occupy {n} positions among {2**n} sequences.',f'Probability = {F(n,2**n)}.'])
                    else: b.q(t,f'Toss {n} independent fair coins. Find P(at most one head).',F(n+1,2**n),[f'One all-tail sequence plus {n} one-head sequences gives {n+1} favourable outcomes.',f'Probability = {F(n+1,2**n)}.'])
                else:
                    target=n+4
                    count=sum(i+j==target for i in range(1,7) for j in range(1,7))
                    if t == 0: b.q(t,f'Two independent fair dice are rolled. Find P(sum = {target}).',F(count,36),[f'There are {count} ordered pairs with sum {target}, out of 36.',f'Probability = {F(count,36)}.'])
                    elif t == 1: b.q(t,f'Two independent fair dice are rolled. Find P(both scores ≤ {n}).',F(n*n,36),[f'Each die has {n} qualifying scores, giving {n*n} ordered pairs.',f'Probability = {F(n*n,36)}.'])
                    else:
                        count=sum(i+j>=target for i in range(1,7) for j in range(1,7))
                        b.q(t,f'Two independent fair dice are rolled. Find P(sum ≥ {target}).',F(count,36),[f'Count all ordered pairs with sums {target} through 12: {count} pairs.',f'Probability = {F(count,36)}.'])
    return b.dump()


def build_all():
    return [fn() for fn in [linear,quadratics,progressions,triangles,coordinates,trig,applications,circles,areas,solids,statistics,probability]]


if __name__ == '__main__':
    from app.schemas.adaptive import PracticeBank
    for content in build_all():
        bank = PracticeBank.model_validate(content)
        chapter = int(bank.chapterId[-2:])
        path = ROOT / 'data' / f'{NAMES[chapter]}-practice-v1.json'
        path.write_text(json.dumps(bank.model_dump(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f'{bank.chapterId}: {len(bank.concepts)} concepts, {len(bank.questions)} questions')
