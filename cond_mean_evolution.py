"""
created on May 20, 2014

@author: Nikola Jajcay
"""

from src import wavelet_analysis
from src.data_class import load_station_data, DataField
from surrogates.surrogates import SurrogateField
import numpy as np
from datetime import datetime, date
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from multiprocessing import Process, Queue


def render(diffs, meanvars, stds = None, subtit = '', percentil = None, fname = None):
    fig, ax1 = plt.subplots(figsize=(11,8))
    if len(diffs) > 3:
        ax1.plot(diffs, color = '#403A37', linewidth = 2, figure = fig)
    else:
        p2, = ax1.plot(diffs[1], color = '#899591', linewidth = 1.5, figure = fig)
        if stds is not None:
            ax1.plot(diffs[1] + stds[0], color = '#899591', linewidth = 0.7, figure = fig)
            ax1.plot(diffs[1] - stds[0], color = '#899591', linewidth = 0.7, figure = fig)
            ax1.fill_between(np.arange(0,diffs[1].shape[0],1), diffs[1] + stds[0], diffs[1] - stds[0], 
                             facecolor = "#899591", alpha = 0.5)
        p1, = ax1.plot(diffs[0], color = '#403A37', linewidth = 2, figure = fig)
        if percentil != None:
            for pos in np.where(percentil[:, 0] == True)[0]:
                ax1.plot(pos, diffs[0][pos], 'o', markersize = 8, color = '#403A37')
    #ax1.plot(total_diffs[0], np.arange(0,len(total_diffs[0])), total_diffs[1], np.arange(0, cnt))
    ax1.axis([0, cnt-1, diff_ax[0], diff_ax[1]])
    ax1.set_xlabel('middle year of %.2f-year wide window' % (WINDOW_LENGTH / 365.25), size = 14)
    if MEANS:
        ax1.set_ylabel('difference in cond mean in temperature [$^{\circ}$C]', size = 14)
    elif not MEANS:
        ax1.set_ylabel('difference in cond variance in temperature [$^{\circ}$C$^2$]', size = 14)
    year_diff = np.round((last_mid_year - first_mid_year) / 10)
    print last_mid_year, first_mid_year, year_diff
    xnames = np.arange(first_mid_year, last_mid_year, year_diff)
    print xnames
    plt.xticks(np.linspace(0, cnt, len(xnames)), xnames, rotation = 30)
    ax2 = ax1.twinx()
    if len(meanvars) > 3:
        ax2.plot(meanvars, color = '#CA4F17', linewidth = 2, figure = fig) # color = '#CA4F17'
    else:
        p4, = ax2.plot(meanvars[1], color = '#64C4A0', linewidth = 1.5, figure = fig)
        if stds is not None:
            ax2.plot(meanvars[1] + stds[1], color = '#64C4A0', linewidth = 0.7, figure = fig)
            ax2.plot(meanvars[1] - stds[1], color = '#64C4A0', linewidth = 0.7, figure = fig)
            ax2.fill_between(np.arange(0,diffs[1].shape[0],1), meanvars[1] + stds[1], meanvars[1] - stds[1],
                             facecolor = "#64C4A0", alpha = 0.5)
        p3, = ax2.plot(meanvars[0], color = '#CA4F17', linewidth = 2, figure = fig)
        if percentil != None:
            for pos in np.where(percentil[:, 1] == True)[0]:
                ax2.plot(pos, meanvars[0][pos], 'o', markersize = 8, color = '#CA4F17')
    if MEANS:
        ax2.set_ylabel('mean of cond means in temperature [$^{\circ}$C]', size = 14)
    elif not MEANS:
        ax2.set_ylabel('mean of cond variance in temperature [$^{\circ}$C$^2$]', size = 14)
    ax2.axis([0, cnt-1, mean_ax[0], mean_ax[1]])
    for tl in ax2.get_yticklabels():
        tl.set_color('#CA4F17')
    if len(diffs) < 3:
        plt.legend([p1, p2, p3, p4], ["difference DATA", "difference SURROGATE mean", "mean DATA", "mean SURROGATE mean"], loc = 2)
    tit = 'SURR: Evolution of difference in cond'
    if MEANS:
        tit += ' mean in temp, '
    else:
        tit += ' variance in temp, '
    if not ANOMALISE:
        tit += 'SAT, '
    else:
        tit += 'SATA, '
    if np.int(WINDOW_LENGTH) == WINDOW_LENGTH:
        tit += ('%d-year window, %d-year shift' % (WINDOW_LENGTH, WINDOW_SHIFT))
    else:
        tit += ('%.2f-year window, %d-year shift' % (WINDOW_LENGTH, WINDOW_SHIFT))
    #plt.title(tit)
    if MEANS:
        tit = ('Evolution of difference in cond means temp SATA -- %s \n' % g.location)
    else:
        tit = ('Evolution of difference in cond variance in temp SATA -- %s \n' % g.location)
    tit += subtit
    plt.text(0.5, 1.05, tit, horizontalalignment = 'center', size = 16, transform = ax2.transAxes)
    #ax2.set_xticks(np.arange(start_date.year, end_date.year, 20))
    
    if fname is not None:
        plt.savefig(fname)
    else:
        plt.show()
        
        
        
        
ANOMALISE = True
PERIOD = 8 # years, period of wavelet
WINDOW_LENGTH = 16384
WINDOW_SHIFT = 1 # years, delta in the sliding window analysis
MEANS = False # if True, compute conditional means, if False, compute conditional variance
WORKERS = 22
NUM_SURR = 1000 # how many surrs will be used to evaluate
MF_SURR = False
diff_ax = (1, 7)
mean_ax = (9, 18)


## loading data
g = load_station_data('TG_STAID000027.txt', date(1830,1,1), date(2014,1,1), ANOMALISE)
g_working = DataField()
g_surrs = DataField()


print("[%s] Wavelet analysis in progress with %d year window shifted by %d year(s)..." % (str(datetime.now()), WINDOW_LENGTH, WINDOW_SHIFT))
k0 = 6. # wavenumber of Morlet wavelet used in analysis
y = 365.25 # year in days
fourier_factor = (4 * np.pi) / (k0 + np.sqrt(2 + np.power(k0,2)))
period = PERIOD * y # frequency of interest
s0 = period / fourier_factor # get scale 


cond_means = np.zeros((8,))
to_wavelet = WINDOW_LENGTH + int(8 * y)

def get_equidistant_bins():
    return np.array(np.linspace(-np.pi, np.pi, 9))
    


def _cond_difference_surrogates(g_temp, a, start_cut, jobq, resq):
    mean, var, trend = a
    while jobq.get() is not None:
        sg = SurrogateField()
        sg.copy_field(g_temp)
        if MF_SURR:
            sg.construct_multifractal_surrogates()
        else:
            sg.construct_fourier_surrogates_spatial()
        sg.add_seasonality(mean, var, trend)
        wave, _, _, _ = wavelet_analysis.continous_wavelet(sg.surr_data, 1, False, wavelet_analysis.morlet, dj = 0, s0 = s0, j1 = 0, k0 = k0) # perform wavelet
        phase = np.arctan2(np.imag(wave), np.real(wave))
        _, _, idx = g_temp.get_data_of_precise_length('16k', start_cut, None, False)
        sg.surr_data = sg.surr_data[idx[0] : idx[1]]
        phase = phase[0, idx[0] : idx[1]]
        phase_bins = get_equidistant_bins() # equidistant bins
        for i in range(cond_means.shape[0]): # get conditional means for current phase range
            #phase_bins = get_equiquantal_bins(phase_temp) # equiquantal bins
            ndx = ((phase >= phase_bins[i]) & (phase <= phase_bins[i+1]))
            if MEANS:
                cond_means[i] = np.mean(sg.surr_data[ndx])
            else:
                cond_means[i] = np.var(sg.surr_data[ndx], ddof = 1)
        diff = (cond_means.max() - cond_means.min()) # append difference to list    
        mean_var = np.mean(cond_means)
        
        resq.put((diff, mean_var))
    
    
    
difference_data = []
meanvar_data = []
cnt = 0

difference_surr = []
difference_surr_std = []
meanvar_surr = []
meanvar_surr_std = []

difference_95perc = []
mean_95perc = []


start_year = date.fromordinal(g.time[0]).year
sm = date.fromordinal(g.time[0]).month
sd = date.fromordinal(g.time[0]).day

start_idx = 0
end_idx = to_wavelet

_, _, idx = g.get_data_of_precise_length('16k', date.fromordinal(g.time[4*y]), None, False)
first_mid_year = date.fromordinal(g.time[(idx[1] - idx[0])/2]).year


while end_idx < g.data.shape[0]:
    cnt += 1
    
    # data
    g_working.data = g.data[start_idx : end_idx].copy()
    g_working.time = g.time[start_idx : end_idx].copy()
    if np.all(np.isnan(g_working.data) == False):
        wave, _, _, _ = wavelet_analysis.continous_wavelet(g_working.data, 1, True, wavelet_analysis.morlet, dj = 0, s0 = s0, j1 = 0, k0 = k0) # perform wavelet
        phase = np.arctan2(np.imag(wave), np.real(wave)) # get phases from oscillatory modes
        start_cut = date.fromordinal(g.time[start_idx + 4*y])
        idx = g_working.get_data_of_precise_length('16k', start_cut, None, True)
        last_mid_year = date.fromordinal(g_working.time[(idx[1] - idx[0])/2]).year
        phase = phase[0, idx[0] : idx[1]]
        phase_bins = get_equidistant_bins() # equidistant bins
        for i in range(cond_means.shape[0]): # get conditional means for current phase range
            ndx = ((phase >= phase_bins[i]) & (phase <= phase_bins[i+1]))
            if MEANS:
                cond_means[i] = np.mean(g_working.data[ndx])
            else:
                cond_means[i] = np.var(g_working.data[ndx], ddof = 1)
        difference_data.append(cond_means.max() - cond_means.min()) # append difference to list    
        meanvar_data.append(np.mean(cond_means))
    else:
        difference_data.append(np.nan)
        meanvar_data.append(np.nan)
        
    # surrogates
    if NUM_SURR != 0:
        surr_completed = 0
        surr_date = date(start_year + 5*cnt/7, sm, sd) # POTSDAM 5*cnt/11, PRG/STHLM 5*cnt/7
        diffs = np.zeros((NUM_SURR,))
        mean_vars = np.zeros_like(diffs)
        g_surrs.data, g_surrs.time, _ = g.get_data_of_precise_length('32k', surr_date, None, COPY = False)
        if np.all(np.isnan(g_surrs.data) == False):
            # construct the job queue
            jobQ = Queue()
            resQ = Queue()
            for i in range(NUM_SURR):
                jobQ.put(1)
            for i in range(WORKERS):
                jobQ.put(None)
            a = g_surrs.get_seasonality(DETREND = True)
            workers = [Process(target = _cond_difference_surrogates, args = (g_surrs, a, start_cut, jobQ, resQ)) for iota in range(WORKERS)]
            for w in workers:
                w.start()
            while surr_completed < NUM_SURR:
                # get result
                diff, meanVar = resQ.get()
                diffs[surr_completed] = diff
                mean_vars[surr_completed] = meanVar
                surr_completed += 1
            for w in workers:
                w.join()
                
            difference_surr.append(np.mean(diffs))
            difference_surr_std.append(np.std(diffs, ddof = 1))
            meanvar_surr.append(np.mean(mean_vars))
            meanvar_surr_std.append(np.std(mean_vars, ddof = 1))
            
            percentil = difference_data[-1] > diffs
            no_true = percentil[percentil == True].shape[0]
            difference_95perc.append(True if (no_true > NUM_SURR * 0.95) else False)
            
            percentil = meanvar_data[-1] > mean_vars
            no_true = percentil[percentil == True].shape[0]
            mean_95perc.append(True if (no_true > NUM_SURR * 0.95) else False)
            print("%d. time point - data: %.2f, surr mean: %.2f, surr std: %.2f" % (cnt, difference_data[-1], np.mean(diffs), np.std(diffs, ddof = 1)))    
        else:
            difference_surr.append(0)
            difference_surr_std.append(0)
            meanvar_surr.append(0)
            meanvar_surr_std.append(0)

    start_idx = g.find_date_ndx(date(start_year + WINDOW_SHIFT*cnt, sm, sd))
    end_idx = start_idx + to_wavelet

print("[%s] Wavelet analysis on data done." % (str(datetime.now())))
difference_data = np.array(difference_data)
meanvar_data = np.array(meanvar_data)
difference_95perc = np.array(difference_95perc)
mean_95perc = np.array(mean_95perc)

where_percentil = np.column_stack((difference_95perc, mean_95perc))

fn = ("debug/PRG_%d_surr_" % NUM_SURR)
if not MEANS:
    fn += 'var_'
if MF_SURR:
    fn += 'MF_REWORK.eps'
else:
    fn += 'FT_REWORK.eps'

render([difference_data, np.array(difference_surr)], [meanvar_data, np.array(meanvar_surr)], [np.array(difference_surr_std), np.array(meanvar_surr_std)],
        subtit = ("95 percentil: difference - %d/%d and mean %d/%d" % (difference_95perc[difference_95perc == True].shape[0], cnt, mean_95perc[mean_95perc == True].shape[0], cnt)), 
        percentil = where_percentil, fname = fn)









