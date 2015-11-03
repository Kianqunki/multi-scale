"""
created on Mar 4, 2014

@author: Nikola Jajcay, jajcay(at)cs.cas.cz
"""

import numpy as np
from src.data_class import DataField



def get_single_FT_surrogate(ts):
    """
    Returns single 1D Fourier transform surrogate.
    """

    np.random.seed()
    xf = np.fft.rfft(ts, axis = 0)
    angle = np.random.uniform(0, 2 * np.pi, (xf.shape[0],))
    # set the slowest frequency to zero, i.e. not to be randomised
    angle[0] = 0

    cxf = xf * np.exp(1j * angle)

    return np.fft.irfft(cxf, n = ts.shape[0], axis = 0)



def get_single_MF_surrogate(ts, randomise_from_scale = 2):
    """
    Returns single 1D multifractal surrogate.
    """

    return _compute_MF_surrogates([None, None, None, ts, randomise_from_scale])[-1]



def get_single_AR_surrogate(ts, order_range = [1,1]):
    """
    Returns single 1D autoregressive surrogate of some order.
    Order could be found numerically by setting order_range, or
    entered manually by selecting min and max order range to the
    desired order - e.g. [1,1].
    If the order was supposed to estimate, it is also returned.
    """

    _, _, _, order, res = _prepare_AR_surrogates([None, None, None, order_range, 'sbc', ts])
    num_ts = ts.shape[0] - order.order()
    res = res[:num_ts, 0]

    surr = _compute_AR_surrogates([None, None, None, res, order, num_ts])[-1]

    if np.diff(order_range) == 0:
        return surr
    else:
        return surr, order.order()



def _prepare_AR_surrogates(a):
    from var_model import VARModel
    i, j, lev, order_range, crit, ts = a
    if not np.any(np.isnan(ts)):
        v = VARModel()
        v.estimate(ts, order_range, True, crit, None)
        r = v.compute_residuals(ts)
    else:
        v = None
        r = np.nan
    return (i, j, lev, v, r) 
    
    
    
def _compute_AR_surrogates(a):
    i, j, lev, res, model, num_tm_s = a
    r = np.zeros((num_tm_s, 1), dtype = np.float64)       
    if not np.all(np.isnan(res)):
        ndx = np.argsort(np.random.uniform(size = (num_tm_s,)))
        r[ndx, 0] = res

        ar_surr = model.simulate_with_residuals(r)[:, 0]
    else:
        ar_surr = np.nan
        
    return (i, j, lev, ar_surr)
    
    
    
def _compute_FT_surrogates(a):
    i, j, lev, data, angle = a
            
    # transform the time series to Fourier domain
    xf = np.fft.rfft(data, axis = 0)
     
    # randomise the time series with random phases     
    cxf = xf * np.exp(1j * angle)
    
    # return randomised time series in time domain
    ft_surr = np.fft.irfft(cxf, n = data.shape[0], axis = 0)
    
    return (i, j, lev, ft_surr)
    


def _compute_MF_surrogates(a):
    import pywt
    np.random.seed()
    
    i, l, lev, ts, randomise_from_scale = a
    
    if not np.all(np.isnan(ts)):
        n = int(np.log2(ts.shape[0])) # time series length should be 2^n
        n_real = np.log2(ts.shape[0])
        
        if n != n_real:
            # if time series length is not 2^n
            raise Exception("Time series length must be power of 2 (2^n).")
        
        # get coefficient from discrete wavelet transform, 
        # it is a list of length n with numpy arrays as every object
        coeffs = pywt.wavedec(ts, 'db1', level = n-1)
        
        # prepare output lists and append coefficients which will not be shuffled
        coeffs_tilde = []
        for j in range(randomise_from_scale):
            coeffs_tilde.append(coeffs[j])
    
        shuffled_coeffs = []
        for j in range(randomise_from_scale):
            shuffled_coeffs.append(coeffs[j])
        
        # run for each desired scale
        for j in range(randomise_from_scale, len(coeffs)):
            
            # get multiplicators for scale j
            multiplicators = np.zeros_like(coeffs[j])
            for k in range(coeffs[j-1].shape[0]):
                if coeffs[j-1][k] == 0:
                    print("**WARNING: some zero coefficients in DWT transform!")
                    coeffs[j-1][k] = 1
                multiplicators[2*k] = coeffs[j][2*k] / coeffs[j-1][k]
                multiplicators[2*k+1] = coeffs[j][2*k+1] / coeffs[j-1][k]
           
            # shuffle multiplicators in scale j randomly
            coef = np.zeros_like(multiplicators)
            multiplicators = np.random.permutation(multiplicators)
            
            # get coefficients with tilde according to a cascade
            for k in range(coeffs[j-1].shape[0]):
                coef[2*k] = multiplicators[2*k] * coeffs_tilde[j-1][k]
                coef[2*k+1] = multiplicators[2*k+1] * coeffs_tilde[j-1][k]
            coeffs_tilde.append(coef)
            
            # sort original coefficients
            coeffs[j] = np.sort(coeffs[j])
            
            # sort shuffled coefficients
            idx = np.argsort(coeffs_tilde[j])
            
            # finally, rearange original coefficient according to coefficient with tilde
            temporary = np.zeros_like(coeffs[j])
            temporary[idx] = coeffs[j]
            shuffled_coeffs.append(temporary)
        
        # return randomised time series as inverse discrete wavelet transform
        mf_surr = pywt.waverec(shuffled_coeffs, 'db1')

    else:
        mf_surr = np.nan
        
    return (i, l, lev, mf_surr)



def _create_amplitude_adjusted_surrogates(a):
    i, j, lev, d, surr, m, v, t = a
    data = d.copy()
    
    if not np.all(np.isnan(data)):
        # sort surrogates
        idx = np.argsort(surr)
        
        # return seasonality back to the data
        if t is not None:
            data += t
        data *= v
        data += m
        
        # amplitude adjustment are original data sorted according to the surrogates
        data = np.sort(data)
        aa_surr = np.zeros_like(data)
        aa_surr[idx] = data

    else:
        aa_surr = np.nan

    return (i, j, lev, aa_surr)




class SurrogateField(DataField):
    """
    Class holds geofield of surrogate data and can construct surrogates.
    """
    
    def __init__(self, data = None):
        DataField.__init__(self)
        self.surr_data = None
        self.model_grid = None
        self.data = data
        

        
    def copy_field(self, field):
        """
        Makes a copy of another DataField
        """
        
        self.data = field.data.copy()
        if field.lons is not None:
            self.lons = field.lons.copy()
        else:
            self.lons = None
        if field.lats is not None:
            self.lats = field.lats.copy()
        else:
            self.lats = None
        self.time = field.time.copy()
        
        
        
    def add_seasonality(self, mean, var, trend):
        """
        Adds seasonality to surrogates if there were constructed from deseasonalised
        and optionally detrended data.
        """
        
        if self.surr_data is not None:
            if trend is not None:
                self.surr_data += trend
            self.surr_data *= var
            self.surr_data += mean
        else:
            raise Exception("Surrogate data has not been created yet.")
            
            
        
    def remove_seasonality(self, mean, var, trend):
        """
        Removes seasonality from surrogates in order to use same field for 
        multiple surrogate construction.
        """        
        
        if self.surr_data is not None:
            self.surr_data -= mean
            self.surr_data /= var
            if trend is not None:
                self.surr_data -= trend
        else:
            raise Exception("Surrogate data has not been created yet.")



    def center_surr(self):
        """
        Centers the surrogate data to zero mean and unit variance.
        """

        if self.surr_data is not None:
            self.surr_data -= np.nanmean(self.surr_data, axis = 0)
            self.surr_data /= np.nanstd(self.surr_data, axis = 0, ddof = 1)
        else:
            raise Exception("Surrogate data has not been created yet.")
        
        
        
    def get_surr(self):
        """
        Returns the surrogate data
        """
        
        if self.surr_data is not None:
            return self.surr_data.copy()
        else:
            raise Exception("Surrogate data has not been created yet.")
        


    def construct_fourier_surrogates(self, pool = None):
        """
        Constructs Fourier Transform (FT) surrogates (independent realizations which preserve
        linear structure and covariance structure)
        """
        
        if self.data is not None:

            np.random.seed()
            
            if pool is None:
                map_func = map
            else:
                map_func = pool.map
                
            if self.data.ndim > 1:
                num_lats = self.lats.shape[0]
                num_lons = self.lons.shape[0]
                if self.data.ndim == 4:
                    num_levels = self.data.shape[1]
                else:
                    num_levels = 1
                    self.data = self.data[:, np.newaxis, :, :]
            else:
                num_lats = 1
                num_lons = 1
                num_levels = 1
                self.data = self.data[:, np.newaxis, np.newaxis, np.newaxis]
                
            # generate uniformly distributed random angles
            a = np.fft.rfft(np.random.rand(self.data.shape[0]), axis = 0)
            angle = np.random.uniform(0, 2 * np.pi, (a.shape[0],))
            
            # set the slowest frequency to zero, i.e. not to be randomised
            angle[0] = 0
            del a
            
            job_data = [ (i, j, lev, self.data[:, lev, i, j], angle) for lev in range(num_levels) for i in range(num_lats) for j in range(num_lons) ]
            job_results = map_func(_compute_FT_surrogates, job_data)
            
            self.surr_data = np.zeros_like(self.data)
            
            for i, j, lev, surr in job_results:
                self.surr_data[:, lev, i, j] = surr
                
            # squeeze single-dimensional entries (e.g. station data)
            self.surr_data = np.squeeze(self.surr_data)
            self.data = np.squeeze(self.data)
           
        else:
            raise Exception("No data to randomise in the field. First you must copy some DataField.")
        
        
        
    def construct_fourier_surrogates_spatial(self, pool = None):
        """
        Constructs Fourier Transform (FT) surrogates (independent realizations which preserve
        linear structure but not covariance structure - shuffles also along spatial dimensions)
        (should be also used with station data which has only temporal dimension)
        """
        
        if self.data is not None:

            np.random.seed()
            
            if pool is None:
                map_func = map
            else:
                map_func = pool.map
                
            if self.data.ndim > 1:
                num_lats = self.lats.shape[0]
                num_lons = self.lons.shape[0]
                if self.data.ndim == 4:
                    num_levels = self.data.shape[1]
                else:
                    num_levels = 1
                    self.data = self.data[:, np.newaxis, :, :]
            else:
                num_lats = 1
                num_lons = 1
                num_levels = 1
                self.data = self.data[:, np.newaxis, np.newaxis, np.newaxis]
            
            # same as above except generate random angles along all dimensions of input data
            a = np.fft.rfft(np.random.rand(self.data.shape[0]), axis = 0)
            angle = np.random.uniform(0, 2 * np.pi, (a.shape[0], num_levels, num_lats, num_lons))
            angle[0, ...] = 0
            del a
            job_data = [ (i, j, lev, self.data[:, lev, i, j], angle[:, lev, i, j]) for lev in range(num_levels) for i in range(num_lats) for j in range(num_lons) ]
            job_results = map_func(_compute_FT_surrogates, job_data)
            
            self.surr_data = np.zeros_like(self.data)
            
            for i, j, lev, surr in job_results:
                self.surr_data[:, lev, i, j] = surr
                
            # squeeze single-dimensional entries (e.g. station data)
            self.surr_data = np.squeeze(self.surr_data)
            self.data = np.squeeze(self.data)
            
        else:
            raise Exception("No data to randomise in the field. First you must copy some DataField.")
    
        
        
    def construct_multifractal_surrogates(self, pool = None, randomise_from_scale = 2):
        """
        Constructs multifractal surrogates (independent shuffling of the scale-specific coefficients,
        preserving so-called multifractal structure - hierarchical process exhibiting information flow
        from large to small scales)
        written according to: Palus, M. (2008): Bootstraping multifractals: Surrogate data from random 
        cascades on wavelet dyadic trees. Phys. Rev. Letters, 101.
        """

        import pywt
        
        if self.data is not None:

            if pool is None:
                map_func = map
            else:
                map_func = pool.map
            
            if self.data.ndim > 1:
                num_lats = self.lats.shape[0]
                num_lons = self.lons.shape[0]
                if self.data.ndim == 4:
                    num_levels = self.data.shape[1]
                else:
                    num_levels = 1
                    self.data = self.data[:, np.newaxis, :, :]
            else:
                num_lats = 1
                num_lons = 1
                num_levels = 1
                self.data = self.data[:, np.newaxis, np.newaxis, np.newaxis]
            
            self.surr_data = np.zeros_like(self.data)

            job_data = [ (i, j, lev, self.data[:, lev, i, j], randomise_from_scale) for lev in range(num_levels) for i in range(num_lats) for j in range(num_lons) ]
            job_results = map_func(_compute_MF_surrogates, job_data)
            
            for i, j, lev, surr in job_results:
                self.surr_data[:, lev, i, j] = surr
            
            # squeeze single-dimensional entries (e.g. station data)
            self.surr_data = np.squeeze(self.surr_data)
            self.data = np.squeeze(self.data)
            
        else:
            raise Exception("No data to randomise in the field. First you must copy some DataField.")
        


    def prepare_AR_surrogates(self, pool = None, order_range = [1, 1], crit = 'sbc'):
        """
        Prepare for generating AR(k) surrogates by identifying the AR model and computing
        the residuals. Adapted from script by Vejmelka -- https://github.com/vejmelkam/ndw-climate
        """
        
        if self.data is not None:
            
            if pool is None:
                map_func = map
            else:
                map_func = pool.map
                
            if self.data.ndim > 1:
                num_lats = self.lats.shape[0]
                num_lons = self.lons.shape[0]
                if self.data.ndim == 4:
                    num_levels = self.data.shape[1]
                else:
                    num_levels = 1
                    self.data = self.data[:, np.newaxis, :, :]
            else:
                num_lats = 1
                num_lons = 1
                num_levels = 1
                self.data = self.data[:, np.newaxis, np.newaxis, np.newaxis]
            num_tm = self.time.shape[0]
                
            job_data = [ (i, j, lev, order_range, crit, self.data[:, lev, i, j]) for lev in range(num_levels) for i in range(num_lats) for j in range(num_lons) ]
            job_results = map_func(_prepare_AR_surrogates, job_data)
            max_ord = 0
            for r in job_results:
                if r[3] is not None and r[3].order() > max_ord:
                    max_ord = r[3].order()
            num_tm_s = num_tm - max_ord
            
            self.model_grid = np.zeros((num_levels, num_lats, num_lons), dtype = np.object)
            self.residuals = np.zeros((num_tm_s, num_levels, num_lats, num_lons), dtype = np.float64)
    
            for i, j, lev, v, r in job_results:
                self.model_grid[lev, i, j] = v
                if v is not None:
                    self.residuals[:, lev, i, j] = r[:num_tm_s, 0]
                else:
                    self.residuals[:, lev, i, j] = np.nan
    
            self.max_ord = max_ord
            
            self.data = np.squeeze(self.data)
            
        else:
            raise Exception("No data to randomise in the field. First you must copy some DataField.")
        
        
        
    def construct_surrogates_with_residuals(self, pool = None):
        """
        Constructs a new surrogate time series from AR(k) model.
        Adapted from script by Vejmelka -- https://github.com/vejmelkam/ndw-climate
        """
        
        if self.model_grid is not None:
            
            if pool is None:
                map_func = map
            else:
                map_func = pool.map
            
            if self.data.ndim > 1:
                num_lats = self.lats.shape[0]
                num_lons = self.lons.shape[0]
                if self.data.ndim == 4:
                    num_levels = self.data.shape[1]
                else:
                    num_levels = 1
            else:
                num_lats = 1
                num_lons = 1
                num_levels = 1
            num_tm_s = self.time.shape[0] - self.max_ord
            
            job_data = [ (i, j, lev, self.residuals[:, lev, i, j], self.model_grid[lev, i, j], num_tm_s) for lev in range(num_levels) for i in range(num_lats) for j in range(num_lons) ]
            job_results = map_func(_compute_AR_surrogates, job_data)
            
            self.surr_data = np.zeros((num_tm_s, num_levels, num_lats, num_lons))
            
            for i, j, lev, surr in job_results:
                self.surr_data[:, lev, i, j] = surr
                    
            self.surr_data = np.squeeze(self.surr_data)

        else:
           raise Exception("The AR(k) model is not simulated yet. First prepare surrogates!") 



    def amplitude_adjust_surrogates(self, mean, var, trend, pool = None):
        """
        Performs so-called amplitude adjustment to already created surrogate data. 
        """

        if self.surr_data is not None and self.data is not None:

            if pool is None:
                map_func = map
            else:
                map_func = pool.map


            if self.data.ndim > 1:
                num_lats = self.lats.shape[0]
                num_lons = self.lons.shape[0]
                if self.data.ndim == 4:
                    num_levels = self.data.shape[1]
                else:
                    num_levels = 1
                    self.data = self.data[:, np.newaxis, :, :]
                    self.surr_data = self.surr_data[:, np.newaxis, :, :]
            else:
                num_lats = 1
                num_lons = 1
                num_levels = 1
                self.data = self.data[:, np.newaxis, np.newaxis, np.newaxis]
                self.surr_data = self.surr_data[:, np.newaxis, np.newaxis, np.newaxis]
                
            old_shape = self.surr_data.shape

            job_data = [ (i, j, lev, self.data[:, lev, i, j], self.surr_data[:, lev, i, j], mean, var, trend) for lev in range(num_levels) for i in range(num_lats) for j in range(num_lons) ]
            job_results = map_func(_create_amplitude_adjusted_surrogates, job_data)

            self.surr_data = np.zeros(old_shape)

            for i, j, lev, AAsurr in job_results:
                self.surr_data[:, lev, i, j] = AAsurr

            # squeeze single-dimensional entries (e.g. station data)
            self.surr_data = np.squeeze(self.surr_data)
            self.data = np.squeeze(self.data)

        else:
            raise Exception("No surrogate data or/and no data in the field. "
                            "Amplitude adjustment works on already copied data and created surrogates.")
