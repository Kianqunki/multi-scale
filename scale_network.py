import numpy as np
from src.data_class import DataField
import src.wavelet_analysis as wvlt
from datetime import datetime
import sys
sys.path.append('/home/nikola/Work/phd/mutual_information')
from mutual_information import mutual_information

import multiprocessing as mp
from time import sleep


def _get_oscillatory_modes(a):
    """
    Gets oscillatory modes in terms of phase and amplitude from wavelet analysis for given data.
    """
    i, j, s0, flag, data = a
    wave, _, _, _ = wvlt.continous_wavelet(data, 1, False, wvlt.morlet, dj = 0, s0 = s0, j1 = 0, k0 = 6.)
    phase = np.arctan2(np.imag(wave), np.real(wave))
    if flag:
        amplitude = np.sqrt(np.power(np.real(wave),2) + np.power(np.imag(wave),2))
    
    if flag:
        return i, j, (phase, amplitude)
    else:
        return i, j, (phase)


def _get_phase_coherence(a):
    """
    Gets mean phase coherence for given data.
    """

    i, j, ph1, ph2 = a
    # get continuous phase
    for ii in range(ph1.shape[0] - 1):
        if np.abs(ph1[ii+1] - ph1[ii]) > 1:
            ph1[ii+1: ] += 2 * np.pi
        if np.abs(ph2[ii+1] - ph2[ii]) > 1:
            ph2[ii+1: ] += 2 * np.pi

    # get phase diff
    diff = ph1 - ph2

    # compute mean phase coherence
    coh = np.power(np.mean(np.cos(diff)), 2) + np.power(np.mean(np.sin(diff)), 2)

    return i, j, coh


def _get_mutual_inf_gauss(a):
    """
    Gets mutual information using Gauss algorithm for given data.
    """

    i, j, ph1, ph2 = a
    corr = np.corrcoef([ph1, ph2])[0, 1]
    mi = -0.5 * np.log(1 - np.power(corr, 2))
    
    return i, j, mi


def _get_mutual_inf_EQQ(a):
    """
    Gets mutual information using EQQ algorithm for given data.
    """
    
    i, j, ph1, ph2 = a
    return i, j, mutual_information(ph1, ph2, algorithm = 'EQQ2', bins = 8, log2 = False)




class ScaleSpecificNetwork(DataField):
    """
    Class holds geo data (inherits methods from DataField) and can construct networks.
    """

    def __init__(self, fname, varname, start_date, end_date, lats, lons, level = None, sampling = 'monthly', anom = False):
        """
        Initialisation of the class.
        """

        # if sampling == 'monthly':
        #     self.g = load_NCEP_data_monthly(fname, varname, start_date, end_date, None, None, None, anom)
        # elif sampling == 'daily':
        #     self.g = load_NCEP_data_daily(fname, varname, start_date, end_date, None, None, None, anom)

        DataField.__init__(self)
        self.load(fname, varname, dataset = "NCEP", print_prog = False)
        self.select_date(start_date, end_date)
        self.select_lat_lon(lats, lons)
        if level is not None:
            self.select_level(level)
        if anom:
            self.anomalise()
        day, month, year = self.extract_day_month_year()
        print("[%s] NCEP data loaded with shape %s. Date range is %d.%d.%d - %d.%d.%d inclusive." 
                % (str(datetime.now()), str(self.data.shape), day[0], month[0], 
                   year[0], day[-1], month[-1], year[-1]))


        self.phase = None
        self.amplitude = None
        self.adjacency_matrix = None

        self.num_lats = self.lats.shape[0]
        self.num_lons = self.lons.shape[0]
        self.sampling = sampling



    def wavelet(self, period, get_amplitude = False, pool = None):
        """
        Performs wavelet analysis on the data.
        """

        k0 = 6. # wavenumber of Morlet wavelet used in analysis, suppose Morlet mother wavelet
        if self.sampling == 'monthly':
            y = 12
        elif self.sampling == 'daily':
            y = 365.25
        fourier_factor = (4 * np.pi) / (k0 + np.sqrt(2 + np.power(k0,2)))
        per = period * y # frequency of interest
        s0 = per / fourier_factor # get scale

        self.phase = np.zeros_like(self.data)
        if get_amplitude:
            self.amplitude = np.zeros_like(self.data)

        if pool is None:
            map_func = map
        elif pool is not None:
            map_func = pool.map

        job_args = [ (i, j, s0, get_amplitude, self.data[:, i, j]) for i in range(self.num_lats) for j in range(self.num_lons) ]
        job_result = map_func(_get_oscillatory_modes, job_args)
        del job_args

        for i, j, res in job_result:
            self.phase[:, i, j] = res[0]
            if get_amplitude:
                self.amplitude[:, i, j] = res[1]

        del job_result


    def _process_matrix(self, jobq, resq):
        
        while True:
            a = jobq.get() # get queued input

            if a is None: # if it is None, we are finished, put poison pill to resq
                # resq.put(None)
                break # break infinity cycle
            else:
                i, j, ph1, ph2, method = a # compute stuff
                if method == "MPC":
                    for ii in range(ph1.shape[0] - 1):
                        if np.abs(ph1[ii+1] - ph1[ii]) > 1:
                            ph1[ii+1: ] += 2 * np.pi
                        if np.abs(ph2[ii+1] - ph2[ii]) > 1:
                            ph2[ii+1: ] += 2 * np.pi
                    # get phase diff
                    diff = ph1 - ph2
                    # compute mean phase coherence
                    coh = np.power(np.mean(np.cos(diff)), 2) + np.power(np.mean(np.sin(diff)), 2)
                    resq.put((i, j, coh))

                elif method == "MIEQQ":
                    resq.put((i, j, mutual_information(ph1, ph2, algorithm = 'EQQ2', bins = 8, log2 = False)))

                elif method == "MIGAU":
                    corr = np.corrcoef([ph1, ph2])[0, 1]                    
                    mi = -0.5 * np.log(1 - np.power(corr, 2)) if corr < 1. else 0
                    resq.put((i, j, mi)) 



    def get_adjacency_matrix(self, method = "MPC", pool = None, use_queue = True, num_workers = 0):
        """
        Gets the matrix of mean phase coherence between each two grid-points.
        Methods for adjacency matrix:
            MPC - mean phase coherence
            MIEQQ - mutual information - equiquantal algorithm
            MIGAU - mutual information - Gauss algorithm
        """
        
        self.phase = self.flatten_field(self.phase)

        start = datetime.now()

        if not use_queue:
            self.adjacency_matrix = np.zeros((self.phase.shape[1], self.phase.shape[1]))

            if pool is None:
                map_func = map
            elif pool is not None:
                map_func = pool.map
            job_args = [ (i, j, self.phase[:, i], self.phase[:, j]) for i in range(self.phase.shape[1]) for j in range(i, self.phase.shape[1]) ]
            if method == 'MPC':
                job_results = map_func(_get_phase_coherence, job_args)
            elif method == 'MIGAU':
                job_results = map_func(_get_mutual_inf_gauss, job_args)
            elif method == 'MIEQQ':
                job_results = map_func(_get_mutual_inf_EQQ, job_args)
            del job_args

            for i, j, coh in job_results:
                self.adjacency_matrix[i, j] = coh
                self.adjacency_matrix[j, i] = coh

            for i in range(self.adjacency_matrix.shape[0]):
                self.adjacency_matrix[i, i] = 0.

            del job_results

        else:

            jobs = mp.Queue()
            results = mp.Queue()

            # start workers - BEFORE filling the queue as they are simultaneously computing while filling the queue
            workers = [mp.Process(target = self._process_matrix, args = (jobs, results)) for i in range(num_workers)]
            for w in workers:
                w.start()
                print "worker started"

            # fill queue with actual inputs
            cnt_results = 0
            for i in range(self.phase.shape[1]):
                for j in range(i, self.phase.shape[1]):
                    cnt_results += 1
                    jobs.put([i, j, self.phase[:, i], self.phase[:, j], method])
            
            # fill queue with None for workers to finish
            for i in range(num_workers):
                jobs.put(None)

            print "queue populated"
            print cnt_results

            self.adjacency_matrix = np.zeros((self.phase.shape[1], self.phase.shape[1]))

            # start processing results queue before actually workers finish as the queue might got filled and
            # processes would hang
            # while True:
            #     a = results.get()
            #     if a is None: # again, poison pill, the one None is put into results when workers are finished
            #         break
            #     else:
            #         i, j, val = a # write values - matrix is symmetric across all three methods
            #         self.adjacency_matrix[i, j] = val
            #         self.adjacency_matrix[j, i] = val
            cnt = 0
            while cnt < cnt_results:
                i, j, val = results.get()
                self.adjacency_matrix[i, j] = val
                self.adjacency_matrix[j, i] = val
                cnt += 1

            # finally, finish workers
            for w in workers:
                w.join()

            print "workers finished"

            for i in range(self.adjacency_matrix.shape[0]):
                self.adjacency_matrix[i, i] = 0.

        print datetime.now()-start
        
        self.phase = self.reshape_flat_field(self.phase)


    def save_net(self, fname, only_matrix = False):
        """
        Saves the scale specific network.
        If only_matrix is True, saves only adjacency_matrix, else saves the whole class.
        """

        import cPickle

        with open(fname, 'wb') as f:
            if only_matrix:
                cPickle.dump({'adjacency_matrix' : self.adjacency_matrix}, f, protocol = cPickle.HIGHEST_PROTOCOL)
            else:
                cPickle.dump(self.__dict__, f, protocol = cPickle.HIGHEST_PROTOCOL)


    def load_net(self, fname):
        """
        Loads the network into the class.
        """

        import cPickle

        with open(fname, 'rb') as f:
            data = cPickle.load(f)

        self.__dict__ = data

