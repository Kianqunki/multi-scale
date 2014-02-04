"""
created on Feb 04, 2014

@author: Nikola Jajcay
"""

import data_class
import numpy as np
import wavelet_analysis
from datetime import datetime



# loading data
print("[%s] Loading station data..." % (str(datetime.now())))
g = data_class.DataField()
g.load_station_data('Klemday07.raw')
day, month, year = g.extract_day_month_year()
## cekni datum od kedy
print("[%s] Data from %s loaded with shape %s. Date range is %d.%d.%d - %d.%d.%d" 
        % (str(datetime.now()), g.location, str(g.data.shape), day[0], month[0], 
           year[0], day[-1], month[-1], year[-1]))
           
# wavelet
k0 = 6. # wavenumber of Morlet wavelet used in analysis
y = 365.25 # year in days
fourier_factor = (4 * np.pi) / (k0 + np.sqrt(2 + np.power(k0,2)))
period = 8 * y # frequency of interest - 8 years
s0 = period / fourier_factor
print("[%s] Wavelet analysis in progress..." % (str(datetime.now())))
wave, _, _ = wavelet_analysis.continous_wavelet(g.data, 1, True, s0 = s0, j1 = 0, k0 = k0)

phase = np.zeros((wave.shape[1],))
amplitude = np.zeros((wave.shape[1],))

phase = np.arctan2(np.imag(wave), np.real(wave))
amplitude = np.sqrt(np.power(np.real(wave),2) + np.power(np.imag(wave),2))

print phase[:20]
print
print amplitude[:20]
        



