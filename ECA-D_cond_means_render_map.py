"""
created on June 13, 2014

@author: Nikola Jajcay
"""

import cPickle
#import hickle as hkl
from datetime import datetime, date
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
import numpy as np


def render_differences_map(diffs, lats, lons, subtit = '', fname = None):
    fig = plt.figure(figsize=(20,16))
    lat_ndx = np.argsort(lats)
    lats = lats[lat_ndx]
    m = Basemap(projection = 'merc',
                llcrnrlat = lats[0], urcrnrlat = lats[-1],
                llcrnrlon = lons[0], urcrnrlon = lons[-1],
                resolution = 'c')
                
    m.fillcontinents(color = "#ECF0F3", lake_color = "#A9E5FF", zorder = 0)
    m.drawmapboundary(fill_color = "#A9E5FF")
    m.drawcoastlines(linewidth = 2, color = "#333333")
    m.drawcountries(linewidth = 1.5, color = "#333333")
    m.drawparallels(np.arange(25, 80, 10), linewidth = 1.2, labels = [1,0,0,0], color = "#222222")
    m.drawmeridians(np.arange(-40, 80, 10), linewidth = 1.2, labels = [0,0,0,1], color = "#222222")
    x, y = m(*np.meshgrid(lons, lats))
    if not MEANS:
        levs = np.arange(0.5,6,0.25) # 0.5 - 6 / 0.25
    else:
        levs = np.arange(0,1,0.05) # 0 - 4 / 0.2
    cs = m.contourf(x, y, diffs, levels = levs, cmap = plt.get_cmap('CMRmap'))
    cbar = m.colorbar(cs, location = 'right', pad = "15%")
    if MEANS:
        cbar.set_label("differecnce [$^{\circ}$C]", size = 18)
    else:
        cbar.set_label("differecnce in standard deviation [$^{\circ}$C]", size = 18)
    if SIGN:
        if MEANS:
            title = ("ECA & D reanalysis - differences of conditional means \n %d %s surrogates" % (num_surr, SURR_TYPE))
        else:
            title = ("ECA & D reanalysis - differences of conditional standard deviation \n %d %s surrogates" % (num_surr, SURR_TYPE))        
    else:
        if MEANS:
            title = ("ECA & D reanalysis - differences of conditional means \n MF SURROGATE STD")
        else:
            title = ("ECA & D reanalysis - differences of conditional standard deviation \n DATA")
    title += subtit
    plt.title(title, size = 22)
    
    if fname != None:
        plt.savefig(fname)
    else:
        plt.show()



SURR_TYPE = 'MF' # MF, FT or AR
START_DATE = date(1960,1,1)
MEANS = True
ANOMALISE = True
PICKLE = True # whether to use pickled file or hickled
SIGN = False # wheter to check significance or just plot results
SIGMAS_ABOVE = 2
PERCENTIL = 95



# load data 
print("[%s] Loading data..." % (str(datetime.now())))
fname = ('result/ECA-D_%s_cond_means_data_from_%s_16k' % ('SATA' if ANOMALISE else 'SAT', 
         str(START_DATE)))
if PICKLE:
    with open(fname + '.bin', 'rb') as f:
        data = cPickle.load(f)
else:
    data = hkl.load(fname + '.hkl')
difference_data = data['difference_data']
mean_data = data['mean_data']
#difference_data_var = data['difference_data_var']
#mean_data_var = data['mean_data_var']
lats = data['lats']
lons = data['lons']
del data

# load surrogates
print("[%s] Data loaded. Now loading surrogates..." % (str(datetime.now())))
fname = ('result/ECA-D_%s_cond_means_%ssurrogates_from_%s_16k' % ('SATA' if ANOMALISE else 'SAT', 
             SURR_TYPE, str(START_DATE)))
if PICKLE:
    with open(fname + '.bin', 'rb') as f:
        data = cPickle.load(f)
else:
    data = hkl.load(fname + '.hkl')
difference_surrogates = data['difference_surrogates']
mean_surrogates = data['mean surrogates']
#difference_surrogates_var = data['difference_surrogates_var']
#mean_surrogates_var = data['mean_surrogates_var']
del data
print("[%s] Surrogates loaded." % (str(datetime.now())))


if SIGN:
    # compute significance
    result_sigma = np.zeros_like(difference_data)
    result_percentil = np.zeros_like(difference_data)
    num_surr = difference_surrogates.shape[0]
    for lat in range(lats.shape[0]):
        for lon in range(lons.shape[0]):
            if MEANS:
                if np.isnan(difference_data[lat, lon]): # if on lat x lon is NaN
                    result_sigma[lat, lon] = np.nan
                    result_percentil[lat, lon] = np.nan
                else:
                    # sigma-based significance
                    sigma = np.std(difference_surrogates[:, lat, lon], axis = 0, ddof = 1)
                    mean = np.mean(difference_surrogates[:, lat, lon], axis = 0)
                    if difference_data[lat, lon] >= mean + SIGMAS_ABOVE*sigma:
                        result_sigma[lat, lon] = difference_data[lat, lon]
                    else:
                        result_sigma[lat, lon] = np.nan # or np.nan
                        
                    # percentil-based significance
                    greater_mat = np.greater(difference_data[lat, lon], difference_surrogates[:, lat, lon])
                    if np.sum(greater_mat) > PERCENTIL/100. * num_surr:
                        result_percentil[lat, lon] = difference_data[lat, lon]
                    else:
                        result_percentil[lat, lon] = np.nan # or np.nan
            else:
                if np.isnan(difference_data_var[lat, lon]): # if on lat x lon is NaN
                    result_sigma[lat, lon] = np.nan
                    result_percentil[lat, lon] = np.nan
                else:
                    # sigma-based significance
                    sigma = np.std(difference_surrogates_var[:, lat, lon], axis = 0, ddof = 1)
                    mean = np.mean(difference_surrogates_var[:, lat, lon], axis = 0)
                    if difference_data_var[lat, lon] >= mean + SIGMAS_ABOVE*sigma:
                        result_sigma[lat, lon] = difference_data_var[lat, lon]
                    else:
                        result_sigma[lat, lon] = np.nan # or np.nan
                        
                    # percentil-based significance
                    greater_mat = np.greater(difference_data_var[lat, lon], difference_surrogates_var[:, lat, lon])
                    if np.sum(greater_mat) > PERCENTIL/100. * num_surr:
                        result_percentil[lat, lon] = difference_data_var[lat, lon]
                    else:
                        result_percentil[lat, lon] = np.nan # or np.nan
                   
                
    fname = ('debug/ECA-D_%s_cond_%s_%ssurrogates_from_%s_16k_above_%.1fsigma.png' % ('SATA' if ANOMALISE else 'SAT', 
                 'means' if MEANS else 'std', SURR_TYPE, str(START_DATE), SIGMAS_ABOVE))
    render_differences_map(result_sigma, lats, lons, subtit = (' - above %.2f $\sigma$ (STDs)' % SIGMAS_ABOVE), 
                           fname = fname)
    
    fname = ('debug/ECA-D_%s_cond_%s_%ssurrogates_from_%s_16k_above_%dpercentil.png' % ('SATA' if ANOMALISE else 'SAT', 
                 'means' if MEANS else 'std', SURR_TYPE, str(START_DATE), PERCENTIL))
    render_differences_map(result_percentil, lats, lons, subtit = (' - %d percentil' % PERCENTIL), fname = fname)
    
else:
    fname = ('debug/ECA-D_%s_cond_%s_surrogate_std_from_%s.png' % ('SATA' if ANOMALISE else 'SAT', 'means' if MEANS else 'std', 
                                                            str(START_DATE)))
    if MEANS:
        render_differences_map(np.std(difference_surrogates, axis = 0, ddof = 1), lats, lons, subtit = (' - no significance test'), 
                                fname = fname)
    else:
        render_differences_map(difference_data_var, lats, lons, subtit = (' - no significance test'), 
                                fname = fname)
