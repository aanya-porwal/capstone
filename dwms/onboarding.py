"""Small deterministic conversational onboarding parser; financial fields are confirmed by the user."""
import re
STEPS=[
 ('age','How old are you? You can answer naturally, for example: “I’m 28.”'),
 ('income','What is your approximate monthly take-home income? For example: “Around ₹90,000 a month.”'),
 ('expenses','Roughly how much do you spend each month, including essentials and lifestyle?'),
 ('current_savings','How much do you currently have across savings and investments?'),
 ('monthly_investment','How much could you comfortably invest each month after expenses and debt payments?'),
 ('goal','What is one important financial goal, how much will it cost in today’s money, and when do you need the money? For example: “A home down payment of ₹25 lakh in 7 years.”'),
 ('risk_tolerance','Imagine your investments temporarily fell 20%. Would you sell, feel uncomfortable but stay invested, or remain comfortable?'),
 ('risk_capacity','Could a temporary 20% loss disrupt essential needs or near-term goals? Consider job stability, dependants, debt and emergency savings.'),
]
def amount(text):
    t=text.lower().replace(',','').replace('₹','').replace('rs.','').replace('inr','')
    m=re.search(r'(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lac|l|k)?',t)
    if not m: return None
    v=float(m.group(1)); unit=m.group(2)
    return int(v*({'crore':10000000,'cr':10000000,'lakh':100000,'lac':100000,'l':100000,'k':1000}.get(unit,1)))
def parse_step(key,text,profile):
    p=dict(profile)
    if key=='age':
        m=re.search(r'\b(\d{2})\b',text); p['age']=int(m.group(1)) if m else None
    elif key in ('income','expenses','current_savings','monthly_investment'):
        p[key]=amount(text)
    elif key=='goal':
        nums=re.findall(r'(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lac|l|k)?',text.lower().replace(',',''))
        vals=[]
        for n,u in nums:
            vals.append(int(float(n)*({'crore':10000000,'cr':10000000,'lakh':100000,'lac':100000,'l':100000,'k':1000}.get(u,1))))
        years=re.search(r'(\d+)\s*(?:years?|yrs?)',text.lower())
        p['goal_amount']=vals[0] if vals else None; p['goal_years']=int(years.group(1)) if years else None
        p['goal_name']='User-defined goal'
        if p['goal_amount'] is None or p['goal_years'] is None: return profile,False,'Please include both an approximate amount (for example ₹25 lakh) and a timeline (for example 7 years).'
    elif key=='risk_tolerance':
        t=text.lower(); p['risk_tolerance']=20 if any(x in t for x in ['sell','panic','cannot','can’t']) else (80 if any(x in t for x in ['comfortable','fine','stay invested','remain']) else 50)
    elif key=='risk_capacity':
        t=text.lower(); p['risk_capacity']=25 if any(x in t for x in ['yes','disrupt','difficult','low']) else (75 if any(x in t for x in ['no','manageable','stable','emergency']) else 50)
    if key!='goal' and p.get(key) is None: return profile,False,'I could not confidently identify that value. Could you give me an approximate number or describe it another way?'
    return p,True,None
