import os
import py7zr
import shutil
from ftplib import FTP
from osgeo import gdal, osr
import shutil
import rasterio
from rasterio.merge import merge
from tqdm.notebook import tqdm


# Prepare data folder
DATAPATH = 'data'
os.makedirs(DATAPATH, exist_ok=True)
TEMP_ZIP = os.path.join(DATAPATH, "temp7z")
EXTRACTION_PATH = os.path.join(DATAPATH, "RGE_ALTI_1m")

# Define requested info to access the FTP.
URL = "ftp3.ign.fr"
USERNAME = "RGE_ALTI_ext"
PASSWORD = "Thae5eerohsei8ve"

REGIONS = {
    'Auvergne-Rhône-Alpes': ['01', '03', '07', '15', '26', '38', '42', '43', '63', '69', '73', '74'],
    'Bourgogne-Franche-Comté': ['21', '25', '39', '58', '70', '71', '89', '90'],
    'Bretagne': ['35', '22', '56', '29'],
    'Centre-Val de Loire': ['18', '28', '36', '37', '41', '45'],
    'Corse': ['2A', '2B'],
    'Grand Est': ['08', '10', '51', '52', '54', '55', '57', '67', '68', '88'],
    'Guadeloupe': ['971'],
    'Guyane': ['973'],
    'Hauts-de-France': ['02', '59', '60', '62', '80'],
    'Île-de-France': ['75', '77', '78', '91', '92', '93', '94', '95'],
    'La Réunion': ['974'],
    'Martinique': ['972'],
    'Normandie': ['14', '27', '50', '61', '76'],
    'Nouvelle-Aquitaine': ['16', '17', '19', '23', '24', '33', '40', '47', '64', '79', '86', '87'],
    'Occitanie': ['09', '11', '12', '30', '31', '32', '34', '46', '48', '65', '66', '81', '82'],
    'Pays de la Loire': ['44', '49', '53', '72', '85'],
    'Provence-Alpes-Côte d\'Azur': ['04', '05', '06', '13', '83', '84'],
}

# Create a small helper class to manipulate our ftp connection
# without leaving the connection open between calls
class FTPHelper:
    def __init__(self, url, username, password):
        self.url = url
        self.username = username
        self.password = password
    
    def list_files(self):
        """
        Connects to ftp server and returns a list of file names stored on it.
        """
        with FTP(self.url) as ftp:
            ftp.login(self.username, self.password)
            filenames = ftp.nlst()
        return filenames


    def download_file(self, filename, local_folder, verbose=True):
        """
        Connects to ftp server and downloads remote `filename` to local `local_folder`.

        Disable verbose to avoid printing the progress bar.
        """
        # Create the directory to store the downloaded file.
        os.makedirs(local_folder, exist_ok = True)
        # Define the output filename.
        output_filepath = os.path.join(local_folder, filename)
        # Download the file (big files so ze show a progress bar)
        with FTP(self.url) as ftp:
            ftp.login(self.username, self.password)
            filesize = ftp.size(filename)
            with open(output_filepath, 'wb') as f:
                with tqdm(total=filesize,
                    unit='B', unit_scale=True, unit_divisor=1024,
                    disable=not verbose) as pbar:
                    pbar.set_description(f"Downloading {filename}")
                    def callback_(data):
                        l = len(data)
                        pbar.update(l)
                        f.write(data)
                    ftp.retrbinary('RETR ' + filename, callback_)
        print(f"{filename} is downloaded.")
        return output_filepath

def extract_rge(filename):
    """
    Extracts the zip DEM.
    """
    zipfile_path = os.path.join(TEMP_ZIP, filename)
    os.makedirs(EXTRACTION_PATH, exist_ok = True)
    with py7zr.SevenZipFile(zipfile_path, mode='r') as archive:
        archive.extractall(path=EXTRACTION_PATH) #WIN: check the path lenght in case of error FileNotFound
    print(f"{zipfile_path} is extracted to {EXTRACTION_PATH}.")


def get_path_asc_paths(filename, EXTRACTION_PATH):
    """
    This funciton returns a list of paths of asc files.
    """
    for root, dirs, files in os.walk(EXTRACTION_PATH, filename[:-3]):
        if "1_DONNEES_LIVRAISON" in root:
            asc_paths_list = sorted([os.path.join(root, name) for name in files if name.endswith(".asc")])

    return asc_paths_list

def get_header_asc(filepath):
    """
    This function reads the header of an asc file and returns 
    the data into a dictionnary
    """
    file = open(filepath)
    content = file.readlines()[:6]
    content = [item.split() for item in content]
    return dict(content)

class RGEitem():
    """
    This class is used to handle RGE items.
    """
    def __init__(self, filepath):
        self.filename = os.path.basename(filepath)
        self.dir = os.path.dirname(filepath)
        self.data = np.loadtxt(filepath, skiprows=6)
        self.header = get_header_asc(filepath)
        self.ncols = int(self.header['ncols'])
        self.nrows = int(self.header['nrows'])
        self.xllc = float(self.header['xllcorner'])
        self.yllc = float(self.header['yllcorner'])
        self.res = float(self.header['cellsize'])
        self.zmin = float(self.data.min())
        self.zmax = float(self.data.max())
        self.novalue = -99999.

def asc_to_tif(file, output_raster_dir, epsg):
    """
    Transforms an .asc file into a geoTIFF.

    Params:
    -------
    file: an RGEitem
    output_raster_dir (str): path to the directory where the tif will be saved.
    epsg (int): projection system.

    Returns:
    --------
    output_rasterpath (str): name of the output geoTIFF
    """
    xmin = file.xllc
    ymax = file.yllc + file.nrows * file.res 
    geotransform = (xmin, file.res, 0, ymax, 0, -file.res)

    output_rasterpath = os.path.join(output_raster_dir, file.filename[:-4] + ".tif")

    # Open the file
    output_raster = gdal.GetDriverByName('GTiff').Create(output_rasterpath, file.ncols, file.nrows, 1, gdal.GDT_Float32)
    # Specify the coordinates.  
    output_raster.SetGeoTransform(geotransform)
    # Establish the coordinate encoding.  
    srs = osr.SpatialReference()  
    # Specify the projection.               
    srs.ImportFromEPSG(epsg)                     
    # Export the coordinate system to the file.
    output_raster.SetProjection(srs.ExportToWkt())
    # Writes the array.   
    output_raster.GetRasterBand(1).WriteArray(file.data)
    # Set nodata value.  
    output_raster.GetRasterBand(1).SetNoDataValue(file.novalue) 
    output_raster.FlushCache()
    return output_rasterpath

def create_rge_mosaic(asc_paths_list, result_path, mosaic_name, crs):
    """
    Creates a mosaic associated to multiple asc files.

    Params:
    -------
    asc_paths_list (list): list of asc files paths.
    mosaic_path (str): path of the output mosaic.
    crs (int): coordinate reference system (ex. 2154 for EPSG:2154).
    """

    # Create tmp dir to save intermediate tifs.
    tmpdir = os.path.join(DATAPATH, 'local_tifs')
    os.makedirs(tmpdir, exist_ok = True)
    
    output_raster_paths_list = [asc_to_tif(RGEitem(ascpath), tmpdir, crs) for ascpath in asc_paths_list]
    
    # Safely load rasters and create the mosaic.
    from contextlib import ExitStack
    with ExitStack() as stack:
        raster_to_mosaic_list = [stack.enter_context(rasterio.open(path)) 
            for path in output_raster_paths_list
        ]
        mosaic, output = merge(raster_to_mosaic_list)
        output_meta = raster_to_mosaic_list[0].meta.copy()
    
    output_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": output,
    })

    # Save the result.
    os.makedirs(result_path, exist_ok=True)
    mosaic_path = os.path.join(result_path, mosaic_name)
    with rasterio.open(mosaic_path, "w", **output_meta) as m:
        m.write(mosaic)
    
    # Purge the tmp dir.
    shutil.rmtree(tmpdir)

    return mosaic_path
