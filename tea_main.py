#!/usr/bin/env python3

import argparse
import copy
import datetime
import csv
import os
import tempfile
from typing import List, Dict, Any, Optional
import matplotlib.pyplot as plt
import numpy as np
import shutil

from create_plants import create_dri_eaf_system, create_hybrid_system, create_plasma_system
from mass_energy_flow import solve_mass_energy_flow, add_dri_eaf_mass_and_energy, add_hybrid_mass_and_energy,\
                             add_plasma_mass_and_energy, electricity_demand_per_major_device, report_slag_composition
from plant_costs import load_prices_from_csv, add_steel_plant_lcop, break_even_co2e_price, co2e_per_tonne_steel
from plot_helpers import histogram_labels_from_datasets, add_stacked_histogram_data_to_axis, add_titles_to_axis
from sensitivity import sensitivity_analysis_runner_from_csv, report_sensitivity_analysis_for_system
from system import System

def main():
    ## Setup
    args = parse_args()
    prices = load_prices_from_csv(args.price_file)
    config = load_config_from_csv(args.config_file)
    systems = create_systems(config)
    system_names = [s.name for s in systems]
    
    run_sensitivity_analysis = bool(args.sensitivity_file)
    if run_sensitivity_analysis:
        sensitivity_runner = sensitivity_analysis_runner_from_csv(args.sensitivity_file)
        if sensitivity_runner:
            sensitivity_runner.systems = copy.deepcopy(systems)
        else:
            run_sensitivity_analysis = False

    if args.render_dir:
        render_systems(systems, args.render_dir)

    ## Solve
    print("Solving mass and energy flow and calculating cost...")
    for s in systems:
        solve_mass_energy_flow(s, s.add_mass_energy_flow_func, args.verbose)
        add_steel_plant_lcop(s, prices, args.verbose)
    print("Done.")

    ## Report
    if not run_sensitivity_analysis:
        generate_lcop_report(systems)

        if args.verbose:
            for s in systems:
                report_slag_composition(s)

    ## Sensitivity Analysis
    if run_sensitivity_analysis:
        tmp_dir = tempfile.gettempdir()
        output_dir = os.path.join(tmp_dir, f"TEA_SA_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(output_dir)
        generate_lcop_report(systems, output_dir, args.config_file, args.price_file, args.sensitivity_file)
        
        print("Running sensitivity analysis...")
        sensitivity_indicators = sensitivity_runner.run(prices)
        for s, si in zip(sensitivity_runner.systems, sensitivity_indicators):
            report_sensitivity_analysis_for_system(output_dir, s, si)
        print(f"Done. Results saved to {output_dir}")
        

    ## Plots
    if args.mass_flow:
        inputs_for_systems = [s.system_inputs(ignore_flows_named=['infiltrated air'], separate_mixtures_named=['h2 rich gas'], mass_flow_only=True) for s in systems]
        input_mass_labels = histogram_labels_from_datasets(inputs_for_systems)
        _, input_mass_ax = plt.subplots()
        add_stacked_histogram_data_to_axis(input_mass_ax, system_names, input_mass_labels, inputs_for_systems)
        add_titles_to_axis(input_mass_ax, 'Input Mass Flow / Tonne Liquid Steel', 'Mass (kg)')

        outputs_for_systems = [s.system_outputs(ignore_flows_named=['infiltrated air'], mass_flow_only=True) for s in systems]
        output_mass_labels = histogram_labels_from_datasets(outputs_for_systems)
        _, output_mass_ax = plt.subplots()
        add_stacked_histogram_data_to_axis(output_mass_ax, system_names, output_mass_labels, outputs_for_systems)
        add_titles_to_axis(output_mass_ax, 'Output Mass Flow / Tonne Liquid Steel', 'Mass (kg)')

    if args.energy_flow:
        electricity_for_systems = [electricity_demand_per_major_device(s) for s in systems]
        electricity_labels = histogram_labels_from_datasets(electricity_for_systems)
        _, energy_ax = plt.subplots()
        add_stacked_histogram_data_to_axis(energy_ax, system_names, electricity_labels, electricity_for_systems)
        add_titles_to_axis(energy_ax, 'Electricity Demand / Tonne Liquid Steel', 'Energy (GJ)')

    lcop_itemised_for_systems = [s.lcop_breakdown for s in systems]
    lcop_labels = histogram_labels_from_datasets(lcop_itemised_for_systems)
    _, lcop_ax = plt.subplots()
    add_stacked_histogram_data_to_axis(lcop_ax, system_names, lcop_labels, lcop_itemised_for_systems)
    add_titles_to_axis(lcop_ax, 'Levelised Cost of Liquid Steel', 'LCOS [USD/tls]')

    plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Technoeconomic assessment of low-emission steelmaking using hydrogen plasma.')
    parser.add_argument('-p', '--price_file', help='path to the csv file containing capex and commondity prices.', required=False, default='prices_default.csv')
    parser.add_argument('-c', '--config_file', help='path to the csv file containing the system configuration.', required=False, default='config_default.csv')
    parser.add_argument('-r', '--render_dir', help='path to directory to render the steelplant system diagrams.', required=False, default=None)
    parser.add_argument('-s', '--sensitivity_file', help='path to the csv file containing the sensitivity analysis settings.', required=False, default=None)
    parser.add_argument('-m', '--mass_flow', help='show the mass flow bar chart boolean flag.', required=False, action='store_true')
    parser.add_argument('-e', '--energy_flow', help='show the enery flow bar chart boolean flag.', required=False, action='store_true')
    parser.add_argument('-v', '--verbose', help='when enabled, print / log debug messages.', required=False, action='store_true')
    args = parser.parse_args()
    return args


def create_systems(config: Dict[str, Dict[str, Any]]) -> List[System]:
    ## Create the system objects
    on_prem_h2, h2_storage, annual_steel, lifetime = get_important_config_entries("DRI-EAF", config)
    dri_eaf_system = create_dri_eaf_system("DRI-EAF", on_prem_h2, h2_storage, annual_steel, lifetime)
    on_prem_h2, h2_storage, annual_steel, lifetime = get_important_config_entries("Plasma", config)
    plasma_system = create_plasma_system("Plasma", on_prem_h2, h2_storage, annual_steel, lifetime)
    on_prem_h2, h2_storage, annual_steel, lifetime = get_important_config_entries("Plasma Ar-H2", config)
    plasma_bof_system = create_plasma_system("Plasma BOF", on_prem_h2, h2_storage, annual_steel, lifetime, bof_steelmaking=True)
    on_prem_h2, h2_storage, annual_steel, lifetime = get_important_config_entries("Hybrid 33", config)
    hybrid33_system = create_hybrid_system("Hybrid 33", on_prem_h2, h2_storage, 33.33, annual_steel, lifetime)
    on_prem_h2, h2_storage, annual_steel, lifetime = get_important_config_entries("Hybrid 55", config)
    hybrid55_system = create_hybrid_system("Hybrid 55", on_prem_h2, h2_storage, 55.0, annual_steel, lifetime)

    dri_eaf_system.add_mass_energy_flow_func = add_dri_eaf_mass_and_energy
    plasma_system.add_mass_energy_flow_func = add_plasma_mass_and_energy
    plasma_bof_system.add_mass_energy_flow_func = add_plasma_mass_and_energy
    hybrid33_system.add_mass_energy_flow_func = add_hybrid_mass_and_energy
    hybrid55_system.add_mass_energy_flow_func = add_hybrid_mass_and_energy

    run_prereduction_sensitivity = False
    if run_prereduction_sensitivity:
        systems = []
        for rd in np.linspace(5.0, 90.0, 18):
            on_prem_h2, h2_storage, annual_steel, lifetime = get_important_config_entries("Hybrid 33", config)
            hybrid33_system = create_hybrid_system(f"{rd}", on_prem_h2, h2_storage, rd, annual_steel, lifetime)
            hybrid33_system.add_mass_energy_flow_func = add_hybrid_mass_and_energy
            systems.append(hybrid33_system)
    else:
        systems = [dri_eaf_system,
                   plasma_system,
                   plasma_bof_system,
                   hybrid33_system]

    # Overwrite system vars here to modify behaviour
    default_config = config.get("all", {})
    for entry in default_config:
        for system in systems:
            system.system_vars[entry] = default_config[entry]

    for system in systems:
        system_specific_config = config.get(system.name.lower(), {})
        for entry in system_specific_config:
            system.system_vars[entry] = system_specific_config[entry]

    return systems


def render_systems(systems: List[System], render_dir: str):
    for s in systems:
        s.render(render_dir, view=True)


def load_config_from_csv(filename: str) -> Dict[str, Dict[str, Any]]:
    config = {}
    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # skip the title row
        for row in reader:
            if not row:
                continue
            system_name = row[0].strip().lower()
            variable_name = row[1].strip()
            variable_type = row[3].strip().lower()
            variable_value = row[2].strip()
            if variable_type.lower() == "string":
                pass
            elif variable_type.lower() == "number":
                variable_value = float(variable_value)
            elif variable_type.lower() == "boolean":
                variable_value = variable_value.lower() == "true"
            else:
                raise ValueError(f"Unrecognised variable type {variable_type} in config file {filename}.")

            if system_name in config:
                config[system_name][variable_name] = variable_value
            else:
                config[system_name] = {variable_name: variable_value}
    
    return config


def get_important_config_entries(system_name: str, config: Dict[str, Dict[str, Any]]):
    system_name = system_name.lower()

    system_specific_config = config.get(system_name, {})
    default_config = config.get("all", {})

    try:
        on_premises_h2_production = system_specific_config["on premises h2 production"]
    except KeyError:
        on_premises_h2_production = default_config.get("on premises h2 production", False)

    try:
        h2_storage_type = system_specific_config["h2 storage type"]
    except KeyError:
        h2_storage_type = default_config.get("h2 storage type", "salt caverns")

    try:
        annual_steel_production_tonnes = system_specific_config["annual steel production tonnes"]
    except KeyError:
        annual_steel_production_tonnes = default_config.get("annual steel production tonnes", 1.5e6)

    try:
        plant_lifetime_years = system_specific_config["plant lifetime years"]
    except KeyError:
        plant_lifetime_years = default_config.get("plant lifetime years", 20.0)

    return on_premises_h2_production, h2_storage_type, annual_steel_production_tonnes, plant_lifetime_years


def generate_lcop_report(systems: List[System], output_dir: Optional[str]=None, 
                         config_file: Optional[str]=None, prices_file: Optional[str]=None, sensitivity_file: Optional[str]=None):
    if output_dir is None:
        for s in systems:
            print(f"{s.name} total lcop [USD] = {s.lcop():.2f}")
            for k, v in s.lcop_breakdown.items():
                print(f"    {k} = {v:.2f}")
            print(f"    CO2e emissions [kg/tls] = {co2e_per_tonne_steel(s)}")
            print(f"    CO2e BF-BOF breakeven price [USD/t CO2e] = {break_even_co2e_price(s)}")
    else:
        file_path = os.path.join(output_dir, "lcop.csv")
        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["System Name", "Item", "LCOP [USD]"])
            for system in systems:
                writer.writerow([system.name, "Total", f"{system.lcop():.2f}"])
                for k, v in system.lcop_breakdown.items():
                    writer.writerow(["", f"{k}", f"{v:.2f}"])

        # Copy config files to the output_dir
        if config_file is not None:
            shutil.copy(config_file, os.path.join(output_dir, os.path.basename(config_file)))
        if prices_file is not None:
            shutil.copy(prices_file, os.path.join(output_dir, os.path.basename(prices_file)))
        if sensitivity_file is not None:
            shutil.copy(sensitivity_file, os.path.join(output_dir, os.path.basename(sensitivity_file)))
                    

if __name__ == '__main__':
    main()
