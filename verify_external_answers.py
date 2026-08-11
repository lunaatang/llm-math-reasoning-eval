import sympy as sp
from sympy import Rational, sqrt, floor, gcd, divisors, factorint

results = []

def check(pid, claimed, computed):
    claimed_val = sp.nsimplify(sp.sympify(claimed))
    match = sp.simplify(claimed_val - computed) == 0
    results.append((pid, claimed, str(computed), match))

# EXT-1: r+s=7/2, rs=3/2, r^3+s^3=(r+s)^3-3rs(r+s)
rs_sum = Rational(7,2); rs_prod = Rational(3,2)
ext1 = rs_sum**3 - 3*rs_prod*rs_sum
check("EXT-1", "217/8", ext1)

# EXT-2: x^12 mod (x^2-x-1), remainder F_12 x + F_11; a+b
# Fibonacci F1=F2=1: F11=89, F12=144
fib = [0,1,1]
for i in range(3,13): fib.append(fib[-1]+fib[-2])
ext2 = fib[12] + fib[11]
check("EXT-2", "233", ext2)

# EXT-3: x+1/x=3, S5 via recurrence
S=[2,3]
for i in range(2,6): S.append(3*S[-1]-S[-2])
check("EXT-3", "123", S[5])

# EXT-4: n ≡2 mod7, ≡3 mod8, ≡4 mod9, least positive
sol=None
for n in range(1,505):
    if n%7==2 and n%8==3 and n%9==4:
        sol=n; break
check("EXT-4", "499", sp.Integer(sol))

# EXT-5: 7^2026 mod 1000
ext5 = pow(7,2026,1000)
check("EXT-5", "649", sp.Integer(ext5))

# EXT-6: perfect square divisors of 10!
f = factorint(sp.factorial(10))  # {2:8,3:4,5:2,7:1}
count=1
for p,e in f.items():
    count *= (e//2 + 1)
check("EXT-6", "30", sp.Integer(count))

# EXT-7: 13-14-15 triangle, OI^2 = R(R-2r)
a,b,c=13,14,15
s=Rational(a+b+c,2)
area=sp.sqrt(s*(s-a)*(s-b)*(s-c))
r=area/s
R=Rational(a*b*c,1)/(4*area)
ext7=sp.simplify(R*(R-2*r))
check("EXT-7", "65/64", ext7)

# EXT-8: cyclic quad 2,3,4,5, area^2 = (s-a)(s-b)(s-c)(s-d)
s2=Rational(2+3+4+5,2)
ext8=(s2-2)*(s2-3)*(s2-4)*(s2-5)
check("EXT-8", "120", ext8)

# EXT-9: 5-digit from {0..5} no repeat, divisible by 5
count=0
from itertools import permutations
for p in permutations(range(6),5):
    if p[0]==0: continue
    num=int(''.join(map(str,p)))
    if num%5==0: count+=1
check("EXT-9", "216", sp.Integer(count))

# EXT-10: lattice paths (0,0)->(7,5), never above y=x
# count paths with steps R=(1,0),U=(0,1) staying y<=x always
from functools import lru_cache
@lru_cache(None)
def paths(x,y):
    if y>x: return 0
    if x==0 and y==0: return 1
    total=0
    if x>0: total+=paths(x-1,y)
    if y>0: total+=paths(x,y-1)
    return total
check("EXT-10", "297", sp.Integer(paths(7,5)))

# EXT-11: theta Q4, cos=3/5 => sin=-4/5, tan=-4/3; tan(3theta)
t=Rational(-4,3)
ext11=sp.simplify((3*t - t**3)/(1-3*t**2))
check("EXT-11", "44/117", ext11)

# EXT-12: log2(x)+6/log2(x)=5 => t^2-5t+6=0 => t=2,3 => x=4,8 sum=12
# BUT: problem says x>1, both 4 and 8 are >1, sum=12
check("EXT-12", "12", sp.Integer(4+8))

print(f"{'ID':8} {'claimed':12} {'computed':14} {'OK?'}")
print("-"*45)
for pid,claimed,computed,match in results:
    print(f"{pid:8} {claimed:12} {computed:14} {'✓' if match else 'XX MISMATCH'}")
