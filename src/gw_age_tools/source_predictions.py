"""
created matt_dumont 
on: 22/09/23
"""
import warnings
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from gw_age_tools.exponential_piston_flow import make_age_dist, check_age_inputs


def predict_source_future_past_conc_bepm(initial_conc, mrt, mrt_p1, frac_p1, f_p1, f_p2,
                                         prev_slope, fut_slope, age_range, max_conc, min_conc,
                                         max_fut_conc=np.inf, min_fut_conc=0, precision=2):
    """
    predict the source and receptor concentration in the future and past based on the current concentration
    the historical observed slope and the future predicted/scenario slope
    :param initial_conc: initial concentration (at time = 0 yrs)
    :param mrt: mean residence time of the source (yrs)
    :param mrt_p1: mean residence time of the first piston (yrs)
    :param frac_p1: fraction of the source that is in the first piston
    :param f_p1: fraction of exponential flow the first piston
    :param f_p2: fraction of exponential flow the second piston
    :param prev_slope: slope of the previous trend (conc/yr)
    :param fut_slope: slope of the future trend (conc/yr)
    :param age_range: range of ages to predict the source concentration for (yrs)
                      (start, stop) where start is negative and stop is positive years from the present
                      time = 0 yrs is the present
    :param max_conc: maximum concentration of the source (to limit optimisation)
    :param min_conc: minimum concentration of the source (to limit optimisation)
    :param max_fut_conc: maximum concentration of the source in the future (to limit the future slope creating crazy
                         numbers)
    :param min_fut_conc: minimum concentration of the source in the future (to limit the slope creating
                         negative numbers)
    :param precision: precision of the age distribution times (decimal places) default is 2, approximately monthly
    :return: (source_conc, receptor_conc) where source_conc is a pandas series of the source concentration
                and receptor_conc is a pandas series of the receptor concentration both indexed by age in years
                relative to the initial concentration at time = 0 yrs (- for past, + for future)
    """
    start, stop = age_range
    assert start < stop, 'start must be less than stop'
    assert start <= 0, 'start must be less than or equal to 0'
    assert stop >= 0, 'stop must be greater than or equal to 0'

    mrt_p2 = None
    mrt, mrt_p2 = check_age_inputs(mrt, mrt_p1, mrt_p2, frac_p1, precision, f_p1, f_p2)
    age_step, ages, age_fractions = make_age_dist(mrt, mrt_p1, mrt_p2, frac_p1, precision, f_p1, f_p2, start=np.nan)

    source_conc_past = predict_historical_source_conc(init_conc=initial_conc,
                                                      mrt=mrt, mrt_p1=mrt_p1, mrt_p2=mrt_p2,
                                                      frac_p1=frac_p1, f_p1=f_p1, f_p2=f_p2,
                                                      prev_slope=prev_slope, max_conc=max_conc, min_conc=min_conc,
                                                      start_age=start, precision=precision)

    fut_idx = np.arange(0, stop + age_step, age_step).round(precision)

    source_future_conc = pd.Series(
        index=fut_idx,
        data=source_conc_past.loc[0] + fut_slope * fut_idx
    )
    source_future_conc = source_future_conc.clip(lower=min_fut_conc, upper=max_fut_conc)

    total_source_conc = pd.concat([source_conc_past.drop(index=0), source_future_conc]).sort_index()
    out_years = np.arange(start, stop, age_step).round(precision)
    out_conc = np.full_like(out_years, np.nan)
    for i, t in enumerate(out_years):
        out_conc[i] = (total_source_conc.loc[(t - ages).round(precision)] * age_fractions).sum()
    receptor_conc = pd.Series(index=out_years, data=out_conc)

    return total_source_conc, receptor_conc


def predict_future_conc_bepm(once_and_future_source_conc: pd.Series, predict_start, predict_stop,
                             mrt_p1, frac_p1, f_p1, f_p2, mrt=None, mrt_p2=None, fill_value=1,
                             fill_threshold=0.05, precision=2, pred_step=0.01):
    """
    predict the receptor concentration based on the source concentration time series and the 
    binary piston flow model parameters  
    :param once_and_future_source_conc: pd.Series of the source concentration index by age in decimal years
                                        the Series can have missing values and will be interpolated onto a
                                        0.01 yr regular index therefore the once_and_future_source_conc may
                                        be passed with values only at the start, stop, and inflection points
    :param predict_start: start of the prediction period (decimal years)
    :param predict_stop: end of the prediction period (decimal years)
    :param mrt_p1: mean residence time of the first piston (yrs)
    :param frac_p1: fraction of the source that is in the first piston
    :param f_p1: fraction of exponential flow the first piston
    :param f_p2: fraction of exponential flow the second piston
    :param mrt: mean residence time of the source (yrs) or None one of mrt or mrt_p2 must be passed
    :param mrt_p2: mean residence time of the second piston (yrs) or None one of mrt or mrt_p2 must be passed
    :param fill_value: value to prepend to the source concentration to meet the full age distribution needed (e.g.
                       the concentration of very old water), up to the fill_threshold may be filled with the
                       fill_value before an error is raised
    :param fill_threshold: threshold for the source concentration to be filled with the minimum value default is
                             0.05 (5% of the concentration at the start time)
    :param precision: precision of the age distribution (decimal places)
    :param pred_step: step size for the prediction (yrs) default is 0.01 (approximately monthly), but this
                      can result in longer run times for large prediction periods, so a larger step size
                      can be used.  Note that pred_step must be greater or equal to the precision used
    :return: receptor_conc a pandas series of the receptor concentration indexed by age in years
    """
    mrt, mrt_p2 = check_age_inputs(mrt, mrt_p1, mrt_p2, frac_p1, precision, f_p1, f_p2)
    assert isinstance(pred_step, float), 'pred_step must be a float'

    age_step, ages, age_fractions = make_age_dist(mrt, mrt_p1, mrt_p2, frac_p1, precision, f_p1, f_p2)
    assert pred_step >= age_step, f'{pred_step=} must be greater than or equal to the {precision=}'

    assert isinstance(once_and_future_source_conc, pd.Series), 'once_and_future_source_conc must be a pandas Series'
    assert pd.api.types.is_float_dtype(once_and_future_source_conc.index), ('index of once_and_future_source_conc'
                                                                            'must be float')
    assert pd.api.types.is_number(predict_start), 'predict_start must be a number'
    assert pd.api.types.is_number(predict_stop), 'predict_stop must be a number'
    assert pd.api.types.is_number(fill_value), 'min_value must be a number'
    assert pd.api.types.is_number(fill_threshold), 'fill_threshold must be a number'

    # make the source concentration a regular series
    once_and_future_source_conc = once_and_future_source_conc.copy(True)
    once_and_future_source_conc.index = once_and_future_source_conc.index.values.round(precision)
    expect_idx_vals = np.arange(once_and_future_source_conc.index.min(),
                                once_and_future_source_conc.index.max() + age_step,
                                age_step).round(precision)
    temp = pd.Series(index=expect_idx_vals, data=np.nan)
    temp.loc[once_and_future_source_conc.index] = once_and_future_source_conc.values
    once_and_future_source_conc = temp
    once_and_future_source_conc = once_and_future_source_conc.sort_index()
    once_and_future_source_conc = once_and_future_source_conc.interpolate(method='linear', limit_direction='both')

    # check that enough concentration data has been passed for the stop,
    if predict_stop > once_and_future_source_conc.index.max():
        raise ValueError(f'predict_stop ({predict_stop}) must be less than or equal to the max age of the source '
                         f'({once_and_future_source_conc.index.max()})')

    # check the start
    pred_ages = (predict_start - ages).round(precision)
    idx = np.in1d(pred_ages, once_and_future_source_conc.index)
    if not idx.all():
        missing_age_frac = age_fractions[~idx].sum()
        minium_pass_age = np.flip(pred_ages)[(np.flip(age_fractions).cumsum() >= fill_threshold).argmax()]
        if missing_age_frac > fill_threshold:
            raise ValueError(
                f'the source concentration is missing {missing_age_frac * 100:0.2f}% of the concentration on'
                f' the old end of the source.  This is greater than the fill_threshold of '
                f'{fill_threshold} and the prediction cannot be made, concentration data must be passed'
                f'from at least {minium_pass_age} years')
        else:
            warnings.warn(f'the source concentration is missing {missing_age_frac * 100:0.2f}% of the concentration on'
                          f' the old end of the source.  This is less than the fill_threshold of '
                          f'{fill_threshold} and the missing values will be filled with the minimum value of '
                          f'{fill_value} and the prediction will be made. To avoid this warning pass concentration '
                          f'data from at least {pred_ages.min()} years')

            once_and_future_source_conc = pd.concat((once_and_future_source_conc,
                                                     pd.Series(index=pred_ages[~idx], data=fill_value)))

    out_times = np.arange(predict_start, predict_stop, pred_step).round(precision)
    out_conc = np.full_like(out_times, np.nan)
    for i, t in enumerate(out_times):
        out_conc[i] = (once_and_future_source_conc.loc[(t - ages).round(precision)] * age_fractions).sum()
    receptor_conc = pd.Series(index=out_times, data=out_conc)
    return receptor_conc


def predict_historical_source_conc(init_conc, mrt, mrt_p1, mrt_p2, frac_p1, f_p1, f_p2, prev_slope, max_conc,
                                   min_conc, start_age=np.nan, precision=2):
    """
    Estimate the historical source concentration based on the receptor initial concentration the previous slope and the
    BEPEM model parameters

    :param init_conc: the receptor initial concentration
    :param mrt: mean residence time of the source (yrs)
    :param mrt_p1: mean residence time of the first piston (yrs)
    :param mrt_p2: mean residence time of the second piston (yrs)
    :param frac_p1: fraction of the source that is in the first piston
    :param f_p1: fraction of exponential flow the first piston
    :param f_p2: fraction of exponential flow the second piston (use a dummy value if frac_p1 = 1)
    :param prev_slope: slope of the previous trend (conc/yr)
    :param max_conc: maximum concentration of the source (to limit optimisation)
    :param min_conc: minimum concentration of the source (to limit optimisation)
    :param start_age: set a start age for the source concentration (yrs) default is np.nan which will use the
                        maximum of the mrt_p1 and mrt_p2
    :param precision: precision of the age distribution (decimal places) default is 2, approximately monthly
    :return: source_conc_past a pandas series of the source concentration indexed by age in years
    """
    mrt, mrt_p2 = check_age_inputs(mrt, mrt_p1, mrt_p2, frac_p1, precision, f_p1, f_p2)
    age_step, ages, age_fractions = make_age_dist(mrt, mrt_p1, mrt_p2, frac_p1, precision, f_p1, f_p2)
    t = np.arange(-5, 1, 1).astype(float)
    ydata = pd.Series(index=t, data=init_conc + prev_slope * t)

    def opt_func(t_vals, source_slope, source_init_conc):
        ages_source = np.arange(0, np.nanmax([mrt_p1, mrt_p2]) * 5 + 5 + age_step, age_step).round(precision)
        total_source_conc = pd.Series(index=-ages_source, data=source_init_conc - source_slope * ages_source)
        total_source_conc.loc[total_source_conc < min_conc] = min_conc

        t_vals.round(precision)
        out_conc = np.full_like(t_vals, np.nan)
        for i, t in enumerate(t_vals):
            out_conc[i] = (total_source_conc.loc[(t - ages).round(precision)] * age_fractions).sum()
        return out_conc

    (s_slope, s_init), pcov = curve_fit(opt_func, t, ydata, p0=[prev_slope, init_conc],
                                        bounds=([0, 0], [np.inf, max_conc]))
    ages = np.arange(0., np.nanmax([mrt_p1, mrt_p2, np.abs(start_age)]) * 5 * 2 + age_step, age_step).round(
        precision)
    source_conc_past = pd.Series(index=ages * -1, data=s_init - s_slope * ages)
    source_conc_past.loc[source_conc_past < min_conc] = min_conc
    return source_conc_past


def lightweight_predict_future(source, out_years, ages, age_fractions, precision):
    """
    a lightweight version of predict_future_conc_bepm that does not check inputs and does not interpolate the source
    concentration and does not check the parmeters... use at your own warning
    :param source:
    :param out_years:
    :param ages:
    :param age_fractions:
    :param precision:
    :return:
    """
    out_conc = np.full_like(out_years, np.nan)
    for i, t in enumerate(out_years):
        out_conc[i] = (source.loc[(t - ages).round(precision)] * age_fractions).sum()
    receptor_conc = pd.Series(index=out_years, data=out_conc)
    return receptor_conc


def estimate_source_conc_bepfm(n_inflections, inflect_xlim, inflect_ylim, ts_data, source_start_conc,
                               mrt, mrt_p1, mrt_p2, frac_p1, f_p1, f_p2, precision=2,
                               inflect_start_x=None, inflect_start_y=None):  # todo check, make test, document
    """
    Estimate the source concentration based on a prescribed number of inflection points in the source data
    These inflection points must be constrained by the inflect_xlim and inflect_ylim
    :param n_inflections: int number of inflection points to use
    :param inflect_xlim: list of tuples (or similar) of the x limits of the inflection points
                            (e.g. [(start_date1, 10), (start_date2, 20)..])
    :param inflect_ylim: list of tuples (or similar) of the y limits. The y limits are in units of concentration
                         (ts.values)
    :param ts_data: pd.Series, time series data of the source concentration must have a datetime index
    :param source_start_conc: concentration of the source at the start of the time series (e.g. the natural
                                concentration)
    :param mrt: mean residence time of the source (yrs)
    :param mrt_p1: mean residence time of the first piston (yrs)
    :param mrt_p2: mean residence time of the second piston (yrs)
    :param frac_p1: fraction of the source that is in the first piston
    :param f_p1: fraction of exponential flow the first piston
    :param f_p2: fraction of exponential flow the second piston (use a dummy value if frac_p1 = 1)
    :param precision: precision of the age distribution (decimal places) default is 2, approximately monthly
    :param inflect_start_x: start points for the inflection points (x values) if None then the start points will be
                            set to the center of inflect_xlim
    :param inflect_start_y: start points for the inflection points (y values) if None then the start points will be
                            set to the center of inflect_ylim
    :return:
    """
    assert isinstance(ts_data, pd.Series), 'ts_data must be a pandas Series'
    assert pd.api.types.is_datetime64_any_dtype(ts_data.index), 'ts_data must have a datetime index'
    assert isinstance(n_inflections, int) and n_inflections > 0, 'n_inflections must be an integer > 0'
    assert pd.api.types.is_number(source_start_conc), 'source_start_conc must be a number'
    assert source_start_conc >= 0, 'source_start_conc must be greater than or equal to 0'

    inflect_xlim = np.atleast_2d(inflect_xlim)
    inflect_ylim = np.atleast_2d(inflect_ylim)
    assert inflect_xlim.shape == inflect_ylim.shape, 'inflect_xlim and inflect_ylim must have the same shape'
    assert inflect_xlim.shape == (n_inflections, 2), 'inflect_xlim and inflect_ylim must be shape (n_inflections, 2)'
    assert pd.api.types.is_datetime64_any_dtype(inflect_xlim), 'inflect_xlim must be a datetime'
    assert pd.api.types.is_numeric_dtype(inflect_ylim), 'inflect_ylim must be a number'
    start_date = ts_data.index.min()

    # convert inflect_xlim from datetime to years from start
    inflect_xlim = np.array([
        ((pd.Series(inflect_xlim[:, 0]) - start_date).dt.days / 365.25).values,
        ((pd.Series(inflect_xlim[:, 1]) - start_date).dt.days / 365.25).values,
    ]).transpose().round(precision)

    if inflect_start_x is not None:
        assert len(inflect_start_x) == n_inflections, 'inflect_start_x must be the same length as n_inflections'
        assert pd.api.types.is_datetime64_any_dtype(inflect_start_x), 'inflect_start_x must be a datetime'
        inflect_start_x = ((pd.Series(inflect_start_x) - start_date).dt.days / 365.25).values.round(precision)
    else:
        inflect_start_x = inflect_xlim.mean(axis=1).round(precision)

    if inflect_start_y is not None:
        assert len(inflect_start_y) == n_inflections, 'inflect_start_y must be the same length as n_inflections'
        assert pd.api.types.is_numeric_dtype(inflect_start_y), 'inflect_start_y must be a number'
        inflect_start_y = np.array(inflect_start_y)
    else:
        inflect_start_y = inflect_ylim.mean(axis=1)

    # make age info
    mrt, mrt_p2 = check_age_inputs(mrt, mrt_p1, mrt_p2, frac_p1, precision, f_p1, f_p2)
    age_step, ages, age_fractions = make_age_dist(mrt, mrt_p1, mrt_p2, frac_p1, precision, f_p1, f_p2)

    intime = ((ts_data.index - start_date).days / 365.25).values.round(precision)

    # run create source (to ensure it works)
    use_args = np.concatenate((inflect_start_x[:, np.newaxis], inflect_start_y[:, np.newaxis]), axis=1).flatten()
    use_lims_min = []
    use_lims_max = []
    for i in range(n_inflections):
        use_lims_min.append(inflect_xlim[i, 0])
        use_lims_min.append(inflect_ylim[i, 0])
        use_lims_max.append(inflect_xlim[i, 1])
        use_lims_max.append(inflect_ylim[i, 1])
    use_lims = [use_lims_min, use_lims_max]
    assert np.atleast_2d(use_lims).shape == (2, n_inflections * 2), 'use_lims must be shape (2, n_inflections*2)'
    _make_source(ages, intime, precision, source_start_conc, n_inflections, use_args)

    # make function to optimise
    def opt_func(t, *args):
        assert len(args) == n_inflections * 2, 'args must be a list of length n_inflections * 2'
        t = t.round(precision)
        source = _make_source(ages, t, precision, source_start_conc, n_inflections, args)
        out_conc = predict_future_conc_bepm(once_and_future_source_conc=source, predict_start=t.min(),
                                            predict_stop=(t.max() + age_step).round(precision),
                                            mrt_p1=mrt_p1, frac_p1=frac_p1, f_p1=f_p1, f_p2=f_p2, mrt=mrt,
                                            mrt_p2=mrt_p2,
                                            fill_value=source_start_conc,
                                            fill_threshold=0.10, precision=precision, pred_step=age_step)
        out_conc = out_conc.loc[t]
        assert not out_conc.isna().any()
        return out_conc

    # run opt_function once to ensure it works
    assert not np.isnan(intime).any()
    temp = opt_func(intime, *use_args)
    assert not temp.isna().any()

    # run optimisation
    print('running optimisation')
    params, pcov = curve_fit(opt_func, intime, ts_data.values,
                             p0=use_args,
                             bounds=use_lims)

    # generate results (source, true receptor, and modelled receptor)
    source = _make_source(ages, intime, precision, source_start_conc, n_inflections, params)
    true_receptor = pd.Series(index=intime, data=ts_data.values)
    modelled_receptor = opt_func(intime, *params)

    source.index = start_date + pd.to_timedelta(source.index * 365.25, unit='D')
    true_receptor.index = start_date + pd.to_timedelta(true_receptor.index * 365.25, unit='D')
    modelled_receptor.index = start_date + pd.to_timedelta(modelled_receptor.index * 365.25, unit='D')

    return source, true_receptor, modelled_receptor


def _make_source(ages, t, precision, source_start_conc, n_inflections, args):
    age_step = 10 ** -precision
    source = pd.Series(index=np.arange(-ages.max(), t.max() + age_step * 2, age_step).round(precision),
                       data=np.nan).round(precision).sort_index()
    source[0 - ages.max()] = source_start_conc
    assert len(args) == n_inflections * 2, 'args must be a list of length n_inflections * 2'
    for i in range(n_inflections):
        x0 = args[i * 2]
        y0 = args[i * 2 + 1]
        source[x0] = y0
    source[source.index.max()] = y0  # set last concentration to the same as the last inflection point
    source = source.interpolate(method='linear', limit_direction='both')
    return source
