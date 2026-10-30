import requests, re
OLLAMA='http://localhost:11434/api/chat'

def ollama_available():
    try: return requests.get('http://localhost:11434/api/tags',timeout=1.5).ok
    except Exception: return False

def reply(message,profile,analysis,history=None,model='qwen2.5:3b'):
    system=('You are the conversational interface for a financial education and planning prototype for India. '
    'Never invent market prices, returns, tax calculations or allocations. Use only the supplied computed results. '
    'Do not execute trades or guarantee returns. If data is proxy/assumption, disclose it. '
    'Ask one natural follow-up question if a required financial input is missing. Keep explanations clear and concise. '
    'This is not regulated investment advice.')
    if not ollama_available():
        return deterministic_reply(message,profile,analysis)
    msgs=[{'role':'system','content':system+'\nPROFILE: '+str(profile)+'\nCOMPUTED ENGINE OUTPUT: '+str(analysis)}]
    for h in (history or [])[-8:]: msgs.append({'role':h['role'],'content':h['content']})
    msgs.append({'role':'user','content':message})
    try:
        r=requests.post(OLLAMA,json={'model':model,'messages':msgs,'stream':False,'options':{'temperature':0.2}},timeout=90); r.raise_for_status()
        return r.json()['message']['content']
    except Exception: return deterministic_reply(message,profile,analysis)

def deterministic_reply(message,profile,analysis):
    m=message.lower()
    if not analysis: return 'I can help build your financial profile. Tell me about your income, monthly expenses, existing investments, debt, and the goals you want your money to fund.'
    if any(k in m for k in ['risk','volatile','loss','safe']):
        return f"Your current risk score is {profile.get('risk_score','not yet assessed')}/100. The engine estimates portfolio annualised volatility at {analysis.get('volatility',0):.1%}. Risk tolerance and risk capacity are assessed separately; this is a planning estimate, not a guarantee against losses."
    if any(k in m for k in ['tax','80c','capital gain','harvest']):
        return 'The tax module distinguishes equity short-term and long-term gains, estimates tax on proposed disposals, and checks whether an 80C deduction is available under the selected regime. Tax treatment depends on the exact instrument, holding period and applicable tax-year rules.'
    if any(k in m for k in ['goal','house','retire','corpus','sip']):
        g=analysis.get('goal_simulation',{})
        return f"Based on the current assumptions, the simulated probability of reaching your stated goal is {g.get('goal_probability',0):.1%}. The median simulated corpus is ₹{g.get('median',0):,.0f}. This is scenario analysis, not a forecast. We can change your monthly contribution, horizon or target to test feasibility."
    alloc=analysis.get('allocation',[])
    lines=[f"The current model estimates annual return of {analysis.get('expected_return',0):.1%} and annualised volatility of {analysis.get('volatility',0):.1%}." ]
    for a in alloc[:5]: lines.append(f"{a['asset']}: {a['weight']:.1%}")
    lines.append('The two bundled price histories are short, and several asset-class inputs remain explicitly labelled priors. Treat the allocation as a research prototype, not a live investment instruction.')
    return '\n'.join(lines)
