#!/usr/bin/env python3

import copy
import math


class ShomateEquation:
    """
    The Shomate equation.
    Used to calculate the molar heat capacity, enthalpy and entropy.
    Units follow the convention of the NIST database.
    """
    def __init__(self, min_kelvin: float, max_kelvin: float, coeffs: tuple):
        assert min_kelvin < max_kelvin
        assert len(coeffs) == 8 # coeffs: (a, b, c, d, e, f, g, h)
        self.min_kelvin = min_kelvin
        self.max_kelvin = max_kelvin
        self.coeffs = coeffs

    def __repr__(self):
        return f"ShomateEquation({self.min_kelvin}-{self.max_kelvin}K, A={self.coeffs[0]}, B={self.coeffs[1]}, " \
               f"C={self.coeffs[2]}, D={self.coeffs[3]}, E={self.coeffs[4]}, F={self.coeffs[5]} "\
               f"G={self.coeffs[6]}, H={self.coeffs[7]})"

    def delta_h(self, moles: float, t_initial: float, t_final: float) -> float:
        if not (self.min_kelvin <= t_initial <= self.max_kelvin) or \
            not (self.min_kelvin <= t_final <= self.max_kelvin):
            raise Exception("ShomateEquation::delta_h: temperatures must be within the range of the heat capacity")
        t_initial /= 1000
        t_final /= 1000
        energy_kJ = moles * (self.coeffs[0] * (t_final - t_initial) + \
                       self.coeffs[1] / 2 * (t_final**2 - t_initial**2) + \
                       self.coeffs[2] / 3 * (t_final**3 - t_initial**3) + \
                       self.coeffs[3] / 4 * (t_final**4 - t_initial**4) + \
                       self.coeffs[4] / t_final - self.coeffs[4] / t_initial)
        return energy_kJ * 1000


class SimpleHeatCapacity:
    """
    Heat capacity at constant pressure stored as a constant value.
    """
    def __init__(self, min_kelvin: float, max_kelvin: float, cp: float):
        """
        cp: heat capacity at constant pressure in J/mol K
        """
        assert min_kelvin < max_kelvin
        self.min_kelvin = min_kelvin
        self.max_kelvin = max_kelvin
        self.cp = cp

    def __repr__(self):
        return f"SimpleHeatCapacity({self.min_kelvin}-{self.max_kelvin}K, cp={self.cp})"
    
    def delta_h(self, moles: float, t_initial: float, t_final: float) -> float:
        if not (self.min_kelvin <= t_initial <= self.max_kelvin) or \
            not (self.min_kelvin <= t_final <= self.max_kelvin):
            raise Exception("SimpleHeatCapacity::delta_h: temperatures must be within the range of the heat capacity")
        return moles * self.cp * (t_final - t_initial)


class LatentHeat:
    """
    Latent heat required for melting or boiling.
    """
    def __init__(self, temp_kelvin: float, latent_heat: float):
        """
        Latent heat in J/mol
        """
        self.temp_kelvin = temp_kelvin
        self.latent_heat = latent_heat

    def __repr__(self):
        return f"LatentHeat({self.temp_kelvin} K, latent_heat={self.latent_heat} J/mol)"
    
    def delta_h(self, moles: float):
        return moles * self.latent_heat


class ThermoData:
    """
    Contains a list HeatCapacity instances. Each must cover a different range,
    and be continuous (no gaps between the thermo data ranges).
    """
    def __init__(self, heat_capacities: list, latent_heats: list = []):
        """
        heat_capacities: a list of ShomateEquation or SimpleHeatCapacitys
            with non-overlapping temperature ranges.
        """

        # Validate the input types
        for heat_capacity in heat_capacities:
            if not isinstance(heat_capacity, (ShomateEquation, SimpleHeatCapacity)):
                raise Exception("ThermoData::init: ThermoData must be initialised with a list of ShomateEquation or SimpleHeatCapacity instances")
        
        for latent_heat in latent_heats:
            if not isinstance(latent_heat, LatentHeat):
                raise Exception("ThermoData::init: ThermoData must be initialised with a list of LatentHeat instances")

        # Ensure non-overlapping continous heat capacity range
        self.heat_capacities = copy.deepcopy(heat_capacities)
        self.heat_capacities.sort(key=lambda x: x.min_kelvin)
        for i in range(len(self.heat_capacities) - 1):
            if not math.isclose(self.heat_capacities[i].max_kelvin, \
                                 self.heat_capacities[i + 1].min_kelvin):
                raise Exception("ThermoData::init: Non-continuous temperature ranges (gap or overlap detected)")
            
        self.min_kelvin = self.heat_capacities[0].min_kelvin
        self.max_kelvin = self.heat_capacities[-1].max_kelvin

        # Ensure the latent heat values lie within the heat capacity range
        self.latent_heats = copy.deepcopy(latent_heats)
        self.latent_heats.sort(key=lambda x: x.temp_kelvin)
        for latent_heat in self.latent_heats:
            if not (self.min_kelvin <= latent_heat.temp_kelvin <= self.max_kelvin):
                raise Exception("ThermoData::init: Latent heat temperature out of range")
            
    def __repr__(self):
        return f"ThermoData({self.heat_capacities}, {self.latent_heats})"
    
    def delta_h(self, moles: float, t_initial: float, t_final: float) -> float:
        if not (self.min_kelvin <= t_initial <= self.max_kelvin) or \
            not (self.min_kelvin <= t_final <= self.max_kelvin):
            s = f"ThermoData::delta_h: temperatures must be within the range of the heat capacity ({self.min_kelvin}K - {self.max_kelvin}K)"
            s += f" t_initial={t_initial}K, t_final={t_final}K"
            raise Exception(s)
        
        if math.isclose(moles, 0.0):
            return 0.0

        # ensure initial temp is always less than final, then flip if needed
        # keeps the maths simple
        flip_result = t_final < t_initial
        if flip_result:
            t_initial, t_final = t_final, t_initial

        delta_h = 0

        # Add the contributions from the latent heats
        for latent_heat in self.latent_heats:
            if t_initial <= latent_heat.temp_kelvin < t_final:
                delta_h += latent_heat.delta_h(moles)

        # Find the heat capacity that covers the initial temperature
        for heat_capacity in self.heat_capacities:
            if heat_capacity.min_kelvin <= t_initial <= heat_capacity.max_kelvin:
                if heat_capacity.min_kelvin <= t_final <= heat_capacity.max_kelvin:
                    # Result is entirlly within one heat capacity range
                    delta_h += heat_capacity.delta_h(moles, t_initial, t_final)
                    break
                else:
                    # Result spans multiple heat capacity ranges
                    delta_h += heat_capacity.delta_h(moles, t_initial, heat_capacity.max_kelvin)
                    t_initial = heat_capacity.max_kelvin              

        if flip_result:
            delta_h *= -1
        return delta_h

#TODO: Understand if there are special requirements for plasmas