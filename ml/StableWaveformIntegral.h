#ifndef NU_MU_STABLE_WAVEFORM_INTEGRAL_H
#define NU_MU_STABLE_WAVEFORM_INTEGRAL_H

#include <algorithm>
#include <cmath>
#include <limits>

// Unnormalised ROOT "crystalball" shape, integrated only over a finite window.
// n <= 1 is allowed: the finite-window integral remains defined.
inline double StableWaveformIntegral(double peak, double mean, double sigma,
                                     double alpha, double n, double low, double high) {
    if (!std::isfinite(peak) || !std::isfinite(mean) || !std::isfinite(sigma) ||
        !std::isfinite(alpha) || !std::isfinite(n) || !std::isfinite(low) ||
        !std::isfinite(high) || sigma <= 0. || alpha == 0. || n <= 0. || high < low)
        return std::numeric_limits<double>::quiet_NaN();
    const double a = std::abs(alpha);
    double z0 = (low - mean) / sigma;
    double z1 = (high - mean) / sigma;
    if (alpha < 0.) {
        z0 = -z0;
        z1 = -z1;
    }
    if (z1 < z0) std::swap(z0, z1);
    double integral = 0.;
    if (z0 < -a) {
        const double end = std::min(z1, -a);
        const double logU0 = std::log1p((-a - end) * a / n);
        const double logU1 = std::log1p((-a - z0) * a / n);
        const double k = 1. - n;
        const double difference = k == 0. ? logU1 - logU0 :
            std::exp(k * logU0) * std::expm1(k * (logU1 - logU0)) / k;
        integral += n / a * std::exp(-.5 * a * a) * difference;
    }
    if (z1 > -a) {
        const double start = std::max(z0, -a);
        const double sqrtTwo = std::sqrt(2.);
        const double difference = start >= 0. ?
            std::erfc(start / sqrtTwo) - std::erfc(z1 / sqrtTwo) :
            std::erf(z1 / sqrtTwo) - std::erf(start / sqrtTwo);
        integral += std::sqrt(std::acos(-1.) / 2.) * difference;
    }
    return peak * sigma * integral;
}

#endif
