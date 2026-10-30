"""Illustrative India tax-aware planning. Rules are configurable and must be verified for the applicable tax year."""
from dataclasses import dataclass

RULES={'tax_year':'FY 2026-27','equity_ltcg_rate':0.125,'equity_stcg_rate':0.20,'equity_ltcg_exemption':125000,'cess_rate':0.04,'old_regime_80c_cap':150000,'elss_lockin_years':3}

def equity_gain_tax(realised_gain, holding_months, regime='new', other_112a_ltcg=0.0):
    gain=max(0,float(realised_gain)); tax=0.0
    if holding_months>=12:
        taxable=max(0,gain+max(0,other_112a_ltcg)-RULES['equity_ltcg_exemption'])
        tax=taxable*RULES['equity_ltcg_rate']
    else: tax=gain*RULES['equity_stcg_rate']
    return {'gain':gain,'estimated_tax_before_cess':tax,'cess':tax*RULES['cess_rate'],'estimated_tax':tax*(1+RULES['cess_rate']),'holding_period_months':holding_months,'rule_basis':RULES['tax_year']}

def tax_aware_sell_lots(lots, cash_needed, tax_rate_other=0.30):
    """Select lots to raise cash while minimising estimated tax; FIFO is not assumed."""
    remaining=float(cash_needed); chosen=[]; tax_total=0.0
    for lot in sorted(lots,key=lambda x:(max(0,x['gain_per_unit'])* (0.125 if x['holding_months']>=12 else .20),-x['holding_months'])):
        units=min(float(lot['units']),remaining/max(float(lot['price']),1e-9))
        if units<=0: continue
        proceeds=units*float(lot['price']); gain=units*float(lot['gain_per_unit'])
        tax=equity_gain_tax(gain,int(lot['holding_months']))['estimated_tax']
        chosen.append({'lot':lot.get('name','lot'),'units_sold':units,'proceeds':proceeds,'gain':gain,'estimated_tax':tax})
        remaining-=proceeds; tax_total+=tax
        if remaining<=0: break
    return {'sales':chosen,'raised':cash_needed-max(remaining,0),'shortfall':max(remaining,0),'estimated_tax':tax_total,'warning':'Illustrative lot-selection logic; actual FIFO, STT, fund classification, exemptions and tax-year law must be verified before use.'}

def compare_80c(regime, existing_eligible, proposed_eligible):
    if regime=='new': return {'eligible_additional':0,'message':'Section 80C deduction generally unavailable under the default new regime; do not buy a tax-saving product solely for this deduction.'}
    remaining=max(0,RULES['old_regime_80c_cap']-float(existing_eligible))
    return {'eligible_additional':min(remaining,float(proposed_eligible)),'remaining_limit':remaining,'message':'Illustrative Section 80C headroom under old-regime assumptions; verify individual eligibility.'}

def tax_aware_rebalance(current_values, target_weights, lots_by_asset=None, drift_threshold=0.05):
    """Suggest drift-band trades and estimate tax on sells using supplied acquisition lots.
    current_values are current market values by asset; target_weights sum to one.
    No trades are executed.
    """
    lots_by_asset=lots_by_asset or {}
    total=sum(max(0,float(v)) for v in current_values.values())
    if total<=0: return {'trades':[],'estimated_tax':0.0,'message':'No current holdings supplied.'}
    if abs(sum(target_weights.values())-1)>1e-5: raise ValueError('Target weights must sum to one.')
    trades=[]; tax=0.0; tax_known=True
    for asset,target_w in target_weights.items():
        current=float(current_values.get(asset,0)); target=total*float(target_w); drift=current/total-float(target_w)
        if abs(drift)<drift_threshold: continue
        delta=target-current
        if delta>0: trades.append({'asset':asset,'action':'BUY','estimated_amount':delta,'drift':drift,'estimated_tax':0.0})
        else:
            needed=-delta; lot_result=tax_aware_sell_lots(lots_by_asset.get(asset,[]),needed) if lots_by_asset.get(asset) else {'raised':0,'shortfall':needed,'estimated_tax':None,'sales':[],'warning':'No acquisition lots supplied; tax estimate unavailable.'}
            if lot_result['estimated_tax'] is None: tax_known=False
            else: tax+=lot_result['estimated_tax']
            trades.append({'asset':asset,'action':'SELL','estimated_amount':needed,'drift':drift,'estimated_tax':lot_result['estimated_tax'],'lot_selection':lot_result})
    return {'trades':trades,'estimated_tax':tax if tax_known else None,'drift_threshold':drift_threshold,'message':'Illustrative drift-band rebalance. Actual execution requires verified holdings, acquisition lots, exit loads, transaction costs and tax rules.'}
