# Plasma Steelmaking Technoeconomic Analysis
## About
This project is a technoeconomic assessment of four different low-emission steel plants; three plasma-based steelmaking processes and the more established hydrogen direct reduction – electric arc furnace (HDR-EAF) pathway. The code accompanies a paper that is currently under peer review.

```
@article{cooper2024technoeconomic,
  title={Technoeconomic analysis of low-emission steelmaking using hydrogen thermal plasma},
  author={Cooper, Christopher and Brooks, Geoffrey and Rhamdhani, M. Akbar and Pye, John and Rahbari, Alireza}
}
```

## Install
### Requirements
* Python3.
* Ubuntu, MacOS or Windows.

### Minimum Install
Download the code using git, or download the code as a zip file from github.
```
git clone https://github.com/chris-phd/plasma-steelmaking-technoeconomics.git
```

Install the python dependencies using pip.
```
cd plasma-steelmaking-technoeconomics
pip install -r requirements.txt
```

Check the installation.
```
python tea_main.py --help
python test.py
```

### Optional Install (Ubuntu Only)
This step is not necessary to run the technoeconomic analysis.

Graphviz is required to use the -r command line option to render a diagram of the different steel plants. It is used to verify that the structure of the mass and energy flow model is correct. This feature has not been tested on Windows or MacOS. Only Ubuntu is officially supported. 

Install graphviz and add it to the environment PATH.
```
sudo apt update
sudo apt install graphiz
```

## Running the Code
Run the technoeconomic analysis.
```
python tea_main.py -c config/config_default.csv -p config/prices_default.csv
```

Run the default case with sensitivity analysis.
```
python tea_main.py -c config/config_default.csv -p config/prices_default.csv -s config/sensitivity.csv
```

If graphviz is installed, optionally render the systems using -r.
```
python tea_main.py -c config/config_default.csv -p config/prices_default.csv -r /tmp/path_to_dir_to_save_pdfs/
```

### Modify the Settings
A config.csv file and a prices.csv file must be supplied to run the technoeconomic analysis. These input files can be modified to check the economics under different conditions.

To use custom capex or commodity prices, overwrite values in config/prices_default.csv or create a new prices.csv. For example, to increase the price of hydrogen to 5.00 USD/kg, modify the hydrogen entry to read:
```
H2,3.00,PerKilogram,5,
```

The config.csv file manages all non-price settings, such as efficiency, slag basicity, ore composition, the use of on-premesis hydrogen generation and so on. The full list of available settings can be found in create_plants.py. 

For example, to increase slag basicity in the HDR-EAF system, add the following entry to the bottom of the input config.csv file:
```
dri-eaf,b2 basicity,3.5,number
```

To increase slag basicity for all systems:
```
all,b2 basicity,3.5,number
```

config/config_custom_ore.csv shows how to use an ore with a custom ore composition. Currently, only hematite ore is supported.