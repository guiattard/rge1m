# rge1m
Processing the RGE Alti 1m (IGN) for implementation into earth engine.

## Install requirements
Install the requirements as follow. First create a activate a new virtual environement:

```
python3 -m venv venv-rge
source venv-rge/bin/activate
```
Then install all requirements:
```
pip install -r requirements.txt 
```

## In case of trouble with GDAL on Ubuntu:
Add the following repos and install gdal-bin:
```
sudo add-apt-repository ppa:ubuntugis/ppa
sudo apt-get update
sudo apt-get install gdal-bin
```
then, install dependencies for gdal libs:
```
sudo apt install libpq5
sudo apt install libpq-dev
```
and finnaly install the apropriate version of GDAL:
```
ogrinfo --version
sudo apt-get install libgdal-dev
export CPLUS_INCLUDE_PATH=/usr/include/gdal
export C_INCLUDE_PATH=/usr/include/gdal
pip install GDAL=='GDAL VERSION FROM OGRINFO'
```

## Create the kernel associated to the venv:
```
source venv-rge/bin/activate
python3 -m pip install ipykernel
python3 -m ipykernel install --user --name=venv-rge
```
