#!/usr/bin/env python3

import copy
import csv
from enum import Enum
import numpy as np 
import os
from typing import Dict, List, Optional, Callable

from mass_energy_flow import solve_mass_energy_flow
from plant_costs import PriceEntry, add_steel_plant_lcop
from system import System


class ParameterType(Enum):
    Price = 1
    SystemVar = 2
    BoolSystemVar = 3


class SensitivityIndicator:
    def __init__(self, indicator_name: str, system_name: str, parameter_name: str, parameter_type: ParameterType):
        """
        indicator_name: Name of the indicator: Elasticity, MinMax, SpiderPlot, etc.
        system_name: Name of the system that the indicator was calculated for
        parameter_name: Name of the parameter the indicator was calculated for
        parameter_type: Indicates where in the model the parameter being analysed is stored.
        parameter_vals: The value of the parameter for each run. The dependent variable, X
        result_vals: The value of the result of interest. The independent variable, Y
        calculate: Method to calculate the sensitivity indicator from the X and Y values.
        """
        self.indicator_name: str = indicator_name
        self.system_name: str = system_name
        self.parameter_name: str = parameter_name
        self.parameter_type: ParameterType = parameter_type
        self._base_parameter_val: Optional[float] = None
        self._base_result_val: Optional[float] = None
        self._parameter_vals: np.ndarray = np.array([])
        self._result_vals: np.ndarray = np.array([])
        self._calculate: Optional[Callable] = None
        self._success: Optional[bool] = None
        self._error_msg: str = ""

    @property
    def base_parameter_val(self) -> Optional[float]:
        return self._base_parameter_val
    
    @base_parameter_val.setter
    def base_parameter_val(self, value: Optional[float]):
        self._base_parameter_val = value

    @property
    def base_result_val(self) -> Optional[float]:
        return self._base_result_val
    
    @base_result_val.setter
    def base_result_val(self, value: Optional[float]):
        self._base_result_val = value

    @property
    def parameter_vals(self) -> np.ndarray:
        return self._parameter_vals

    @parameter_vals.setter
    def parameter_vals(self, value: np.ndarray):
        self._parameter_vals = value

    @property
    def result_vals(self) -> np.ndarray:
        return self._result_vals

    @result_vals.setter
    def result_vals(self, value: np.ndarray):
        self._result_vals = value

    @property
    def calculate(self) -> Optional[Callable]:
        return self._calculate

    @calculate.setter
    def calculate(self, value: Optional[Callable]):
        self._calculate = value

    @property
    def success(self) -> Optional[bool]:
        return self._success

    @success.setter
    def success(self, value: Optional[bool]):
        self._success = value

    @property
    def error_msg(self) -> str:
        return self._error_msg

    @error_msg.setter
    def error_msg(self, value: str):
        self._error_msg = value


def report_sensitivity_analysis_for_system(output_dir: str, system: System,
                                           sensitivity_indicators: List[SensitivityIndicator]):
    system_name_sanitised = system.name.replace(' ', '_')
    output_filename = os.path.join(output_dir, system_name_sanitised + ".csv")
    with open(output_filename, 'w') as file:
        file.write(system.name + "\n\n")
        file.write("parameter_name,indicator_name,sensitivity index param 1,sensitivity index param 2,\
                    sensitivity index param 3\n")

        for si in sensitivity_indicators:
            if system.name != si.system_name: 
                raise Exception("System does not match the given sensitivity analysis indicator during reporting.")

            if not si.success:
                file.write(f"{si.parameter_name},{si.indicator_name},FAILED,{si.error_msg}\n")
                continue

            si_val = si.calculate(si.parameter_vals, si.result_vals)
            if isinstance(si_val, float):
                # Elasticity or MinMax
                file.write(f"{si.parameter_name},{si.indicator_name},{si_val:.6f},\n")
            elif isinstance(si_val, np.ndarray):
                # Spider Plot
                if len(si_val) != len(si.parameter_vals):
                    raise Exception("For multi-param sensitivity indicators, expected the num of param_vals to be \
                                    equal to the result_vals but failed")
                i = 0
                for param, result in zip(si.parameter_vals, si_val):
                    try:
                        perc_change_from_base = (param - si.base_parameter_val) / si.base_parameter_val * 100
                    except TypeError:
                        # expect this path to run when the params are non numerics. E.g. bools or strings
                        perc_change_from_base = param
                    file.write(f"{si.parameter_name},{si.indicator_name}_{i},{param:.4f},{perc_change_from_base:.2f},\
                                {result:.2f}\n")
                    i += 1


def calculate_min_max_si(parameter_vals: np.ndarray[float], result_vals: np.ndarray[float]) -> float:
    if len(parameter_vals) != 2 or len(result_vals) != 2:
        raise ValueError("MinMax sensitivity indicator requires two parameter values and two result values.")

    return (result_vals[1] - result_vals[0]) / result_vals[0]


def calculate_elasticity_si(parameter_vals: np.ndarray[float], result_vals: np.ndarray[float]) -> float:
    if len(parameter_vals) != 2 or len(result_vals) != 2:
        raise ValueError("Elasticity sensitivity indicator requires two parameter values and two result values.")

    x = (parameter_vals[0] + parameter_vals[1]) * 0.5
    y = (result_vals[0] + result_vals[1]) * 0.5

    return (result_vals[1] - result_vals[0]) / (parameter_vals[1] - parameter_vals[0]) * (x / y)


def calculate_spider_plot_si(parameter_vals: np.ndarray[float], result_vals: np.ndarray[float]) -> np.ndarray[float]:
    if len(parameter_vals) != len(result_vals):
        raise ValueError("SpiderPlot sensitivity indicator requires the same number of parameter values \
                         and result values.")
    return result_vals
    

class SensitivityCase:
    def __init__(self, system_name: str, parameter_name: str, parameter_type: ParameterType):
        self.system_name = system_name
        self.parameter_name = parameter_name
        self.parameter_type = parameter_type
        self._x_max = 0.0
        self._x_min = 0.0
        self._max_perc_change = 30.0
        self._num_perc_increments = 11
        self._elasticity_perc_change = 3.0
    
    @property
    def x_max(self) -> float:
        return self._x_max

    @x_max.setter
    def x_max(self, value: float):
        self._x_max = value

    @property
    def x_min(self) -> float:
        return self._x_min

    @x_min.setter
    def x_min(self, value: float):
        self._x_min = value

    @property
    def max_perc_change(self) -> float:
        return self._max_perc_change

    @max_perc_change.setter
    def max_perc_change(self, value: float):
        self._max_perc_change = value

    @property
    def num_increments(self) -> int:
        return self._num_perc_increments

    @num_increments.setter
    def num_increments(self, value: int):
        self._num_perc_increments = value

    @property
    def elasticity_perc_change(self) -> float:
        return self._elasticity_perc_change

    @elasticity_perc_change.setter
    def elasticity_perc_change(self, value: float):
        self._elasticity_perc_change = value

    def create_sensitivity_indicators(self, system: System, prices: Dict[str, PriceEntry]) -> List[SensitivityIndicator]:
        if system.name != self.system_name and self.system_name.upper() != "ALL":
            return []

        if self.parameter_type == ParameterType.BoolSystemVar:
            if self.parameter_name not in system.system_vars:
                return []
            base_case_val = system.system_vars[self.parameter_name]
            boolean_min_max = SensitivityIndicator("BooleanMinMax", system.name, self.parameter_name,
                                                   self.parameter_type)
            boolean_min_max.parameter_vals = np.array([False, True])
            boolean_min_max.calculate = calculate_min_max_si
            boolean_min_max.base_parameter_val = base_case_val
            boolean_min_max.base_result_val = system.lcop()

            return [boolean_min_max]
        elif self.parameter_type == ParameterType.Price:
            base_case_val = prices[self.parameter_name].price_usd
        elif self.parameter_type == ParameterType.SystemVar:
            if self.parameter_name in system.system_vars:
                base_case_val = system.system_vars[self.parameter_name]
            else:
                return []
        else:
            raise ValueError("Parameter type not recognized. Cannot setup sensitivity analysis.")

        if not isinstance(base_case_val, float) and not isinstance(base_case_val, int):
            raise ValueError(f"The parameter type needs to be a numeric float or int, not {type(base_case_val)}")

        spider_plot = SensitivityIndicator("SpiderPlot", system.name, self.parameter_name,
                                           self.parameter_type)
        spider_plot.parameter_vals = np.linspace(self.x_min, self.x_max, self.num_increments)
        spider_plot.calculate = calculate_spider_plot_si
        spider_plot.base_parameter_val = base_case_val
        spider_plot.base_result_val = system.lcop()

        return [spider_plot]


class SensitivityAnalysisRunner:
    def __init__(self, sensitivity_cases: List[SensitivityCase]):
        self._cases = sensitivity_cases
        self._systems = None

    @property
    def cases(self) -> List[SensitivityCase]:
        return self._cases
    
    @property
    def systems(self) -> List[System]:
        return self._systems
    
    @systems.setter
    def systems(self, value: List[System]):
        self._systems = value
    
    def run(self, prices: Dict[str, PriceEntry]):
        sensitivity_indicators_for_each_system: List[List[SensitivityIndicator]] = []

        # This is going to be so slow.... so many nested loops
        for system in self.systems:
            sensitivity_indicators: List[SensitivityIndicator] = []
            for case in self.cases:
                for si in case.create_sensitivity_indicators(system, prices):
                    for parameter_val in si.parameter_vals:
                        tmp_system = copy.deepcopy(system)
                        tmp_prices = copy.deepcopy(prices)
                        if si.parameter_type == ParameterType.Price:
                            tmp_prices[si.parameter_name].price_usd = parameter_val
                        elif si.parameter_type == ParameterType.SystemVar or si.parameter_type == ParameterType.BoolSystemVar:
                            tmp_system.system_vars[si.parameter_name] = parameter_val
                        else:
                            raise ValueError("Parameter type not recognized. Cannot run sensitivity analysis.")
                    
                        # Solve the system with this new set of parameters and save the result
                        tmp_system.name = f"{tmp_system.name}_SA_{si.parameter_name}_{parameter_val}"
                        try:
                            solve_mass_energy_flow(tmp_system, tmp_system.add_mass_energy_flow_func, False)
                            add_steel_plant_lcop(tmp_system, tmp_prices, False)
                            si.result_vals = np.append(si.result_vals, tmp_system.lcop())
                            si.success = True
                        except Exception as e:
                            si.success = False
                            si.error_msg = f"{e}"
                            break

                    sensitivity_indicators.append(si)
            sensitivity_indicators_for_each_system.append(sensitivity_indicators)

        return sensitivity_indicators_for_each_system


def sensitivity_analysis_runner_from_csv(filename: str) -> Optional[SensitivityAnalysisRunner]:
    sensitivity_cases = []
    with open(filename, 'r') as file:
        try:
            csv_reader = csv.reader(file)
        except csv.Error as e:
            print(f"Error reading CSV file at line {csv_reader.line_num}: {e}")
            return None
        next(csv_reader)  # Skip the header row

        for row in csv_reader:
            system_name = row[0]
            parameter_name = row[1]
            parameter_type = ParameterType[row[2]]
            sensitivity_case = SensitivityCase(system_name, parameter_name, parameter_type)
            if parameter_type == parameter_type.BoolSystemVar:
                sensitivity_cases.append(sensitivity_case)
                continue
            x1 = float(row[3])
            x2 = float(row[4])
            sensitivity_case.x_max = max(x1, x2)
            sensitivity_case.x_min = min(x1, x2)
            sensitivity_case.num_increments = int(row[5])
            sensitivity_case.elasticity_perc_change = float(row[6])
            sensitivity_cases.append(sensitivity_case)

    runner = SensitivityAnalysisRunner(sensitivity_cases)
    return runner
