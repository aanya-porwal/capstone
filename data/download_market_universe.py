"""Optional free data downloader. Yahoo Finance chart endpoint; saves raw adjusted-close histories.
Run: python data/download_market_universe.py --years 10
Provider availability and symbols can change; failed downloads are reported, never imputed silently.
"""
import argparse, json, time
from pathlib import Path
import requests, pandas as pd
OUT=Path(__file__).resolve().parent/'prices'; OUT.mkdir(exist_ok=True)
TICKERS={
 'Nifty 50 ETF':'NIFTYBEES.NS', 'Nifty Next 50 ETF':'JUNIORBEES.NS',
 'Nifty Midcap ETF':'MID150BEES.NS', 'Gold ETF':'GOLDBEES.NS',
 'Liquid Fund proxy':'LIQUIDBEES.NS', 'Gilt ETF proxy':'GILT5YBEES.NS',
 'S&P 500 ETF proxy':'MON100.NS',
 'Nifty 500 ETF proxy':'MAFANG.NS',
 'Nifty Bank ETF proxy':'BANKBEES.NS',
 'Bharat Bond ETF proxy':'BHARATBOND.NS'
}
def fetch(symbol,years):
    period2=int(time.time()); period1=period2-years*365*24*3600
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    r=requests.get(url,params={'period1':period1,'period2':period2,'interval':'1d','events':'div,splits'},headers={'User-Agent':'Mozilla/5.0'},timeout=25); r.raise_for_status(); j=r.json()['chart']
    if j.get('error') or not j.get('result'): raise RuntimeError(str(j.get('error')))
    q=j['result'][0]; adj=q.get('indicators',{}).get('adjclose',[{}])[0].get('adjclose'); close=q['indicators']['quote'][0].get('close')
    values=adj or close; dates=pd.to_datetime(q['timestamp'],unit='s').date
    return pd.DataFrame({'Date':dates,'close':values}).dropna()
def main():
    p=argparse.ArgumentParser(); p.add_argument('--years',type=int,default=10); a=p.parse_args(); report={}
    for name,ticker in TICKERS.items():
        try:
            d=fetch(ticker,a.years); safe=name.lower().replace(' ','_'); d.to_csv(OUT/f'{safe}.csv',index=False)
            report[name]={'ticker':ticker,'rows':len(d),'start':str(d.Date.min()),'end':str(d.Date.max()),'status':'downloaded','note':'Adjusted close when provider supplied it; ETF price/NAV proxy, not index TRI.'}
            print(name,report[name])
        except Exception as e: report[name]={'ticker':ticker,'status':'failed','error':str(e)}; print('FAILED',name,e)
    (OUT/'download_manifest.json').write_text(json.dumps(report,indent=2))
if __name__=='__main__': main()
