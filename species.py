#!/usr/bin/env python3

import cantera as ct
import copy
import math
from typing import List

from thermo import ShomateEquation, SimpleHeatCapacity, CanteraSolution, LatentHeat, ThermoData


class Species:
    def __init__(self, name: str, molecular_mass_kg_per_mol: float, thermo_data: ThermoData,
                 delta_h_formation: float = None):
        """
        An element or compound or ion (SO4[2-], H[+], electron[-]).
        name: The name of the species, e.g. H2, FeO, H2O, etc.
        molecular_mass: The molecular mass of the species in kg/mol.
        thermo_data: The thermodynamic data for the species.
        delta_h_formation: The enthalpy of formation of the species in J/mol at 298 K. 
            Only used for elements.
        """
        self._name = name
        self._moles = 0.0
        self._temp_kelvin = None
        self._mm = molecular_mass_kg_per_mol
        self._thermo_data = thermo_data
        self._delta_h_formation = delta_h_formation

    def __repr__(self):
        return f"Species({self._name}, {self.mass:.2f} kg, {self._temp_kelvin} K)"

    def delta_h(self, t_final_kelvin: float) -> float:
        """
        Calculates the enthalpy change in J required to heat the species to the final temperature.
        Initial temperature of each species must be set.
        Does not modify the temperature of the species.
        """
        if not self._temp_kelvin:
            raise Exception("Species::delta_h: initial temperature is not set")
        return self._thermo_data.delta_h(self._moles, self._temp_kelvin, t_final_kelvin)

    def standard_enthalpy(self) -> float:
        """
        Enthalpy change relative to standard conditions (298.15K, 1 atm) [J]
        Includes any latent heat of phase changes that may occur.
        Does not include the enthalpy of formation.
        """
        return -self.delta_h(298.15)

    def cp(self, return_molar_cp: bool = True) -> float:
        """
        The heat capacity and latent heat
        return_molar_cp: If true, return the molar heat capacity. [J / mol K] 
            If false, return the specific (mass) heat capacity. [J / kg K]
        """
        if not self._temp_kelvin:
            raise Exception("Species::cp: temperature is not set")

        val = self._thermo_data.cp(self._temp_kelvin)
        if not return_molar_cp:
            val /= self._mm

        return val

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def moles(self) -> float:
        return self._moles

    @moles.setter
    def moles(self, value: float):
        if value < 0.0:
            raise Exception("Species::moles: Cannot set moles to a negative value")
        self._moles = value

    @property
    def mass(self) -> float:
        """
        Returns the mass in kg
        """
        return self._moles * self._mm

    @mass.setter
    def mass(self, value: float):
        """
        Sets the mass in kg
        """
        if math.isclose(value + 1.0, 1.0):
            value = 0.0
        if value < 0.0:
            raise Exception("Species::mass: Cannot set mass to a negative value")
        self._moles = value / self._mm

    @property
    def temp_kelvin(self) -> float:
        return self._temp_kelvin

    @temp_kelvin.setter
    def temp_kelvin(self, value: float):
        if value < 0.0:
            raise Exception("Species::temp: Cannot set temp to a negative value")
        self._temp_kelvin = value

    @property
    def mm(self) -> float:
        return self._mm

    @property
    def delta_h_formation(self) -> float:
        if self._delta_h_formation is None:
            raise Exception("Species::enthalpy_formation: enthalpy of formation is not set")
        return self._delta_h_formation

    def is_same_as(self, other_species) -> bool:
        """
        TODO: Not an ideal check of equivalence. Should be fine but fix later.
        """
        try:
            equivalent = math.isclose(self.moles, other_species.moles) and \
                         math.isclose(self.temp_kelvin, other_species.temp_kelvin) and \
                         math.isclose(self.mm, other_species.mm)
        except AttributeError:
            equivalent = False  # can occur if we try to compare a Species to a Mixture

        return equivalent

    def set(self, other_species, deepcopy_thermo_data=False):
        self._name = other_species._name
        self._moles = other_species._moles
        self._temp_kelvin = other_species._temp_kelvin
        self._mm = other_species._mm
        if deepcopy_thermo_data:
            self._thermo_data = copy.deepcopy(other_species._thermo_data)
        else:
            self._thermo_data = other_species._thermo_data
        self._delta_h_formation = other_species._delta_h_formation


class Mixture:
    """
    A list of species. Can represent a mix of gases, metal alloy, slag etc.
    name: The name of the mixture, e.g. air, slag, DRI etc.
    """

    def __init__(self, name: str, species: List[Species]):
        self._name = name
        # should really make this a dict, so that the interface is consistent
        # with the mass in and mass out of the Species class.
        self._species = copy.deepcopy(species)

    def __repr__(self):
        s = f"Mixture({self._name}"
        for species in self._species:
            s += f", {species}"
        s += ")"
        return s

    def report_weight_perc(self):
        total_mass = self.mass
        s = f"Mixture({self._name}"
        for species in self._species:
            s += f", {species.name} {species.mass / total_mass * 100:.2f}%"
        s += ")"
        print(s)

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def temp_kelvin(self) -> float:
        temp = None
        for species in self._species:
            if not temp:
                temp = species.temp_kelvin
            else:
                if species.temp_kelvin != temp:
                    raise Exception("Mixture::temp: temperatures of species do not match")
        return temp

    @temp_kelvin.setter
    def temp_kelvin(self, value: float):
        for species in self._species:
            species.temp_kelvin = value

    @property
    def mass(self) -> float:
        """
        Returns the mass in kg
        """
        mass = 0.0
        for species in self._species:
            mass += species.mass
        return mass

    # TODO: Should make this a dict, so that the interface is consistent
    # with the mass in and mass out of the Species class.
    def species(self, species_name) -> Species:
        for species in self._species:
            if species.name == species_name:
                return species
        raise KeyError(f"Mixture::species: species {species_name} not found in Mixture")

    def remove_species(self, species_name):
        for species in self._species:
            if species.name == species_name:
                self._species.remove(species)
                return
        # raise Exception("Mixture::remove_species: species not found")

    def num_species(self) -> int:
        return len(self._species)

    def merge(self, mixture_or_species):
        """
        Combines mixtures and calculates the new temperature based on thermodynamic mixing.
        That is, total enthalpy before and after mixing is constant.  
        """
        new_species = {}
        total_dh = 0.0
        total_moles_times_molar_heat_capacity = 0.0
        ref_temp = 298.0

        if math.isclose(mixture_or_species.mass, 0):
            return  # no need to merge
        if isinstance(mixture_or_species, Species):
            mixture_or_species = Mixture('tmp', [mixture_or_species])

        self_initial = copy.deepcopy(self)

        for s in self._species + mixture_or_species._species:
            if s.name in new_species:
                new_species[s.name].moles += s.moles
            else:
                new_species[s.name] = copy.deepcopy(s)

            if s.temp_kelvin < ref_temp:
                raise Exception("Mixture::merge: Thermodynamic mix calc. cannot handle temp of species less than \
                                reference temperature.")

            # negative because we are usually cooling down to the reference temp, and we want
            # enthalpy to be positive here 
            dH = -s.delta_h(ref_temp)
            total_dh += dH
            total_moles_times_molar_heat_capacity += dH / (s.temp_kelvin - ref_temp)

        self._species = list(new_species.values())
        self.temp_kelvin = ref_temp + total_dh / total_moles_times_molar_heat_capacity

        # adjust the final cold gas temp iteratively to reduce error caused by assuming the
        # molar heat capacity is constant. (which was done above)
        # TODO reduce repetition add_heat_exchanger_mass_flow(). Pull this optimisation into a separate function
        i = 0
        max_iter = 10
        while True:
            moles_times_molar_heat_capacity = self.delta_h(self.temp_kelvin + 1)

            energy_in_input_mixtures = -self_initial.delta_h(ref_temp) - mixture_or_species.delta_h(ref_temp)
            energy_in_output_mixtures = -self.delta_h(ref_temp)
            assert energy_in_input_mixtures >= 0 and energy_in_output_mixtures >= 0

            if abs((energy_in_input_mixtures - energy_in_output_mixtures) / energy_in_input_mixtures) < 1e-13:
                break

            dH = energy_in_input_mixtures - energy_in_output_mixtures
            dT = dH / moles_times_molar_heat_capacity
            self.temp_kelvin += dT
            i += 1
            if i > max_iter:
                raise Exception(f'Mixture::merge temp calc did not converge after {max_iter} iterations')

    def delta_h(self, t_final_kelvin: float) -> float:
        """
        Calculates the enthalpy in J required to heat the mixture to the final temperature.
        Initial temperature of each species must be set.
        Does not modify the temperature of the mixture.
        """
        energy_joules = 0.0
        for species in self._species:
            energy_joules += species.delta_h(t_final_kelvin)
        return energy_joules

    def standard_enthalpy(self) -> float:
        """
        Enthalpy change relative to standard conditions (298.15K, 1 atm) [J]
        Includes the latent heat of phase changes that may occur. 
        """
        return -self.delta_h(298.15)

    def is_same_as(self, other_mixture) -> bool:
        """
        Not an ideal check of equivalence. Should be fine for now but need to fix later.
        """
        try:
            equivalent = math.isclose(self.mass, other_mixture.mass) and \
                         math.isclose(self.temp_kelvin, other_mixture.temp_kelvin) and \
                         self.num_species() == other_mixture.num_species()
        except AttributeError:
            equivalent = False  # can occur if we try to compare a Species to a Mixture

        return equivalent

    def set(self, other_mixture):
        self._name = other_mixture._name
        self._species = copy.deepcopy(other_mixture._species)

    def species_moles(self) -> List[float]:
        """
        The moles of each species in the mixture
        """
        return [s.moles for s in self._species]

    def species_mass(self) -> List[float]:
        """
        The mass of each species in the mixture
        """
        return [s.mass for s in self._species]

    def cp(self, return_molar_cp: bool = True) -> float:
        """
        Return the average molar heat capacity at the current temperature.
        return_molar_cp: If true, return the molar heat capacity. [J / mol K] 
            If false, return the specific (mass) heat capacity. [J / kg K]
        """
        cps = [s.cp(return_molar_cp) for s in self._species]
        if return_molar_cp:
            weights = self.species_moles()
        else:
            weights = self.species_mass()
        total = sum(weights)
        weights = [w / total for w in weights]

        weighted_average_cp = 0.0
        for c, w in zip(cps, weights):
            weighted_average_cp += c * w

        return weighted_average_cp


# Species - Master copies
# Unless otherwise stated, Shomate Equation data from the NIST Chemistry Webbook
# Latent Heat Data is from the CRC Handbook of Chemistry and Physics, Enthalpy of Fusion, 6-146
# Enthalpy of Formation data is from the CRC Handbook of Chemistry and Physics, Enthalpy of Formation, 5-1
# Nasa polynomial data obtained from Cantera
nasa_gas_species = {s.name: s for s in ct.Species.list_from_file('nasa_gas.yaml')}


def create_dummy_species(name):
    heat_capacities = [SimpleHeatCapacity(273.15, 6000.0, 1.0)]
    thermo_data = ThermoData(heat_capacities)
    s = Species(name, 1.0, thermo_data)
    s.moles = 0.0
    s.temp_kelvin = 298.15
    return s


def create_dummy_mixture(name):
    return Mixture(name, [create_dummy_species('a species')])


def create_h2_species():
    heat_capacities = [ShomateEquation(298, 1000.0,
                                       (33.066178, -11.363417, 11.432816,
                                        -2.772874, -0.158558, -9.980797, 172.707974, 0.0)),
                       ShomateEquation(1000.0, 2500.0,
                                       (18.563083, 12.257357, -2.859786,
                                        0.268238, 1.977990, -1.147438, 156.288133, 0.0)),
                       ShomateEquation(2500.0, 6000.0,
                                       (43.413560, -4.293079, 1.272428,
                                        -0.096876, -20.533862, -38.515158, 162.081354, 0.0))
                       ]
    thermo_data = ThermoData(heat_capacities)
    species = Species('H2',
                      0.00201588,
                      thermo_data,
                      0.0)
    return species


def create_o2_species():
    heat_capacities = [ShomateEquation(100.0, 700.0,
                                       (31.32234, -20.23531, 57.86644,
                                        -36.50624, -0.007374, -8.903471,
                                        246.7945, 0.0)),
                       ShomateEquation(700.0, 2000.0,
                                       (30.03235, 8.772972, -3.988133,
                                        0.788313, -0.741599, -11.32468,
                                        236.1663, 0.0)),
                       ShomateEquation(2000.0, 6000.0,
                                       (20.91111, 10.72071, -2.020498,
                                        0.146449, 9.245722, 5.337651,
                                        237.6185, 0.0))]
    thermo_data = ThermoData(heat_capacities)
    species = Species('O2',
                      0.0319988,
                      thermo_data,
                      0.0)
    return species


def create_h2o_species():
    o2 = create_o2_species()
    h2 = create_h2_species()

    heat_capacities = [ShomateEquation(298.0, 500.0,
                                       (-203.6060, 1523.290, -3196.413,
                                        2474.455, 3.855326, -256.5478, -488.7163, -285.8304)),  # liquid water
                       ShomateEquation(500.0, 1700.0,  # steam
                                       (30.09200, 6.832514, 6.793435,
                                        -2.534480, 0.082139, -250.8810, 223.3967, -241.8264)),
                       ShomateEquation(1700.0, 6000.0,
                                       (41.96426, 8.622053, -1.499780,
                                        0.098119, -11.15764, -272.1797, 219.7809, -241.8264))]
    latent_heats = [LatentHeat(373.5, 35556.0)]
    thermo_data = ThermoData(heat_capacities, latent_heats)
    species = Species('H2O',
                      h2.mm + o2.mm * 0.5,
                      thermo_data,
                      -285.83e3)  # liquid water enthalpy of formation, -241.83e3 for gas phase
    return species


def create_n2_species():
    heat_capacities = [ShomateEquation(100.0, 500.0,
                                       (28.98641, 1.853978, -9.647459,
                                        16.63537, 0.000117, -8.671914, 226.4168, 0.0)),
                       ShomateEquation(500.0, 2000.0,
                                       (19.50583, 19.88705, -8.598535,
                                        1.369784, 0.527601, -4.935202, 212.3900, 0.0)),
                       ShomateEquation(2000.0, 6000.0,
                                       (35.51872, 1.128728, -0.196103,
                                        0.014662, -4.553760, -18.97091, 224.9810, 0.0))]
    thermo_data = ThermoData(heat_capacities)
    species = Species('N2',
                      0.0280134,
                      thermo_data)
    return species


def create_ar_species():
    heat_capacities = [SimpleHeatCapacity(273.15, 6000, 20.786)]
    thermo_data = ThermoData(heat_capacities)
    species = Species('Ar',
                      0.039948,
                      thermo_data)
    return species


def create_fe_species():
    # NIST data is very conflicting for iron. 
    # Using simplified data
    heat_capacities = [ShomateEquation(298, 700.0,
                                       (18.42868, 24.64301, -8.913720,
                                        9.664706, -0.012643, -6.573022, 42.51488,
                                        0.0)),
                       ShomateEquation(700.0, 1042.0,
                                       (-57767.65, 137919.7, -122773.2,
                                        38682.42, 3993.080, 24078.67, -87364.01, 0.0)),
                       ShomateEquation(1042.0, 1100.0,
                                       (-325.8859, 28.92876, 0.0,
                                        0.0, 411.9629, 745.8231, 241.8766, 0.0)),
                       ShomateEquation(1100, 1809,
                                       (-776.7387, 919.4005, -383.7184,
                                        57.08148, 242.1369, 697.6234, -558.3674, 0.0)),
                       SimpleHeatCapacity(1809.0, 3133.345, 46.02400)]  # liquid phase
    latent_heats = [LatentHeat(1811.15, 13810.0)]  # Fe(delta) -> Fe(Liquid), CRC Handbook
    thermo_data = ThermoData(heat_capacities, latent_heats)
    species = Species('Fe',
                      0.055845,
                      thermo_data,
                      0.0)
    return species


def create_feo_species():
    fe = create_fe_species()
    o2 = create_o2_species()

    heat_capacities = [ShomateEquation(298.0, 1650.0,
                                       (45.75120, 18.78553, -5.952201,
                                        0.852779, -0.081265, -286.7429, 110.3120, -272.0441)),
                       ShomateEquation(1650, 5000,
                                       (68.19920, -4.501232e-10, 1.195227e-10,
                                        -1.064302e-11, -3.092680e-10,
                                        -281.4326, 137.8377, -249.5321))  # Liquid phase
                       ]
    latent_heats = [LatentHeat(1644.15, 31189.13)]  # latent heat from factsage
    thermo_data = ThermoData(heat_capacities, latent_heats)
    species = Species('FeO',
                      fe.mm + o2.mm * 0.5,
                      thermo_data,
                      -272.0e3)
    return species


def create_fe3o4_species():
    fe = create_fe_species()
    o2 = create_o2_species()

    heat_capacities = [ShomateEquation(298, 900.0,
                                       (104.2096, 178.5108, 10.61510,
                                        1.132534, -0.994202, -1163.336,
                                        212.0585, -1120.894)),
                       ShomateEquation(900.0, 3000.1,
                                       (200.8320, 1.586435e-7, -6.661682e-8,
                                        9.452452e-9, 3.186020e-8, -1174.135, 388.0790, -1120.894))
                       ]
    thermo_data = ThermoData(heat_capacities)
    species = Species('Fe3O4',
                      fe.mm * 3 + o2.mm * 2.0,
                      thermo_data,
                      -1120.89e3)
    return species


def create_fe2o3_species():
    fe = create_fe_species()
    o2 = create_o2_species()

    heat_capacities = [ShomateEquation(298.0, 950.0,
                                       (93.43834, 108.3577, -50.86447,
                                        25.58683, -1.611330, -863.2094,
                                        161.0719, -825.5032)),
                       ShomateEquation(950.0, 1050,
                                       (150.6240, 0.0, 0.0, 0.0, 0.0,
                                        -875.6066, 252.8814, -825.5032)),
                       ShomateEquation(1050.0, 2500.1,
                                       (110.9362, 32.04714, -9.192333,
                                        0.901506, 5.433677, -843.1471,
                                        228.3548, -825.5032))
                       ]
    thermo_data = ThermoData(heat_capacities)
    species = Species('Fe2O3',
                      fe.mm * 2 + o2.mm * 1.5,
                      thermo_data,
                      -825.50e3)
    return species


def create_c_species():
    heat_capacities = [SimpleHeatCapacity(273.15, 3000.1, 10.68)]  # simplified, but not a large input material
    thermo_data = ThermoData(heat_capacities)
    species = Species('C',
                      0.012011,
                      thermo_data,
                      0.0)  # graphite enthalpy of formation
    return species


def create_co_species():
    c = create_c_species()
    o2 = create_o2_species()

    heat_capacities = [SimpleHeatCapacity(273.15, 298.0, 29.15),
                       ShomateEquation(298.0, 1300.0,
                                       (25.56759, 6.096130, 4.054656,
                                        -2.671301, 0.131021, -118.0089,
                                        227.3665, -110.5271)),
                       ShomateEquation(1300.0, 6000.0,
                                       (35.15070, 1.300095, -0.205921,
                                        0.013550, -3.282780, -127.8375,
                                        231.7120, -110.5271))]
    thermo_data = ThermoData(heat_capacities)
    species = Species('CO',
                      c.mm + o2.mm * 0.5,
                      thermo_data,
                      -110.53e3)
    return species


def create_co2_species():
    c = create_c_species()
    o2 = create_o2_species()

    heat_capacities = [ShomateEquation(273.15, 1200.0,
                                       (24.99735, 55.18696, -33.69137,
                                        7.948387, -0.136638, -403.6075,
                                        228.2431, -393.5224)),
                       ShomateEquation(1200.0, 6000.0,
                                       (58.16639, 2.720074, -0.492289,
                                        0.038844, -6.447293, -425.9186,
                                        263.6125, -393.5224))]
    thermo_data = ThermoData(heat_capacities)
    species = Species('CO2',
                      c.mm + o2.mm,
                      thermo_data,
                      -393.51e3)
    return species


def create_al2o3_species():
    heat_capacities = [SimpleHeatCapacity(273.15, 298.0, 81.0885),
                       ShomateEquation(298.0, 2327.0,
                                       (106.9180, 36.62190, -13.97590,
                                        2.157990, -3.157761, -1710.500,
                                        151.7920, -1666.490)),
                       ShomateEquation(2327.0, 4000.0,
                                       (192.4640, 0.0, 0.0, 0.0, 0.0,
                                        -1773.50, 177.1008, -1620.568))]
    # Adding flux should reduce the melting point. Possibly effect
    # the latent heat value as well?
    latent_heats = [LatentHeat(2345.15, 111100)]
    thermo_data = ThermoData(heat_capacities, latent_heats)
    species = Species('Al2O3',
                      0.101961,
                      thermo_data)
    return species


def create_si_species():
    heat_capacities = [SimpleHeatCapacity(273.15, 298.0, 44.57),
                       ShomateEquation(298.0, 1685.0,
                                       (22.81719, 3.899510, -0.082885,
                                        0.042111, -0.354063, -8.163946,
                                        43.27846, 0.000000)),
                       SimpleHeatCapacity(1685.0, 3504.616, 27.19604)

                       ]
    latent_heats = [LatentHeat(1414.0, 50210)]
    thermo_data = ThermoData(heat_capacities, latent_heats)
    species = Species('Si',
                      0.0280855,
                      thermo_data,
                      0)
    return species


def create_sio2_species():
    heat_capacities = [SimpleHeatCapacity(273.15, 298.0, 44.57),
                       ShomateEquation(298.0, 847.0,
                                       (-6.076591, 251.6755, -324.7964,
                                        168.5604, 0.002548, -917.6893,
                                        -27.96962, -910.8568)),
                       ShomateEquation(847.0, 1996.0,
                                       (58.75340, 10.27925, -0.131384,
                                        0.025210, 0.025601, -929.3292,
                                        105.8092, -910.8568)),
                       SimpleHeatCapacity(1996.0, 3000.1, 77.99)  # NIST data didn't go higher, guessing
                       ]
    # Adding flux should reduce the melting point.
    latent_heats = [LatentHeat(1983.15, 9600)]
    thermo_data = ThermoData(heat_capacities, latent_heats)
    species = Species('SiO2',
                      0.060084,
                      thermo_data,
                      -910.7e3)
    return species


def create_tio2_species():
    heat_capacities = [SimpleHeatCapacity(273.15, 298.0, 55.182),
                       ShomateEquation(298.0, 2000.0,
                                       (67.29830, 18.70940, -11.57900,
                                        2.449561, -1.485471, -964.5140,
                                        117.8630, -938.7220)),
                       SimpleHeatCapacity(2000, 2130.0, 77.626),
                       SimpleHeatCapacity(2130.0, 4000.1, 100.4160)  # liquid phase
                       ]
    # Adding flux should reduce the melting point.
    latent_heats = [LatentHeat(2130.0, 68e3)]
    thermo_data = ThermoData(heat_capacities, latent_heats)
    species = Species('TiO2',  # rutile
                      0.079866,
                      thermo_data,
                      -944.0e3)
    return species


def create_cao_species():
    heat_capacities = [SimpleHeatCapacity(273.15, 298.0, 42.09),
                       ShomateEquation(298.0, 3200.0,  # solid phase
                                       (49.95403, 4.887916, -0.352056,
                                        0.046187, -0.825097, -652.9718,
                                        92.56096, -635.0894)),
                       SimpleHeatCapacity(3200.0, 4500.0, 62.76000)  # liquid phase
                       ]
    latent_heats = [LatentHeat(2845.15, 80000)]
    thermo_data = ThermoData(heat_capacities, latent_heats)
    species = Species('CaO',
                      0.0560774,
                      thermo_data)
    return species


def create_mgo_species():
    heat_capacities = [SimpleHeatCapacity(273.15, 298.0, 37.01),
                       ShomateEquation(298.0, 3105.0,  # solid phase
                                       (47.25995, 5.681621, -0.872665,
                                        0.104300, -1.053955, -619.1316,
                                        76.46176, -601.2408)),
                       SimpleHeatCapacity(3105.0, 5000.0, 66.944)  # liquid phase
                       ]
    latent_heats = [LatentHeat(3098.15, 77000)]
    thermo_data = ThermoData(heat_capacities, latent_heats)
    species = Species('MgO',
                      0.0403044,
                      thermo_data)
    return species


def create_mn_species():
    heat_capacities = [SimpleHeatCapacity(273.15, 298.0, 26.26),
                       ShomateEquation(298.0, 980.0,  # solid phase
                                       (27.24190, 5.237640, 7.783160,
                                        -2.118501, -0.282113, -9.366891,
                                        61.49640, 0.000000)),
                       ShomateEquation(980.0, 1361.0,
                                       (52.29870, -28.67560, 21.48670,
                                        -4.979850, -2.432060, -21.24330,
                                        90.70820, 0.000000)),
                       ShomateEquation(1361.0, 1412.0,
                                       (19.06450, 31.41340, -14.99350,
                                        3.214741, 1.867090, -2.757881,
                                        48.78900, 0.000000)),
                        ShomateEquation(1412.0, 1519.0,
                                       (-534.1720, 679.0530, -296.3700,
                                        46.42660, 161.3420, 468.7150,
                                        -393.5390, 0.000000)),
                       SimpleHeatCapacity(1519.0, 3500.0, 46.024)  # liquid phase
                       ]
    latent_heats = [LatentHeat(1519.0, 12910.0)]
    thermo_data = ThermoData(heat_capacities, latent_heats)
    species = Species('Mn',
                      0.0549380,
                      thermo_data,
                      0.0)
    return species


def create_mno_species():
    heat_capacities = [SimpleHeatCapacity(273.15, 400.0, 37.0),# solid phase
                       SimpleHeatCapacity(400.00, 600.0, 47.0),
                       SimpleHeatCapacity(600.00, 1600.0, 56.0),
                       SimpleHeatCapacity(1600.00, 3000.0, 60.0)# liquid phase
                       ]
    latent_heats = [LatentHeat(1519.0, 43900.0)]
    thermo_data = ThermoData(heat_capacities, latent_heats)
    species = Species('MnO',
                      0.0709374,
                      thermo_data,
                      -385.2e3)
    return species


def create_ch4_species():
    c = create_c_species()
    h2 = create_h2_species()

    heat_capacities = [ShomateEquation(273.15, 1300.0,
                                       (-0.703029, 108.4773, -42.52157,
                                        5.862788, 0.678565, -76.84376,
                                        158.7163, -74.87310)),
                       ShomateEquation(1300.0, 6000.0,
                                       (85.81217, 11.26467, -2.114146,
                                        0.138190, -26.42221, -153.5327,
                                        224.4143, -95.74984))]
    thermo_data = ThermoData(heat_capacities)
    species = Species('CH4',
                      c.mm + 2.0 * h2.mm,
                      thermo_data,
                      -74.6e3)
    return species


def create_h_species():
    heat_capacities = [SimpleHeatCapacity(298, 6000.0, 20.78603)]
    thermo_data = ThermoData(heat_capacities)
    species = Species('H',
                      0.00100794,
                      thermo_data,
                      218e3)
    return species


def create_h2_ar_plasma_species(argon_molar_frac_in_h2_plasma: float = 0.0):
    if not 0.0 <= argon_molar_frac_in_h2_plasma <= 1.0:
        raise ValueError(f'Argon molar fraction must be between 0 and 1, not {argon_molar_frac_in_h2_plasma}')
    h2 = create_h2_species()
    ar = create_ar_species()

    h2_plasma = ct.Solution(thermo='ideal-gas', species=[nasa_gas_species['H2'],
                                                         nasa_gas_species['H2+'],
                                                         nasa_gas_species['H2-'],
                                                         nasa_gas_species['H'],
                                                         nasa_gas_species['H+'],
                                                         nasa_gas_species['H-'],
                                                         nasa_gas_species['Ar'],
                                                         nasa_gas_species['Ar+'],
                                                         nasa_gas_species['Electron']])
    molar_composition = {
        'H2': 1.0 - argon_molar_frac_in_h2_plasma,
        'Ar': argon_molar_frac_in_h2_plasma
    }
    h2_plasma.TPX = 300.0, ct.one_atm, molar_composition
    heat_capacities = [CanteraSolution(h2_plasma)]
    thermo_data = ThermoData(heat_capacities)
    species = Species('H2-Ar Plasma',
                      h2.mm * molar_composition['H2'] + ar.mm * molar_composition['Ar'],
                      thermo_data,
                      0.0)
    return species


def create_scrap_species():
    species = create_fe_species()
    species.name = 'Scrap'
    return species


def create_air_mixture(mass_kg):
    n2 = create_n2_species()
    n2.mass = mass_kg * 0.7812
    o2 = create_o2_species()
    o2.mass = mass_kg * 0.2095
    ar = create_ar_species()
    ar.mass = mass_kg * 0.0093
    mixture = Mixture('Air', [n2, o2, ar])
    return mixture


# Chemical reaction master copies
def compute_reaction_enthalpy(reactants, products, temp_kelvin):
    """
    Calculates the enthalpy of reaction.
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    for species in reactants + products:
        species.temp_kelvin = temp_kelvin
    reactant_enthalpy = 0.0
    for reactant in reactants:
        reactant_enthalpy += reactant.moles * reactant.delta_h_formation
        reactant_enthalpy += reactant.standard_enthalpy()
    product_enthalpy = 0.0
    for product in products:
        product_enthalpy += product.moles * product.delta_h_formation
        product_enthalpy += product.standard_enthalpy()
    return product_enthalpy - reactant_enthalpy


def delta_h_2fe_o2_2feo(temp_kelvin: float = 298.15) -> float:
    """
    2Fe + O2 -> 2FeO
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    fe = create_fe_species()
    fe.moles = 2
    o2 = create_o2_species()
    o2.moles = 1
    reactants = [fe, o2]
    feo = create_feo_species()
    feo.moles = 2
    products = [feo]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_c_o2_co2(temp_kelvin: float = 298.15) -> float:
    """
    C + O2 -> CO2
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    c = create_c_species()
    c.moles = 1
    o2 = create_o2_species()
    o2.moles = 1
    reactants = [c, o2]
    co2 = create_co2_species()
    co2.moles = 1
    products = [co2]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_2c_o2_2co(temp_kelvin: float = 298.15) -> float:
    """
    2C + O2 -> 2CO
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    c = create_c_species()
    c.moles = 2
    o2 = create_o2_species()
    o2.moles = 1
    reactants = [c, o2]
    co = create_co_species()
    co.moles = 2
    products = [co]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_c_2h2_ch4(temp_kelvin: float = 298.15) -> float:
    """
    C + 2H2 -> CH4
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    c = create_c_species()
    c.moles = 1
    h2 = create_h2_species()
    h2.moles = 2
    reactants = [c, h2]
    ch4 = create_ch4_species()
    ch4.moles = 1
    products = [ch4]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_si_o2_sio2(temp_kelvin: float = 298.15) -> float:
    """
    Si + O2 -> SiO2
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    si = create_si_species()
    si.moles = 1
    o2 = create_o2_species()
    o2.moles = 1
    reactants = [si, o2]
    sio2 = create_sio2_species()
    sio2.moles = 1
    products = [sio2]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_sio2_h2_si_h2o(temp_kelvin: float = 298.15) -> float:
    """
    SiO2 + 2H2 -> Si + 2H2O
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    sio2 = create_sio2_species()
    sio2.moles = 1
    h2 = create_h2_species()
    h2.moles = 2
    reactants = [sio2, h2]
    si = create_si_species()
    si.moles = 1
    h2o = create_h2o_species()
    h2o.moles = 2
    products = [si, h2o]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_2mn_o2_2mno(temp_kelvin: float = 298.15) -> float:
    """
    2Mn + O2 -> 2MnO
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    mn = create_mn_species()
    mn.moles = 2
    o2 = create_o2_species()
    o2.moles = 1
    reactants = [mn, o2]
    mno = create_mno_species()
    mno.moles = 2
    products = [mno]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_feo_c_fe_co(temp_kelvin: float = 298.15) -> float:  # Check delta h this gives to a source
    """
    FeO + C -> Fe + CO
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    feo = create_feo_species()
    feo.moles = 1
    c = create_c_species()
    c.moles = 1
    reactants = [feo, c]
    fe = create_fe_species()
    fe.moles = 1
    co = create_co_species()
    co.moles = 1
    products = [fe, co]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_3fe2o3_h2_2fe3o4_h2o(temp_kelvin: float = 298.15) -> float:
    """
    3 Fe2O3 + H2 -> 2 Fe3O4 + H2O
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    fe2o3 = create_fe2o3_species()
    fe2o3.moles = 3
    h2 = create_h2_species()
    h2.moles = 1
    reactants = [fe2o3, h2]
    fe3o4 = create_fe3o4_species()
    fe3o4.moles = 2
    h2o = create_h2o_species()
    h2o.moles = 1
    products = [fe3o4, h2o]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_fe3o4_h2_3feo_h2o(temp_kelvin: float = 298.15) -> float:  # TODO! Check with another source. Seems wrong
    """
    Fe3O4 + H2 -> 3 FeO + H2O
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    fe3o4 = create_fe3o4_species()
    fe3o4.moles = 1
    h2 = create_h2_species()
    h2.moles = 1
    reactants = [fe3o4, h2]
    feo = create_feo_species()
    feo.moles = 3
    h2o = create_h2o_species()
    h2o.moles = 1
    products = [feo, h2o]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_feo_h2_fe_h2o(temp_kelvin: float = 298.15) -> float:  # TODO! Check with another source. Seems wrong
    """
    FeO + H2 -> Fe + H2O
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    feo = create_feo_species()
    feo.moles = 1
    h2 = create_h2_species()
    h2.moles = 1
    reactants = [feo, h2]
    fe = create_fe_species()
    fe.moles = 1
    h2o = create_h2o_species()
    h2o.moles = 1
    products = [fe, h2o]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_fe2o3_h2_2feo_h2o(temp_kelvin: float = 298.15) -> float:
    """
    Fe2O3 + H2 -> 2 FeO + H2O
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    fe2o3 = create_fe2o3_species()
    fe2o3.moles = 1
    h2 = create_h2_species()
    h2.moles = 1
    reactants = [fe2o3, h2]
    feo = create_feo_species()
    feo.moles = 2
    h2o = create_h2o_species()
    h2o.moles = 1
    products = [feo, h2o]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_fe2o3_6h_2fe_3h2o(temp_kelvin: float = 298.15) -> float:
    """
    Fe2O3 + 6 H -> 2 Fe + 3 H2O
    Note: Monatomic hydrogen reduction
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    fe2o3 = create_fe2o3_species()
    fe2o3.moles = 1
    h = create_h_species()
    h.moles = 6
    reactants = [fe2o3, h]
    fe = create_fe_species()
    fe.moles = 2
    h2o = create_h2o_species()
    h2o.moles = 3
    products = [fe, h2o]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_fe2o3_2h_2feo_h2o(temp_kelvin: float = 298.15) -> float:
    """
    Fe2O3 + 2 H -> 2 FeO + H2O
    Note: Monatomic hydrogen reduction
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    fe2o3 = create_fe2o3_species()
    fe2o3.moles = 1
    h = create_h_species()
    h.moles = 2
    reactants = [fe2o3, h]
    feo = create_feo_species()
    feo.moles = 2
    h2o = create_h2o_species()
    h2o.moles = 1
    products = [feo, h2o]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_fe2o3_3h2_2fe_3h2o(temp_kelvin: float = 298.15) -> float:
    """
    Fe2O3 + 3 H2 -> 2 Fe + 3 H2O
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    fe2o3 = create_fe2o3_species()
    fe2o3.moles = 1
    h2 = create_h2_species()
    h2.moles = 3
    reactants = [fe2o3, h2]
    fe = create_fe_species()
    fe.moles = 2
    h2o = create_h2o_species()
    h2o.moles = 3
    products = [fe, h2o]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_feo_2h_fe_h2o(temp_kelvin: float = 298.15) -> float:
    """
    FeO + 2 H -> Fe + H2O
    Note: Monatomic hydrogen reduction
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    feo = create_feo_species()
    feo.moles = 1
    h = create_h_species()
    h.moles = 2
    reactants = [feo, h]
    fe = create_fe_species()
    fe.moles = 1
    h2o = create_h2o_species()
    h2o.moles = 1
    products = [fe, h2o]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_fe3o4_2h_3feo_h2o(temp_kelvin: float = 298.15) -> float:
    """
    Fe3O4 + 2 H -> 3 FeO + H2O
    Note: Monatomic hydrogen reduction
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    fe3o4 = create_fe3o4_species()
    fe3o4.moles = 1
    h = create_h_species()
    h.moles = 2
    reactants = [fe3o4, h]
    feo = create_feo_species()
    feo.moles = 3
    h2o = create_h2o_species()
    h2o.moles = 1
    products = [feo, h2o]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_3fe2o3_2h_2fe3o4_h2o(temp_kelvin: float = 298.15) -> float:
    """
    3 Fe2O3 + 2 H -> 2 Fe3O4 + H2O
    Note: Monatomic hydrogen reduction
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    fe2o3 = create_fe2o3_species()
    fe2o3.moles = 3
    h = create_h_species()
    h.moles = 2
    reactants = [fe2o3, h]
    fe3o4 = create_fe3o4_species()
    fe3o4.moles = 2
    h2o = create_h2o_species()
    h2o.moles = 1
    products = [fe3o4, h2o]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_2h2o_2h2_o2(temp_kelvin: float = 298.15) -> float:
    """
    2 H2O + 474.2 kJ/mol electricity + 97.2 kJ/mol heat -> 2 H2 + O2
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    h2o = create_h2o_species()
    h2o.moles = 2
    reactants = [h2o]
    h2 = create_h2_species()
    h2.moles = 2
    o2 = create_o2_species()
    o2.moles = 1
    products = [h2, o2]
    return compute_reaction_enthalpy(reactants, products, temp_kelvin)


def delta_h_c_c_dissolved() -> float:
    """
    C(gr) -> C (dissolved in Fe)
    From: Madhavan, N., Brooks, G., Rhamdhani, M., Rout, B., & Overbosch, A. (2021). General heat balance
    for oxygen steelmaking. Journal of Iron and Steel Research International, 28, 538–551.
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    return 24.21e3


def delta_h_si_si_dissolved() -> float:
    """
    Si(L) -> Si (dissolved in Fe)
    From: Madhavan, N., Brooks, G., Rhamdhani, M., Rout, B., & Overbosch, A. (2021). General heat balance
    for oxygen steelmaking. Journal of Iron and Steel Research International, 28, 538–551.
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    return -135.30e3


def delta_h_c_dissolved_o2_co2(temp_kelvin: float) -> float:
    """
    C(dissolved in Fe) + O2(g) -> CO2(g)
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    return delta_h_c_o2_co2(temp_kelvin) - delta_h_c_c_dissolved()


def delta_h_2c_dissolved_o2_2co(temp_kelvin: float) -> float:
    """
    2 C(dissolved in Fe) + O2(g) -> 2 CO(g)
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    return delta_h_2c_o2_2co(temp_kelvin) - 2 * delta_h_c_c_dissolved()


def delta_h_si_dissolved_o2_sio2(temp_kelvin: float) -> float:
    """
    Si(dissolved in Fe) + O2(g) -> SiO2(g)
    Returns:
        enthalpy of reaction [J / mol of reaction]
    """
    return delta_h_si_o2_sio2(temp_kelvin) - delta_h_si_si_dissolved()
