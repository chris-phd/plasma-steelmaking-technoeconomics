#!/usr/bin/env python3

import cantera as ct
import math
from typing import Optional, Dict, Any

from species import create_dummy_species, create_dummy_mixture
from system import System, Device, EnergyFlow
from utils import celsius_to_kelvin


def main():
    plasma_system = create_plasma_system("Plasma new")
    plasma_system_2 = create_plasma_system("plasma no h2 production", on_premises_h2_production=False)
    dri_eaf_system = create_dri_eaf_system(on_premises_h2_production=False)
    hybrid33_system = create_hybrid_system("hybrid33 steelmaking new", prereduction_perc=33.33)
    hybrid95_system = create_hybrid_system("hybrid95 steelmaking", prereduction_perc=95.0)
    hybrid33_bof_system = create_hybrid_system("hybrid33-BOF", prereduction_perc=33.33, bof_steelmaking=True)
    plasma_bof_system = create_plasma_system("Plasma-BOF", bof_steelmaking=True)

    plasma_system.render(output_directory="/home/chris/Desktop/")
    plasma_system_2.render(output_directory="/home/chris/Desktop/")
    dri_eaf_system.render(output_directory="/home/chris/Desktop/")
    hybrid33_system.render(output_directory="/home/chris/Desktop/")
    hybrid95_system.render(output_directory="/home/chris/Desktop/")
    hybrid33_bof_system.render(output_directory="/home/chris/Desktop/")
    plasma_bof_system.render(output_directory="/home/chris/Desktop/")


# System Creators
def create_plasma_system(system_name: str = 'plasma steelmaking',
                         on_premises_h2_production: bool = True,
                         h2_storage_method: Optional[str] = 'salt caverns',
                         annual_capacity_tls: float = 1.5e6,
                         plant_lifetime_years: float = 20.0,
                         bof_steelmaking: bool = False) -> System:
    plasma_system = System(system_name, annual_capacity_tls, plant_lifetime_years)

    if on_premises_h2_production:
        water_electrolysis = Device('water electrolysis', 'electrolyser')
        plasma_system.add_device(water_electrolysis)
        if h2_storage_method is not None:
            h2_storage = Device('h2 storage', h2_storage_method)
            plasma_system.add_device(h2_storage)
    h2_heat_exchanger = Device('h2 heat exchanger', 'high temp gas-gas heat exchanger')
    plasma_system.add_device(h2_heat_exchanger)
    condenser = Device('condenser and scrubber', 'steam condenser and scrubber')
    plasma_system.add_device(condenser)
    ore_heater = Device('ore heater', 'ore heater')
    plasma_system.add_device(ore_heater)
    plasma_torch = Device('plasma torch')
    plasma_system.add_device(plasma_torch)
    plasma_smelter = Device('plasma smelter', 'plasma smelter')
    plasma_system.add_device(plasma_smelter)
    join_1 = Device('join 1')
    plasma_system.add_device(join_1)
    if bof_steelmaking:
        bof = Device('bof', 'bof')
        plasma_system.add_device(bof)

    # System variables defaults. Can be overwritten by user before mass and energy flows.
    plasma_system.system_vars['capacity factor'] = 0.9
    plasma_system.system_vars['on premises h2 production'] = on_premises_h2_production
    plasma_system.system_vars['bof steelmaking'] = bof_steelmaking
    plasma_system.system_vars['cheap electricity hours'] = 8.0
    plasma_system.system_vars['h2 storage hours of operation'] = 24.0 - plasma_system.system_vars['cheap electricity hours']
    plasma_system.system_vars['feo soluble in slag percent'] = 27.0
    plasma_system.system_vars['plasma temp K'] = 2750
    plasma_system.system_vars['argon molar percent in h2 plasma'] = 0.0
    plasma_system.system_vars['plasma reduction percent'] = 95.0
    plasma_system.system_vars['plasma h2 excess ratio'] = 2.3
    plasma_system.system_vars['o2 injection kg'] = 0.0
    plasma_system.system_vars['plasma torch electro-thermal eff percent'] = 80.0  # MacRae1992
    plasma_system.system_vars['plasma reactor thermal eff percent'] = 85.0  # assumption
    plasma_system.system_vars['steel exit temp K'] = celsius_to_kelvin(1600)
    plasma_system.system_vars['steelmaking bath temp K'] = plasma_system.system_vars['steel exit temp K']
    plasma_system.system_vars['b2 basicity'] = 2.0
    plasma_system.system_vars['b4 basicity'] = 1.8  # 2.1
    plasma_system.system_vars['use mgo slag weight perc'] = True
    plasma_system.system_vars['slag mgo weight perc'] = 7.0
    plasma_system.system_vars['first ore heater device name'] = ore_heater.name
    plasma_system.system_vars['plasma ore heater temp K'] = celsius_to_kelvin(800)
    plasma_system.system_vars['ironmaking device names'] = [plasma_smelter.name]
    plasma_system.system_vars['electrolysis lhv efficiency percent'] = 70.0
    plasma_system.system_vars['hydrogen loops'] = [plasma_system.system_vars['ironmaking device names']]
    plasma_system.system_vars['h2 consuming device names'] = plasma_system.system_vars['ironmaking device names']
    plasma_system.system_vars['scrap perc'] = 0.0
    plasma_system.system_vars['steel carbon perc'] = 1.0
    plasma_system.system_vars['max heat exchanger temp K'] = celsius_to_kelvin(1400)
    plasma_system.system_vars['max heat exchanger eff perc'] = 75.0
    if h2_storage_method is not None:
        plasma_system.system_vars['h2 storage method'] = h2_storage_method
    if bof_steelmaking:
        add_bof_system_vars(plasma_system.system_vars, plasma_smelter.name, bof.name)
    else:
        plasma_system.system_vars['steelmaking device name'] = plasma_smelter.name
    add_h2_plasma_composition(plasma_system)

    if on_premises_h2_production:
        # electrolysis flows
        plasma_system.add_input(water_electrolysis.name, create_dummy_species('H2O'))
        plasma_system.add_output(water_electrolysis.name, create_dummy_species('O2'))
        if h2_storage_method is not None:
            electricity_type = 'cheap electricity'
        else:
            electricity_type = 'base electricity'
        plasma_system.add_input(water_electrolysis.name, EnergyFlow(electricity_type))
        plasma_system.add_output(water_electrolysis.name, EnergyFlow('losses'))
        plasma_system.add_output(water_electrolysis.name, EnergyFlow('chemical'))

        # h2 storage
        if h2_storage_method is not None:
            plasma_system.add_flow(water_electrolysis.name, h2_storage.name, create_dummy_species('h2 rich gas'))
            plasma_system.add_input(h2_storage.name, EnergyFlow('cheap electricity'))
            plasma_system.add_output(h2_storage.name, EnergyFlow('losses'))

    # condenser
    plasma_system.add_output(condenser.name, create_dummy_species('H2O'))
    plasma_system.add_output(condenser.name, EnergyFlow('losses'))
    plasma_system.add_output(condenser.name, create_dummy_mixture('carbon gas'))
    plasma_system.add_flow(h2_heat_exchanger.name, condenser.name, create_dummy_mixture('recycled h2 rich gas'))

    # Add the condenser costs. Based on the cost of a steam condenser.
    # U = 3000.0 W / m2 K, q_dot = 64 MW, T_lmtd = 132 K
    condenser.device_vars['size m2'] = 161.1

    # join
    plasma_system.add_flow(condenser.name, join_1.name, create_dummy_mixture('recycled h2 rich gas'))
    if on_premises_h2_production:
        if h2_storage_method is not None:
            plasma_system.add_flow(h2_storage.name, join_1.name, create_dummy_species('h2 rich gas'))
        else:
            plasma_system.add_flow(water_electrolysis.name, join_1.name, create_dummy_species('h2 rich gas'))
    else:
        plasma_system.add_input(join_1.name, create_dummy_mixture('h2 rich gas'))
        plasma_system.system_vars['input h2 device name'] = join_1.name

    # heat exchanger
    plasma_system.add_flow(join_1.name, h2_heat_exchanger.name, create_dummy_mixture('h2 rich gas'))
    plasma_system.add_flow(plasma_smelter.name, h2_heat_exchanger.name, create_dummy_mixture('recycled h2 rich gas'))
    plasma_system.add_output(h2_heat_exchanger.name, EnergyFlow('losses'))
    
    # Add heat exchanger size. Based on values for the base case.
    # U = 30 W / m2 K, q_dot = 100 MW, dT_lmtd = 200 K
    h2_heat_exchanger.device_vars['size m2'] = 17000.0

    # ore heater
    plasma_system.add_input(ore_heater.name, create_dummy_mixture('ore'))
    plasma_system.add_input(ore_heater.name, EnergyFlow('base electricity'))
    plasma_system.add_output(ore_heater.name, EnergyFlow('losses'))
    plasma_system.add_output(ore_heater.name, create_dummy_species('h2o'))

    # plasma torch
    plasma_system.add_flow(h2_heat_exchanger.name, plasma_torch.name, create_dummy_mixture('h2 rich gas'))
    plasma_system.add_input(plasma_torch.name, EnergyFlow('base electricity'))
    plasma_system.add_output(plasma_torch.name, EnergyFlow('losses'))

    # plasma smelter
    plasma_system.add_flow(ore_heater.name, plasma_smelter.name, create_dummy_mixture('ore'))
    plasma_system.add_flow(plasma_torch.name, plasma_smelter.name, create_dummy_mixture('plasma h2 rich gas'))
    plasma_system.add_output(plasma_smelter.name, EnergyFlow('losses'))
    plasma_system.add_input(plasma_smelter.name, EnergyFlow('chemical'))
    plasma_system.add_input(plasma_smelter.name, create_dummy_species('carbon'))
    plasma_system.add_input(plasma_smelter.name, create_dummy_mixture('flux'))
    plasma_system.add_input(plasma_smelter.name, create_dummy_species('O2'))
    plasma_system.add_input(plasma_smelter.name, create_dummy_species('scrap'))
    plasma_system.add_output(plasma_smelter.name, create_dummy_mixture('slag'))
    if bof_steelmaking:
        add_bof_flows(plasma_system, plasma_smelter.name, bof.name)
    else:
        plasma_system.add_output(plasma_smelter.name, create_dummy_mixture('steel'))

    return plasma_system


def create_dri_eaf_system(system_name='dri eaf steelmaking', 
                          on_premises_h2_production: bool = True,
                          h2_storage_method: Optional[str] = 'salt caverns',
                          annual_capacity_tls: float = 1.5e6,
                          plant_lifetime_years: float = 20.0) -> System:
    dri_eaf_system = System(system_name, annual_capacity_tls, plant_lifetime_years)

    if on_premises_h2_production:
        water_electrolysis = Device('water electrolysis', 'electrolyser')
        dri_eaf_system.add_device(water_electrolysis)
        if h2_storage_method is not None:
            h2_storage = Device('h2 storage', h2_storage_method)
            dri_eaf_system.add_device(h2_storage)
    h2_heat_exchanger = Device('h2 heat exchanger', 'gas-gas heat exchanger')
    dri_eaf_system.add_device(h2_heat_exchanger)
    join_1 = Device('join 1')
    dri_eaf_system.add_device(join_1)
    h2_heater_2 = Device('h2 heater 2')
    dri_eaf_system.add_device(h2_heater_2)
    condenser = Device('condenser and scrubber', 'steam condenser and scrubber')
    dri_eaf_system.add_device(condenser)
    ore_heater = Device('ore heater', 'ore heater')
    dri_eaf_system.add_device(ore_heater)
    fluidized_bed_1 = Device('fluidized bed 1', 'fluidized bed')
    dri_eaf_system.add_device(fluidized_bed_1)
    briquetting = Device('briquetting','briquetting')
    dri_eaf_system.add_device(briquetting)
    eaf = Device('eaf', 'eaf')
    dri_eaf_system.add_device(eaf)

    # System variables defaults. Can be overwritten by user before mass and energy flows.
    dri_eaf_system.system_vars['capacity factor'] = 0.9
    dri_eaf_system.system_vars['on premises h2 production'] = on_premises_h2_production
    dri_eaf_system.system_vars['cheap electricity hours'] = 8.0
    dri_eaf_system.system_vars['h2 storage hours of operation'] = 24.0 - dri_eaf_system.system_vars['cheap electricity hours']
    dri_eaf_system.system_vars['fluidized beds reduction percent'] = 94.0
    dri_eaf_system.system_vars['fluidized beds temp range'] = 200.0
    dri_eaf_system.system_vars['steelmaking device name'] = eaf.name
    dri_eaf_system.system_vars['feo soluble in slag percent'] = 27.0
    dri_eaf_system.system_vars['steel exit temp K'] = celsius_to_kelvin(1600)
    dri_eaf_system.system_vars['b2 basicity'] = 2.0
    dri_eaf_system.system_vars['b4 basicity'] = 1.8
    dri_eaf_system.system_vars['use mgo slag weight perc'] = True
    dri_eaf_system.system_vars['slag mgo weight perc'] = 7.0
    dri_eaf_system.system_vars['first ore heater device name'] = ore_heater.name
    dri_eaf_system.system_vars['ore heater temp K'] = celsius_to_kelvin(550)
    dri_eaf_system.system_vars['ironmaking device names'] = [fluidized_bed_1.name]
    dri_eaf_system.system_vars['fluidized beds h2 excess ratio'] = 3.84
    dri_eaf_system.system_vars['o2 injection kg'] = 10.0
    dri_eaf_system.system_vars['electrolysis lhv efficiency percent'] = 70.0
    dri_eaf_system.system_vars['hydrogen loops'] = [dri_eaf_system.system_vars['ironmaking device names']]
    dri_eaf_system.system_vars['h2 consuming device names'] = dri_eaf_system.system_vars['ironmaking device names']
    dri_eaf_system.system_vars['scrap perc'] = 0.0
    dri_eaf_system.system_vars['steel carbon perc'] = 1.0
    dri_eaf_system.system_vars['max heat exchanger temp K'] = celsius_to_kelvin(1400)
    dri_eaf_system.system_vars['max heat exchanger eff perc'] = 75.0
    if h2_storage_method is not None:
        dri_eaf_system.system_vars['h2 storage method'] = h2_storage_method

    if on_premises_h2_production:
        # electrolysis flows
        dri_eaf_system.add_input(water_electrolysis.name, create_dummy_species('H2O'))
        dri_eaf_system.add_output(water_electrolysis.name, create_dummy_species('O2'))
        if h2_storage_method is not None:
            electricity_type = 'cheap electricity'
        else:
            electricity_type = 'base electricity'
        dri_eaf_system.add_input(water_electrolysis.name, EnergyFlow(electricity_type))
        dri_eaf_system.add_output(water_electrolysis.name, EnergyFlow('losses'))
        dri_eaf_system.add_output(water_electrolysis.name, EnergyFlow('chemical'))

        # h2 storage
        if h2_storage_method is not None:
            dri_eaf_system.add_flow(water_electrolysis.name, h2_storage.name, create_dummy_species('h2 rich gas'))
            dri_eaf_system.add_input(h2_storage.name, EnergyFlow('cheap electricity'))
            dri_eaf_system.add_output(h2_storage.name, EnergyFlow('losses'))

    # condenser
    dri_eaf_system.add_output(condenser.name, create_dummy_species('H2O'))
    dri_eaf_system.add_output(condenser.name, EnergyFlow('losses'))
    dri_eaf_system.add_flow(h2_heat_exchanger.name, condenser.name, create_dummy_mixture('recycled h2 rich gas'))

    # Add the condenser costs. Based on the cost of a steam condenser.
    # U = 3000.0 W / m2 K, q_dot = 64 MW, T_lmtd = 132 K
    condenser.device_vars['size m2'] = 161.1

    # join
    dri_eaf_system.add_flow(condenser.name, join_1.name, create_dummy_mixture('recycled h2 rich gas'))
    if on_premises_h2_production:
        if h2_storage_method is not None:
            dri_eaf_system.add_flow(h2_storage.name, join_1.name, create_dummy_species('h2 rich gas'))
        else:
            dri_eaf_system.add_flow(water_electrolysis.name, join_1.name, create_dummy_species('h2 rich gas'))
    else:
        dri_eaf_system.add_input(join_1.name, create_dummy_mixture('h2 rich gas'))
        dri_eaf_system.system_vars['input h2 device name'] = join_1.name

    # heat exchanger
    dri_eaf_system.add_flow(join_1.name, h2_heat_exchanger.name, create_dummy_mixture('h2 rich gas'))
    dri_eaf_system.add_flow(fluidized_bed_1.name, h2_heat_exchanger.name, create_dummy_mixture('recycled h2 rich gas'))
    dri_eaf_system.add_output(h2_heat_exchanger.name, EnergyFlow('losses'))

    # Add heat exchanger size. Based on values for the base case.
    # U = 30 W / m2 K, q_dot = 147 MW, dT_lmtd = 157 K
    h2_heat_exchanger.device_vars['size m2'] = 31000.0

    # ore heater
    dri_eaf_system.add_input(ore_heater.name, create_dummy_mixture('ore'))
    dri_eaf_system.add_input(ore_heater.name, EnergyFlow('base electricity'))
    dri_eaf_system.add_output(ore_heater.name, EnergyFlow('losses'))
    dri_eaf_system.add_output(ore_heater.name, create_dummy_species('h2o'))

    # fluidized bed 1
    dri_eaf_system.add_flow(ore_heater.name, fluidized_bed_1.name, create_dummy_mixture('ore'))
    dri_eaf_system.add_flow(h2_heater_2.name, fluidized_bed_1.name, create_dummy_mixture('h2 rich gas'))
    dri_eaf_system.add_input(fluidized_bed_1.name, EnergyFlow('chemical'))
    dri_eaf_system.add_output(fluidized_bed_1.name, EnergyFlow('losses'))

    # heater 2
    dri_eaf_system.add_flow(h2_heat_exchanger.name, h2_heater_2.name, create_dummy_mixture('h2 rich gas'))
    dri_eaf_system.add_input(h2_heater_2.name, EnergyFlow('base electricity'))
    dri_eaf_system.add_output(h2_heater_2.name, EnergyFlow('losses'))

    # briquetting
    dri_eaf_system.add_flow(fluidized_bed_1.name, briquetting.name, create_dummy_mixture('dri'))

    # eaf
    dri_eaf_system.add_flow(briquetting.name, eaf.name, create_dummy_mixture('hbi'))
    dri_eaf_system.add_input(eaf.name, EnergyFlow('base electricity'))
    dri_eaf_system.add_output(eaf.name, EnergyFlow('losses'))
    dri_eaf_system.add_input(eaf.name, create_dummy_species('electrode'))
    dri_eaf_system.add_input(eaf.name, EnergyFlow('chemical'))
    dri_eaf_system.add_input(eaf.name, create_dummy_species('carbon'))
    dri_eaf_system.add_input(eaf.name, create_dummy_mixture('flux'))
    dri_eaf_system.add_input(eaf.name, create_dummy_species('O2'))
    dri_eaf_system.add_input(eaf.name, create_dummy_mixture('infiltrated air'))
    dri_eaf_system.add_input(eaf.name, create_dummy_species('scrap'))
    dri_eaf_system.add_output(eaf.name, create_dummy_mixture('infiltrated air'))
    dri_eaf_system.add_output(eaf.name, create_dummy_mixture('carbon gas'))
    dri_eaf_system.add_output(eaf.name, create_dummy_mixture('slag'))
    dri_eaf_system.add_output(eaf.name, create_dummy_mixture('steel'))

    return dri_eaf_system


def create_hybrid_system(system_name='hybrid steelmaking',  
                         on_premises_h2_production: bool = True,
                         h2_storage_method: Optional[str] = 'salt caverns', 
                         prereduction_perc: float = 33.33, 
                         annual_capacity_tls: float = 1.5e6, 
                         plant_lifetime_years: float = 20.0,
                         bof_steelmaking: bool = False) -> System:
    hybrid_system = System(system_name, annual_capacity_tls, plant_lifetime_years)

    if on_premises_h2_production:
        water_electrolysis = Device('water electrolysis', 'electrolyser')
        hybrid_system.add_device(water_electrolysis)
        if h2_storage_method is not None:
            h2_storage = Device('h2 storage', h2_storage_method)
            hybrid_system.add_device(h2_storage)
    h2_heat_exchanger_1 = Device('h2 heat exchanger 1','gas-gas heat exchanger')
    hybrid_system.add_device(h2_heat_exchanger_1)
    h2_heat_exchanger_2 = Device('h2 heat exchanger 2', 'high temp gas-gas heat exchanger')
    hybrid_system.add_device(h2_heat_exchanger_2)
    condenser_1 = Device('condenser and scrubber 1', 'steam condenser and scrubber')
    hybrid_system.add_device(condenser_1)
    condenser_2 = Device('condenser and scrubber 2', 'steam condenser and scrubber')
    hybrid_system.add_device(condenser_2)
    ore_heater = Device('ore heater', 'ore heater')
    hybrid_system.add_device(ore_heater)
    h2_heater_2 = Device('h2 heater 2', 'gas heater')
    hybrid_system.add_device(h2_heater_2)
    fluidized_bed_1 = Device('fluidized bed 1', 'fluidized bed')
    hybrid_system.add_device(fluidized_bed_1)
    briquetting = Device('briquetting')
    hybrid_system.add_device(briquetting)
    ore_heater_2 = Device('ore heater 2', 'ore heater')
    hybrid_system.add_device(ore_heater_2)
    plasma_torch = Device('plasma torch')
    hybrid_system.add_device(plasma_torch)
    plasma_smelter = Device('plasma smelter', 'plasma smelter')
    hybrid_system.add_device(plasma_smelter)
    join_1 = Device('join 1')
    hybrid_system.add_device(join_1)
    join_2 = Device('join 2')
    hybrid_system.add_device(join_2)
    join_3 = Device('join 3')
    hybrid_system.add_device(join_3)
    if bof_steelmaking:
        bof = Device('bof', 'bof')
        hybrid_system.add_device(bof)

    ironmaking_device_names = [fluidized_bed_1.name]

    # System variables defaults. Can be overwritten by user before mass and energy flows.
    hybrid_system.system_vars['capacity factor'] = 0.9
    hybrid_system.system_vars['on premises h2 production'] = on_premises_h2_production
    hybrid_system.system_vars['bof steelmaking'] = bof_steelmaking
    hybrid_system.system_vars['cheap electricity hours'] = 8.0
    hybrid_system.system_vars['h2 storage hours of operation'] = 24.0 - hybrid_system.system_vars['cheap electricity hours']
    hybrid_system.system_vars['fluidized beds reduction percent'] = prereduction_perc
    hybrid_system.system_vars['fluidized beds temp range'] = 200.0
    hybrid_system.system_vars['feo soluble in slag percent'] = 27.0
    hybrid_system.system_vars['plasma temp K'] = 2750 
    hybrid_system.system_vars['plasma reduction percent'] = 95.0
    hybrid_system.system_vars['plasma torch electro-thermal eff percent'] = 80.0  # MacRae1992
    hybrid_system.system_vars['plasma reactor thermal eff percent'] = 85.0  # assumption
    hybrid_system.system_vars['steel exit temp K'] = celsius_to_kelvin(1600)
    hybrid_system.system_vars['o2 injection kg'] = 0.0
    hybrid_system.system_vars['plasma h2 excess ratio'] = 2.3
    hybrid_system.system_vars['steelmaking bath temp K'] = hybrid_system.system_vars['steel exit temp K']
    hybrid_system.system_vars['b2 basicity'] = 2.0
    hybrid_system.system_vars['b4 basicity'] = 1.8  # 2.1
    hybrid_system.system_vars['use mgo slag weight perc'] = True
    hybrid_system.system_vars['slag mgo weight perc'] = 7.0
    hybrid_system.system_vars['first ore heater device name'] = ore_heater.name
    hybrid_system.system_vars['plasma ore heater device name'] = ore_heater_2.name
    hybrid_system.system_vars['ore heater temp K'] = celsius_to_kelvin(550)
    hybrid_system.system_vars['plasma ore heater temp K'] = celsius_to_kelvin(800)
    hybrid_system.system_vars['ironmaking device names'] = ironmaking_device_names
    hybrid_system.system_vars['fluidized beds h2 excess ratio'] = 3.84
    hybrid_system.system_vars['electrolysis lhv efficiency percent'] = 70.0
    hybrid_system.system_vars['hydrogen loops'] = [ironmaking_device_names, [plasma_smelter.name]]
    hybrid_system.system_vars['h2 consuming device names'] = ironmaking_device_names + [plasma_smelter.name]
    hybrid_system.system_vars['scrap perc'] = 0.0
    hybrid_system.system_vars['steel carbon perc'] = 1.0
    hybrid_system.system_vars['max heat exchanger temp K'] = celsius_to_kelvin(1400)
    hybrid_system.system_vars['max heat exchanger eff perc'] = 75.0
    if h2_storage_method is not None:
        hybrid_system.system_vars['h2 storage method'] = h2_storage_method
    if bof_steelmaking:
        add_bof_system_vars(hybrid_system.system_vars, plasma_smelter.name, bof.name)
    else:
        hybrid_system.system_vars['steelmaking device name'] = plasma_smelter.name
    add_h2_plasma_composition(hybrid_system)

    # electrolysis flows
    if on_premises_h2_production:
        hybrid_system.add_input(water_electrolysis.name, create_dummy_species('H2O'))
        hybrid_system.add_output(water_electrolysis.name, create_dummy_species('O2'))
        if h2_storage_method is not None:
            electricity_type = 'cheap electricity'
        else:
            electricity_type = 'base electricity'
        hybrid_system.add_input(water_electrolysis.name, EnergyFlow(electricity_type))
        hybrid_system.add_output(water_electrolysis.name, EnergyFlow('losses'))
        hybrid_system.add_output(water_electrolysis.name, EnergyFlow('chemical'))

        # h2 storage
        if h2_storage_method is not None:
            hybrid_system.add_flow(water_electrolysis.name, h2_storage.name, create_dummy_species('h2 rich gas'))
            hybrid_system.add_input(h2_storage.name, EnergyFlow('cheap electricity'))
            hybrid_system.add_output(h2_storage.name, EnergyFlow('losses'))

    # join 3
    if on_premises_h2_production:
        if h2_storage_method is not None:
            hybrid_system.add_flow(h2_storage.name, join_3.name, create_dummy_species('h2 rich gas'))
        else:
            hybrid_system.add_flow(water_electrolysis.name, join_3.name, create_dummy_species('h2 rich gas'))
    else:
        hybrid_system.add_input(join_3.name, create_dummy_mixture('h2 rich gas'))
        hybrid_system.system_vars['input h2 device name'] = join_3.name


    # join 2
    hybrid_system.add_flow(condenser_2.name, join_2.name, create_dummy_mixture('recycled h2 rich gas'))
    hybrid_system.add_flow(join_3.name, join_2.name, create_dummy_mixture('h2 rich gas 2'))

    # join 1
    hybrid_system.add_flow(condenser_1.name, join_1.name, create_dummy_mixture('recycled h2 rich gas'))
    hybrid_system.add_flow(join_3.name, join_1.name, create_dummy_mixture('h2 rich gas 1'))

    # condenser 2   
    hybrid_system.add_output(condenser_2.name, create_dummy_species('H2O'))
    hybrid_system.add_output(condenser_2.name, EnergyFlow('losses'))
    hybrid_system.add_output(condenser_2.name, create_dummy_mixture('carbon gas'))
    hybrid_system.add_flow(h2_heat_exchanger_2.name, condenser_2.name, create_dummy_mixture('recycled h2 rich gas'))

    # condenser 1
    hybrid_system.add_output(condenser_1.name, create_dummy_species('H2O'))
    hybrid_system.add_output(condenser_1.name, EnergyFlow('losses'))
    hybrid_system.add_output(condenser_1.name, create_dummy_mixture('carbon gas'))
    hybrid_system.add_flow(h2_heat_exchanger_1.name, condenser_1.name, create_dummy_mixture('recycled h2 rich gas'))

    # Add the condenser costs. Based on the cost of a steam condenser.
    # U = 3000.0 W / m2 K, q_dot = 32 MW, T_lmtd = 132 K
    condenser_1.device_vars['size m2'] = 80.8 
    condenser_2.device_vars['size m2'] = 80.8 

    # heat exchanger 2
    hybrid_system.add_flow(join_2.name, h2_heat_exchanger_2.name, create_dummy_mixture('h2 rich gas'))
    hybrid_system.add_flow(plasma_smelter.name, h2_heat_exchanger_2.name, create_dummy_mixture('recycled h2 rich gas'))
    hybrid_system.add_output(h2_heat_exchanger_2.name, EnergyFlow('losses'))

    # heat exchanger 1
    hybrid_system.add_flow(join_1.name, h2_heat_exchanger_1.name, create_dummy_mixture('h2 rich gas'))
    hybrid_system.add_flow(fluidized_bed_1.name, h2_heat_exchanger_1.name, create_dummy_mixture('recycled h2 rich gas'))
    hybrid_system.add_output(h2_heat_exchanger_1.name, EnergyFlow('losses'))

    # Add heat exchanger sizes. Based on values for the base case for a pure plasma 
    # and a pure HDR-EAF system, scaled by the desired pre-reduction degrere.
    # U = 30 W / m2 K, q_dot = 147 MW, dT_lmtd = 157 K, at a maximum when pre-reduction degree is 100.0
    h2_heat_exchanger_1.device_vars['size m2'] = 31000.0 * prereduction_perc * 0.01

    # U = 30 W / m2 K, q_dot = 100 MW, dT_lmtd = 200 K, at a maximum when pre-reduction degree is 0.0
    h2_heat_exchanger_2.device_vars['size m2'] = 17000.0 * (1 - prereduction_perc * 0.01)

    # ore heater
    hybrid_system.add_input(ore_heater.name, create_dummy_mixture('ore'))
    hybrid_system.add_input(ore_heater.name, EnergyFlow('base electricity'))
    hybrid_system.add_output(ore_heater.name, EnergyFlow('losses'))
    hybrid_system.add_output(ore_heater.name, create_dummy_species('h2o'))

    # fluidized bed 1
    hybrid_system.add_flow(ore_heater.name, fluidized_bed_1.name, create_dummy_mixture('ore'))
    hybrid_system.add_flow(h2_heater_2.name, fluidized_bed_1.name, create_dummy_mixture('h2 rich gas'))
    hybrid_system.add_input(fluidized_bed_1.name, EnergyFlow('chemical'))
    hybrid_system.add_output(fluidized_bed_1.name, EnergyFlow('losses'))

    # heater 2
    hybrid_system.add_flow(h2_heat_exchanger_1.name, h2_heater_2.name, create_dummy_mixture('h2 rich gas'))
    hybrid_system.add_input(h2_heater_2.name, EnergyFlow('base electricity'))
    hybrid_system.add_output(h2_heater_2.name, EnergyFlow('losses'))

    # briquetting
    hybrid_system.add_flow(ironmaking_device_names[-1], briquetting.name, create_dummy_mixture('dri'))

    # ore heater 2
    hybrid_system.add_flow(briquetting.name, ore_heater_2.name, create_dummy_mixture('hbi'))
    hybrid_system.add_input(ore_heater_2.name, EnergyFlow('base electricity'))
    hybrid_system.add_output(ore_heater_2.name, EnergyFlow('losses'))
    
    # plasma torch
    hybrid_system.add_flow(h2_heat_exchanger_2.name, plasma_torch.name, create_dummy_mixture('h2 rich gas'))
    hybrid_system.add_input(plasma_torch.name, EnergyFlow('base electricity'))
    hybrid_system.add_output(plasma_torch.name, EnergyFlow('losses'))

    # plasma smelter
    hybrid_system.add_flow(ore_heater_2.name, plasma_smelter.name, create_dummy_mixture('hbi'))
    hybrid_system.add_flow(plasma_torch.name, plasma_smelter.name, create_dummy_mixture('plasma h2 rich gas'))
    hybrid_system.add_input(plasma_smelter.name, EnergyFlow('chemical'))
    hybrid_system.add_output(plasma_smelter.name, EnergyFlow('losses'))
    hybrid_system.add_input(plasma_smelter.name, create_dummy_species('carbon'))
    hybrid_system.add_input(plasma_smelter.name, create_dummy_mixture('flux'))
    hybrid_system.add_input(plasma_smelter.name, create_dummy_species('O2'))
    hybrid_system.add_input(plasma_smelter.name, create_dummy_species('scrap'))
    hybrid_system.add_output(plasma_smelter.name, create_dummy_mixture('slag'))
    if bof_steelmaking:
        add_bof_flows(hybrid_system, plasma_smelter.name, bof.name)
    else:
        hybrid_system.add_output(plasma_smelter.name, create_dummy_mixture('steel'))

    return hybrid_system


# system creator helpers
def add_bof_system_vars(system_vars: Dict[str, Any], ironmaking_device_name: str, bof_name: str):
    system_vars['feo soluble in slag percent'] = 1.0
    system_vars['b2 basicity'] = 1.0
    system_vars['b4 basicity'] = 1.1
    system_vars['slag mgo weight perc'] = 7.0  # Check what we expect in a melter / blast furnace
    system_vars['steelmaking device name'] = bof_name
    system_vars['ironmaking device name'] = ironmaking_device_name
    system_vars['bof b2 basicity'] = 2.5
    system_vars['bof b4 basicity'] = 2.5
    system_vars['bof slag mgo weight perc'] = 7.0
    system_vars['bof feo in slag perc'] = 12.5  # turkdogan1996 8.2.1a
    system_vars['bof hot metal Si perc'] = 0.4  # turkdogan1996 8.2
    system_vars['bof hot metal C perc'] = 2.0  # perc C from the ironmaking step TODO could reduce this to min for heat balance


def add_bof_flows(system: System, plasma_smelter_name: str, bof_name: str):
    system.add_flow(plasma_smelter_name, bof_name, create_dummy_mixture('steel'))
    system.add_output(bof_name, EnergyFlow('losses'))
    system.add_input(bof_name, EnergyFlow('chemical'))
    system.add_input(bof_name, create_dummy_mixture('flux'))
    system.add_input(bof_name, create_dummy_species('O2'))
    system.add_input(bof_name, create_dummy_species('scrap'))
    system.add_output(bof_name, create_dummy_mixture('slag'))
    system.add_output(bof_name, create_dummy_mixture('steel'))
    system.add_output(bof_name, create_dummy_mixture('carbon gas'))


nasa_gas_species = {s.name: s for s in ct.Species.list_from_file('nasa_gas.yaml')}
def add_h2_plasma_composition(system: System):
    if 'plasma temp K' not in system.system_vars:
        raise Exception("Could not add plasma composition. No 'plasma temp K' system variable.")
    
    h2_plasma = ct.Solution(thermo='ideal-gas', species=[nasa_gas_species['H2'],
                                                        nasa_gas_species['H2+'],
                                                        nasa_gas_species['H2-'],
                                                        nasa_gas_species['H'],
                                                        nasa_gas_species['H+'],
                                                        nasa_gas_species['H-'],
                                                        nasa_gas_species['Electron']])
    h2_plasma.TPX = system.system_vars['plasma temp K'], ct.one_atm, 'H2:1.0'
    h2_plasma.equilibrate('TP')
    h2_fraction = h2_plasma.X[0]
    h_fraction = h2_plasma.X[3]
    if not math.isclose(h2_fraction + h_fraction, 1.0):
        raise Exception("Could not add plasma composition. Expect H2 and H fractions do not sum to 1.")
    system.system_vars['plasma h2 fraction (excl. Ar and H2O)'] = h2_fraction
    system.system_vars['plasma h fraction (excl. Ar and H2O)'] = h_fraction


if __name__ == "__main__":
    main()
