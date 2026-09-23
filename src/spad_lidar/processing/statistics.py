"""Extracted A implementation; public compatibility exports remain at the old path."""
import numpy as np


def histogram_sample_range(trials):
    """Per-bin empirical extrema of the distance-statistics acquisitions."""
    count=len(trials)
    lower=upper=None
    if count:
        lower=np.array(trials[0],dtype=float,copy=True)
        upper=lower.copy()
        for histogram in trials[1:]:
            np.minimum(lower,histogram,out=lower)
            np.maximum(upper,histogram,out=upper)
    return {
        'method':'sample_min_max',
        'trial_count':count,
        'available':bool(count),
        'lower_counts':lower.tolist() if count else None,
        'upper_counts':upper.tolist() if count else None,
        'includes_first_observation':bool(count),
        'source':'distance_statistics_trial_histograms',
        'note':'误差棒为测距统计MC中每个bin的样本最小值—最大值，使用全部重复采集（包括测距失败的采集）；不是均值置信区间，也不是理论保证上下限。蓝柱是这批采集的第1次观测，不取均值。重复0次不显示，1次上下限与蓝柱重合。',
    }

