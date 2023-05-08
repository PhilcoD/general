import pandas as pd
import numpy as np
import apps.salm.logic.Input_tests as input
from scipy.optimize import fsolve

# import Input_tests as input

###############################


def get_curves(curve_categories: list, curves: pd.DataFrame, curves_map: dict, error_msg: list):
    
    """
    Extracts different curve types from ESG curves simulation output. Ouputs dictionary with curve types as keys
    
    Args:
    curve_categories : list
        list of curve type strings
    curves : dataframe 
        dataframe of ESG simulation output
    curves_map : dict
        mapping dictionary for ESG simulations
    error_msg : list
        list of error messages (strings)
        
    Output:
    curves_dict : dict
        dictionary with categories as specified. Each key has dataframe of all esg simulation data of that key type
        
    """
    
    curves_dict = dict()
    missing_categories = []
    for category in curve_categories:
        if category not in curves_map.keys():
            missing_categories.append(category)
            continue
        curves_dict[category] = curves[["Trial", "Timestep"] + [x["esg_name"] for x in curves_map[category]]]
    error_msg.append(f"No mapping in mapping file for: {missing_categories}")
    return curves_dict, error_msg


def forward_spot_curves(forward_categories: list, spot_categories: list, curves_dict: dict, error_msg):

    """
    
    Calculates forward and spot curves for selected curve types. Spot curves only calculated if forward curve calculated for same curve type.
    
    Args:
        forward_categories : list
            list of curve types
        spot_categories : list
            list of curve types
        curves_dict : dict
            dicionary with curve types as keys. Each dataframe Trial column,  Timestep column, followed by n curves columns.
        
    Output:
        all_curves_dict : dict
            dictionary of dictionarys with dataframes. df[curve_type][forward/spot]
        
    """
    
    all_curves_dict = dict()
    for category in forward_categories:
        trial_timestep = curves_dict[category][["Trial", "Timestep"]]
        curve = curves_dict[category].drop(columns=["Trial", "Timestep"])
        forward_curve = ((1 + curve.T).pow(list(range(1, curve.shape[1] + 1)), axis=0) / (
                1 + curve.T.shift(1, fill_value=0)).pow(list(range(0, curve.shape[1])), axis=0) - 1).T
        forward_curve.columns = range(1, curve.shape[1] + 1)
        forward_curve[list(range(forward_curve.shape[1], 101))] = pd.concat(
            [forward_curve[forward_curve.shape[1]]] * (101 - forward_curve.shape[1]), axis=1, ignore_index=True)

        store_dict = dict()
        store_dict["forward"] = trial_timestep.join(forward_curve)

        if category in spot_categories:
            spot_curve = (1 + forward_curve).cumprod(axis=1).pow(1 / np.array(range(1, 101)), axis=1) - 1
            store_dict["spot"] = trial_timestep.join(spot_curve)
        all_curves_dict[category] = store_dict

    return all_curves_dict


def fx_curves_return(curves_dict: dict, error_msg):
    
    """
    
    Calculates fx year on year rate. Takes [CUR]/GBP and converts to GBP/[CUR]
    
    Args:
        curves_dict : dict
            dicionary with curve types as keys. Each dataframe Trial column,  Timestep column, followed by n curves columns.
        error_msg : list
            list of error messages (strings)
        
    Output:
        rates : Dataframe
            dataframe of year on year rates. Columns: Trial, Timestep, n x exchange rate columns 
        
    """

    trial_timestep = curves_dict["fx_rates"][["Trial", "Timestep"]]
    rates = curves_dict["fx_rates"].drop(columns=["Trial", "Timestep"])
    rates = 1 / (rates.pct_change() + 1)
    rates = trial_timestep.join(rates)
    rates.loc[rates["Timestep"] == 0, rates.columns[2:]] = 1
    return rates


def discount_curve(curve_add, base_curve_name: str, all_curves: dict):
    
    """
    
    Calculates 100 year discount rate curve at each trial and timestep
    
    Args:
        curves_add : Series
            Series of length 100, of values to add to base curve at each year
        base_curve_name : str
            name of curve to use as base for discount rate. Must be a key within all_curves dictionary
        
    Output:
        all_curves : dict
            dictionary of dictionarys with dataframes. df[curve_type][forward/spot]
        
    """
        
    trial_timestep = all_curves[base_curve_name]["forward"][["Trial", "Timestep"]]
    base_curve = all_curves[base_curve_name]["forward"].drop(columns=["Trial", "Timestep"])
    discount_rate_forward = base_curve + curve_add.values
    discount_curve = 1 / (1 + discount_rate_forward).cumprod(axis=1)
    discount_curve = trial_timestep.join(discount_curve)
    return discount_curve

##### Code to create liability cashflow proxy if not provided

def liability_cashflows_duration(cashflows, discount_rates_margin, discount_rates_base, all_curves):
    """

    Calculates duration of set of cashflows on year one/LDI basis.
    Used mainly for creation of liability cashflow proxy

    Args:
        cashflows : Dataframe
            1 x 100 Dataframe, of cashflows
        discount_rates_margin : Dataframe
            n x 100 Dataframe of margins to add to curves to calculate discount rates
        discount_rates_base : Series
            Series of curve type names that feature ESG simulations

    Output:
        duration: float
        
    """

    curve_add = discount_rates_margin.loc[0]
    discount_rate_base_map = {"Gilt": "gilts", "Swap": "swaps", "Credit": "credit"}

    curve_base = discount_rate_base_map[discount_rates_base.loc[0]]

    discount_rate = discount_curve(curve_add, curve_base, all_curves)
    discount_rate_t0 = discount_rate[(discount_rate["Trial"] == 1) & (discount_rate["Timestep"] == 0)].drop(
        columns=["Trial", "Timestep"]).squeeze()
    duration = ((cashflows.index * discount_rate_t0 * cashflows).sum()) / ((discount_rate_t0 * cashflows).sum())

    return duration


def sample_cashflow_duration(percentage_low, sample_cflows, discount_rates_margin, discount_rates_base, all_curves):
    """
    Calculates duration mixed set of sample cashflows

    Args:
        cashflows : Dataframe
            2 x 100 Dataframe, of nominal and real cashflows


    Output:
        duration: float
    """
    combined_cflow = percentage_low * sample_cflows['low_duration'] + (1 - percentage_low) * sample_cflows[
        'high_duration']
    return liability_cashflows_duration(combined_cflow, discount_rates_margin, discount_rates_base, all_curves)


def opt_duration(i, sample_cflows, discount_rates_margin, discount_rates_base, duration_target, all_curves):
    """
    Purely a function created to run through optimisation when creating sample
    """
    return sample_cashflow_duration(i, sample_cflows, discount_rates_margin, discount_rates_base,
                                    all_curves) - duration_target


def proxy_cashflows(duration, sample_cflows, inf_link, discount_rates_margin, discount_rates_base, all_curves):
    """
    """
    percent_low = fsolve(opt_duration, 1,
                         args=(sample_cflows, discount_rates_margin, discount_rates_base, duration, all_curves))
    combined_cflow = percent_low * sample_cflows['low_duration'] + (1 - percent_low) * sample_cflows['high_duration']
    cflows = pd.DataFrame(index=range(1, 101))
    cflows.index.name = "Year"
    cflows['real'] = inf_link * combined_cflow
    cflows['nom'] = (1 - inf_link) * combined_cflow
    return cflows.T

#### liability code


def liability_cashflows_scaling(liability_input, liability_cashflows, discount_rates_margin, discount_rates_base,
                                all_curves):
    
    """
    
    Scales the nominal and real cashflows in input to match the PV of liabilities also inputted. Calculates the discount rate curve requested and subsequently the PV of liability inputs. Scales based on this figure vs the PV inputted.
    
    Args:
        liability_input : int
            liability PV 
        liability_cashflows : Dataframe
            2 x 100 Dataframe, of nominal and real cashflows
        discount_rates_margin : Dataframe
            n x 100 Dataframe of margins to add to curves to calculate discount rates
        discount_rates_base : Series
            Series of curve type names that feature ESG simulations
        all_curves : 
            dictionary of dictionarys with dataframes. df[curve_type][forward/spot]
        
    Output:
        liability_cashflows_scaled : 
            2 x 100 Dataframe of scaled nominal and real liabilities
        
    """
    
    liability_real_input = liability_cashflows.T.iloc[:, 0]
    liability_nominal_input = liability_cashflows.T.iloc[:, 1]
    inflation_spot_t0 = all_curves["inflation"]["spot"][
        (all_curves["inflation"]["spot"]["Trial"] == 1) & (all_curves["inflation"]["spot"]["Timestep"] == 0)].drop(
        columns=["Trial", "Timestep"]).squeeze()

    cashflows = liability_real_input * (1 + inflation_spot_t0).pow(np.array(range(1, 101))) + liability_nominal_input
    curve_add = discount_rates_margin.loc[0]

    discount_rate_base_map = {"Gilt": "gilts", "Swap": "swaps", "Credit": "credit"}

    curve_base = discount_rate_base_map[discount_rates_base.loc[0]]

    discount_rate = discount_curve(curve_add, curve_base, all_curves)
    discount_rate_t0 = discount_rate[(discount_rate["Trial"] == 1) & (discount_rate["Timestep"] == 0)].drop(
        columns=["Trial", "Timestep"]).squeeze()
    one_year_pv = (discount_rate_t0 * cashflows).sum()
    scaling = liability_input / one_year_pv
    liability_cashflows_scaled = liability_cashflows * scaling

    return liability_cashflows_scaled


def nominal_cashflows(liability_cashflows, simulation_years=20):
    
    """
    
    Calculates the 100 year nominal cashflows at each year
    
    Args:
        liability_cashflows : int
            2 x 100 Dataframe of scaled nominal and real liabilities
        simulation_years : int (20)
            number of years in each trial
       
    Output:
        nominal_cashflows : Dataframe
            100 x n (n is simulation years) Dataframe of cashflows
        
    """
    
    cashflow_list = [list(liability_cashflows.iloc[1, i:]) + [0] * i for i in range(simulation_years + 1)]
    nominal_cashflows = pd.DataFrame(cashflow_list).T
    nominal_cashflows.index = range(1, 101)
    nominal_cashflows.index.name = "Year"
    nominal_cashflows.columns = [f"Year {str(i)}" for i in range(21)]
    return nominal_cashflows


def inflation_cashflows(liability_cashflows, esg_curves, all_curves, trial_num, inf_add=0, simulation_years=20):
        
    """
    
    Calculates the 100 year inflation cashflows at each trial and timestep based on realised inflation ESG simulation and real liability cashflows
    
    Args:
        liability_cashflows : int
            2 x 100 Dataframe of scaled nominal and real liabilities
        esg_curves : dict
            dictionary with categories as esg curve types. Each key has dataframe of all esg simulation data of that key type
        all_curves : dict
            dictionary of dictionarys with dataframes of forward and spot curves for curve types. df[curve_type][forward/spot]
        trial_num : int
            number of trials in ESG simulation data
        inf_add : int (0)
            margin to add to inflation curve
        simulation_years : int (20)
            number of years in each trial
       
    Output:
        real_inflated_cashflows : Dataframe
            n x 100 (n is total number of trials and timesteps) Dataframe of inflated real cashflows
        
    """
    
    cashflow_list = [list(liability_cashflows.iloc[0, i:]) + [0] * i for i in range(simulation_years + 1)] * trial_num
    real_cashflows = pd.DataFrame(cashflow_list)
    realised_inflation = esg_curves["realised_inflation"]
    realised_inflation = realised_inflation.drop(columns=["Trial", "Timestep"])
    realised_inflation_cashflows = pd.DataFrame(real_cashflows.to_numpy() * realised_inflation.to_numpy())
    inflation_factors = (1 + all_curves["inflation"]["spot"].drop(columns=["Trial", "Timestep"]) + inf_add).pow(
        np.array(range(1, 101)))
    inflation_factors.columns = range(100)
    real_inflated_cashflows = realised_inflation_cashflows.mul(inflation_factors)

    return real_inflated_cashflows


def realised_cashflows(nominal_cashflows, inflation_cashflows, esg_curves, all_curves, trial_num):
    realised_inflation = esg_curves["realised_inflation"]
    trial_timestep = realised_inflation[["Trial", "Timestep"]]

    previous_year_inflation_cashflows = inflation_cashflows.shift()
    previous_year_inflation_cashflows = trial_timestep.join(previous_year_inflation_cashflows)
    previous_year_inflation_cashflows.loc[
        previous_year_inflation_cashflows["Timestep"] == 0, previous_year_inflation_cashflows.columns[2:]] = 0
    previous_year_inflation_cashflows = previous_year_inflation_cashflows.iloc[:, :3]

    realised_inflation_1_year_shift = realised_inflation.drop(columns=["Trial", "Timestep"]).shift()
    realised_inflation_1_year_shift = trial_timestep.join(realised_inflation_1_year_shift)
    realised_inflation_1_year_shift.loc[
        realised_inflation_1_year_shift["Timestep"] == 0, realised_inflation_1_year_shift.columns[2:]] = 1
    realised_inflation_1_year_shift = trial_timestep.join(
        pd.DataFrame(realised_inflation.iloc[:, 2] / realised_inflation_1_year_shift.iloc[:, 2]))

    inflation_spot_curve = all_curves["inflation"]["spot"]
    inflation_spot_curve_1_year_shift = inflation_spot_curve.drop(columns=["Trial", "Timestep"]).shift()
    inflation_spot_curve_1_year_shift = trial_timestep.join(inflation_spot_curve_1_year_shift)
    inflation_spot_curve_1_year_shift.loc[
        inflation_spot_curve_1_year_shift["Timestep"] == 0, inflation_spot_curve_1_year_shift.columns[2:]] = 0
    inflation_spot_curve_1_year_shift = trial_timestep.join(
        pd.DataFrame(1 / (1 + inflation_spot_curve_1_year_shift.iloc[:, 2])))

    previous_year_nominal_cashflows = pd.DataFrame(list(nominal_cashflows.T.shift(fill_value=0).iloc[:, 0]) * trial_num)

    cashflows = pd.DataFrame(previous_year_inflation_cashflows.iloc[:, 2] * realised_inflation_1_year_shift.iloc[:,
                                                                            2] * inflation_spot_curve_1_year_shift.iloc[
                                                                                 :, 2])
    realised_cashflows = trial_timestep.join(cashflows + previous_year_nominal_cashflows)

    return realised_cashflows


def cashflows_present_value(cashflows, discount_rates_margin, discount_rates_base, all_curves, trial_timestep,
                            pv_add=0):
    liability_pv_dict = dict()
    cashflows = cashflows.drop(columns=["Trial", "Timestep"])

    for i in range(discount_rates_margin.shape[0]):
        output = trial_timestep
        discount_rate_base_map = {"Gilt": "gilts", "Swap": "swaps", "Credit": "credit"}
        curve_add = discount_rates_margin.loc[i]
        curve_base = discount_rate_base_map[discount_rates_base.loc[i]]

        discount_rate = discount_curve(curve_add + pv_add, curve_base, all_curves).drop(columns=["Trial", "Timestep"])
        cashflows.columns = discount_rate.columns
        pv = (cashflows * discount_rate).sum(axis=1)
        output = output.assign(pv=pv)
        liability_pv_dict["basis_" + str(i)] = output

    return liability_pv_dict


def present_value_differences(dict1, dict2, trial_timestep):
    diff_dict = dict.fromkeys(dict1.keys())
    for i in dict1.keys():
        diff = dict1[i]["pv"] - dict2[i]["pv"]
        diff_dict[i] = trial_timestep.join(diff)
    return diff_dict


def inflation_cashflows_previous_year_inflation(inflation_cashflows, trial_timestep):
    inflation_cashflows_prev_year_inf = inflation_cashflows.shift().T.shift(-1).T
    inflation_cashflows_prev_year_inf = trial_timestep.join(inflation_cashflows_prev_year_inf)
    inflation_cashflows = trial_timestep.join(inflation_cashflows)

    inflation_cashflows_prev_year_inf.loc[
        inflation_cashflows_prev_year_inf["Timestep"] == 0, inflation_cashflows_prev_year_inf.columns[2:]] = \
        inflation_cashflows.loc[inflation_cashflows["Timestep"] == 0, inflation_cashflows.columns[2:]]

    return inflation_cashflows_prev_year_inf

def ldi_impact(liability_pv, liability_pv_prev_year_inf, realised_cashflows, trial_timestep):
    hedging_basis = list(liability_pv.keys())[0]
    liability_pv_old = liability_pv[hedging_basis]
    liability_pv_old = liability_pv_old.shift()
    liability_pv_old = trial_timestep.join(liability_pv_old["pv"])
    liability_pv_old.loc[liability_pv_old["Timestep"]==0, ["pv"]] = 0
    
    ldi_impact = liability_pv_prev_year_inf[hedging_basis]["pv"] - liability_pv_old["pv"] + realised_cashflows.iloc[:,2]
    ldi_impact = trial_timestep.join(pd.DataFrame(ldi_impact, columns = ["interest"]))
    ldi_impact.loc[ldi_impact["Timestep"]==0, ["interest"]] = 0
    ldi_impact["inflation"] = liability_pv[hedging_basis]["pv"] - liability_pv_prev_year_inf[hedging_basis]["pv"]
    return ldi_impact

def hedging_ldi_impact(ldi_impacts, hedging_ratios, trial_num, trial_timestep):
    
    ldi_hold = ldi_impacts.drop(columns=["Trial", "Timestep"])
    ratios = hedging_ratios.T
    ratios = pd.DataFrame(list(ratios.values)*trial_num)
    ratios.columns = ldi_hold.columns
    
    hedging_ldi_impact = (ldi_hold * ratios).sum(axis=1)
    hedging_ldi_impact = trial_timestep.join(pd.DataFrame(hedging_ldi_impact, columns=["hedging_ldi_impact"]))
    return hedging_ldi_impact

def asset_year_on_year_returns(returns, trial_timestep):
    year_on_year_returns = returns.drop(columns=["Trial"])
    year_on_year_returns = trial_timestep.join(year_on_year_returns.pct_change())
    year_on_year_returns.loc[year_on_year_returns["Timestep"]==0, year_on_year_returns.columns[2:]] = 0
    year_on_year_returns.iloc[:,2:] = year_on_year_returns.iloc[:,2:] + 1
    
    return year_on_year_returns

#new_function
def asset_year_on_year_returns_with_shocks(returns, trial_timestep,asset_shocks,trial_num):
    """
    Function to calculate percantage year on year returns including inputted asset shocks from input template.
    Required as esg data produces
    """
    year_on_year_returns = returns.drop(columns=["Trial"])
    asset_shocks_df =  asset_shocks.loc[:, ~asset_shocks.columns.isin(
        ['Asset class name ESG', 'Meaningful name', 'Prev model name', 'Assets Filter',
         'Classification Flag', 'Subcategory', 'Index linked?',
         'Use for hedging', 'Currency', 'Currency Hedge'])].T
    asset_shocks_df.columns= asset_shocks["Asset class name ESG"]
    asset_shocks_df=pd.concat([asset_shocks_df]*trial_num, ignore_index=True)
    year_on_year_returns = trial_timestep.join(year_on_year_returns.pct_change())
    year_on_year_returns.loc[year_on_year_returns["Timestep"]==0, year_on_year_returns.columns[2:]] = 0
    year_on_year_returns.iloc[:,2:] = year_on_year_returns.iloc[:,2:] + 1

    return year_on_year_returns

def year_on_year_returns_gbp(year_on_year_returns, fx_returns, curves_map, trial_timestep):
    year_on_year_returns = year_on_year_returns.drop(columns=["Trial","Timestep"])
    ordered_currencies = []
    for asset_name in year_on_year_returns.columns:
        for i in curves_map["returns"]:
            if i["esg_name"] == asset_name:
                ordered_currencies.append(i["base_currency"])
                
    USD_fx_rate = list(fx_returns["ESG.Economies.USD.ExchangeRate.NominalValue"].values)
    EUR_fx_rate = list(fx_returns["ESG.Economies.EUR.ExchangeRate.NominalValue"].values)
    GBP_fx_rate = [1]*len(USD_fx_rate)
    
    fx_rate_list = []
    
    for cur in ordered_currencies:
        
        if cur == "USD":
            fx_rate_list.append(USD_fx_rate)
        elif cur == "EUR":
            fx_rate_list.append(EUR_fx_rate)
        else:
            fx_rate_list.append(GBP_fx_rate)
    
    fx_rate_df = pd.DataFrame(fx_rate_list, index=year_on_year_returns.columns)
    fx_rate_df = fx_rate_df.transpose()
    
    year_on_year_returns_gbp = trial_timestep.join(year_on_year_returns*fx_rate_df - 1)
            
    return year_on_year_returns_gbp

def scheme_returns_non_hdg(year_on_year_returns_gbp, asset_allocation, trial_timestep, trial_num):
    year_on_year_returns_gbp = year_on_year_returns_gbp.drop(columns=["Trial","Timestep"])

    asset_allocation_df = pd.DataFrame(list(asset_allocation.values)*trial_num, columns=year_on_year_returns_gbp.columns)
    
    scheme_return_df = asset_allocation_df*year_on_year_returns_gbp
    scheme_return = pd.DataFrame(scheme_return_df.sum(axis=1)) + 1
    scheme_return = trial_timestep.join(scheme_return.shift(-1, fill_value=1))
    scheme_return.loc[scheme_return["Timestep"]==20, scheme_return.columns[2:]] = 1
    
    return scheme_return

def assets_ldi_perfect(starting_asset, hedging_ldi_impacts, returns_non_hdg, realised_cashflows, contributions, trial_timestep, trial_num):
    
    returns_non_hdg_wide = returns_non_hdg.pivot(index="Timestep", columns="Trial")
    hedging_ldi_impact_wide = hedging_ldi_impacts.pivot(index="Timestep", columns="Trial")
    realised_cashflows_wide = realised_cashflows.pivot(index="Timestep", columns="Trial")
    contributions_wide = trial_timestep.join(pd.DataFrame((list(contributions.values)+[0])*trial_num)).pivot(index="Timestep", columns="Trial")
    
    hedging_ldi_impact_wide.columns = realised_cashflows_wide.columns
    
    assets_wide = pd.DataFrame(index = realised_cashflows_wide.index, columns = realised_cashflows_wide.columns)
    assets_wide.loc[0] = [starting_asset] * trial_num
    
    for i in range(assets_wide.shape[0]-1):
        assets_wide.loc[i+1] = assets_wide.loc[i]*returns_non_hdg_wide.loc[i]
        assets_wide.loc[i+1] = assets_wide.loc[i+1] - realised_cashflows_wide.loc[i+1] + hedging_ldi_impact_wide.loc[i+1] + contributions_wide.loc[i]
    
    assets = trial_timestep.join(assets_wide.melt(value_name="assets")["assets"])
    
    return assets

def output_creation(liability_pv, assets, trial_timestep):
    liability_pv_df = pd.DataFrame()
    for basis in liability_pv.keys():
        liability_pv_df[basis] = liability_pv[basis]["pv"]

    surplus_df = liability_pv_df.subtract(assets["assets"], axis=0)*-1
    funding_level_df = 1/(liability_pv_df.divide(assets["assets"], axis=0))

    liability_pv_df.columns = ['Liabilities basis 1', 'Liabilities basis 2', 'Liabilities basis 3']
    surplus_df.columns = ['Surplus basis 1', 'Surplus basis 2', 'Surplus basis 3']
    funding_level_df.columns = ['Funding level basis 1','Funding level basis 2', 'Funding level basis 3']

    output_df = trial_timestep.join([liability_pv_df, assets["assets"], surplus_df, funding_level_df])
    object_cols = output_df.select_dtypes(include=["object"]).columns
    output_df[object_cols] = output_df[object_cols].apply(pd.to_numeric, downcast='float', errors='coerce')
    
    return output_df

def output_creation_v2(liability_pv, assets, trial_timestep):
    liability_pv_df = pd.DataFrame()
    for basis in liability_pv.keys():
        liability_pv_df[basis] = liability_pv[basis]["pv"]

    surplus_df = liability_pv_df.subtract(assets["assets"], axis=0)*-1
    funding_level_df = 1/(liability_pv_df.divide(assets["assets"], axis=0))

    liability_pv_df.columns = ['Liabilities ' + basis for basis in list(liability_pv.keys())]
    surplus_df.columns = ['Surplus ' + basis for basis in list(liability_pv.keys())]
    funding_level_df.columns = ['Funding_level_' + basis for basis in list(liability_pv.keys())]

    output_df = trial_timestep.join([liability_pv_df, assets["assets"], surplus_df, funding_level_df])
    object_cols = output_df.select_dtypes(include=["object"]).columns
    output_df[object_cols] = output_df[object_cols].apply(pd.to_numeric, downcast='float', errors='coerce')

    return output_df

def ldi_leverage(hedging_ratios, liability_pv, ldi_allocation, assets, trial_num):

    pv_hold = pd.DataFrame(columns=list(liability_pv.keys()))
    for key in liability_pv.keys():
        pv_hold[key] = liability_pv[key]["pv"]
    
    ratios = pd.DataFrame(list(hedging_ratios.T.values)*trial_num, columns=hedging_ratios.index)
    ratios.columns.name = None
    assets_to_hdg = pv_hold.multiply(ratios["Interest"], axis="index")

    ldi_allocation_long = pd.Series([float(x) for x in ldi_allocation.values]*trial_num)
    ldi_allocation_actual = assets["assets"]*ldi_allocation_long

    leverage = assets_to_hdg.divide(ldi_allocation_actual, axis="index")
    
    return leverage



## Inputs from csv files to alm function

def discount_rates_margin(Discount_rate_curves_input):
    return Discount_rate_curves_input.loc[:, ~Discount_rate_curves_input.columns.isin(['Name', 'Base_curve'])]


def discount_rates_names(Discount_rate_curves_input):
    """
    Takes DR csv file and outputs the names.
    """
    return Discount_rate_curves_input.loc[:, 'Name']


def discount_rates_base(Discount_rate_curves_input):
    """
    Takes DR csv file and outputs the base curves that are used for liability discount rates. E.g. Swaps/gilts or corp bonds
    """
    return Discount_rate_curves_input.loc[:, 'Base_curve']


def returns(asset_class_list, ESG_returns):
    """
    Outputs returns for all asset classes by year and trial in form for ALM function
    """
    names = asset_class_list["Asset class name ESG"].iloc[:-1].tolist()  # assumes LDI is final row
    names.insert(0, 'Trial')
    return ESG_returns[names]


def non_LDI_asset_allocations(asset_class_list):
    """
    Assumes final row is LDI,
    outputs only allocations by class and year of projection
    """
    return asset_class_list.loc[:, ~asset_class_list.columns.isin(
        ['Asset class name ESG', 'Meaningful name', 'Prev model name', 'Assets Filter',
         'Classification Flag', 'Subcategory', 'Index linked?',
         'Use for hedging', 'Currency', 'Currency Hedge'])][
           :-1].T  # this assumes final row is LDI - need to think how inputs actually will work at some point


def asset_currencies(asset_class_list):
    return asset_class_list[['Currency']]


def LDI_allocations(asset_class_list):
    LDI = asset_class_list[asset_class_list['Meaningful name'] == 'LDI']
    LDI = LDI.loc[:, ~LDI.columns.isin(['Asset class name ESG', 'Meaningful name', 'Prev model name', 'Assets Filter',
                                        'Classification Flag', 'Subcategory', 'Index linked?',
                                        'Use for hedging', 'Currency', 'Currency Hedge'])].T
    LDI.columns = ['LDI']
    return LDI


###latest function


def quantiles_salm(
        simulation_data: pd.DataFrame,
        quantiles_list: list,
        timestep_list: list,
):
    """
        Calculates the inputed quantiles at a timestep for each column in the dataframe
        Args:
            simulation_data: Trial column, Timestep column followed by n columns of data
            quantiles_list: list of integers for quantiles to calculate
            timestep_list: list of integers (timesteps at which quantiles calculated)
        """
    percentiles_df = pd.DataFrame(index=simulation_data.columns)
    for timestep in timestep_list:
        data_hold = (
            simulation_data[simulation_data["Timestep"] == timestep]
                .quantile(quantiles_list)
                .transpose()
        )

        data_hold.columns = [
            "Y" + str(timestep) + " " + str(quantile) + " Percentile" for quantile in quantiles_list
        ]
        percentiles_df = percentiles_df.join(data_hold)
    if "Trial" in percentiles_df.index:
        percentiles_df = percentiles_df.drop("Trial")
    if "Timestep" in percentiles_df.index:
        percentiles_df = percentiles_df.drop("Timestep")

    percentiles_df = percentiles_df.transpose()
    return percentiles_df

    ###latest function


def run_alm(
        curves: pd.DataFrame,
        returns: pd.DataFrame,
        liability_cashflows: pd.DataFrame,
        starting_asset_value: float,
        non_LDI_asset_allocation: pd.DataFrame,
        asset_currencies: pd.DataFrame,
        LDI_allocations: pd.DataFrame,
        discount_rates_margin: pd.DataFrame,
        discount_rates_base: dict,
        hedging_ratios: pd.DataFrame,
        liab_input: float,
        contributions,
        quantiles: list,
        quantiles_years: list,
        curves_map: dict,
) -> pd.DataFrame:
    """Run ALM

    args:
        curves: ESG output of curves
        returns: Relevant returns on asset classes that match allocations dataframe
        cashflows: Nominal and real cashflows
        non_LDI_asset_allocation: Dataframe with same dimensions as one trial of returns.
        LDI_allocations: LDI allocation
        discount_rates_margin: Margin above spot rate
        discount_rates_base: Maps basis name to base curve from calibration to use for discount rate e.g. Gilts,Swaps,Credit
        hedging_ratios: hedging ratios against interest and inflation
        hedging_asset_returns:
        hedging_durations:
        liab_input: start liability value
    """

    curve_categories = ["gilts", "swaps", "credit", "inflation", 'realised_inflation', 'fx_rates']
    forward_categories = ["gilts", "swaps", "credit", "inflation"]
    spot_categories = ["inflation"]
    error_msg = []

    esg_curves, error_msg = get_curves(curve_categories, curves, curves_map, error_msg)
    all_curves = forward_spot_curves(forward_categories, spot_categories, esg_curves, error_msg)
    fx_return = fx_curves_return(esg_curves, error_msg)

    trial_num = esg_curves["gilts"]["Trial"].nunique()
    trial_timestep = esg_curves["gilts"][["Trial", "Timestep"]]

    liability_cashflows_scaled = liability_cashflows_scaling(liab_input, liability_cashflows, discount_rates_margin,
                                                             discount_rates_base, all_curves)
    nominal_cashflow = nominal_cashflows(liability_cashflows_scaled)
    inflation_cashflow = inflation_cashflows(liability_cashflows_scaled, esg_curves, all_curves, trial_num)
    total_cashflows = trial_timestep.join(inflation_cashflow + pd.DataFrame(list(nominal_cashflow.T.values) * trial_num))
    realised_cashflow = realised_cashflows(nominal_cashflow, inflation_cashflow, esg_curves, all_curves, trial_num)

    liability_pv = cashflows_present_value(total_cashflows, discount_rates_margin, discount_rates_base, all_curves,
                                           trial_timestep, pv_add=0)
    liability_pv01 = cashflows_present_value(total_cashflows, discount_rates_margin, discount_rates_base, all_curves,
                                             trial_timestep, pv_add=0.0001)

    pv01_diff = present_value_differences(liability_pv01, liability_pv, trial_timestep)

    inflation_cashflow_01 = inflation_cashflows(liability_cashflows_scaled, esg_curves, all_curves, trial_num,
                                                inf_add=0.0001)
    total_cashflow_ie01 = trial_timestep.join(
        inflation_cashflow_01 + pd.DataFrame(list(nominal_cashflow.T.values) * trial_num))

    liability_ie01 = cashflows_present_value(total_cashflow_ie01, discount_rates_margin, discount_rates_base,
                                             all_curves, trial_timestep, pv_add=0)
    ie01_diff = present_value_differences(liability_ie01, liability_pv, trial_timestep)

    inflation_cashflow_prev_year_inf = inflation_cashflows_previous_year_inflation(inflation_cashflow, trial_timestep).drop(columns=["Trial","Timestep"])
    total_cashflow_prev_year_inf = inflation_cashflow_prev_year_inf + pd.DataFrame(list(nominal_cashflow.T.values)*trial_num)
    liability_pv_prev_year_inf = cashflows_present_value(trial_timestep.join(total_cashflow_prev_year_inf), discount_rates_margin, discount_rates_base, all_curves, trial_timestep)
    
    ldi_impacts = ldi_impact(liability_pv, liability_pv_prev_year_inf, realised_cashflow, trial_timestep)
    hedging_ldi_impacts = hedging_ldi_impact(ldi_impacts, hedging_ratios, trial_num, trial_timestep)
    
    year_on_year_returns = asset_year_on_year_returns(returns, trial_timestep)
    year_on_year_return_gbp = year_on_year_returns_gbp(year_on_year_returns,fx_return, curves_map, trial_timestep) 
    returns_non_hdg = scheme_returns_non_hdg(year_on_year_return_gbp, non_LDI_asset_allocation, trial_timestep, trial_num)
    assets = assets_ldi_perfect(starting_asset_value, hedging_ldi_impacts, returns_non_hdg, realised_cashflow, contributions, trial_timestep, trial_num)

    output_df = output_creation_v2(liability_pv, assets, trial_timestep)
    
    pv_output = output_df[["Trial", "Timestep", "Liabilities basis_1", "Liabilities basis_2", "Liabilities basis_3", "assets"]]
    pv_output = pv_output[(pv_output["Trial"]==1) & (pv_output["Timestep"]==0)].iloc[0,2:]
    
    df_output_quantiles = quantiles_salm(output_df, quantiles, quantiles_years)
    
    leverage = ldi_leverage(hedging_ratios, liability_pv, LDI_allocations, assets, trial_num)

    # for i in range(20):
    #     gilt_rates_1 = curves[curves["Timestep"] == i][
    #         "ESG.Economies.GBP.NominalYieldCurves.NominalYieldCurve.SpotRate(Govt, 1, 3)"].to_frame()
    #     gilt_rates_10 = curves[curves["Timestep"] == i][
    #         "ESG.Economies.GBP.NominalYieldCurves.NominalYieldCurve.SpotRate(Govt, 10, 3)"].to_frame()
    #     gilt_rates_20 = curves[curves["Timestep"] == i][
    #         "ESG.Economies.GBP.NominalYieldCurves.NominalYieldCurve.SpotRate(Govt, 20, 3)"].to_frame()
    # gilt_rates = pd.DataFrame(np.concatenate([gilt_rates_1, gilt_rates_10, gilt_rates_20], axis=1))
    # gilt_rates.columns = ['1 year spot rate', '10 year spot rate', '20 year spot rate']
    return {"Backing - percentiles": df_output_quantiles, "Backing - inputs": pv_output, "Backing - leverage": leverage,}

def run_alm_from_excel_inputs(
        ESG_curves,
        ESG_returns,
        ALM_inputs_new,
        curves_map):
    """
    Runs full ALM taking the ESG curves and return files and the starting asset value.
    """
    liability_cashflows = input.extract_table_data_from_ID('ID_cashflow_and_DR',
                                                           ALM_inputs_new['Liabilities']).iloc[:, :3].set_index(
        'Year').T
    dr = input.extract_table_data_from_ID('ID_cashflow_and_DR', ALM_inputs_new['Liabilities']).iloc[:,
         6:].set_index(liability_cashflows.T.index).T
    dr.reset_index(drop=True, inplace=True)

    curves = ESG_curves
    asset_returns = returns(input.extract_table_data_from_ID('ID_strategy', ALM_inputs_new['Asset_strategy_1']),
                            ESG_returns)
    liability_cashflows = input.extract_table_data_from_ID('ID_cashflow_and_DR',
                                                           ALM_inputs_new['Liabilities']).iloc[:, :3].set_index(
        'Year').T
    starting_asset_value = input.extract_table_data_from_ID('ID_st_asset', ALM_inputs_new['Asset_strategy_1']).iloc[0][
        0]
    non_LDI_asset_allocation = non_LDI_asset_allocations(
        input.extract_table_data_from_ID('ID_strategy', ALM_inputs_new['Asset_strategy_1']))
    asset_currency = asset_currencies(
        input.extract_table_data_from_ID('ID_strategy', ALM_inputs_new['Asset_strategy_1']))
    LDI_allocation = LDI_allocations(
        input.extract_table_data_from_ID('ID_strategy', ALM_inputs_new['Asset_strategy_1']))
    discount_rates_margin = dr
    discount_rates_base = pd.DataFrame(
        input.extract_table_data_from_ID('ID_cashflow_and_DR', ALM_inputs_new['Liabilities']).iloc[:,
        6:].columns.values.tolist())[0]
    hedging_ratios = input.extract_table_data_from_ID('ID_hedge_ratios', ALM_inputs_new['Asset_strategy_1']).iloc[:,
                     9:].set_index('Rate')
    liab_input = input.extract_table_data_from_ID('ID_starting_liability_value', ALM_inputs_new['Liabilities'])[
        'Starting_liability_value'][0]
    contributions = input.extract_table_data_from_ID('ID_conts', ALM_inputs_new['Asset_strategy_1']).iloc[:,
                    1] * 10 ** 6
    quantiles = [0.005, 0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99, 0.995]
    quantiles_years = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

    output = run_alm(
        curves=curves,
        returns=asset_returns,
        liability_cashflows=liability_cashflows,
        starting_asset_value=starting_asset_value,
        non_LDI_asset_allocation=non_LDI_asset_allocation,
        asset_currencies=asset_currency,
        LDI_allocations=LDI_allocation,
        discount_rates_margin=discount_rates_margin,
        discount_rates_base=discount_rates_base,
        hedging_ratios=hedging_ratios,
        liab_input=liab_input,
        contributions=contributions,
        quantiles=quantiles,
        quantiles_years=quantiles_years,
        curves_map=curves_map,
    )
    output.update({"Asset_strategy_1": ALM_inputs_new['Asset_strategy_1'],
                   "Liabilities": ALM_inputs_new['Liabilities']})
    return output


###multistrategy run

def run_alm_mult(
        curves: pd.DataFrame,
        returns: pd.DataFrame,
        liability_cashflows: pd.DataFrame,
        starting_asset_value: float,
        non_LDI_asset_allocation: pd.DataFrame,
        asset_currencies: pd.DataFrame,
        LDI_allocations: pd.DataFrame,
        discount_rates_margin: pd.DataFrame,
        discount_rates_base: dict,
        hedging_ratios: pd.DataFrame,
        liab_input: float,
        contributions,
        quantiles: list,
        quantiles_years: list,
        curves_map: dict,
        asset_strat_num: float,
        asset_shocks: pd.DataFrame
) -> pd.DataFrame:

    curve_categories = ["gilts", "swaps", "credit", "inflation", 'realised_inflation', 'fx_rates']
    forward_categories = ["gilts", "swaps", "credit", "inflation"]
    spot_categories = ["inflation"]
    error_msg = []

    esg_curves, error_msg = get_curves(curve_categories, curves, curves_map, error_msg)
    all_curves = forward_spot_curves(forward_categories, spot_categories, esg_curves, error_msg)
    fx_return = fx_curves_return(esg_curves, error_msg)

    trial_num = esg_curves["gilts"]["Trial"].nunique()
    trial_timestep = esg_curves["gilts"][["Trial", "Timestep"]]

    liability_cashflows_scaled = liability_cashflows_scaling(liab_input, liability_cashflows, discount_rates_margin,
                                                             discount_rates_base, all_curves)
    nominal_cashflow = nominal_cashflows(liability_cashflows_scaled)
    inflation_cashflow = inflation_cashflows(liability_cashflows_scaled, esg_curves, all_curves, trial_num)
    total_cashflows = trial_timestep.join(inflation_cashflow + pd.DataFrame(list(nominal_cashflow.T.values) * trial_num))
    realised_cashflow = realised_cashflows(nominal_cashflow, inflation_cashflow, esg_curves, all_curves, trial_num)

    liability_pv = cashflows_present_value(total_cashflows, discount_rates_margin, discount_rates_base, all_curves,
                                           trial_timestep, pv_add=0)
    liability_pv01 = cashflows_present_value(total_cashflows, discount_rates_margin, discount_rates_base, all_curves,
                                             trial_timestep, pv_add=0.0001)

    pv01_diff = present_value_differences(liability_pv01, liability_pv, trial_timestep)

    inflation_cashflow_01 = inflation_cashflows(liability_cashflows_scaled, esg_curves, all_curves, trial_num,
                                                inf_add=0.0001)
    total_cashflow_ie01 = trial_timestep.join(
        inflation_cashflow_01 + pd.DataFrame(list(nominal_cashflow.T.values) * trial_num))

    liability_ie01 = cashflows_present_value(total_cashflow_ie01, discount_rates_margin, discount_rates_base,
                                             all_curves, trial_timestep, pv_add=0)
    ie01_diff = present_value_differences(liability_ie01, liability_pv, trial_timestep)

    inflation_cashflow_prev_year_inf = inflation_cashflows_previous_year_inflation(inflation_cashflow, trial_timestep).drop(columns=["Trial","Timestep"])
    total_cashflow_prev_year_inf = inflation_cashflow_prev_year_inf + pd.DataFrame(list(nominal_cashflow.T.values)*trial_num)
    liability_pv_prev_year_inf = cashflows_present_value(trial_timestep.join(total_cashflow_prev_year_inf), discount_rates_margin, discount_rates_base, all_curves, trial_timestep)
    
    ldi_impacts = ldi_impact(liability_pv, liability_pv_prev_year_inf, realised_cashflow, trial_timestep)
    hedging_ldi_impacts = hedging_ldi_impact(ldi_impacts, hedging_ratios, trial_num, trial_timestep)

    # updated funciton in below for asset shocks
    year_on_year_returns = asset_year_on_year_returns_with_shocks(returns, trial_timestep, asset_shocks,trial_num)  # asset_year_on_year_returns(returns, trial_timestep)
    year_on_year_return_gbp = year_on_year_returns_gbp(year_on_year_returns,fx_return, curves_map, trial_timestep)
    returns_non_hdg = scheme_returns_non_hdg(year_on_year_return_gbp, non_LDI_asset_allocation, trial_timestep, trial_num)
    assets = assets_ldi_perfect(starting_asset_value, hedging_ldi_impacts, returns_non_hdg, realised_cashflow, contributions, trial_timestep, trial_num)

    output_df = output_creation_v2(liability_pv, assets, trial_timestep)

    pv_output = output_df[["Trial", "Timestep", "Liabilities basis_1", "Liabilities basis_2", "Liabilities basis_3", "assets"]]
    pv_output = pv_output[(pv_output["Trial"]==1) & (pv_output["Timestep"]==0)].iloc[0,2:]

    df_output_quantiles = quantiles_salm(output_df, quantiles, quantiles_years)

    leverage = ldi_leverage(hedging_ratios, liability_pv, LDI_allocations, assets, trial_num)

    for i in range(20):
        gilt_rates_1 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.NominalYieldCurves.NominalYieldCurve.SpotRate(Govt, 1, 3)"].to_frame()
        gilt_rates_10 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.NominalYieldCurves.NominalYieldCurve.SpotRate(Govt, 10, 3)"].to_frame()
        gilt_rates_20 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.NominalYieldCurves.NominalYieldCurve.SpotRate(Govt, 20, 3)"].to_frame()
        swap_rates_1 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.NominalYieldCurves.SWAP.SpotRate(Govt, 1, 3)"].to_frame()
        swap_rates_10 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.NominalYieldCurves.SWAP.SpotRate(Govt, 10, 3)"].to_frame()
        swap_rates_20 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.NominalYieldCurves.SWAP.SpotRate(Govt, 20, 3)"].to_frame()
        credit_rates_1 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.NominalSpotRate(AA, 1, 3)"].to_frame()
        credit_rates_10 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.NominalSpotRate(AA, 10, 3)"].to_frame()
        credit_rates_20 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.NominalSpotRate(AA, 20, 3)"].to_frame()
        inf_rates_1 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.InflationRates.Inflation.SpotExpectation(1)"].to_frame()
        inf_rates_10 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.InflationRates.Inflation.SpotExpectation(10)"].to_frame()
        inf_rates_20 = curves[curves["Timestep"] == i][
            "ESG.Economies.GBP.InflationRates.Inflation.SpotExpectation(20)"].to_frame()
    rates = pd.DataFrame(np.concatenate([gilt_rates_1, gilt_rates_10, gilt_rates_20,
                                         swap_rates_1, swap_rates_10, swap_rates_20,
                                         credit_rates_1, credit_rates_10, credit_rates_20,
                                         inf_rates_1, inf_rates_10, inf_rates_20], axis=1))

    rates.columns = ['Gilt 1 year spot rate', 'Gilt 10 year spot rate', 'Gilt 20 year spot rate',
                     'Swap 1 year spot rate', 'Swap 10 year spot rate', 'Swap 20 year spot rate',
                     'Credit 1 year spot rate', 'Credit 10 year spot rate', 'Credit 20 year spot rate',
                     'RPI 1 year spot rate', 'RPI 10 year spot rate', 'RPI 20 year spot rate']

    return {"Backing - percentiles_strat_"+str(asset_strat_num): df_output_quantiles,
            "Backing - inputs_strat_"+str(asset_strat_num): pv_output,
            "Backing - leverage_strat_"+str(asset_strat_num): leverage,
            "Backing - Liabilities DR": rates}


def run_alm_from_excel_inputs_multistrat(
        ESG_curves,
        ESG_returns,
        ALM_inputs_new,
        curves_map,
        sample_cflows):
    """
    Runs full ALM taking the ESG curves and return files and the starting asset value.
    """

    liability_cashflows = input.extract_table_data_from_ID('ID_cashflow_and_DR',
                                                           ALM_inputs_new['Liabilities']).iloc[:, :3].set_index('Year').T
    dr = input.extract_table_data_from_ID('ID_cashflow_and_DR', ALM_inputs_new['Liabilities']).iloc[:,
         6:].set_index(liability_cashflows.T.index).T
    dr.reset_index(drop=True, inplace=True)

    curves = ESG_curves

    discount_rates_margin = dr
    discount_rates_base = pd.DataFrame(
        input.extract_table_data_from_ID('ID_cashflow_and_DR', ALM_inputs_new['Liabilities']).iloc[:,
        6:].columns.values.tolist())[0]
    print(discount_rates_base)

    liab_input = input.extract_table_data_from_ID('ID_starting_liability_value', ALM_inputs_new['Liabilities'])[
        'Starting_liability_value'][0]
    curve_categories = ["gilts", "swaps", "credit", "inflation", 'realised_inflation', 'fx_rates']
    forward_categories = ["gilts", "swaps", "credit", "inflation"]
    spot_categories = ["inflation"]
    error_msg = []

    esg_curves, error_msg = get_curves(curve_categories, curves, curves_map, error_msg)
    all_curves = forward_spot_curves(forward_categories, spot_categories, esg_curves, error_msg)
    cflow_prov= input.extract_table_data_from_ID('ID_cashflows provided',ALM_inputs_new['Liabilities'])['Are_cashflows_provided'][0]
    if cflow_prov=='Yes':
        liability_cashflows = input.extract_table_data_from_ID('ID_cashflow_and_DR',
                                                           ALM_inputs_new['Liabilities']).iloc[:, :3].set_index('Year').T
    else:
        liab_inputs = input.extract_table_data_from_ID('ID_starting_liability_value', ALM_inputs_new['Liabilities'])
        liability_cashflows = proxy_cashflows(liab_inputs['Duration'][0],sample_cflows,liab_inputs['Inflation linkage'][0],discount_rates_margin, discount_rates_base, all_curves)

    quantiles = [0.005, 0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99, 0.995]
    quantiles_years = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    number_asset_strat = input.extract_table_data_from_ID('ID_input_modules_set_up', ALM_inputs_new['SetUp'])['Value'][0]
    output_dict = {}
    for i in range(1,number_asset_strat+1):
        asset_returns = returns(input.extract_table_data_from_ID('ID_strategy', ALM_inputs_new['Asset_strategy_' + str(i)]),
                            ESG_returns)
        starting_asset_value = input.extract_table_data_from_ID('ID_st_asset', ALM_inputs_new['Asset_strategy_' + str(i)]).iloc[0][
        0]
        asset_shocks = input.extract_table_data_from_ID('ID_shocks', ALM_inputs_new['Asset_strategy_' + str(i)])
        non_LDI_asset_allocation = non_LDI_asset_allocations(
            input.extract_table_data_from_ID('ID_strategy', ALM_inputs_new['Asset_strategy_' + str(i)]))
        asset_currency = asset_currencies(
            input.extract_table_data_from_ID('ID_strategy', ALM_inputs_new['Asset_strategy_' + str(i)]))
        LDI_allocation = LDI_allocations(
            input.extract_table_data_from_ID('ID_strategy', ALM_inputs_new['Asset_strategy_' + str(i)]))
        hedging_ratios = input.extract_table_data_from_ID('ID_hedge_ratios', ALM_inputs_new['Asset_strategy_' + str(i)]).iloc[:,
                     9:].set_index('Rate')
        contributions = input.extract_table_data_from_ID('ID_conts', ALM_inputs_new['Asset_strategy_' + str(i)]).iloc[:,
                    1] * 10 ** 6

        output = run_alm_mult(
            curves=curves,
            returns=asset_returns,
            liability_cashflows=liability_cashflows,
            starting_asset_value=starting_asset_value,
            non_LDI_asset_allocation=non_LDI_asset_allocation,
            asset_currencies=asset_currency,
            LDI_allocations=LDI_allocation,
            discount_rates_margin=discount_rates_margin,
            discount_rates_base=discount_rates_base,
            hedging_ratios=hedging_ratios,
            liab_input=liab_input,
            contributions=contributions,
            quantiles=quantiles,
            quantiles_years=quantiles_years,
            curves_map=curves_map,
            asset_strat_num=i,
            asset_shocks=asset_shocks
            )
        output_dict.update(output)
        output_dict.update({"Liabilities": ALM_inputs_new["Liabilities"], "SetUp":ALM_inputs_new["SetUp"]})

    for i in range(1,number_asset_strat+1):
        output_dict.update({f"Asset_strategy_{i}": ALM_inputs_new[f'Asset_strategy_{i}']})
    return output_dict


def run_alm_single_strat(
        curves: pd.DataFrame,
        returns: pd.DataFrame,
        liability_cashflows: pd.DataFrame,
        starting_asset_value: float,
        non_LDI_asset_allocation: pd.DataFrame,
        asset_currencies: pd.DataFrame,
        LDI_allocations: pd.DataFrame,
        discount_rates_margin: pd.DataFrame,
        discount_rates_base: dict,
        hedging_ratios: pd.DataFrame,
        liab_input: float,
        contributions,
        quantiles: list,
        quantiles_years: list,
        curves_map: dict,
) -> pd.DataFrame:
    """Run ALM
    args:
        curves: ESG output of curves
        returns: Relevant returns on asset classes that match allocations dataframe
        cashflows: Nominal and real cashflows
        non_LDI_asset_allocation: Dataframe with same dimensions as one trial of returns.
        LDI_allocations: LDI allocation
        discount_rates_margin: Margin above spot rate
        discount_rates_base: Maps basis name to base curve from calibration to use for discount rate e.g. Gilts,Swaps,Credit
        hedging_ratios: hedging ratios against interest and inflation
        hedging_asset_returns:
        hedging_durations:
        liab_input: start liability value
    """

    curve_categories = ["gilts", "swaps", "credit", "inflation", 'realised_inflation', 'fx_rates']
    forward_categories = ["gilts", "swaps", "credit", "inflation"]
    spot_categories = ["inflation"]
    error_msg = []

    esg_curves, error_msg = get_curves(curve_categories, curves, curves_map, error_msg)
    all_curves = forward_spot_curves(forward_categories, spot_categories, esg_curves, error_msg)
    fx_return = fx_curves_return(esg_curves, error_msg)

    trial_num = esg_curves["gilts"]["Trial"].nunique()
    trial_timestep = esg_curves["gilts"][["Trial", "Timestep"]]

    liability_cashflows_scaled = liability_cashflows_scaling(liab_input, liability_cashflows, discount_rates_margin,
                                                             discount_rates_base, all_curves)
    nominal_cashflow = nominal_cashflows(liability_cashflows_scaled)
    inflation_cashflow = inflation_cashflows(liability_cashflows_scaled, esg_curves, all_curves, trial_num)
    total_cashflows = trial_timestep.join(inflation_cashflow + pd.DataFrame(list(nominal_cashflow.T.values) * trial_num))
    realised_cashflow = realised_cashflows(nominal_cashflow, inflation_cashflow, esg_curves, all_curves, trial_num)

    liability_pv = cashflows_present_value(total_cashflows, discount_rates_margin, discount_rates_base, all_curves,
                                           trial_timestep, pv_add=0)
    liability_pv01 = cashflows_present_value(total_cashflows, discount_rates_margin, discount_rates_base, all_curves,
                                             trial_timestep, pv_add=0.0001)

    pv01_diff = present_value_differences(liability_pv01, liability_pv, trial_timestep)

    inflation_cashflow_01 = inflation_cashflows(liability_cashflows_scaled, esg_curves, all_curves, trial_num,
                                                inf_add=0.0001)
    total_cashflow_ie01 = trial_timestep.join(
        inflation_cashflow_01 + pd.DataFrame(list(nominal_cashflow.T.values) * trial_num))

    liability_ie01 = cashflows_present_value(total_cashflow_ie01, discount_rates_margin, discount_rates_base,
                                             all_curves, trial_timestep, pv_add=0)
    ie01_diff = present_value_differences(liability_ie01, liability_pv, trial_timestep)

    inflation_cashflow_prev_year_inf = inflation_cashflows_previous_year_inflation(inflation_cashflow, trial_timestep).drop(columns=["Trial","Timestep"])
    total_cashflow_prev_year_inf = inflation_cashflow_prev_year_inf + pd.DataFrame(list(nominal_cashflow.T.values)*trial_num)
    liability_pv_prev_year_inf = cashflows_present_value(trial_timestep.join(total_cashflow_prev_year_inf), discount_rates_margin, discount_rates_base, all_curves, trial_timestep)

    ldi_impacts = ldi_impact(liability_pv, liability_pv_prev_year_inf, realised_cashflow, trial_timestep)
    hedging_ldi_impacts = hedging_ldi_impact(ldi_impacts, hedging_ratios, trial_num, trial_timestep)

    #updated funciton in below for asset shocks
    year_on_year_returns = asset_year_on_year_returns_with_shocks(returns, trial_timestep,asset_shocks,trial_num)#asset_year_on_year_returns(returns, trial_timestep)
    year_on_year_return_gbp = year_on_year_returns_gbp(year_on_year_returns,fx_return, curves_map, trial_timestep)
    returns_non_hdg = scheme_returns_non_hdg(year_on_year_return_gbp, non_LDI_asset_allocation, trial_timestep, trial_num)
    assets = assets_ldi_perfect(starting_asset_value, hedging_ldi_impacts, returns_non_hdg, realised_cashflow, contributions, trial_timestep, trial_num)

    output_df = output_creation_v2(liability_pv, assets, trial_timestep)

    pv_output = output_df[["Trial", "Timestep", "Liabilities basis_1", "Liabilities basis_2", "Liabilities basis_3", "assets"]]
    pv_output = pv_output[(pv_output["Trial"]==1) & (pv_output["Timestep"]==0)].iloc[0,2:]

    df_output_quantiles = quantiles_salm(output_df, quantiles, quantiles_years)

    leverage = ldi_leverage(hedging_ratios, liability_pv, LDI_allocations, assets, trial_num)

    # for i in range(20):
    #     gilt_rates_1 = curves[curves["Timestep"] == i][
    #         "ESG.Economies.GBP.NominalYieldCurves.NominalYieldCurve.SpotRate(Govt, 1, 3)"].to_frame()
    #     gilt_rates_10 = curves[curves["Timestep"] == i][
    #         "ESG.Economies.GBP.NominalYieldCurves.NominalYieldCurve.SpotRate(Govt, 10, 3)"].to_frame()
    #     gilt_rates_20 = curves[curves["Timestep"] == i][
    #         "ESG.Economies.GBP.NominalYieldCurves.NominalYieldCurve.SpotRate(Govt, 20, 3)"].to_frame()
    # gilt_rates = pd.DataFrame(np.concatenate([gilt_rates_1, gilt_rates_10, gilt_rates_20], axis=1))
    # gilt_rates.columns = ['1 year spot rate', '10 year spot rate', '20 year spot rate']
    return {"Backing - percentiles": df_output_quantiles, "Backing - inputs": pv_output, "Backing - leverage": leverage,}