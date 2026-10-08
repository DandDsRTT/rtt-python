# rtt.library examples

Verified snippets for the library (each one was run; its exact output follows). Import from rtt.library.<module> as shown. Signatures for every public function are in the reference above.

## rtt.library.addition
Temperament arithmetic: the sum and difference of two addable temperaments (e.g. ET sums like 12+19=31, comma sums, rank-2 mapping sums like meantone+porcupine=tetracot).
Functions:
- sum_(t1: Temperament, t2: Temperament) -> Temperament: temperament sum in canonical form; returns t1's canonical form if both are equal; output has t1's variance
- diff_(t1: Temperament, t2: Temperament) -> Temperament: temperament difference in canonical form (sign-normalized, so diff_(a, b) == diff_(b, a))
Pitfalls:
- The function names end in an underscore: sum_ and diff_ (they shadow nothing; there is no plain sum/diff).
- Temperaments must have the same rank, dimensionality and domain basis; otherwise ValueError("temperaments not addable: dimensions or bases differ").
- Addition is defined only up to sign: diff_ is sign-normalized by canonical form, so diff_(12-ET, 19-ET) and diff_(19-ET, 12-ET) both give ⟨7 11 16 19]. Do not use diff_ to tell which ET is 'larger'.
- sum_(t, t) returns t (canonicalized); diff_(t, t) raises ValueError("cannot diff a temperament with itself").
- Mixed variance is allowed: the second argument is dualized to the first's variance, and the result comes back in the FIRST argument's variance.
- The result's domain basis is preserved (e.g. two 2.3.7 maps sum to a 2.3.7 map).
### Temperament sum and difference of two commas (meantone + porcupine), with ratios
```python
from rtt.library.addition import sum_, diff_
from rtt.library.parsing import parse_temperament_data
from rtt.library.formatting import to_ebk
from rtt.library.math_utils import pcv_to_quotient
meantone, porcupine = parse_temperament_data("[4 -4 1⟩"), parse_temperament_data("[1 -5 3⟩")
s, d = sum_(meantone, porcupine), diff_(meantone, porcupine)
print(to_ebk(s), pcv_to_quotient(s.matrix[0]))
print(to_ebk(d), pcv_to_quotient(d.matrix[0]))
```
Output:
```
[5 -9 4⟩ 20000/19683
[-3 -1 2⟩ 25/24
```
### ET sum/difference: 12 + 19 = 31, 12 - 19 -> 7 (sign normalized)
```python
from rtt.library.addition import sum_, diff_
from rtt.library.parsing import parse_temperament_data
from rtt.library.formatting import to_ebk
et12, et19 = parse_temperament_data("⟨12 19 28 34]"), parse_temperament_data("⟨19 30 44 53]")
print(to_ebk(sum_(et12, et19)))
print(to_ebk(diff_(et12, et19)))
```
Output:
```
⟨31 49 72 87]
⟨7 11 16 19]
```
### Rank-2 mapping sum/diff: meantone + porcupine = tetracot, difference = dicot
```python
from rtt.library.addition import sum_, diff_
from rtt.library.parsing import parse_temperament_data
from rtt.library.formatting import to_ebk
from rtt.library.dual import dual
meantone = parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]⧽")
porcupine = parse_temperament_data("[⟨1 2 3] ⟨0 3 5]⧽")
tetracot = sum_(meantone, porcupine)
dicot = diff_(meantone, porcupine)
print(to_ebk(tetracot), to_ebk(dual(tetracot)))
print(to_ebk(dicot), to_ebk(dual(dicot)))
```
Output:
```
[⟨1 1 1] ⟨0 4 9]⧽ [5 -9 4⟩
[⟨1 1 2] ⟨0 2 1]⧽ [-3 -1 2⟩
```
### Errors: non-addable pair and diffing a temperament with itself; summing with itself returns it
```python
from rtt.library.addition import sum_, diff_
from rtt.library.parsing import parse_temperament_data
et7 = parse_temperament_data("⟨7 11 16]")
meantone = parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]⧽")
for a, b in ((et7, meantone), (et7, et7)):
    try:
        print(diff_(a, b))
    except ValueError as e:
        print("ValueError:", e)
print(sum_(et7, et7))
```
Output:
```
ValueError: temperaments not addable: dimensions or bases differ
ValueError: cannot diff a temperament with itself
Temperament(matrix=((7, 11, 16),), variance=<Variance.ROW: 'row'>, domain_basis=None)
```

## rtt.library.canonicalization
Canonical (defactored Hermite normal) form of mappings and comma bases, so two different-looking matrices for the same temperament compare equal.
Functions:
- canonical_form(t: Temperament) -> Temperament: canonical mapping (ROW) or canonical comma basis (COL); keeps a nonstandard domain basis, turns a standard prime-limit basis into None
- canonical_ma(matrix: Matrix) -> Matrix: canonical mapping of a raw matrix: defactor, Hermite normal form, remove redundant zero rows
- canonical_ca(matrix: Matrix) -> Matrix: canonical comma basis of a raw matrix of comma vectors (rotate_180 ∘ canonical_ma ∘ rotate_180)
- column_hermite_defactor(matrix: Matrix) -> Matrix: the defactoring step alone (removes enfactoring), not yet in Hermite form
Pitfalls:
- Two mappings describe the same temperament exactly when their canonical_form results are equal; compare canonical forms, never raw matrices.
- The canonical mapping is not necessarily the familiar generator form: meantone's canonical form is [⟨1 0 -4] ⟨0 1 4]⧽, while the fifth-and-octave form [⟨1 1 0] ⟨0 1 4]⧽ is the equave-reduced form (generator_forms).
- Canonical comma vectors are sign-normalized by their trailing entry, so they can be ratios below 1: meantone's canonical comma is [4 -4 1⟩ = 80/81. Use comma_forms.positive_ratio_ca or math_utils.super_ to present 81/80.
- Canonicalization defactors: ⟨24 38 56] becomes ⟨12 19 28]. Check enfactoring with matrix_utils.smith_normal_form_with_transforms if that matters.
- canonical_ma / canonical_ca take raw matrices; canonical_form takes a Temperament.
### Canonical form identifies a temperament regardless of how its mapping was written
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.canonicalization import canonical_form
from rtt.library.formatting import to_ebk

fifth_form = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
from_ets = parse_temperament_data("[⟨5 8 12] ⟨7 11 16]⧽")
print(to_ebk(canonical_form(fifth_form)))
print(to_ebk(canonical_form(from_ets)))
print(canonical_form(fifth_form) == canonical_form(from_ets))
```
Output:
```
[⟨1 0 -4] ⟨0 1 4]⧽
[⟨1 0 -4] ⟨0 1 4]⧽
True
```
### Canonicalization defactors (removes enfactoring) and drops redundant rows; comma bases are canonicalized too
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.canonicalization import canonical_form, canonical_ma, canonical_ca
from rtt.library.formatting import to_ebk

print(to_ebk(canonical_form(parse_temperament_data("⟨24 38 56]"))))
print(to_ebk(canonical_form(parse_temperament_data("[⟨12 19 28] ⟨24 38 56]⧽"))))
print(to_ebk(canonical_form(parse_temperament_data("[-8 8 -2⟩"))))
print(canonical_ma(((17, 16, -4), (4, -4, 1))))
print(canonical_ca(((-4, 4, -1),)))
```
Output:
```
⟨12 19 28]
⟨12 19 28]
[4 -4 1⟩
((1, 0, 0), (0, 4, -1))
((4, -4, 1),)
```
### A nonstandard domain basis is kept; a standard prime-limit basis is dropped to None
```python
from rtt.library.temperament import Temperament, Variance
from rtt.library.canonicalization import canonical_form

print(canonical_form(Temperament(((22, 70, 62),), Variance.ROW, (2, 9, 7))))
print(canonical_form(Temperament(((24, 38, 56),), Variance.ROW, (2, 3, 5))))
```
Output:
```
Temperament(matrix=((11, 35, 31),), variance=<Variance.ROW: 'row'>, domain_basis=(2, 9, 7))
Temperament(matrix=((12, 19, 28),), variance=<Variance.ROW: 'row'>, domain_basis=None)
```

## rtt.library.change_basis
Re-expresses a temperament over a different domain basis: restricts a mapping to a subgroup, or extends a comma basis to a larger basis, returning the canonical form.
Functions:
- change_domain_basis(t: Temperament, target_domain_basis: tuple) -> Temperament: dispatches on t.variance (ROW -> change_domain_basis_for_m, COL -> change_domain_basis_for_c)
- change_domain_basis_for_m(m: Temperament, target_subspace: tuple) -> Temperament: restrict a ROW mapping to a sub-basis
- change_domain_basis_for_c(c: Temperament, target_superspace: tuple) -> Temperament: extend a COL comma basis to a super-basis
Pitfalls:
- Direction depends on variance: a mapping (ROW) can only be RESTRICTED to a sub-basis; a comma basis (COL) can only be EXTENDED to a super-basis. To extend a mapping, dual() it to its comma basis, extend, and dual() back
- The _for_m/_for_c variants do NOT convert variance; passing a comma basis to change_domain_basis_for_m treats its vectors as map rows (wrong). Prefer change_domain_basis, which dispatches on variance.
- target_domain_basis is a tuple of ints/Fractions (use parse_domain_basis("2.9.11")), not a string.
- The result is canonical form, which divides out common factors: 22-ET restricted to 2.9.11 prints as ⟨11 35 38], not ⟨22 70 76]. Explain this when a user expects the original ET number.
- When the target is a standard prime limit the result's domain_basis is None (e.g. restricting meantone to 2.3).
### Extend a comma basis to 7-limit; restrict a 5-limit mapping to the 2.3 subgroup
```python
from rtt.library.change_basis import change_domain_basis
from rtt.library.parsing import parse_temperament_data, parse_domain_basis
from rtt.library.formatting import to_ebk
meantone_comma = parse_temperament_data("[4 -4 1⟩")
print(to_ebk(change_domain_basis(meantone_comma, parse_domain_basis("2.3.5.7"))))
meantone = parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]⧽")
r = change_domain_basis(meantone, parse_domain_basis("2.3"))
print(to_ebk(r), r.domain_basis)
```
Output:
```
[4 -4 1 0⟩
[⟨1 0] ⟨0 1]⟩ None
```
### Restrict 22-ET (2.3.5.11) to the 2.9.11 subgroup (note the gcd is divided out)
```python
from rtt.library.change_basis import change_domain_basis
from rtt.library.parsing import parse_temperament_data, parse_domain_basis
from rtt.library.formatting import to_ebk
et22 = parse_temperament_data("2.3.5.11 ⟨22 35 51 76]")
r = change_domain_basis(et22, parse_domain_basis("2.9.11"))
print(r)
print(to_ebk(r))
```
Output:
```
Temperament(matrix=((11, 35, 38),), variance=<Variance.ROW: 'row'>, domain_basis=(2, 9, 11))
⟨11 35 38]
```
### Invalid basis changes raise ValueError
```python
from rtt.library.change_basis import change_domain_basis
from rtt.library.parsing import parse_temperament_data
et12 = parse_temperament_data("⟨12 19 28]")
try:
    change_domain_basis(et12, (2, 3, 5, 7))
except ValueError as e:
    print("ValueError:", e)
comma = parse_temperament_data("[4 -4 1⟩")
try:
    change_domain_basis(comma, (2, 9, 7))
except ValueError as e:
    print("ValueError:", e)
```
Output:
```
ValueError: target domain basis must be a sub-basis of the mapping's
ValueError: target domain basis must be a super-basis of the comma basis's
```
### Comma basis over 2.9/7.5/3 re-expressed over 2.3.5.7 (standard result has domain_basis None)
```python
from fractions import Fraction as F
from rtt.library.change_basis import change_domain_basis
from rtt.library.temperament import Temperament, Variance
from rtt.library.formatting import to_ebk
c = Temperament(((0, 1, 0), (0, -2, 1)), Variance.COL, (2, F(9, 7), F(5, 3)))
r = change_domain_basis(c, (2, 3, 5, 7))
print(r)
print(to_ebk(r))
```
Output:
```
Temperament(matrix=((0, -1, 1, 0), (0, -2, 0, 1)), variance=<Variance.COL: 'col'>, domain_basis=None)
⧼[0 -1 1 0⟩ [0 -2 0 1⟩]
```

## rtt.library.comma_forms
Alternative presentations of a comma basis: positive-ratio (each comma above 1) and minimal (simplest commas spanning the same lattice).
Functions:
- positive_ratio_ca(matrix: Matrix, jip_octaves) -> Matrix: canonical comma basis with each comma's sign flipped so its ratio is greater than 1
- minimal_ca(matrix: Matrix, jip_octaves) -> Matrix: lattice-reduced comma basis of the simplest commas (by log-prime-weighted complexity) that generate the same temperament, made positive and ordered b…
Pitfalls:
- Both take a raw matrix of comma vectors (e.g. dual(t).matrix), not a Temperament; passing a Temperament raises TypeError.
- jip_octaves is the just tuning map in octaves (log2 of each prime), usually generator_forms.standard_jip_octaves(d); it must have length d.
- standard_jip_octaves assumes the standard primes; for a nonstandard domain basis build the tuple yourself as math.log2 of each basis element.
- minimal_ca searches small integer combinations of a reduced basis; for very high-nullity inputs it falls back to the reduced seed basis.
- Results are raw vectors; convert with math_utils.pcv_to_quotient (standard primes only) to show ratios.
### Positive-ratio comma basis: canonical commas sign-flipped so each ratio is greater than 1
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.dual import dual
from rtt.library.comma_forms import positive_ratio_ca
from rtt.library.generator_forms import standard_jip_octaves
from rtt.library.math_utils import pcv_to_quotient

commas = dual(parse_temperament_data("[⟨1 0 -4 -13] ⟨0 1 4 10]⧽")).matrix
print(commas)
positive = positive_ratio_ca(commas, standard_jip_octaves(4))
print(positive)
print([pcv_to_quotient(v) for v in positive])
```
Output:
```
((4, -4, 1, 0), (13, -10, 0, 1))
((-4, 4, -1, 0), (-13, 10, 0, -1))
[Fraction(81, 80), Fraction(59049, 57344)]
```
### Minimal comma basis: the simplest commas generating the same comma lattice (septimal meantone, 12-ET)
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.dual import dual
from rtt.library.comma_forms import minimal_ca
from rtt.library.generator_forms import standard_jip_octaves
from rtt.library.math_utils import pcv_to_quotient

for text, d in [("[⟨1 0 -4 -13] ⟨0 1 4 10]⧽", 4), ("⟨12 19 28]", 3)]:
    commas = dual(parse_temperament_data(text)).matrix
    minimal = minimal_ca(commas, standard_jip_octaves(d))
    print(text, "canonical:", [pcv_to_quotient(v) for v in commas])
    print(text, "minimal:  ", [pcv_to_quotient(v) for v in minimal])
```
Output:
```
[⟨1 0 -4 -13] ⟨0 1 4 10]⧽ canonical: [Fraction(80, 81), Fraction(57344, 59049)]
[⟨1 0 -4 -13] ⟨0 1 4 10]⧽ minimal:   [Fraction(81, 80), Fraction(126, 125)]
⟨12 19 28] canonical: [Fraction(531441, 524288), Fraction(32805, 32768)]
⟨12 19 28] minimal:   [Fraction(81, 80), Fraction(128, 125)]
```

## rtt.library.complexity
Computes interval complexities (prescaled q-norms of prime-count vectors) and the complexity prescaler diagonal used for damage weighting and all-interval tuning.
Functions:
- get_complexity_prescaler(t: Temperament, spec: ComplexitySpec, override=None) -> list[float]: diagonal prescaler, one weight per domain-basis element: log2(n*d)**log_prime_power * (n*d)**prime_power o…
- get_complexity(pcv: tuple, t: Temperament, spec: ComplexitySpec, prescaler_override=None) -> float: complexity of the interval whose prime-count vector (in t's domain basis, padded to d) is pcv: q-nor…
Pitfalls:
- get_complexity takes a ComplexitySpec, not a TuningSchemeSpec or a name: use resolve_tuning_scheme(name).complexity to get the complexity a scheme uses. It is also importable as rtt.library.tuning.get_complexity (same function).
- pcv must be a prime-count vector in the temperament's domain basis padded to its dimensionality d: quotient_to_pcv(Fraction(3, 2)) is only (-1, 1) for a 5-limit temperament; pad it with pad_vectors_with_zeros_up_to_d.
- Units: log-prime complexities are in octaves (log2 units), so lp(5/4) = log2(4) + log2(5) = 4.3219; copfr is a count of prime factors; sopfr is a sum of primes (5/4 -> 2+2+5 = 9). Simplicity weights are 1/complexity.
- Size-factor complexities (lils, ils, lols, ols, limit) are normalized by dividing by (1 + size_factor); lols / ols also zero out prime 2 (rough = 3), so the lols complexity of 5/4 is log2(5) = 2.3219.
- For a nonstandard domain basis the default (neutral) complexity factors each basis element into primes (2.3.13/5's third prescaler entry is log2(13*5) = 6.0224)
### Complexity of 5/4 under several complexity specs, including the ones carried by named schemes
```python
from fractions import Fraction

from rtt.library.complexity import get_complexity
from rtt.library.math_utils import pad_vectors_with_zeros_up_to_d, quotient_to_pcv
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning_scheme_names import ComplexitySpec, resolve_tuning_scheme

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
pcv = pad_vectors_with_zeros_up_to_d((quotient_to_pcv(Fraction(5, 4)),), 3)[0]
print("5/4 as prime-count vector:", pcv)
for label, spec in [
    ("lp (log-prime taxicab, the S/C default)", ComplexitySpec()),
    ("E (log-prime Euclidean)", ComplexitySpec(norm_power=2)),
    ("copfr", ComplexitySpec(log_prime_power=0)),
    ("sopfr", ComplexitySpec(log_prime_power=0, prime_power=1)),
    ("from scheme minimax-E-lils-S", resolve_tuning_scheme("minimax-E-lils-S").complexity),
    ("from scheme minimax-lols-S", resolve_tuning_scheme("minimax-lols-S").complexity),
]:
    print(f"{label:42s} {get_complexity(pcv, meantone, spec):.4f}")
```
Output:
```
5/4 as prime-count vector: (-2, 0, 1)
lp (log-prime taxicab, the S/C default)    4.3219
E (log-prime Euclidean)                    3.0645
copfr                                      3.0000
sopfr                                      9.0000
from scheme minimax-E-lils-S               1.5407
from scheme minimax-lols-S                 2.3219
```
### Prescaler diagonals for standard and nonstandard (2.3.13/5) domains
```python
from rtt.library.complexity import get_complexity_prescaler
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning_scheme_names import ComplexitySpec

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
print("log-prime:", [round(x, 4) for x in get_complexity_prescaler(meantone, ComplexitySpec())])
print("sopfr:", get_complexity_prescaler(meantone, ComplexitySpec(log_prime_power=0, prime_power=1)))
print("copfr:", get_complexity_prescaler(meantone, ComplexitySpec(log_prime_power=0)))
barbados = parse_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]⧽")
print("2.3.13/5 log-prime:", [round(x, 4) for x in get_complexity_prescaler(barbados, ComplexitySpec())])
print("2.3.13/5 nonprime-based:", [round(x, 4) for x in get_complexity_prescaler(barbados, ComplexitySpec(nonprime_basis_approach="nonprime-based"))])
print("override passes through:", get_complexity_prescaler(meantone, ComplexitySpec(), override=(1.0, 2.0, 3.0)))
```
Output:
```
log-prime: [1.0, 1.585, 2.3219]
sopfr: [2.0, 3.0, 5.0]
copfr: [1.0, 1.0, 1.0]
2.3.13/5 log-prime: [1.0, 1.585, 6.0224]
2.3.13/5 nonprime-based: [1.0, 1.585, 1.3785]
override passes through: (1.0, 2.0, 3.0)
```
### Neutral (prime-factored) versus nonprime-based complexity of 11/7 in the 2.7/3.11/3 subgroup
```python
from math import log2

from rtt.library.complexity import get_complexity
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning_scheme_names import ComplexitySpec

t = parse_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]⧽")
eleven_over_seven = (0, -1, 1)
print("neutral (prime-factored):", round(get_complexity(eleven_over_seven, t, ComplexitySpec()), 4), "= log2(77) =", round(log2(77), 4))
print("nonprime-based:", round(get_complexity(eleven_over_seven, t, ComplexitySpec(nonprime_basis_approach="nonprime-based")), 4))
```
Output:
```
neutral (prime-factored): 6.2668 = log2(77) = 6.2668
nonprime-based: 3.0969
```

## rtt.library.dimensions
Dimensionality d, rank r and nullity n of a Temperament of either variance.
Functions:
- get_dimensionality(t: Temperament) -> int: d, the length of the vectors/maps (number of domain-basis elements)
- get_rank(t: Temperament) -> int: r; for ROW the matrix rank of the mapping, for COL d minus the matrix rank of the comma basis
- get_nullity(t: Temperament) -> int: n = d - r (number of independent commas)
Pitfalls:
- For a comma basis (COL) get_rank is the temperament's rank (d - number of independent commas), not the number of commas; [4 -4 1⟩ has r=2.
- Rank counts linearly independent rows only: duplicate or enfactored rows do not raise it ("[⟨12 19 28] ⟨24 38 56]⧽" has r=1).
- A tuning map with float entries parses as a rank-1 ROW Temperament.
- Dimensionality ignores the domain basis values; "2.3.7 ..." is still d=3.
### Dimensionality d, rank r and nullity n of mappings, comma bases and ETs
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.dimensions import get_dimensionality, get_rank, get_nullity

for text in ["[⟨1 1 0] ⟨0 1 4]⧽", "[4 -4 1⟩", "⟨12 19 28]", "[⟨1 0 -4 -13] ⟨0 1 4 10]⧽",
             "[[4 -4 1 0⟩ [1 2 -3 1⟩]", "2.3.7 [⟨1 1 3] ⟨0 3 -1]⧽"]:
    t = parse_temperament_data(text)
    print(f"{text:28} d={get_dimensionality(t)} r={get_rank(t)} n={get_nullity(t)}")
```
Output:
```
[⟨1 1 0] ⟨0 1 4]⧽            d=3 r=2 n=1
[4 -4 1⟩                     d=3 r=2 n=1
⟨12 19 28]                   d=3 r=1 n=2
[⟨1 0 -4 -13] ⟨0 1 4 10]⧽    d=4 r=2 n=2
[[4 -4 1 0⟩ [1 2 -3 1⟩]      d=4 r=2 n=2
2.3.7 [⟨1 1 3] ⟨0 3 -1]⧽     d=3 r=2 n=1
```
### Rank counts linearly independent rows, so a redundant row does not raise it
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.dimensions import get_rank

print(get_rank(parse_temperament_data("[⟨1 0 0] ⟨0 1 0] ⟨1 1 0]⧽")))
print(get_rank(parse_temperament_data("[⟨12 19 28] ⟨24 38 56]⧽")))
print(get_rank(parse_temperament_data("[[4 -4 1⟩ [-8 8 -2⟩]")))
```
Output:
```
2
1
2
```

## rtt.library.domain_basis
Domain-basis (subgroup) arithmetic: canonicalizing, merging, intersecting and comparing bases, and expressing ratios or basis changes between a subgroup and its prime superspace.
Functions:
- canonical_domain_basis(unparsed_domain_basis: str) -> tuple: canonical form of a dotted STRING, e.g. "2.7.9" -> (2, 9, 7)
- canonical_domain_basis_private(domain_basis: tuple) -> tuple: canonical form of a TUPLE of ints/Fractions; may reorder, drop redundant elements and replace elements (2.5/3.7/5 -> (2, 5/3, 7/3))
- is_standard_prime_limit_domain_basis(domain_basis: tuple) -> bool: True iff the basis canonicalizes to the first n primes (order-insensitive: (2,3,7,5,11) is True; (2,3,5,9,11) is False)
- domain_basis_merge(*bases: tuple) -> tuple: canonical basis of the span-union, e.g. (2,3,5)+(2,9,7) -> (2,3,5,7)
- domain_basis_intersection(*bases: tuple) -> tuple: canonical basis of the intersection, e.g. (2,5/3) & (2,9,5) -> (2, 25/9); disjoint -> (1,)
- is_subspace_of(subspace: tuple, superspace: tuple) -> bool: whether every element of subspace lies in superspace's span
- signs_match(a: int, b: int) -> bool: True if either is 0 or both have the same sign (helper for factor tests)
- is_numerator_factor(subspace_entry: tuple, superspace_entry: tuple) -> bool: prime-count-vector helper used to build basis changes
- is_denominator_factor(subspace_entry: tuple, superspace_entry: tuple) -> bool: prime-count-vector helper used to build basis changes
- get_domain_basis_change_for_m(original_superspace: tuple, target_subspace: tuple) -> tuple: integer matrix with one row per TARGET element giving its counts of each ORIGINAL element (used to restrict…
- get_domain_basis_change_for_c(original_subspace: tuple, target_superspace: tuple) -> tuple: same matrix shape, rows per ORIGINAL subspace element in terms of the TARGET superspace elements (used to ex…
- filter_target_intervals_for_nonstandard_domain_basis(quotients: tuple, domain_basis: tuple) -> tuple: keeps only the Fractions that lie in the basis span
- get_simplest_prime_only_basis(domain_basis: tuple) -> tuple[int, ...]: sorted primes appearing in the elements, e.g. (2, 5/3, 9/7) -> (2,3,5,7); (2, 13/5) -> (2,5,13)
- express_quotients_in_domain_basis(quotients: tuple, domain_basis: tuple) -> tuple: each Fraction as an integer vector over the basis ELEMENTS (works for any basis tuple, including a prime superspace l…
Pitfalls:
- Basis elements are ints or fractions.Fraction (Fraction(13, 5)), never strings, except canonical_domain_basis which takes a dotted STRING ("2.7.9"); its tuple twin is canonical_domain_basis_private.
- A Temperament with domain_basis=None means the standard prime limit for its dimensionality; library results over a standard basis come back with domain_basis=None, so compare with get_domain_basis(t), not t.domain_basis.
- To attach a subgroup when parsing EBK, prefix the basis: parse_temperament_data("2.9.7 ⟨11 35 31]").
- Canonicalization can change elements, not just reorder them: (2, 5/3, 7/5) -> (2, 5/3, 7/3); (2, 3, 15) -> (2, 3, 5); (2, 3, 9) -> (2, 3). Do not assume the user's element list survives.
- express_quotients_in_domain_basis silently truncates when a ratio is NOT in the basis span (3/2 over (2, 9, 7) returns (-1, 0, 0) with no error).
- get_domain_basis_dimension counts primes up to the largest prime used (2.9.7 -> 4 because 7 is the 4th prime), not the number of basis elements.
- domain_basis_intersection of bases with no common span returns (1,), not an empty tuple.
### Canonicalize a domain basis (string or tuple) and test for a standard prime limit
```python
from rtt.library.domain_basis import canonical_domain_basis, canonical_domain_basis_private, is_standard_prime_limit_domain_basis
from fractions import Fraction as F
print(canonical_domain_basis("2.7.9"))
print(canonical_domain_basis("2.3.15"))
print(canonical_domain_basis_private((2, F(5, 3), F(7, 5))))
print(is_standard_prime_limit_domain_basis((2, 3, 7, 5, 11)), is_standard_prime_limit_domain_basis((2, 3, 5, 9, 11)))
```
Output:
```
(2, 9, 7)
(2, 3, 5)
(2, Fraction(5, 3), Fraction(7, 3))
True False
```
### Merge (span-union) and intersect domain bases; subspace test
```python
from rtt.library.domain_basis import domain_basis_merge, domain_basis_intersection, is_subspace_of
from fractions import Fraction as F
print(domain_basis_merge((2, 3, 5), (2, 9, 7)))
print(domain_basis_intersection((2, 3, 5, 7), (2, 3, 5), (2, 5, 7)))
print(domain_basis_intersection((2, F(5, 3)), (2, 9, 5)))
print(is_subspace_of((2, 9, 5), (2, 3, 5)), is_subspace_of((2, 3, 5), (2, 9, 5)))
```
Output:
```
(2, 3, 5, 7)
(2, 5)
(2, Fraction(25, 9))
True False
```
### Read the domain basis of a parsed temperament (prefix syntax '2.9.7 <map>'), basis matrix, prime dimension, simplest prime-only basis
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.domain_basis import get_domain_basis, get_basis_a, get_domain_basis_dimension, get_simplest_prime_only_basis
t = parse_temperament_data("2.9.7 ⟨11 35 31]")
print(t)
print(get_domain_basis(t))
print(get_domain_basis(parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]⧽")))
print(get_basis_a(t).matrix)
print(get_domain_basis_dimension((2, 9, 7)), get_simplest_prime_only_basis((2, 9, 7)))
```
Output:
```
Temperament(matrix=((11, 35, 31),), variance=<Variance.ROW: 'row'>, domain_basis=(2, 9, 7))
(2, 9, 7)
(2, 3, 5)
((1, 0, 0, 0), (0, 2, 0, 0), (0, 0, 0, 1))
4 (2, 3, 7)
```
### Keep only target ratios that live in a subgroup, then express them as vectors over the subgroup basis
```python
from fractions import Fraction as F
from rtt.library.domain_basis import filter_target_intervals_for_nonstandard_domain_basis, express_quotients_in_domain_basis
basis = (2, 9, 7)
targets = (F(3, 2), F(9, 8), F(7, 4), F(9, 7), F(5, 4))
kept = filter_target_intervals_for_nonstandard_domain_basis(targets, basis)
print([str(q) for q in kept])
print(express_quotients_in_domain_basis(kept, basis))
```
Output:
```
['9/8', '7/4', '9/7']
((-3, 1, 0), (-2, 0, 1), (0, 1, -1))
```

## rtt.library.dual
Convert between a mapping and its comma basis (the integer null-space dual), both returned in canonical form.
Functions:
- dual(t: Temperament) -> Temperament: mapping -> canonical comma basis (COL), comma basis -> canonical mapping (ROW); domain basis carried over; an empty null space gives a single all-zero vector/map
- mapping_matrix(t: Temperament) -> Matrix: the raw mapping matrix whether t is a mapping (returned as is) or a comma basis (its dual)
Pitfalls:
- dual returns canonical form, so the comma basis is the canonical one, often not the simplest or positive commas (12-ET gives 531441/524288 and 32805/32768).
- To build a temperament from commas, pad every comma's prime-count vector to the same d before constructing the COL Temperament, then call dual.
- Full-rank mappings (just intonation) dualize to an all-zero comma ((0, 0, 0),), and an all-zero map dualizes to the identity comma basis.
- For a nonstandard domain basis the returned vectors are in that basis (2.3.7 gives [-10 1 3⟩ = 3·7³/2¹⁰ = 1029/1024); do not decode them with pcv_to_quotient.
- mapping_matrix returns the canonical mapping when given a comma basis, but returns a given mapping unchanged (not canonicalized).
### Comma basis of a mapping (and back): dual flips variance and returns canonical form
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.dual import dual
from rtt.library.formatting import to_ebk
from rtt.library.math_utils import pcv_to_quotient, super_

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
commas = dual(meantone)
print(to_ebk(commas))
print([pcv_to_quotient(v) for v in commas.matrix])
print([super_(pcv_to_quotient(v)) for v in commas.matrix])
print(to_ebk(dual(commas)))
```
Output:
```
[4 -4 1⟩
[Fraction(80, 81)]
[Fraction(81, 80)]
[⟨1 0 -4] ⟨0 1 4]⧽
```
### Mapping from a list of commas: 81/80 and 126/125 give septimal meantone; 81/80 and 128/125 give 12-ET
```python
from fractions import Fraction
from rtt.library.temperament import Temperament, Variance
from rtt.library.math_utils import quotient_to_pcv, pad_vectors_with_zeros_up_to_d
from rtt.library.dual import dual
from rtt.library.formatting import to_ebk

def mapping_from_commas(ratios, d):
    vectors = pad_vectors_with_zeros_up_to_d(tuple(quotient_to_pcv(Fraction(r)) for r in ratios), d)
    return dual(Temperament(vectors, Variance.COL))

print(to_ebk(mapping_from_commas(["81/80", "126/125"], 4)))
print(to_ebk(mapping_from_commas(["81/80", "128/125"], 3)))
```
Output:
```
[⟨1 0 -4 -13] ⟨0 1 4 10]⧽
⟨12 19 28]
```
### mapping_matrix gives the mapping matrix whatever the input variance; comma basis of an ET
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.dual import dual, mapping_matrix
from rtt.library.formatting import to_ebk

print(mapping_matrix(parse_temperament_data("[4 -4 1⟩")))
print(mapping_matrix(parse_temperament_data("⟨12 19 28]")))
print(to_ebk(dual(parse_temperament_data("⟨12 19 28]"))))
print(dual(parse_temperament_data("2.3.7 [⟨1 1 3] ⟨0 3 -1]⧽")))
```
Output:
```
((1, 0, -4), (0, 1, 4))
((12, 19, 28),)
[[-19 12 0⟩ [-15 8 1⟩]
Temperament(matrix=((-10, 1, 3),), variance=<Variance.COL: 'col'>, domain_basis=(2, 3, 7))
```

## rtt.library.equal_temperament
Builds the maps of an equal temperament (EDO) over any domain basis: patent maps, warted maps named like '17c', and the full list of uniform (generalized-patent) maps.
Functions:
- patent_val(n: int, domain_basis: tuple) -> tuple[int, ...]: the patent map of n-ET; each entry is round(n*log2(element)) with halves rounded UP
- warted_val(n: int, warts: str, domain_basis: tuple) -> tuple[int, ...]: the map named by wart letters; letter a = 1st basis ELEMENT, b = 2nd, c = 3rd
- wart_name(n: int, warts: str = "") -> str: joins number and letters, e.g. wart_name(17, "c") == "17c"
- parse_wart_name(value: str) -> tuple[int, str]: "17c" -> (17, "c"); strips whitespace and lowercases (" 22B " -> (22, "b")); raises ValueError on junk like "c12" or ""
- uniform_maps(domain_basis: tuple, max_n: int) -> list[tuple[int, str, tuple[int, ...]]]: every uniform map with n = 1..max_n as (n, warts, map)
Pitfalls:
- All five functions return plain tuples/strings, not Temperament objects. To do more RTT with a map, wrap it: Temperament((patent_val(12, (2, 3, 5)),), Variance.ROW) (note the extra tuple: matrix is a tuple of rows).
- domain_basis must be a tuple of ints/Fractions, not a dotted string; use rtt.library.parsing.parse_domain_basis("2.9.7") -> (2, 9, 7) and parse_domain_basis("2.3.13/5") -> (2, 3, Fraction(13, 5)).
- Wart letters index basis POSITIONS, not primes: in 2.9.7, 'b' adjusts the 9 entry. Letters beyond the basis length are silently ignored, so there is no 'p' (patent) suffix: parse_wart_name("22p") == (22, 'p') and warted_val(22, 'p', (2, 3,…
- Repeated letters walk outward in distance order (k-th nearest integer), alternating sides, not 'always up' or 'always down'.
- patent_val rounds exact halves up (math.floor(x + 0.5)), not to even.
- dual() of an ET gives the library's canonical (Hermite-style) comma basis, which is not the simplest-comma list: 12-ET -> 531441/524288 and 32805/32768, not 81/80 and 128/125.
- EBK input strings accept Unicode or ASCII brackets: '⟨12 19 28]' == '<12 19 28]' (map), '[4 -4 1⟩' == '[4 -4 1>' (vector), '[⟨1 0 -4] ⟨0 1 4]⧽' == '[<1 0 -4] <0 1 4]]' (mapping)
### Patent map (patent val) of an EDO in a standard prime limit
```python
from rtt.library.equal_temperament import patent_val
print(patent_val(12, (2, 3, 5)))
print(patent_val(19, (2, 3, 5)))
print(patent_val(31, (2, 3, 5, 7)))
print(patent_val(72, (2, 3, 5, 7, 11)))
```
Output:
```
(12, 19, 28)
(19, 30, 44)
(31, 49, 72, 87)
(72, 114, 167, 202, 249)
```
### Warted map from a wart name like '17c' (and a plain patent name '22')
```python
from rtt.library.equal_temperament import parse_wart_name, warted_val, patent_val
n, warts = parse_wart_name("17c")
print(n, repr(warts))
print("patent 17:", patent_val(17, (2, 3, 5)))
print("17c:     ", warted_val(n, warts, (2, 3, 5)))
print("22 (patent), 11-limit:", warted_val(*parse_wart_name("22"), (2, 3, 5, 7, 11)))
```
Output:
```
17 'c'
patent 17: (17, 27, 39)
17c:      (17, 27, 40)
22 (patent), 11-limit: (22, 35, 51, 62, 76)
```
### List every uniform (generalized-patent) map of 17-ET in the 5-limit, with wart names
```python
from rtt.library.equal_temperament import uniform_maps
for n, warts, val in uniform_maps((2, 3, 5), 17):
    if n == 17:
        print(f"{n}{warts}", val)
```
Output:
```
17bcc (17, 26, 38)
17b (17, 26, 39)
17 (17, 27, 39)
17c (17, 27, 40)
17bbc (17, 28, 40)
17bbccc (17, 28, 41)
```
### Patent map over a nonstandard domain basis (subgroup) parsed from a dotted string
```python
from rtt.library.equal_temperament import patent_val
from rtt.library.parsing import parse_domain_basis
basis = parse_domain_basis("2.9.7")
print(basis)
print(patent_val(12, basis))
basis2 = parse_domain_basis("2.3.13/5")
print(basis2, patent_val(12, basis2))
```
Output:
```
(2, 9, 7)
(12, 38, 34)
(2, 3, Fraction(13, 5)) (12, 19, 17)
```

## rtt.library.exterior_algebra
Exterior-algebra view of temperaments as multivectors: conversion to/from matrices, canonical form, dual, progressive/regressive/interior products, and multivector sum/difference.
Functions:
- Multivector(coords: tuple, grade: int, variance: Variance, dimensionality: int | None = None): frozen dataclass; coords are the largest minors in lexicographic index order (see ea_indices)
- ea_get_largest_minors_l(u: Multivector) -> tuple: u.coords
- ea_get_grade(u: Multivector) -> int: u.grade
- ea_get_variance(u: Multivector) -> Variance: u.variance
- ea_get_d(u: Multivector) -> int: dimensionality (inferred from len(coords) = C(d, grade)); ValueError if nondecomposable
- ea_get_r(u: Multivector) -> int: rank (grade for ROW, d - grade for COL); ValueError if nondecomposable
- ea_get_n(u: Multivector) -> int: nullity (grade for COL, d - grade for ROW); ValueError if nondecomposable
- ea_indices(d: int, grade: int) -> tuple: the index tuples labeling the coords, e.g. (4, 2) -> ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))
- is_nondecomposable(u: Multivector) -> bool: True if no matrix corresponds to u
- multivector_to_matrix(u: Multivector) -> Temperament: canonical mapping (ROW) or comma basis (COL); ValueError if nondecomposable or all-zero
- ea_canonical_form(u: Multivector) -> Multivector: gcd removed, leading coord positive (ROW) / trailing coord positive (COL); all-zero returned unchanged; ValueError if nondecomposable
- ea_dual(u: Multivector) -> Multivector: the complementary multivector of opposite variance (meantone multimap (1,4,4) <-> comma (4,-4,1)); ValueError if nondecomposable
- progressive_product(u1, u2) -> Multivector: wedge product (requires same variance and dimensionality, grade sum <= d); dependent inputs give an all-zero multivector
- regressive_product(u1, u2) -> Multivector: dual of the progressive product of the duals (e.g. the comma shared by two ETs)
Pitfalls:
- Say 'multivector' (multimap for ROW, multicomma for COL); the project bans the older slang term for these objects. The web app deliberately does not surface multivectors, so answer with matrices (multivector_to_matrix + to_ebk) unless the u…
- Multivector takes (coords, grade, variance[, dimensionality]); coords must be in ea_indices(d, grade) order. Dimensionality is inferred from len(coords) = C(d, grade) for grade >= 1; for grade 0 pass it explicitly, e.g.
- Equality is dataclass equality, so compare canonical forms (ea_canonical_form) and the same variance; ea_dual flips variance.
- A nondecomposable multivector (no corresponding temperament) raises ValueError in ea_get_d/ea_get_r/ea_get_n, ea_canonical_form, ea_dual and multivector_to_matrix; check with is_nondecomposable first.
- progressive_product raises ValueError for mismatched variance ("progressive product requires matching variance"), mismatched dimensionality ("...matching dimensionality") or grade sum > d; linearly dependent inputs (e.g.
- ea_sum/ea_diff raise ValueError("multivectors not addable: dimensions differ"), ValueError("cannot diff a temperament with itself"), or ValueError("multivectors not addable") when the sum is nondecomposable.
### Mapping matrix -> multivector, its dual (the comma multivector), and d/r/n
```python
from rtt.library.exterior_algebra import matrix_to_multivector, ea_dual, ea_get_r, ea_get_n, ea_get_d
from rtt.library.parsing import parse_temperament_data
mm = matrix_to_multivector(parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]⧽"))
print(mm)
print(ea_dual(mm))
print(ea_get_d(mm), ea_get_r(mm), ea_get_n(mm))
```
Output:
```
Multivector(coords=(1, 4, 4), grade=2, variance=<Variance.ROW: 'row'>, dimensionality=None)
Multivector(coords=(4, -4, 1), grade=1, variance=<Variance.COL: 'col'>, dimensionality=None)
3 2 1
```
### Progressive product of two ET multivectors gives meantone; regressive product of two comma multivectors gives their shared comma
```python
from rtt.library.exterior_algebra import Multivector, progressive_product, multivector_to_matrix, regressive_product
from rtt.library.temperament import Variance
from rtt.library.formatting import to_ebk
et5 = Multivector((5, 8, 12), 1, Variance.ROW)
et7 = Multivector((7, 11, 16), 1, Variance.ROW)
meantone = progressive_product(et5, et7)
print(meantone)
print(to_ebk(multivector_to_matrix(meantone)))
c1 = Multivector((44, -30, 19), 2, Variance.COL)
c2 = Multivector((28, -19, 12), 2, Variance.COL)
print(regressive_product(c1, c2))
```
Output:
```
Multivector(coords=(1, 4, 4), grade=2, variance=<Variance.ROW: 'row'>, dimensionality=None)
[⟨1 0 -4] ⟨0 1 4]⧽
Multivector(coords=(4, -4, 1), grade=1, variance=<Variance.COL: 'col'>, dimensionality=None)
```
### Multivector sum/diff and canonical form
```python
from rtt.library.exterior_algebra import Multivector, ea_sum, ea_diff, ea_canonical_form
from rtt.library.temperament import Variance
meantone = Multivector((1, 4, 4), 2, Variance.ROW)
porcupine = Multivector((3, 5, 1), 2, Variance.ROW)
print(ea_sum(meantone, porcupine))
print(ea_diff(meantone, porcupine))
print(ea_canonical_form(Multivector((-31, -49, -72, -87, -107), 1, Variance.ROW)))
```
Output:
```
Multivector(coords=(4, 9, 5), grade=2, variance=<Variance.ROW: 'row'>, dimensionality=None)
Multivector(coords=(2, 1, -3), grade=2, variance=<Variance.ROW: 'row'>, dimensionality=None)
Multivector(coords=(31, 49, 72, 87, 107), grade=1, variance=<Variance.ROW: 'row'>, dimensionality=None)
```
### Nondecomposable detection, index order of coordinates, and the antisymmetric tensor
```python
from rtt.library.exterior_algebra import Multivector, is_nondecomposable, multivector_to_matrix, ea_indices, u_to_tensor
from rtt.library.temperament import Variance
bad = Multivector((2, -4, 8, -9, 7, 2), 2, Variance.ROW)
print(is_nondecomposable(bad))
try:
    multivector_to_matrix(bad)
except ValueError as e:
    print("ValueError:", e)
print(ea_indices(4, 2))
print(u_to_tensor(Multivector((1, 4, 4), 2, Variance.ROW)))
```
Output:
```
True
ValueError: nondecomposable multivector has no matrix
((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
((0, 1, 4), (-1, 0, 4), (-4, -4, 0))
```

## rtt.library.formatting
Render Temperaments and individual vectors/maps back into extended bra-ket (EBK) strings.
Functions:
- to_ebk(t: Temperament) -> str: full EBK string, e.g. "[⟨1 0 -4] ⟨0 1 4]⧽", "⟨12 19 28]", "[-4 4 -1⟩", "[[-4 4 -1⟩ [7 0 -3⟩]"
- format_output(output: Temperament, fmt: str = "wolfram") -> Temperament | str: fmt="ebk" returns to_ebk(output); any other fmt returns the Temperament unchanged
- vector_to_ebk(vector: tuple, t: Temperament) -> str: one vector; closing bracket ⟩ if len == dimensionality of t, ⧽ if len == rank of t, else plain ]
- covector_to_ebk(covector: tuple, t: Temperament) -> str: one map; ⟨...] if len == dimensionality of t, ⧼...] if len == rank of t, else [...]
- strip_negative_zero(text: str) -> str: "-0.000" -> "0.000"; leaves real negatives like "-0.001" alone
Pitfalls:
- Float entries are printed with exactly 3 decimals (1901.95500001 -> "1901.955", -0.0001 -> "0.000"); ints print bare and Fractions print as a/b. Round or convert before formatting if you want something else.
- The second argument of vector_to_ebk / covector_to_ebk is a context Temperament used only to pick bracket shapes by comparing the length with its dimensionality and rank.
- Outer brackets for multi-vector Temperaments also depend on counts: a comma basis whose number of commas equals the rank renders as "⧼[4 -4 1 0⟩ [13 -10 0 1⟩]" (septimal meantone), which still re-parses correctly.
- to_ebk drops the domain basis; prepend it yourself (e.g. "2.3.7 " + to_ebk(t)) when t.domain_basis is not None.
### Render Temperaments back to EBK strings
```python
from rtt.library.formatting import to_ebk
from rtt.library.temperament import Temperament, Variance

print(to_ebk(Temperament(((1, 0, -4), (0, 1, 4)), Variance.ROW)))
print(to_ebk(Temperament(((12, 19, 28),), Variance.ROW)))
print(to_ebk(Temperament(((-4, 4, -1),), Variance.COL)))
print(to_ebk(Temperament(((-4, 4, -1), (7, 0, -3)), Variance.COL)))
print(to_ebk(Temperament(((1201.397, 1898.446, 2788.196),), Variance.ROW)))
```
Output:
```
[⟨1 0 -4] ⟨0 1 4]⧽
⟨12 19 28]
[-4 4 -1⟩
[[-4 4 -1⟩ [7 0 -3⟩]
⟨1201.397 1898.446 2788.196]
```
### Float entries print with 3 decimals (negative zero stripped); Fractions print exactly
```python
from fractions import Fraction
from rtt.library.formatting import to_ebk, format_output, strip_negative_zero
from rtt.library.temperament import Temperament, Variance

print(to_ebk(Temperament(((-0.0001, 1901.95500001, 2786.3137),), Variance.ROW)))
print(to_ebk(Temperament(((Fraction(1, 4), Fraction(-1, 3), 0),), Variance.COL)))
t = Temperament(((1, 0, -4), (0, 1, 4)), Variance.ROW)
print(format_output(t, "ebk"))
print(format_output(t) == t)
print(strip_negative_zero("-0.000"), strip_negative_zero("-0.001"))
```
Output:
```
⟨0.000 1901.955 2786.314]
[1/4 -1/3 0⟩
[⟨1 0 -4] ⟨0 1 4]⧽
True
0.000 -0.001
```
### Bracket shape depends on the temperament passed as context: length d gives ⟩ / ], length r gives ⧽ / ⧼, otherwise plain [ ]
```python
from rtt.library.formatting import vector_to_ebk, covector_to_ebk, to_ebk
from rtt.library.parsing import parse_temperament_data
from rtt.library.dual import dual

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
print(vector_to_ebk((-2, 0, 1), meantone))
print(vector_to_ebk((-2, 4), meantone))
print(covector_to_ebk((1200.0, 696.578), meantone))
print(to_ebk(dual(parse_temperament_data("[⟨1 0 -4 -13] ⟨0 1 4 10]⧽"))))
```
Output:
```
[-2 0 1⟩
[-2 4⧽
⧼1200.000 696.578]
⧼[4 -4 1 0⟩ [13 -10 0 1⟩]
```

## rtt.library.generator_detempering
Finds just-intonation intervals for a temperament's generators: the Smith-normal-form generator detempering, membership tests, and the simplest alternative ratios (preimages) that map to a given generator.
Functions:
- GENERATOR_PREIMAGE_COUNT = 12: default count for get_generator_preimages
- get_generator_detempering(t: Temperament) -> Temperament: COL Temperament D whose rows D.matrix[i] are prime-count vectors of generator i (M*D = identity)
- maps_to_the_generator(mapping: Matrix, index: int, vector) -> bool: True iff the raw mapping matrix sends vector to exactly one step of generator `index` and zero of every other generator
- get_generator_preimages(t: Temperament, index: int, count: int = 12) -> tuple[tuple[int, ...], ...]: up to `count` distinct prime-count vectors that map to generator `index`, sorted by product complex…
Pitfalls:
- The generators are defined by the mapping ROWS you pass: the canonical meantone form [⟨1 0 -4] ⟨0 1 4]⧽ has generators 2 and 3, while [⟨1 1 0] ⟨0 1 4]⧽ has 2 and 3/2 and [⟨1 2 4] ⟨0 -1 -4]⧽ has 2 and 4/3.
- The Smith-normal-form detempering is valid but not always the simplest or super-unison: porcupine's second generator comes out as [-1 2 -1⟩ = 9/10.
- get_generator_preimages is not exhaustive: it searches the detempering vector plus comma combinations with coefficients within a radius (6 for nullity 1, 3 for nullity 2, 2 for nullity 3, 1 beyond), then keeps the `count` simplest.
- maps_to_the_generator takes a RAW matrix (Temperament.matrix), not a Temperament, and the vector must have length d: quotient_to_pcv(Fraction(3, 2)) is only (-1, 1) and returns False for a 5-limit mapping.
- D.matrix rows are column vectors stored as rows (COL variance); convert each with rtt.library.math_utils.pcv_to_quotient (standard prime basis only; for a subgroup, multiply the basis elements manually).
### Generator detempering of meantone: the generators as prime-count vectors and ratios
```python
from rtt.library.generator_detempering import get_generator_detempering
from rtt.library.parsing import parse_temperament_data
from rtt.library.formatting import to_ebk
from rtt.library.math_utils import pcv_to_quotient
meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
D = get_generator_detempering(meantone)
print(to_ebk(D))
print([str(pcv_to_quotient(v)) for v in D.matrix])
```
Output:
```
[[1 0 0⟩ [-1 1 0⟩]
['2', '3/2']
```
### Simplest generator preimages (ratios mapping to generator i), sorted by product complexity
```python
from rtt.library.generator_detempering import get_generator_preimages
from rtt.library.parsing import parse_temperament_data
from rtt.library.math_utils import pcv_to_quotient
meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
print([str(pcv_to_quotient(v)) for v in get_generator_preimages(meantone, 1, count=6)])
et12 = parse_temperament_data("⟨12 19 28]")
print([str(pcv_to_quotient(v)) for v in get_generator_preimages(et12, 0, count=5)])
```
Output:
```
['3/2', '40/27', '243/160', '3200/2187', '19683/12800', '256000/177147']
['16/15', '25/24', '135/128', '250/243', '256/243']
```
### Test whether a ratio maps to generator 1 (note the length-d padding requirement)
```python
from fractions import Fraction
from rtt.library.generator_detempering import maps_to_the_generator
from rtt.library.parsing import parse_temperament_data, parse_quotient_list
from rtt.library.math_utils import quotient_to_pcv
m = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽").matrix
print("unpadded 3/2:", quotient_to_pcv(Fraction(3, 2)), maps_to_the_generator(m, 1, quotient_to_pcv(Fraction(3, 2))))
for q, v in zip(("3/2", "40/27", "3/1", "2/1"), parse_quotient_list("3/2 40/27 3/1 2/1", 3)):
    print(q, v, maps_to_the_generator(m, 1, v))
```
Output:
```
unpadded 3/2: (-1, 1) False
3/2 (-1, 1, 0) True
40/27 (3, -3, 1) True
3/1 (0, 1, 0) False
2/1 (1, 0, 0) False
```
### Generator detempering of porcupine and of a comma basis (comma input is dualized)
```python
from rtt.library.generator_detempering import get_generator_detempering
from rtt.library.parsing import parse_temperament_data
from rtt.library.formatting import to_ebk
porcupine = parse_temperament_data("[⟨1 2 3] ⟨0 3 5]⧽")
print(to_ebk(get_generator_detempering(porcupine)))
print(to_ebk(get_generator_detempering(parse_temperament_data("[4 -4 1⟩"))))
```
Output:
```
[[1 0 0⟩ [-1 2 -1⟩]
[[1 0 0⟩ [0 1 0⟩]
```

## rtt.library.generator_embedding
Exact rational tuning from held intervals: the generator embedding G = H(MH)^-1 and the tempering projection P = G*M for a mapping M that holds r chosen just intervals unchanged (e.g. quarter-comma meantone holds 2/1 and 5/4).
Functions:
- get_generator_embedding(mapping: Temperament, held: Temperament) -> tuple[tuple[Fraction, ...], ...]: d x r matrix G (row i = prime i, column j = generator j) whose columns are fractional prime-count…
- get_tempering_projection(mapping: Temperament, held: Temperament) -> tuple[tuple[Fraction, ...], ...]: d x d projection P = G*M sending each just prime-count vector to its tempered one
Pitfalls:
- `held` must be a COL Temperament whose rows are the prime-count vectors of exactly r (= rank) held intervals, padded to length d: Temperament(parse_quotient_list("2/1 5/4", 3), Variance.COL).
- Held intervals must be independent and must not be tempered out: holding 81/80 in meantone raises sympy NonInvertibleMatrixError ("Matrix det == 0; not invertible."); the wrong number of held intervals raises sympy NonSquareMatrixError.
- Return values are plain nested tuples of fractions.Fraction, not Temperaments: P is d x d, G is d x r with rows = primes and columns = generators (so generator j is the column G[i][j] over i).
- The results are in octave-free prime-count units; to get cents multiply by the just tuning map 1200*log2(p) per prime (see the example: quarter-comma fifth = 696.578 cents, octave 1200.0).
- The mapping's rows define which generators G returns (same caveat as generator_detempering): with [⟨1 1 0] ⟨0 1 4]⧽ the second generator is the fifth.
- Holding 2/1 and 5/4 is equivalent to holding 2/1 and 5/1 (same span), so both give quarter-comma meantone.
### Tempering projection P and generator embedding G for meantone holding 2/1 and 5/1 (quarter-comma)
```python
from rtt.library.generator_embedding import get_tempering_projection, get_generator_embedding
from rtt.library.parsing import parse_temperament_data, parse_quotient_list
from rtt.library.temperament import Temperament, Variance
meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
held = Temperament(parse_quotient_list("2/1 5/1", 3), Variance.COL)
print(held.matrix)
print(get_tempering_projection(meantone, held))
print(get_generator_embedding(meantone, held))
```
Output:
```
((1, 0, 0), (0, 0, 1))
((Fraction(1, 1), Fraction(1, 1), Fraction(0, 1)), (Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)), (Fraction(0, 1), Fraction(1, 4), Fraction(1, 1)))
((Fraction(1, 1), Fraction(0, 1)), (Fraction(0, 1), Fraction(0, 1)), (Fraction(0, 1), Fraction(1, 4)))
```
### Generator sizes in cents from the generator embedding (quarter-comma meantone fifth)
```python
import math
from rtt.library.generator_embedding import get_generator_embedding
from rtt.library.parsing import parse_temperament_data, parse_quotient_list
from rtt.library.temperament import Temperament, Variance
meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
held = Temperament(parse_quotient_list("2/1 5/4", 3), Variance.COL)
G = get_generator_embedding(meantone, held)
just_cents = [1200 * math.log2(p) for p in (2, 3, 5)]
generators = [sum(float(G[i][j]) * just_cents[i] for i in range(3)) for j in range(2)]
print([round(g, 3) for g in generators])
```
Output:
```
[1200.0, 696.578]
```
### Projection holding 2/1 and 3/2: idempotent, sends 81/80 to the unison and 5/4 to 81/64
```python
from rtt.library.generator_embedding import get_tempering_projection
from rtt.library.matrix_utils import matrix_multiply
from rtt.library.parsing import parse_temperament_data, parse_quotient_list
from rtt.library.temperament import Temperament, Variance
from rtt.library.superspace import apply_matrix_to_vectors
meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
P = get_tempering_projection(meantone, Temperament(parse_quotient_list("2/1 3/2", 3), Variance.COL))
print(P)
print(matrix_multiply(P, P) == P)
print(apply_matrix_to_vectors(P, parse_quotient_list("81/80 5/4", 3)))
```
Output:
```
((Fraction(1, 1), Fraction(0, 1), Fraction(-4, 1)), (Fraction(0, 1), Fraction(1, 1), Fraction(4, 1)), (Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)))
True
((Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)), (Fraction(-6, 1), Fraction(4, 1), Fraction(0, 1)))
```

## rtt.library.generator_forms
Alternative generator forms of a mapping (minimal-generator, equave-reduced, positive-generator flip and shift), plus the standard just tuning map in octaves.
Functions:
- standard_jip_octaves(dimensionality: int) -> tuple[float, ...]: log2 of the first d primes, i.e. the just tuning map in octaves ((1.0, 1.585, 2.322) for d=3)
- minimal_generator_ma(matrix: Matrix, jip_octaves) -> Matrix: mingen form, each generator between 0 and half its period (meantone -> ((1, 2, 4), (0, -1, -4)), a ~4/3 generator)
- equave_reduced_ma(matrix: Matrix, jip_octaves) -> Matrix: each generator reduced into [0, period) (septimal meantone -> ((1, 1, 0, -3), (0, 1, 4, 10)), octave and fifth)
- positive_generator_ma(matrix: Matrix, jip_octaves) -> Matrix: canonical form with any negative-generator row sign-flipped (porcupine -> ((1, 2, 3), (0, -3, -5)))
- positive_generator_shift_ma(matrix: Matrix, jip_octaves) -> Matrix: positive generators obtained by shifting the period row when possible instead of flipping (sensi -> ((1, -1, -1), (0, 7, 9)))
Pitfalls:
- All forms take a raw mapping matrix (t.matrix), not a Temperament; passing a Temperament raises TypeError. Wrap the result in Temperament(result, Variance.ROW) to format it.
- Each form starts from the canonical form, so any equivalent input mapping yields the same output.
- jip_octaves is in octaves, not cents, and must match the mapping's dimensionality; standard_jip_octaves assumes standard primes.
- Generator sizes used to choose the form are computed internally from a weighted pseudo-inverse; the functions return mappings, not generator tunings. Use rtt.library.tuning for tunings in cents.
### Alternate generator forms of a mapping (raw matrices in, raw matrices out)
```python
from rtt.library.generator_forms import (standard_jip_octaves, minimal_generator_ma,
    equave_reduced_ma, positive_generator_ma, positive_generator_shift_ma)

jip3, jip4 = standard_jip_octaves(3), standard_jip_octaves(4)
meantone = ((1, 0, -4), (0, 1, 4))
septimal_meantone = ((1, 0, -4, -13), (0, 1, 4, 10))
print(jip3)
print("mingen meantone:", minimal_generator_ma(meantone, jip3))
print("equave-reduced septimal meantone:", equave_reduced_ma(septimal_meantone, jip4))
print("positive-generator porcupine:", positive_generator_ma(((1, 2, 3), (0, 3, 5)), jip3))
print("positive-generator shift sensi:", positive_generator_shift_ma(((1, 6, 8), (0, 7, 9)), jip3))
```
Output:
```
(1.0, 1.584962500721156, 2.321928094887362)
mingen meantone: ((1, 2, 4), (0, -1, -4))
equave-reduced septimal meantone: ((1, 1, 0, -3), (0, 1, 4, 10))
positive-generator porcupine: ((1, 2, 3), (0, -3, -5))
positive-generator shift sensi: ((1, -1, -1), (0, 7, 9))
```
### Feed a parsed Temperament by passing its .matrix (and the right dimensionality for the octave sizes)
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.dimensions import get_dimensionality
from rtt.library.formatting import to_ebk
from rtt.library.temperament import Temperament, Variance
from rtt.library.generator_forms import standard_jip_octaves, minimal_generator_ma

t = parse_temperament_data("[⟨5 8 12] ⟨7 11 16]⧽")
jip = standard_jip_octaves(get_dimensionality(t))
mingen = minimal_generator_ma(t.matrix, jip)
print(mingen)
print(to_ebk(Temperament(mingen, Variance.ROW)))
```
Output:
```
((1, 2, 4), (0, -1, -4))
[⟨1 2 4] ⟨0 -1 -4]⧽
```

## rtt.library.list_utils
Small helpers for single integer/rational vectors: remove common factors, clear denominators, find first/last nonzero entries.
Functions:
- divide_out_gcd(values: tuple[int, ...]) -> tuple[int, ...]: divide by the gcd of the absolute values, sign kept ((24, 38, 56) -> (12, 19, 28)); all zeros returned unchanged
- mult_by_lcd(values: tuple) -> tuple[int, ...]: multiply by the lcm of denominators to get integers ((1/3, 1, 2/5) -> (5, 15, 6))
- leading_entry(values: tuple) -> first nonzero entry
- trailing_entry(values: tuple) -> last nonzero entry
- all_zeros_l(values: tuple) -> bool: True if every entry is 0
Pitfalls:
- divide_out_gcd does not normalize sign: (-8, 8, -2) -> (-4, 4, -1). Use canonicalization for a sign-normalized form.
- leading_entry / trailing_entry raise StopIteration on an all-zero vector; check all_zeros_l first.
- These work on one flat vector; for a whole matrix use matrix_utils.
### Integer-vector helpers: remove a common factor, clear denominators, first/last nonzero entries
```python
from fractions import Fraction
from rtt.library.list_utils import divide_out_gcd, mult_by_lcd, leading_entry, trailing_entry, all_zeros_l

print(divide_out_gcd((24, 38, 56)))
print(divide_out_gcd((0, -6, 9)))
print(mult_by_lcd((Fraction(1, 3), 1, Fraction(2, 5))))
print(leading_entry((0, -6, 9, 0)), trailing_entry((0, -6, 9, 0)))
print(all_zeros_l((0, 0, 0)), all_zeros_l((0, 1, 0)))
```
Output:
```
(12, 19, 28)
(0, -2, 3)
(5, 15, 6)
-6 9
True False
```
### Pitfall: divide_out_gcd keeps the sign; leading_entry on an all-zero list raises StopIteration
```python
from rtt.library.list_utils import divide_out_gcd, leading_entry

print(divide_out_gcd((-8, 8, -2)))
print(divide_out_gcd((0, 0, 0)))
try:
    leading_entry((0, 0, 0))
except StopIteration:
    print("StopIteration")
```
Output:
```
(-4, 4, -1)
(0, 0, 0)
StopIteration
```

## rtt.library.math_utils
Ratio arithmetic: ratios <-> prime-count vectors, primes, padding, octave/equave reduction and super.
Functions:
- quotient_to_pcv(quotient: Fraction | int) -> tuple[int, ...]: prime-count vector of a ratio (also accepts a string like "81/80", anything Fraction() accepts)
- pcv_to_quotient(pcv: tuple[int, ...]) -> Fraction: inverse over the standard primes 2, 3, 5, 7, ... ((-4, 4, -1) -> Fraction(81, 80))
- get_primes(count: int) -> tuple[int, ...]: the first count primes (get_primes(5) -> (2, 3, 5, 7, 11))
- pad_vectors_with_zeros_up_to_d(matrix: tuple[tuple[int, ...], ...], d: int) -> tuple[tuple[int, ...], ...]: right-pad every vector with zeros to length d
- equave_reduce(quotient: Fraction | int, equave: Fraction | int = 2) -> Fraction: multiply/divide by the equave into [1, equave) (equave_reduce(10, 3) -> 10/9)
- octave_reduce(quotient: Fraction | int) -> Fraction: equave_reduce with equave 2 (3 -> 3/2, 2/3 -> 4/3)
- super_(quotient: Fraction | int) -> Fraction: the reciprocal if the ratio is below 1, else unchanged (80/81 -> 81/80)
Pitfalls:
- quotient_to_pcv returns a vector only as long as its largest prime; pad with pad_vectors_with_zeros_up_to_d before combining with a mapping of larger dimensionality.
- Pass exact ratios (Fraction, int, or an "a/b" string). A float is converted with Fraction(float): 1.5 works, but 1.1 becomes a 52-bit fraction whose factorization can hang for a long time.
- pcv_to_quotient always reads entries as exponents of 2, 3, 5, 7, ...; for a nonstandard domain basis (e.g. 2.3.7 or 2.9.7) you must multiply the basis elements yourself, otherwise you get a wrong ratio.
- There is no cents helper in these modules; cents = 1200 * math.log2(ratio). Tuning maps returned by rtt.library.tuning are already in cents.
- quotient_to_pcv(0) returns (0,) instead of raising; do not pass 0.
### Convert ratios to prime-count vectors and back (vectors are only as long as the largest prime present)
```python
from fractions import Fraction
from rtt.library.math_utils import quotient_to_pcv, pcv_to_quotient, pad_vectors_with_zeros_up_to_d

print(quotient_to_pcv(Fraction(81, 80)))
print(quotient_to_pcv("81/80"))
print(quotient_to_pcv(5))
print(quotient_to_pcv(Fraction(7, 4)))
print(pad_vectors_with_zeros_up_to_d((quotient_to_pcv(Fraction(3, 2)), quotient_to_pcv(Fraction(5, 4))), 4))
print(pcv_to_quotient((-4, 4, -1)))
print(pcv_to_quotient((1, 0, -1, 0, 1)))
```
Output:
```
(-4, 4, -1)
(-4, 4, -1)
(0, 0, 1)
(-2, 0, 0, 1)
((-1, 1, 0, 0), (-2, 0, 1, 0))
81/80
22/5
```
### Size of an interval in cents (the library works in cents for tunings: 1200·log2)
```python
from fractions import Fraction
from math import log2
from rtt.library.math_utils import pcv_to_quotient

for vector in [(-1, 1, 0), (-4, 4, -1), (-2, 0, 0, 1)]:
    ratio = pcv_to_quotient(vector)
    print(vector, ratio, round(1200 * log2(ratio), 3))
```
Output:
```
(-1, 1, 0) 3/2 701.955
(-4, 4, -1) 81/80 21.506
(-2, 0, 0, 1) 7/4 968.826
```
### Primes, octave/equave reduction, and super (flip a ratio under 1)
```python
from fractions import Fraction
from rtt.library.math_utils import get_primes, octave_reduce, equave_reduce, super_

print(get_primes(6))
print(octave_reduce(3), octave_reduce(Fraction(2, 3)), octave_reduce(Fraction(9, 4)))
print(equave_reduce(10, 3), equave_reduce(7, 3))
print(super_(Fraction(80, 81)), super_(Fraction(5, 3)))
```
Output:
```
(2, 3, 5, 7, 11, 13)
3/2 4/3 9/8
10/9 7/3
81/80 5/3
```
### Pitfall: pcv_to_quotient assumes the standard primes 2, 3, 5, 7...; for a nonstandard domain basis multiply the basis elements yourself
```python
from fractions import Fraction
from rtt.library.parsing import parse_temperament_data
from rtt.library.dual import dual
from rtt.library.math_utils import pcv_to_quotient

commas = dual(parse_temperament_data("2.3.7 [⟨1 1 3] ⟨0 3 -1]⧽"))
vector, basis = commas.matrix[0], commas.domain_basis
print(vector, basis)
print("wrong (read as 2.3.5):", pcv_to_quotient(vector))
ratio = Fraction(1)
for element, exponent in zip(basis, vector):
    ratio *= Fraction(element) ** exponent
print("right (2.3.7):", ratio)
```
Output:
```
(-10, 1, 3) (2, 3, 7)
wrong (read as 2.3.5): 375/1024
right (2.3.7): 1029/1024
```

## rtt.library.matrix_utils
Exact integer/rational matrix operations on plain tuples of tuples: Hermite and Smith normal forms, inverse, transpose, product, minors, zero-row cleanup.
Functions:
- Matrix = tuple[tuple[int, ...], ...] (type alias; all functions take and return plain tuples of tuples, not Temperaments)
- hnf(matrix: Matrix) -> Matrix: row-style Hermite normal form (hnf(((5, 8, 12), (7, 11, 16))) -> ((1, 0, -4), (0, 1, 4)))
- hnf_with_transform(matrix: Matrix) -> tuple[Matrix, Matrix]: (unimodular transform U, hnf) with U·matrix = hnf
- smith_normal_form_with_transforms(matrix: Matrix) -> tuple[Matrix, Matrix, Matrix]: (left, middle, right) with left·matrix·right = middle
- inverse(x) -> Fraction | tuple: scalar -> 1/x; flat vector -> elementwise reciprocals; square matrix -> exact inverse as Fractions
- transpose(matrix: Matrix) -> Matrix
- matrix_multiply(a: Matrix, b: Matrix) -> Matrix: plain product a·b (rows of a against columns of b)
- get_largest_minors_l(matrix: Matrix) -> tuple[int, ...]: all r×r minors of a rank-r matrix (columns in lexicographic combination order), gcd divided out
- reverse_inner_l(matrix) -> Matrix: reverse each row; reverse_outer_l(matrix) -> Matrix: reverse row order; rotate_180(matrix) -> Matrix: both
- inner_l_length(matrix) -> int: length of the first row
- all_zeros(matrix) -> bool
- remove_all_zero_lists(matrix) -> Matrix: drop all-zero rows (may return ())
- remove_unneeded_zero_lists(matrix) -> Matrix: drop all-zero rows but keep a single zero row if everything was zero
Pitfalls:
- These functions operate on raw matrices. Pass t.matrix, not a Temperament; and remember a COL Temperament's matrix holds vectors as inner tuples, so mapping·commas is matrix_multiply(mapping, transpose(commas)).
- hnf alone does not defactor (⟨24 38 56] stays enfactored); use canonicalization.canonical_ma / canonical_form for the canonical mapping.
- inverse returns exact Fractions and raises sympy's NonInvertibleMatrixError on a singular matrix.
- The middle matrix from smith_normal_form_with_transforms is not always strictly diagonal (for ((2, 0), (0, 3)) it returns ((1, 0), (-3, 6))); read only the pivot (diagonal) entries.
- get_largest_minors_l is the multivector-entry calculation; the project does not surface multivectors, so prefer mappings and comma bases when answering.
### Hermite normal form of a pair of ET maps (5 & 7) gives the meantone mapping
```python
from rtt.library.matrix_utils import hnf, hnf_with_transform

print(hnf(((5, 8, 12), (7, 11, 16))))
transform, result = hnf_with_transform(((5, 8, 12), (7, 11, 16)))
print(transform, result)
```
Output:
```
((1, 0, -4), (0, 1, 4))
((-11, 8), (7, -5)) ((1, 0, -4), (0, 1, 4))
```
### Exact inverse (Fractions), transpose and integer matrix product
```python
from rtt.library.matrix_utils import inverse, transpose, matrix_multiply

print(inverse(((1, 1), (0, 1))))
print(inverse((1, 2, 4)))
print(inverse(3))
mapping = ((1, 1, 0), (0, 1, 4))
commas = ((-4, 4, -1), (1, -5, 3))
print(transpose(commas))
print(matrix_multiply(mapping, transpose(commas)))
```
Output:
```
((Fraction(1, 1), Fraction(-1, 1)), (Fraction(0, 1), Fraction(1, 1)))
(Fraction(1, 1), Fraction(1, 2), Fraction(1, 4))
1/3
((-4, 1), (4, -5), (-1, 3))
((0, -4), (0, 7))
```
### Smith normal form exposes enfactoring: ⟨24 38 56] has a diagonal factor of 2
```python
from rtt.library.matrix_utils import smith_normal_form_with_transforms, matrix_multiply

left, diagonal, right = smith_normal_form_with_transforms(((24, 38, 56),))
print(diagonal)
print(matrix_multiply(matrix_multiply(left, ((24, 38, 56),)), right) == diagonal)
print(smith_normal_form_with_transforms(((1, 0, -4), (0, 1, 4)))[1])
```
Output:
```
((2, 0, 0),)
True
((1, 0, 0), (0, 1, 0))
```
### Largest minors (gcd removed), zero-row cleanup, and 180-degree rotation
```python
from rtt.library.matrix_utils import (get_largest_minors_l, remove_all_zero_lists,
    remove_unneeded_zero_lists, rotate_180, all_zeros)

print(get_largest_minors_l(((1, 0, -4), (0, 1, 4))))
print(get_largest_minors_l(((1, 0, -4, -13), (0, 1, 4, 10))))
print(remove_all_zero_lists(((12, 19, 28), (0, 0, 0))))
print(remove_unneeded_zero_lists(((0, 0, 0), (0, 0, 0))))
print(rotate_180(((1, 0, -4), (0, 1, 4))))
print(all_zeros(((0, 0), (0, 0))))
```
Output:
```
(1, 4, 4)
(1, 4, 10, 4, 13, 12)
((12, 19, 28),)
((0, 0, 0),)
((4, 1, 0), (-4, 0, 1))
True
```

## rtt.library.merging
Map-merging and comma-merging of temperaments (the 'join' and 'meet' that build a temperament from ETs or from commas), across possibly different domain bases.
Functions:
- map_merge(*temperaments: Temperament) -> Temperament: stacks the mappings (COL inputs are dualized first) over the INTERSECTION of the input domain bases; returns the canonical mapping (ROW). E.g.
- comma_merge(*temperaments: Temperament) -> Temperament: stacks the comma bases (ROW inputs are dualized first) over the MERGE (union) of the input domain bases
Pitfalls:
- Both functions are variadic: pass Temperaments as separate arguments (map_merge(a, b, c) or map_merge(*list)), not a list.
- Output variance is fixed regardless of inputs: map_merge always returns a ROW mapping, comma_merge always a COL comma basis. dual() the result to get the other side.
- map_merge works over the INTERSECTION of the inputs' domain bases (it may shrink the subgroup, e.g. 2.3.5.11 with 2.9.7.11 -> 2.9.11); comma_merge works over the UNION (2.3.5 with 2.9.7 -> 2.3.5.7).
- COL Temperament matrices store each vector as a ROW tuple: Temperament(((4, -4, 1),), Variance.COL) is the single comma [4 -4 1⟩; two commas are ((-11, 7, 0), (-7, 3, 1)).
- rtt.library.math_utils.quotient_to_pcv(Fraction(81, 80)) gives (-4, 4, -1); canonical form flips the sign so the comma prints as [4 -4 1⟩.
- Results are canonical forms (Hermite-style), so the comma basis printed is generally not the 'simplest commas' a person would list.
### Map-merge 5-ET and 7-ET into meantone, then get its comma
```python
from rtt.library.merging import map_merge
from rtt.library.parsing import parse_temperament_data
from rtt.library.formatting import to_ebk
from rtt.library.dual import dual
meantone = map_merge(parse_temperament_data("⟨5 8 12]"), parse_temperament_data("⟨7 11 16]"))
print(to_ebk(meantone))
print(to_ebk(dual(meantone)))
```
Output:
```
[⟨1 0 -4] ⟨0 1 4]⧽
[4 -4 1⟩
```
### Comma-merge 81/80 and 250/243 (from ratios) into the 7-ET comma basis, then get its map
```python
from fractions import Fraction
from rtt.library.merging import comma_merge
from rtt.library.temperament import Temperament, Variance
from rtt.library.math_utils import quotient_to_pcv
from rtt.library.dual import dual
from rtt.library.formatting import to_ebk
c1 = Temperament((quotient_to_pcv(Fraction(81, 80)),), Variance.COL)
c2 = Temperament((quotient_to_pcv(Fraction(250, 243)),), Variance.COL)
print(c1.matrix, c2.matrix)
merged = comma_merge(c1, c2)
print(to_ebk(merged))
print(to_ebk(dual(merged)))
```
Output:
```
((-4, 4, -1),) ((1, -5, 3),)
[[-11 7 0⟩ [-7 3 1⟩]
⟨7 11 16]
```
### Merge three 7-limit ETs into marvel; comma-merge three commas into a rank-1 comma basis
```python
from rtt.library.merging import map_merge, comma_merge
from rtt.library.parsing import parse_temperament_data
from rtt.library.formatting import to_ebk
marvel = map_merge(*(parse_temperament_data(s) for s in ("⟨7 11 16 19]", "⟨12 19 28 34]", "⟨22 35 51 62]")))
print(to_ebk(marvel))
et = comma_merge(*(parse_temperament_data(s) for s in ("[2 2 -1 -1⟩", "[4 -4 1 0⟩", "[-14 3 4 0⟩")))
print(to_ebk(et))
```
Output:
```
[⟨1 0 0 -5] ⟨0 1 0 2] ⟨0 0 1 2]⧽
[[-30 19 0 0⟩ [-26 15 1 0⟩ [-6 2 0 1⟩]
```
### Merges across different domain bases (map_merge intersects, comma_merge unions)
```python
from rtt.library.merging import map_merge, comma_merge
from rtt.library.temperament import Temperament, Variance
t1 = Temperament(((22, 35, 51, 76),), Variance.ROW, (2, 3, 5, 11))
t2 = Temperament(((17, 54, 48, 59),), Variance.ROW, (2, 9, 7, 11))
print(map_merge(t1, t2))
c1 = Temperament(((4, -4, 1),), Variance.COL)
c2 = Temperament(((6, -1, -1),), Variance.COL, (2, 9, 7))
print(comma_merge(c1, c2))
```
Output:
```
Temperament(matrix=((1, 0, 13), (0, 1, -3)), variance=<Variance.ROW: 'row'>, domain_basis=(2, 9, 11))
Temperament(matrix=((4, -4, 1, 0), (-6, 2, 0, 1)), variance=<Variance.COL: 'col'>, domain_basis=None)
```

## rtt.library.parsing
Turn extended bra-ket (EBK) text, ratio lists and dotted domain-basis strings into Temperament objects, prime-count vectors and Fractions.
Functions:
- parse_temperament_data(data: str | Temperament) -> Temperament: parse an EBK string such as "[⟨1 1 0] ⟨0 1 4]⧽" (mapping), "⟨12 19 28]" (map), "[-4 4 -1⟩" (prime-count vector) or "[[-4 4 -1⟩ [7 0 -3⟩]…
- is_covariant_ebk(ebk: str) -> bool: True when the EBK string is a map/mapping (opens with ⟨, <, ⧼ or {), False for vectors and comma bases
- parse_quotients(text: str) -> list[Fraction]: every integer or a/b token in the text, e.g. "{2/1, 3/2, 5/4}" or "4:5:6"
- parse_quotient_list(text: str, d: int) -> tuple[tuple[int, ...], ...]: the ratios in text as prime-count vectors, right-padded with zeros to length d
- parse_domain_basis(text: str) -> tuple: "2.3.7" -> (2, 3, 7); non-integer elements become Fractions ("2.3.13/5" -> (2, 3, Fraction(13, 5)))
- parse_ebk_vector(text: str) -> tuple: the inside of one bracket ("1 0 -4" or "1, 0, -4") -> (1, 0, -4); entries become int, Fraction ("1/4") or float ("1901.955")
Pitfalls:
- Input must be bracketed EBK. A bare ratio ("81/80") or bare numbers ("12 19 28") raise ValueError; for "12 19 28" the leading "12" is even misread as a domain-basis prefix.
- Variance comes from the bracket shapes only: ⟨...] / <...] / {...] / ⧼...] = map (ROW); [...⟩ / |...> / [...⧽ = vector (COL). Mixing bra and ket brackets in one string raises ValueError("mixed bra/ket variance ...").
- Doubled brackets like "⟨⟨1 4 4]]" (multivector notation) raise ValueError; the library only accepts maps and vectors.
- A COL Temperament stores each vector as one inner tuple: "[[-4 4 -1⟩ [7 0 -3⟩]" -> matrix ((-4, 4, -1), (7, 0, -3)). The inner tuples are the commas, not the rows of the math matrix whose columns are commas; transpose if you need that.
- Decimal entries parse as float ("1200.000" -> 1200.0) while "1200" stays int; a/b entries become Fraction.
- parse_quotient_list only pads, it never truncates: "{9/8, 7/4}" with d=3 gives ((-3, 2, 0), (-2, 0, 0, 1)), a ragged result. Filter out ratios with primes beyond the limit yourself.
- The domain-basis prefix must be dot-separated with no spaces inside ("2.3.7", "2.9.7"), followed by whitespace and the EBK.
### Parse a mapping written in extended bra-ket notation (EBK) into a Temperament
```python
from rtt.library.parsing import parse_temperament_data

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
print(meantone.matrix)
print(meantone.variance)
print(meantone.domain_basis)
```
Output:
```
((1, 1, 0), (0, 1, 4))
Variance.ROW
None
```
### Single maps, single prime-count vectors, comma bases, and ASCII bracket aliases all parse; variance is inferred from the brackets
```python
from rtt.library.parsing import parse_temperament_data

for text in ["⟨12 19 28]", "<12 19 28]", "[-4 4 -1⟩", "|-4 4 -1>", "[1, -5, 3⟩",
             "[[-4 4 -1⟩ [7 0 -3⟩]", "[<1 0 -4] <0 1 4]>", "⟨1200.000 1901.955 2786.314]"]:
    t = parse_temperament_data(text)
    print(f"{text!r:32} -> {t.variance.name} {t.matrix}")
```
Output:
```
'⟨12 19 28]'                     -> ROW ((12, 19, 28),)
'<12 19 28]'                     -> ROW ((12, 19, 28),)
'[-4 4 -1⟩'                      -> COL ((-4, 4, -1),)
'|-4 4 -1>'                      -> COL ((-4, 4, -1),)
'[1, -5, 3⟩'                     -> COL ((1, -5, 3),)
'[[-4 4 -1⟩ [7 0 -3⟩]'           -> COL ((-4, 4, -1), (7, 0, -3))
'[<1 0 -4] <0 1 4]>'             -> ROW ((1, 0, -4), (0, 1, 4))
'⟨1200.000 1901.955 2786.314]'   -> ROW ((1200.0, 1901.955, 2786.314),)
```
### A dotted domain-basis prefix selects a nonstandard (subgroup) domain basis
```python
from rtt.library.parsing import parse_temperament_data, parse_domain_basis

print(parse_temperament_data("2.3.7 [⟨1 1 3] ⟨0 3 -1]⧽"))
print(parse_temperament_data("2.9.7 ⟨11 35 31]"))
print(parse_domain_basis("2.3.13/5"))
```
Output:
```
Temperament(matrix=((1, 1, 3), (0, 3, -1)), variance=<Variance.ROW: 'row'>, domain_basis=(2, 3, 7))
Temperament(matrix=((11, 35, 31),), variance=<Variance.ROW: 'row'>, domain_basis=(2, 9, 7))
(2, 3, Fraction(13, 5))
```
### Turn ratio lists into prime-count vectors padded to a dimensionality
```python
from rtt.library.parsing import parse_quotients, parse_quotient_list

print(parse_quotients("{2/1, 3/2, 5/4}"))
print(parse_quotients("4:5:6"))
print(parse_quotient_list("{9/8, 81/80, 5/4}", 3))
```
Output:
```
[Fraction(2, 1), Fraction(3, 2), Fraction(5, 4)]
[Fraction(4, 1), Fraction(5, 1), Fraction(6, 1)]
((-3, 2, 0), (-4, 4, -1), (-2, 0, 1))
```

## rtt.library.superspace
Small exact-matrix helpers for the chapter-9 nonstandard-domain 'superspace' (the simplest prime-only basis containing a subgroup): lifting subgroup vectors into prime space, composing mappings with the basis embedding, and solving for generator embeddings.
Functions:
- apply_matrix_to_vectors(matrix, vectors) -> tuple: matrix times each vector (vectors given as row tuples); entries may be ints or Fractions
- lift_vectors(basis_embedding: Matrix, vectors) -> tuple: re-express subgroup vectors over the superspace primes (B_L^T * v for each v)
- compose_mapping_with_embedding(mapping: Matrix, basis_embedding: Matrix) -> Matrix: M_L * B_L^T, the rL x d map from subgroup elements to superspace generators; () if either input is empty
- greedy_independent_rows(vectors, limit: int) -> tuple: keeps each vector in order iff linearly independent of those already kept, at most `limit`
- extend_to_full_image_rank(mapping: Matrix, vectors) -> Matrix | None: keeps the given vectors and appends lowest-index unit vectors until mapping*columns reaches rank len(mapping); None if impossible
- least_squares_left_factor(product, right_factor) -> tuple: exact X = product * pinv(right_factor) as Fractions (X * right_factor == product when solvable)
Pitfalls:
- Every function takes RAW matrices (tuples of row tuples), not Temperament objects; use t.matrix.
- The superspace is get_simplest_prime_only_basis(domain_basis) (e.g. 2.3.13/5 -> (2, 3, 5, 13)), which can SKIP primes. Lifted vectors are over those superspace primes, so rtt.library.math_utils.pcv_to_quotient (which assumes 2, 3, 5, 7, 11,…
- Build B_L with express_quotients_in_domain_basis(domain_basis, superspace) and the superspace mapping M_L with dual(change_domain_basis_for_c(comma_basis_temperament, superspace)).matrix
- Vectors passed to apply_matrix_to_vectors / lift_vectors are rows of the `vectors` tuple, each of the right length; mismatched lengths are not checked and silently truncate.
- extend_to_full_image_rank keeps the given vectors unconditionally (even degenerate ones) and returns None, not an exception, when full image rank cannot be reached.
- least_squares_left_factor uses sympy's exact pseudoinverse; it always returns a result, so check X * right_factor == product if you need an exact factor.
### Build the superspace embedding B_L for 2.3.13/5 and lift a comma (676/675) to the prime superspace
```python
from fractions import Fraction as F
from rtt.library.domain_basis import get_simplest_prime_only_basis, express_quotients_in_domain_basis
from rtt.library.superspace import lift_vectors
domain_basis = (2, 3, F(13, 5))
superspace = get_simplest_prime_only_basis(domain_basis)
B_L = express_quotients_in_domain_basis(domain_basis, superspace)
print(superspace)
print(B_L)
comma_in_domain = express_quotients_in_domain_basis((F(676, 675),), domain_basis)
print(comma_in_domain)
lifted = lift_vectors(B_L, comma_in_domain)
print(lifted)
q = F(1)
for p, e in zip(superspace, lifted[0]):
    q *= F(p) ** e
print(q)
```
Output:
```
(2, 3, 5, 13)
((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 1))
((2, -3, 2),)
((2, -3, -2, 2),)
676/675
```
### Superspace mapping M_L, and the composite domain->superspace-generators map M_s->L = M_L B_L^T
```python
from fractions import Fraction as F
from rtt.library.domain_basis import get_simplest_prime_only_basis, express_quotients_in_domain_basis
from rtt.library.change_basis import change_domain_basis_for_c
from rtt.library.dual import dual
from rtt.library.temperament import Temperament, Variance
from rtt.library.superspace import compose_mapping_with_embedding, apply_matrix_to_vectors, lift_vectors
domain_basis = (2, 3, F(13, 5))
superspace = get_simplest_prime_only_basis(domain_basis)
B_L = express_quotients_in_domain_basis(domain_basis, superspace)
commas = Temperament(express_quotients_in_domain_basis((F(676, 675),), domain_basis), Variance.COL, domain_basis)
M_L = dual(change_domain_basis_for_c(commas, superspace)).matrix
print("M_L:", M_L)
M_sL = compose_mapping_with_embedding(M_L, B_L)
print("M_s->L:", M_sL)
vectors = ((2, -3, 2), (1, 0, 0), (0, 1, -1))
print(apply_matrix_to_vectors(M_sL, vectors))
print(apply_matrix_to_vectors(M_L, lift_vectors(B_L, vectors)))
```
Output:
```
M_L: ((1, 0, 0, -1), (0, 2, 0, 3), (0, 0, 1, 1))
M_s->L: ((1, 0, -1), (0, 2, 3), (0, 0, 0))
((0, 0, 0), (1, 0, 0), (1, -1, 0))
((0, 0, 0), (1, 0, 0), (1, -1, 0))
```
### Greedy independent rows and extending a held set to full image rank (None when impossible)
```python
from rtt.library.superspace import greedy_independent_rows, extend_to_full_image_rank
print(greedy_independent_rows(((1, 0, 0), (2, 0, 0), (0, 0, 1)), 3))
M_L = ((1, 0, 0, -1), (0, 2, 0, 3), (0, 0, 1, 1))
print(extend_to_full_image_rank(M_L, ((1, 0, 0, 0), (0, 0, -1, 1))))
print(extend_to_full_image_rank(((1, 0), (2, 0)), ()))
```
Output:
```
((1, 0, 0), (0, 0, 1))
((1, 0, 0, 0), (0, 0, -1, 1), (0, 0, 1, 0))
None
```
### Exact least-squares left factor G with G*M = P
```python
from fractions import Fraction as F
from rtt.library.superspace import least_squares_left_factor
from rtt.library.matrix_utils import matrix_multiply
P = ((F(1), F(0), F(-1)), (F(0), F(1), F(3, 2)), (F(0), F(0), F(0)))
M_sL = ((1, 0, -1), (0, 2, 3), (0, 0, 0))
G = least_squares_left_factor(P, M_sL)
print(G)
print(matrix_multiply(G, M_sL) == P)
```
Output:
```
((Fraction(1, 1), Fraction(0, 1), Fraction(0, 1)), (Fraction(0, 1), Fraction(1, 2), Fraction(0, 1)), (Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)))
True
```

## rtt.library.symbolic_tuning
Returns the exact rational closed-form generator operator for unweighted miniRMS tuning schemes, so tunings can be expressed as exact combinations of 1200*log2(prime).
Functions:
- has_rational_closed_form(spec: TuningSchemeSpec, t: Temperament) -> bool: True only when optimization power is 2 (miniRMS), slope is unityWeight, the scheme is not all-interval, no destretching, no no…
- closed_form_generator_operator(t: Temperament, spec: TuningSchemeSpec | str) -> sympy.Matrix | None: exact rational d x r matrix G (rows = domain primes, columns = generators) with generator tuning ma…
Pitfalls:
- has_rational_closed_form requires a TuningSchemeSpec (call resolve_tuning_scheme(name) first) and takes (spec, t) in that order; closed_form_generator_operator takes (t, spec) and accepts a name string.
- Only unweighted miniRMS schemes qualify (names ending in '-U' with 'miniRMS'). Any S or C slope, minimax/miniaverage, all-interval, destretched, prime-based/nonprime-based, size-factor complexity, or a domain basis with a nonprime element (…
- The operator is d x r (rows = primes, columns = generators): multiply the just tuning map ROW vector on the LEFT (just * G) to get generators, then * mapping to get the tuning map. Entries are exact sympy Rationals
- 'miniRMS-U' with no target set gives the pseudoinverse operator (just * pinv(M)), which equals the numeric result of 'primes miniRMS-U' (meantone (1202.607, 696.741))
### Which schemes have a rational closed form, and the operator for each
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.symbolic_tuning import closed_form_generator_operator, has_rational_closed_form
from rtt.library.tuning_scheme_names import resolve_tuning_scheme

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
for name in ["miniRMS-U", "held-octave miniRMS-U", "{2, 3/2, 5/4} miniRMS-U", "miniRMS-S", "minimax-U", "TILT miniRMS-C"]:
    spec = resolve_tuning_scheme(name)
    print(f"{name:26s} closed form? {has_rational_closed_form(spec, meantone)}  operator={closed_form_generator_operator(meantone, name)}")
```
Output:
```
miniRMS-U                  closed form? True  operator=Matrix([[17/33, -1/33], [16/33, 1/33], [-4/33, 8/33]])
held-octave miniRMS-U      closed form? True  operator=Matrix([[1, -1/33], [0, 1/33], [0, 8/33]])
{2, 3/2, 5/4} miniRMS-U    closed form? True  operator=Matrix([[13/21, -5/21], [8/21, 5/21], [-2/21, 4/21]])
miniRMS-S                  closed form? False  operator=None
minimax-U                  closed form? False  operator=None
TILT miniRMS-C             closed form? False  operator=None
```
### Exact generator sizes as rational combinations of 1200*log2(p), checked against the numeric optimizer
```python
import sympy as sp

from rtt.library.domain_basis import get_domain_basis
from rtt.library.parsing import parse_temperament_data
from rtt.library.symbolic_tuning import closed_form_generator_operator
from rtt.library.tuning import optimize_generator_tuning_map

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
scheme = "held-octave {5/4, 3/2} miniRMS-U"
operator = closed_form_generator_operator(meantone, scheme)
primes = [int(p) for p in get_domain_basis(meantone)]
print("operator (d rows x r cols):", operator)
for k in range(operator.cols):
    terms = " + ".join(f"({operator[i, k]})·1200·log2({p})" for i, p in enumerate(primes) if operator[i, k] != 0)
    value = sum(operator[i, k] * 1200 * sp.log(p, 2) for i, p in enumerate(primes))
    print(f"generator {k + 1} = {terms} = {float(sp.N(value)):.6f}")
print("numeric optimizer:", tuple(round(x, 6) for x in optimize_generator_tuning_map(meantone, scheme)))
```
Output:
```
operator (d rows x r cols): Matrix([[1, -1/17], [0, 1/17], [0, 4/17]])
generator 1 = (1)·1200·log2(2) = 1200.000000
generator 2 = (-1/17)·1200·log2(2) + (1/17)·1200·log2(3) + (4/17)·1200·log2(5) = 696.894697
numeric optimizer: (1200.0, 696.894697)
```
### Nonprime domain basis has no closed form; a non-consecutive prime basis does
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.symbolic_tuning import closed_form_generator_operator

print(closed_form_generator_operator(parse_temperament_data("2.9.5 [⟨1 1 0] ⟨0 1 4]⧽"), "miniRMS-U"))
print(closed_form_generator_operator(parse_temperament_data("2.3.7 [⟨1 1 0] ⟨0 1 4]⧽"), "miniRMS-U"))
```
Output:
```
None
Matrix([[17/33, -1/33], [16/33, 1/33], [-4/33, 8/33]])
```

## rtt.library.target_intervals
Generates target-interval sets (truncated integer limit triangle TILT, odd limit diamond OLD, otonal chords) as Fraction ratios and resolves their default limits for a domain basis.
Functions:
- MIN_SIZE = Fraction(15, 13), MAX_SIZE = Fraction(13, 4): size bounds of a TILT
- get_tilt(integer_limit: int) -> tuple[Fraction, ...]: TILT: ratios n/d with 2 <= n <= integer_limit, d < n, 15/13 <= n/d <= 13/4 and n*d <= 13*integer_limit (deduplicated, cached)
- get_old(odd_limit: int) -> tuple[Fraction, ...]: odd limit diamond, octave-reduced, with 2/1 prepended (cached)
- get_otonal_chord(harmonics: tuple[int, ...]) -> tuple[Fraction, ...]: every interval between two harmonics of the chord, e.g. (4, 5, 6)
- default_tilt_limit(domain_basis: tuple) -> int: nextprime(largest numerator or denominator in the basis) - 1 (6 for 2.3.5, 10 for 2.3.5.7)
- default_old_limit(domain_basis: tuple) -> int: nextprime(largest odd part in the basis) - 2 (5 for 2.3.5, 9 for 2.3.5.7)
- process_tilt(target_spec: str, domain_basis: tuple) -> tuple[Fraction, ...]: parses 'TILT', 'N-TILT' or 'truncated integer limit triangle' into its ratios, using default_tilt_limit when no N
- process_old(target_spec: str, domain_basis: tuple) -> tuple[Fraction, ...]: parses 'OLD', 'N-OLD' or 'odd limit diamond' into its ratios, using default_old_limit when no N
Pitfalls:
- get_tilt / get_old / process_tilt / process_old return Fractions and do NOT filter to the temperament's primes: process_old('9-OLD', (2, 3, 5)) still contains 8/7, 7/4, 9/7 etc.
- OLD ratios are octave-reduced and always include 2/1 first; the order is generation order, not sorted by size. TILT includes ratios above the octave (3/1, 5/2) and is bounded by 15/13 and 13/4.
- quotient_to_pcv (in rtt.library.math_utils) returns a vector only as long as its highest prime, e.g. 3/2 -> (-1, 1); pad with pad_vectors_with_zeros_up_to_d((v,), d)[0] before using it with a d-dimensional temperament.
- Default limits come from the domain basis, not the temperament's rank or the mapping: 2.3.5 gives 6-TILT / 5-OLD, 2.3.5.7 gives 10-TILT / 9-OLD, 2.9.21 gives 22-TILT / 21-OLD, 2.3.13/5 gives 16-TILT / 15-OLD.
- get_otonal_chord takes a tuple of harmonics (ints), e.g. (4, 5, 6, 7), not a ratio string.
### TILT, OLD and otonal-chord target sets as ratios
```python
from rtt.library.target_intervals import get_old, get_otonal_chord, get_tilt

print("6-TILT:", [str(q) for q in get_tilt(6)])
print("5-OLD:", [str(q) for q in get_old(5)])
print("7-OLD:", [str(q) for q in get_old(7)])
print("4:5:6:7 otonal chord:", [str(q) for q in get_otonal_chord((4, 5, 6, 7))])
```
Output:
```
6-TILT: ['2', '3', '3/2', '4/3', '5/2', '5/3', '5/4', '6/5']
5-OLD: ['2', '4/3', '8/5', '3/2', '6/5', '5/4', '5/3']
7-OLD: ['2', '4/3', '8/5', '8/7', '3/2', '6/5', '12/7', '5/4', '5/3', '10/7', '7/4', '7/6', '7/5']
4:5:6:7 otonal chord: ['5/4', '3/2', '7/4', '6/5', '7/5', '7/6']
```
### Default limits per domain basis and the process_* parsers (note: unfiltered by prime limit)
```python
from fractions import Fraction

from rtt.library.target_intervals import default_old_limit, default_tilt_limit, process_old, process_tilt

for basis in [(2, 3, 5), (2, 3, 5, 7), (2, 9, 21), (2, 3, Fraction(13, 5))]:
    print(basis, "default TILT limit:", default_tilt_limit(basis), "default OLD limit:", default_old_limit(basis))
print([str(q) for q in process_tilt("TILT", (2, 3, 5))])
print([str(q) for q in process_old("9-OLD", (2, 3, 5))])
print([str(q) for q in process_old("odd limit diamond", (2, 3, 5, 7))][:6], "...")
```
Output:
```
(2, 3, 5) default TILT limit: 6 default OLD limit: 5
(2, 3, 5, 7) default TILT limit: 10 default OLD limit: 9
(2, 9, 21) default TILT limit: 22 default OLD limit: 21
(2, 3, Fraction(13, 5)) default TILT limit: 16 default OLD limit: 15
['2', '3', '3/2', '4/3', '5/2', '5/3', '5/4', '6/5']
['2', '4/3', '8/5', '8/7', '16/9', '3/2', '6/5', '12/7', '5/4', '5/3', '10/7', '10/9', '7/4', '7/6', '7/5', '14/9', '9/8', '9/5', '9/7']
['2', '4/3', '8/5', '8/7', '16/9', '3/2'] ...
```
### Resolve a target set into prime-count vectors for a temperament (via rtt.library.tuning.resolve_target_intervals) and convert ratios <-> prime-count vectors
```python
from fractions import Fraction

from rtt.library.math_utils import pcv_to_quotient, quotient_to_pcv
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning import resolve_target_intervals

septimal_meantone = parse_temperament_data("[⟨1 0 -4 -13] ⟨0 1 4 10]⧽")
vectors = resolve_target_intervals("OLD", septimal_meantone, 4)
print(len(vectors), "targets; first five:", vectors[:5])
print("as ratios:", [str(pcv_to_quotient(v)) for v in vectors[:5]])
print("quotient_to_pcv(81/80) =", quotient_to_pcv(Fraction(81, 80)))
print("quotient_to_pcv(7/4) =", quotient_to_pcv(Fraction(7, 4)))
```
Output:
```
19 targets; first five: ((1, 0, 0, 0), (2, -1, 0, 0), (3, 0, -1, 0), (3, 0, 0, -1), (4, -2, 0, 0))
as ratios: ['2', '4/3', '8/5', '8/7', '16/9']
quotient_to_pcv(81/80) = (-4, 4, -1)
quotient_to_pcv(7/4) = (-2, 0, 0, 1)
```
### A 9-OLD target set applied to a 5-limit temperament keeps only its 5-limit members
```python
from rtt.library.math_utils import pcv_to_quotient
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning import resolve_target_intervals

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
vectors = resolve_target_intervals("9-OLD", meantone, 3)
print(len(vectors), [str(pcv_to_quotient(v)) for v in vectors])
```
Output:
```
11 ['2', '4/3', '8/5', '16/9', '3/2', '6/5', '5/4', '5/3', '10/9', '9/8', '9/5']
```

## rtt.library.temperament
The core immutable data types: Temperament (matrix + variance + optional domain basis) and the Variance enum (ROW for maps, COL for vectors).
Functions:
- class Variance(Enum): ROW = "row" (maps, mappings: covariant) and COL = "col" (prime-count vectors, comma bases: contravariant)
- Variance.from_string(text: str) -> Variance: synonyms such as "mapping", "map", "row", "covariant", "et", "edo" -> ROW
- Temperament(matrix: tuple[tuple[int, ...], ...], variance: Variance, domain_basis: tuple[int, ...] | None = None): frozen (immutable, hashable) dataclass
Pitfalls:
- Always build matrix as a tuple of tuples. A list of lists makes a Temperament that is unequal to the tuple form and is unhashable (TypeError), which breaks equality checks and caching.
- For a COL Temperament each inner tuple is one vector (one comma), not a row of the column-major math matrix.
- domain_basis=None and an explicit standard basis like (2, 3, 5) are not equal as dataclass fields; canonical_form normalizes a standard prime-limit basis to None.
- Temperament has no methods; all operations are free functions in the other modules (dual, canonical_form, get_rank, to_ebk, ...).
### Build a Temperament directly (matrix must be a tuple of tuples) and compare it with a parsed one
```python
from rtt.library.temperament import Temperament, Variance
from rtt.library.parsing import parse_temperament_data

et12 = Temperament(((12, 19, 28),), Variance.ROW)
print(et12 == parse_temperament_data("⟨12 19 28]"))
comma = Temperament(((-4, 4, -1),), Variance.COL)
print(comma == parse_temperament_data("[-4 4 -1⟩"))
septimal_subgroup = Temperament(((1, 1, 3), (0, 3, -1)), Variance.ROW, (2, 3, 7))
print(septimal_subgroup)
```
Output:
```
True
True
Temperament(matrix=((1, 1, 3), (0, 3, -1)), variance=<Variance.ROW: 'row'>, domain_basis=(2, 3, 7))
```
### Variance.from_string accepts many synonyms; unknown words raise ValueError
```python
from rtt.library.temperament import Variance

for word in ["mapping", "map", "row", "covariant", "comma basis", "comma", "vector", "col", "contravariant"]:
    print(word, "->", Variance.from_string(word))
try:
    Variance.from_string("sideways")
except ValueError as error:
    print("ValueError:", error)
```
Output:
```
mapping -> Variance.ROW
map -> Variance.ROW
row -> Variance.ROW
covariant -> Variance.ROW
comma basis -> Variance.COL
comma -> Variance.COL
vector -> Variance.COL
col -> Variance.COL
contravariant -> Variance.COL
ValueError: Unrecognized variance: 'sideways'
```
### Pitfall: a list-of-lists matrix is not equal to the tuple form and is unhashable
```python
from rtt.library.temperament import Temperament, Variance

as_lists = Temperament([[12, 19, 28]], Variance.ROW)
as_tuples = Temperament(((12, 19, 28),), Variance.ROW)
print(as_lists == as_tuples)
try:
    hash(as_lists)
except TypeError as error:
    print("TypeError:", error)
print(hash(as_tuples) == hash(Temperament(((12, 19, 28),), Variance.ROW)))
```
Output:
```
False
TypeError: unhashable type: 'list'
True
```

## rtt.library.tuning
Optimizes generator tuning maps and tuning maps (in cents) for a temperament under a tuning scheme, and evaluates per-target and mean damage of any given tuning.
Functions:
- optimize_generator_tuning_map(t: Temperament, spec: TuningSchemeSpec | str, prescaler_override=None, weights_override=None) -> tuple[float, ...]: optimal generator tuning map in cents, one entry per m…
- optimize_tuning_map(t, spec, prescaler_override=None, weights_override=None) -> tuple[float, ...]: optimal tuning map in cents, one entry per domain-basis element (primes 2,3,5,.
- get_tuning_map_damages(t, tuning_map: tuple, spec: TuningSchemeSpec | str) -> dict[Fraction, float]: damage of each target interval (weighted |tempered - just| in cents) under the scheme's targets and…
- get_generator_tuning_map_damages(t, generator_tuning_map: tuple, spec) -> dict[Fraction, float]: same as get_tuning_map_damages but starting from generators
- get_tuning_map_mean_damage(t, tuning_map: tuple, spec) -> float: power mean of the damages at the scheme's optimization power (max for minimax, RMS for miniRMS, arithmetic mean for miniaverage, p-mean…
- get_generator_tuning_map_mean_damage(t, generator_tuning_map: tuple, spec) -> float: mean damage starting from generators
- tuning_map_from_generators(t, generator_tuning_map: tuple) -> numpy.ndarray: generators @ mapping (returns an ndarray, not a tuple)
- generator_tuning_map_from_t_and_tuning_map(t, tuning_map: tuple) -> tuple[float, ...]: recovers generators from a tuning map via the pseudoinverse of the mapping
- get_just_tuning_map(t) -> tuple[float, ...]: 1200*log2 of each domain-basis element (cents), e.g. (1200.0, 1901.955, 2786.314) for 2.3.5
- resolve_target_intervals(target_spec: str, t: Temperament, d: int) -> tuple[tuple[int, ...], ...]: turns 'primes', 'TILT', '6-TILT', 'OLD', '9-OLD', '{2/1, 3/2, 5/4}' (or long forms 'truncated integer…
- damage_weights(vectors: tuple[tuple[int, ...], ...], t, spec: TuningSchemeSpec, prescaler_override=None, weights_override=None) -> numpy.ndarray: per-target weights: 1 for unityWeight, complexity for…
- get_dual_power(power: float) -> float: dual norm power 1/(1-1/p): 1 -> inf, 2 -> 2.0, inf -> 1.0; ValueError for power < 1
- (re-exported by import, usable as rtt.library.tuning.X) get_complexity, get_complexity_prescaler from rtt.library.complexity
Pitfalls:
- t must be a Temperament object, not an EBK string: optimize_generator_tuning_map("[⟨1 1 0] ⟨0 1 4]⧽", "minimax-S") raises AttributeError: 'str' object has no attribute 'matrix'. Always wrap with parse_temperament_data(...).
- Every tuning value is in cents (1200 per octave). A generator tuning map has one entry per mapping row; a tuning map has one entry per domain-basis element (prime). Damages are (weighted) cents
- Generators follow the FORM of the mapping you pass, not a canonical one: the same meantone given as [⟨1 2 4] ⟨0 -1 -4]⧽ gives minimax-S generators (1201.699, 504.134) (a fourth) instead of (1201.699, 697.564)
- A scheme name ending in U or C with NO target-set prefix (e.g. 'minimax-U', 'minimax-C', 'miniRMS-U') parses to target_intervals=None: nothing is optimized and the generators default toward just via the pseudoinverse (meantone gives (1202.6…
- A bare S name with no target set is all-interval (target_intervals='{}'): optimization is over the primes at the dual of the complexity norm power, so the optimization-power word does not matter: 'miniRMS-S', 'miniaverage-S', 'mini-3-mean-S…
- Target intervals needing primes beyond the temperament's limit are silently dropped: '{2/1, 3/2, 7/4} minimax-U' on 5-limit meantone returns (1200.0, 701.9550008653873) because 7/4 is discarded and 2/1 and 3/2 are then both just.
- ValueErrors: non-systematic or malformed names ('minimax', 'least squares', lowercase 'minimax-es'); 'destretched-81/80 minimax-ES' on meantone ('cannot destretch by an interval the temperament tempers out')
- weights_override must have exactly one positive finite weight per RESOLVED target (after unison/out-of-limit filtering), otherwise it is silently ignored and the slope-derived weights are used.
### Optimal generators and tuning map of 5-limit meantone under all-interval schemes (minimax-S, minimax-ES) plus held-octave and destretched-octave variants
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning import optimize_generator_tuning_map, optimize_tuning_map

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
for scheme in ["minimax-S", "minimax-ES", "held-octave minimax-ES", "destretched-octave minimax-ES"]:
    g = optimize_generator_tuning_map(meantone, scheme)
    tm = optimize_tuning_map(meantone, scheme)
    print(f"{scheme:30s} generators={tuple(round(x, 3) for x in g)} tuning map={tuple(round(x, 3) for x in tm)}")
```
Output:
```
minimax-S                      generators=(1201.699, 697.564) tuning map=(1201.699, 1899.263, 2790.258)
minimax-ES                     generators=(1201.397, 697.049) tuning map=(1201.397, 1898.446, 2788.196)
held-octave minimax-ES         generators=(1200.0, 697.214) tuning map=(1200.0, 1897.214, 2788.857)
destretched-octave minimax-ES  generators=(1200.0, 696.239) tuning map=(1200.0, 1896.239, 2784.955)
```
### Target-set schemes (TILT, OLD, explicit set), held intervals, and an equal temperament built from a patent map
```python
from rtt.library.equal_temperament import patent_val
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning import optimize_generator_tuning_map, optimize_tuning_map

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
for scheme in ["TILT minimax-U", "held-octave TILT miniRMS-U", "held-octave OLD minimax-U",
               "{2/1, 3/2, 5/4} minimax-C", "held-{2/1, 5/4} minimax-U"]:
    g = optimize_generator_tuning_map(meantone, scheme)
    print(f"{scheme:28s} -> {tuple(round(x, 3) for x in g)}")

et31 = Temperament((patent_val(31, (2, 3, 5, 7)),), Variance.ROW)
print("31-ET patent map:", et31.matrix[0])
print("31-ET minimax-S step:", round(optimize_generator_tuning_map(et31, "minimax-S")[0], 4))
print("31-ET TILT miniRMS-U tuning map:", tuple(round(x, 3) for x in optimize_tuning_map(et31, "TILT miniRMS-U")))
```
Output:
```
TILT minimax-U               -> (1200.0, 696.578)
held-octave TILT miniRMS-U   -> (1200.0, 696.274)
held-octave OLD minimax-U    -> (1200.0, 696.578)
{2/1, 3/2, 5/4} minimax-C    -> (1205.691, 699.753)
held-{2/1, 5/4} minimax-U    -> (1200.0, 696.578)
31-ET patent map: (31, 49, 72, 87)
31-ET minimax-S step: 38.757
31-ET TILT miniRMS-U tuning map: (1201.269, 1898.781, 2790.045, 3371.305)
```
### Per-target damages and mean damage of an optimized tuning and of a hand-given 12-ET tuning map
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning import (
    get_generator_tuning_map_damages,
    get_generator_tuning_map_mean_damage,
    get_tuning_map_damages,
    get_tuning_map_mean_damage,
    optimize_generator_tuning_map,
)

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
scheme = "TILT minimax-U"
g = optimize_generator_tuning_map(meantone, scheme)
damages = get_generator_tuning_map_damages(meantone, g, scheme)
for quotient, damage in damages.items():
    print(f"{str(quotient):>4s}: {damage:.3f}")
print("max damage:", round(get_generator_tuning_map_mean_damage(meantone, g, scheme), 3))

et12 = parse_temperament_data("⟨12 19 28]")
tuning_map = (1200, 1900, 2800)
print({str(q): round(d, 3) for q, d in get_tuning_map_damages(et12, tuning_map, "TILT miniRMS-U").items()})
print("RMS damage:", round(get_tuning_map_mean_damage(et12, tuning_map, "TILT miniRMS-U"), 3))
```
Output:
```
2: 0.000
   3: 5.377
 3/2: 5.377
 4/3: 5.377
 5/2: 0.000
 5/3: 5.377
 5/4: 0.000
 6/5: 5.377
max damage: 5.377
{'2': 0.0, '3': 1.955, '3/2': 1.955, '4/3': 1.955, '5/2': 13.686, '5/3': 15.641, '5/4': 13.686, '6/5': 15.641}
RMS damage: 10.461
```
### Just tuning map, generators <-> tuning map conversion, and the pitfall that a U/C scheme with no target set does no optimization
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning import (
    generator_tuning_map_from_t_and_tuning_map,
    get_just_tuning_map,
    optimize_generator_tuning_map,
    tuning_map_from_generators,
)

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
print("just tuning map:", tuple(round(x, 3) for x in get_just_tuning_map(meantone)))
tm = tuning_map_from_generators(meantone, (1200.0, 696.578))
print("tuning map:", type(tm).__name__, [round(float(x), 3) for x in tm])
print("back to generators:", tuple(round(x, 3) for x in generator_tuning_map_from_t_and_tuning_map(meantone, tuple(tm))))
for scheme in ["minimax-U", "TILT minimax-U"]:
    print(f"{scheme}:", tuple(round(x, 3) for x in optimize_generator_tuning_map(meantone, scheme)))
```
Output:
```
just tuning map: (1200.0, 1901.955, 2786.314)
tuning map: ndarray [1200.0, 1896.578, 2786.312]
back to generators: (1200.0, 696.578)
minimax-U: (1202.607, 696.741)
TILT minimax-U: (1200.0, 696.578)
```

## rtt.library.tuning_ranges
Computes, per generator, the range of sizes (in cents, with the octave held pure) over which a temperament's tuning stays monotone or stays within the tradeoff region of its target intervals.
Functions:
- get_generator_tuning_range(t: Temperament, mode: Literal['monotone', 'tradeoff'], target_spec: str = 'OLD') -> tuple[tuple[float, float], ...] | None: one (min, max) cents pair per generator
- Mode = Literal['monotone', 'tradeoff'] (type alias)
Pitfalls:
- Both modes hold the first domain-basis element (assumed to be the octave, 2/1) at exactly its just size 1200 cents as an equality constraint, so a generator that is the octave comes back as (1200.0, 1200.0).
- Ranges are in the generator form of the mapping you pass: porcupine [⟨1 2 3] ⟨0 3 5]⧽ gives a negative range (-166.015, -157.821). Re-express or negate if the user expects the positive generator.
- Returns None (not an exception) when the range does not exist: 'monotone' when no monotone tuning is possible (e.g. ⟨1 1]), 'tradeoff' when the octave is tempered out (e.g. ⟨0 1 4]). Check for None before indexing.
- mode must be exactly 'monotone' or 'tradeoff' (ValueError: unknown mode otherwise). target_spec defaults to 'OLD' (the default odd limit of the domain), not TILT.
- Targets beyond the temperament's primes are filtered out ('9-OLD' on a 5-limit temperament uses only its 5-limit members). 'tradeoff' enumerates every combination of r-1 targets, so large ranks with large target sets get slow.
### Meantone fifth: tradeoff and monotone ranges over the default OLD and over 9-OLD
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning_ranges import get_generator_tuning_range

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
for mode in ("tradeoff", "monotone"):
    ranges = get_generator_tuning_range(meantone, mode)
    print(mode, [tuple(round(x, 3) for x in r) for r in ranges])
print("tradeoff over 9-OLD:", [tuple(round(x, 3) for x in r) for r in get_generator_tuning_range(meantone, "tradeoff", "9-OLD")])
```
Output:
```
tradeoff [(1200.0, 1200.0), (694.786, 701.955)]
monotone [(1200.0, 1200.0), (685.714, 720.0)]
tradeoff over 9-OLD: [(1200.0, 1200.0), (691.202, 701.955)]
```
### Other temperaments, None results, and the unknown-mode error
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning_ranges import get_generator_tuning_range

for ebk in ["[⟨1 0 2] ⟨0 5 1]⧽", "[⟨1 2 3] ⟨0 3 5]⧽", "⟨1 1]", "⟨0 1 4]"]:
    t = parse_temperament_data(ebk)
    ranges = {mode: get_generator_tuning_range(t, mode) for mode in ("tradeoff", "monotone")}
    print(ebk, {mode: None if r is None else [tuple(round(x, 3) for x in pair) for pair in r] for mode, r in ranges.items()})
try:
    get_generator_tuning_range(parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽"), "tradoff")
except ValueError as error:
    print("ValueError:", error)
```
Output:
```
[⟨1 0 2] ⟨0 5 1]⧽ {'tradeoff': [(1200.0, 1200.0), (378.91, 386.314)], 'monotone': [(1200.0, 1200.0), (360.0, 400.0)]}
[⟨1 2 3] ⟨0 3 5]⧽ {'tradeoff': [(1200.0, 1200.0), (-166.015, -157.821)], 'monotone': [(1200.0, 1200.0), (-171.429, -150.0)]}
⟨1 1] {'tradeoff': [(1200.0, 1200.0)], 'monotone': None}
⟨0 1 4] {'tradeoff': None, 'monotone': None}
ValueError: unknown mode: 'tradoff'
```

## rtt.library.tuning_scheme_names
Parses systematic tuning-scheme names into TuningSchemeSpec objects and renders specs back into systematic names.
Functions:
- TuningSchemeSpec(optimization_power: float, target_intervals: str | None = None, damage_weight_slope: str = 'unityWeight', complexity_norm_power: float = 1, complexity_log_prime_power: float = 1, comp…
- ComplexitySpec(norm_power: float = 1, log_prime_power: float = 1, prime_power: float = 0, size_factor: float = 0, rough: int = 0, nonprime_basis_approach: str = ''): frozen dataclass consumed by rtt.l…
- tuning_scheme_from_systematic_name(name: str) -> TuningSchemeSpec: parses a systematic name; ValueError if it is not one
- resolve_tuning_scheme(spec: TuningSchemeSpec | str) -> TuningSchemeSpec: parses a string, passes a spec through unchanged
- systematic_name(spec: TuningSchemeSpec) -> str | None: inverse of the parser (round-trips canonical names); None for specs with no systematic name (non-integer optimization power other than inf/2/1, c…
- damage_name_traits(name: str) -> dict: e.g. 'E-copfr-S-damage' -> {'damage_weight_slope': ..., 'complexity_norm_power': ..., ...} kwargs to splat into TuningSchemeSpec
- complexity_name_traits(name: str) -> tuple[dict, str | None]: e.g. 'lols-complexity' -> (complexity traits, 'octave'); the second item is the held interval implied by the complexity (or None)
- annotation_code(spec: TuningSchemeSpec, letter: str) -> str: the complexity-plus-slope code for a slope letter, e.g. 'E-sopfr-C'
- TuningSchemeSpec(optimization_power, target_intervals=None, damage_weight_slope='unityWeight', complexity_norm_power=1, complexity_log_prime_power=1, complexity_prime_power=0, complexity_size_factor=0…
- ComplexitySpec(norm_power=1, log_prime_power=1, prime_power=0, size_factor=0, rough=0, nonprime_basis_approach=''): frozen dataclass of the complexity traits
- tuning_scheme_from_systematic_name(name: str) -> TuningSchemeSpec: parse a systematic name; ValueError if it does not end in U, S or C
- resolve_tuning_scheme(spec: TuningSchemeSpec | str) -> TuningSchemeSpec: string -> parsed spec, spec -> unchanged (all tuning functions accept either)
- systematic_name(spec: TuningSchemeSpec) -> str | None: inverse of the parser; None for specs with no systematic name (e.g. optimization power 1.5, norm power 3)
- annotation_code(spec: TuningSchemeSpec, letter: str) -> str: the complexity annotation for a slope letter, e.g. annotation_code(parse('minimax-E-sopfr-S'), 'C') == 'E-sopfr-C'
Pitfalls:
- GRAMMAR (in this order, space-separated): [held-<interval> ] [destretched-<interval> ] [<target set> ] [prime-based | nonprime-based ] <power word>-<complexity annotation><slope letter>.
- Power words: 'minimax' (p = inf), 'miniRMS' (p = 2), 'miniaverage' (p = 1), 'mini-N-mean' (p = N, integer N only, e.g. 'mini-3-mean-S').
- Complexity annotation tokens, joined by hyphens before the slope letter: (none) = log-prime taxicab (q = 1, log-prime power 1; same as 'lopfr' / 'lp'); 'E' = Euclidean (q = 2), e.g. 'minimax-ES', 'minimax-E-copfr-S'
- Target sets: 'TILT' / 'N-TILT' (e.g. '6-TILT'), 'OLD' / 'N-OLD' (e.g. '9-OLD'), 'primes', or an explicit brace set of ratios such as '{2/1, 3/2, 5/4}' (digits, slashes, commas and spaces only).
- With no target set: an S name becomes all-interval (target_intervals='{}'), but a U or C name gets target_intervals=None (no targets at all, so no real optimization). So write 'TILT minimax-U', not 'minimax-U'.
- Held intervals: 'held-octave', 'held-2', 'held-2/1', 'held-{2}', 'held-{2/1}' are synonyms; several: 'held-{2/1, 3/2} TILT minimax-U' or 'held-{2/1, 5/4} minimax-U'. Destretching: 'destretched-octave minimax-ES'.
- The long-form phrases 'odd limit diamond' / 'truncated integer limit triangle' are NOT understood inside a scheme NAME: 'odd limit diamond minimax-U' silently misparses to target_intervals=None, held_intervals='octave', complexity_size_fact…
- Token detection is substring based: any '-E' in the name selects the Euclidean norm and any '-M' selects the max norm, so keep exactly the systematic spellings.
### Render specs back into systematic names (round trip), including None for unnameable specs
```python
from math import inf

from rtt.library.tuning_scheme_names import TuningSchemeSpec, resolve_tuning_scheme, systematic_name

for name in ["minimax-copfr-S", "held-octave TILT minimax-ES", "{2/1, 3/2} minimax-U", "minimax-lols-S"]:
    print(f"{name!r:32} -> {systematic_name(resolve_tuning_scheme(name))!r}")

spec = TuningSchemeSpec(optimization_power=2, target_intervals="TILT", damage_weight_slope="complexityWeight",
                        complexity_norm_power=2, complexity_log_prime_power=0, complexity_prime_power=1)
print(systematic_name(spec))
print(systematic_name(TuningSchemeSpec(optimization_power=1.5, target_intervals="{}", damage_weight_slope="simplicityWeight")))
print(systematic_name(TuningSchemeSpec(optimization_power=inf, target_intervals="{}", damage_weight_slope="simplicityWeight", complexity_norm_power=3)))
```
Output:
```
'minimax-copfr-S'                -> 'minimax-copfr-S'
'held-octave TILT minimax-ES'    -> 'held-octave TILT minimax-ES'
'{2/1, 3/2} minimax-U'           -> '{2/1, 3/2} minimax-U'
'minimax-lols-S'                 -> 'minimax-lols-S'
TILT miniRMS-E-sopfr-C
None
None
```

## rtt.library.tuning_solvers
Low-level numeric solver that finds the generator vector minimizing the p-norm of (tempered - just) over a set of already-weighted target rows.
Functions:
- solve_optimum(tempered: numpy.ndarray, just: numpy.ndarray, power: float, rank: int) -> numpy.ndarray: tempered is k x r (each target's generator counts = target_vector @ mapping.T, already multiplied…
Pitfalls:
- This is a raw solver: it knows nothing about schemes, held intervals, weights or domain bases. Weights must be pre-multiplied into both tempered rows and just values by the caller.
- Arguments must be numpy float arrays; tempered is k x rank, just has length k; power is a float (use float('inf') for minimax).
- Powers other than 1, 2 and inf use Nelder-Mead and are only approximate (agreement to roughly 1e-3 cents is typical); powers 1 and inf solve linear programs and raise ValueError if scipy's linprog fails to converge.
- Ties: p = inf returns the nested-minimax solution (successively minimizing the remaining maximum); p = 1 returns the p -> 1+ limit when the miniaverage optimum is not unique, so results are deterministic.
### Same small system solved at powers 2, inf, 1 and 3
```python
import numpy as np

from rtt.library.tuning_solvers import solve_optimum

tempered = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 1.0]])
just = np.array([100.0, 200.0, 305.0, 390.0])
for power in [2, float("inf"), 1, 3]:
    generators = solve_optimum(tempered, just, power, 2)
    errors = tempered @ generators - just
    print(f"p={power}: generators={np.round(generators, 3).tolist()} errors={np.round(errors, 3).tolist()}")
```
Output:
```
p=2: generators=[96.667, 201.667] errors=[-3.333, 1.667, -6.667, 5.0]
p=inf: generators=[95.0, 205.0] errors=[-5.0, 5.0, -5.0, 5.0]
p=1: generators=[97.287, 200.0] errors=[-2.713, 0.0, -7.713, 4.574]
p=3: generators=[95.988, 203.085] errors=[-4.012, 3.085, -5.927, 5.061]
```
### Hand-built unity-weight minimax of meantone over {2/1, 3/2, 5/4} (equals the library's high-level result for that target set with unit weights)
```python
from math import log2

import numpy as np

from rtt.library.tuning_solvers import solve_optimum

mapping = np.array([[1, 1, 0], [0, 1, 4]], dtype=float)
just_map = np.array([1200 * log2(p) for p in (2, 3, 5)])
targets = np.array([[1, 0, 0], [-1, 1, 0], [-2, 0, 1]], dtype=float)
tempered = targets @ mapping.T
just = targets @ just_map
generators = solve_optimum(tempered, just, float("inf"), 2)
print("minimax over {2/1, 3/2, 5/4}, unity weights:", np.round(generators, 3).tolist())
```
Output:
```
minimax over {2/1, 3/2, 5/4}, unity weights: [1203.072, 698.883]
```

## rtt.library.variance_utils
Variance-aware arithmetic on Temperaments: products (mapping an interval or comma), sums and differences of maps, scaling, and variance checks.
Functions:
- multiply(temperaments: list[Temperament], variance: Variance) -> int | Temperament: product left to right, with COL operands transposed so their vectors become columns
- add_t(t1: Temperament, t2: Temperament) -> Temperament: entrywise sum (keeps t1's variance and domain basis)
- subtract_t(t1: Temperament, t2: Temperament) -> Temperament: entrywise difference
- scale(t: Temperament, scalar) -> Temperament: multiply every entry
- is_rows(t: Temperament) -> bool / is_cols(t: Temperament) -> bool: variance checks
- reinterpret_as_dual_variance(t: Temperament) -> Temperament: same matrix, flipped variance label (not a dual; use dual.dual for the null-space dual)
Pitfalls:
- A comma is tempered out exactly when multiply([map_or_mapping, comma], ...) is 0 (or an all-zero Temperament for a multi-row mapping).
- To get an interval's generator-count vector under a mapping use Variance.COL: multiply([mapping, interval_vector], Variance.COL) -> Temperament(((-2, 4),), COL) for 5/4 in meantone.
- The interval vector length must equal the mapping's dimensionality; pad with math_utils.pad_vectors_with_zeros_up_to_d.
- multiply drops domain_basis from the result.
- add_t / subtract_t zip silently: mismatched lengths truncate instead of raising (⟨12 19 28] + ⟨7 11] -> ⟨19 30]). Map sums are only meaningful between maps of the same domain basis.
### Is a comma tempered out? Map it: a result of 0 means yes
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Variance
from rtt.library.variance_utils import multiply

et12 = parse_temperament_data("⟨12 19 28]")
print(multiply([et12, parse_temperament_data("[-4 4 -1⟩")], Variance.ROW))
print(multiply([et12, parse_temperament_data("[-1 1 0⟩")], Variance.ROW))
meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
print(multiply([meantone, parse_temperament_data("[[-4 4 -1⟩ [1 -5 3⟩]")], Variance.ROW))
```
Output:
```
0
7
Temperament(matrix=((0, -4), (0, 7)), variance=<Variance.ROW: 'row'>, domain_basis=None)
```
### Map an interval to its generator-count vector under a mapping (5/4 in meantone = four fifths minus two octaves)
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.formatting import to_ebk
from rtt.library.temperament import Variance
from rtt.library.variance_utils import multiply

meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
generator_counts = multiply([meantone, parse_temperament_data("[-2 0 1⟩")], Variance.COL)
print(generator_counts)
print(to_ebk(generator_counts))
```
Output:
```
Temperament(matrix=((-2, 4),), variance=<Variance.COL: 'col'>, domain_basis=None)
[-2 4⟩
```
### Add / subtract / scale maps (map arithmetic: ⟨12 19 28] + ⟨7 11 16] = ⟨19 30 44])
```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.formatting import to_ebk
from rtt.library.variance_utils import add_t, subtract_t, scale, is_rows, is_cols, reinterpret_as_dual_variance

et12 = parse_temperament_data("⟨12 19 28]")
et7 = parse_temperament_data("⟨7 11 16]")
print(to_ebk(add_t(et12, et7)))
print(to_ebk(subtract_t(et12, et7)))
print(to_ebk(scale(et12, 2)))
print(is_rows(et12), is_cols(et12), is_cols(reinterpret_as_dual_variance(et12)))
```
Output:
```
⟨19 30 44]
⟨5 8 12]
⟨24 38 56]
True False True
```
