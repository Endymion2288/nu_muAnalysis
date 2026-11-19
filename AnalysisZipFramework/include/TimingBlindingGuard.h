#ifndef TIMING_BLINDING_GUARD_H
#define TIMING_BLINDING_GUARD_H

#include <cmath>
#include <cstdint>

namespace TimingBlinding {

/**
 * Event-level kinematics and scintillator charges needed to evaluate the
 * orthogonal SR-ZoneB blinding guard (roadmap Section 5.1 & T0).
 */
struct EventKinematicsAndVeto {
    bool isMC{false};
    int distanceToCollidingBCID{0};
    int longTracks{0};
    float veto20Charge{0.0f};
    float veto21Charge{0.0f};
    float timingChargeTop{0.0f};
    float timingChargeBottom{0.0f};
    float preshower0Charge{0.0f};
    float preshower1Charge{0.0f};
    double leadYatTrig{0.0};
    double leadPz0GeV{0.0};
    uint32_t leadNLayers{0};
    double leadNDoF{0.0};
    double leadChi2NDF{999.0};
    double leadRMax{999.0};
    double leadRIFT{999.0};
    double leadRVetoNu{999.0};
    double leadThetaMrad{999.0};
    float vetoNu0RawCharge{0.0f};
    float vetoNu1RawCharge{0.0f};
    float vetoNu0ReducedCharge{-1.0f};
    float vetoNu1ReducedCharge{-1.0f};
};

/**
 * Returns true if the event passes all baseline downstream kinematic and
 * downstream scintillator requirements prior to the VetoNu veto (cuts.yaml).
 */
inline bool isKinematicSignalRegion(const EventKinematicsAndVeto& ev) {
    if (ev.longTracks <= 0) return false;
    if (!std::isfinite(ev.veto20Charge) || !std::isfinite(ev.veto21Charge)) return false;
    if (!(ev.veto20Charge > 40.0f && ev.veto21Charge > 40.0f)) return false;

    if (!std::isfinite(ev.leadYatTrig)) {
        return false;
    }
    const bool hitsTiming =
        (ev.leadYatTrig > 20.0 && std::isfinite(ev.timingChargeTop) && ev.timingChargeTop > 20.0f) ||
        (ev.leadYatTrig < -20.0 && std::isfinite(ev.timingChargeBottom) && ev.timingChargeBottom > 20.0f) ||
        (std::abs(ev.leadYatTrig) <= 20.0 &&
         std::isfinite(ev.timingChargeTop) && std::isfinite(ev.timingChargeBottom) &&
         (ev.timingChargeTop + ev.timingChargeBottom) > 20.0f);
    if (!hitsTiming) return false;

    if (!std::isfinite(ev.preshower0Charge) || !std::isfinite(ev.preshower1Charge)) return false;
    if (!(ev.preshower0Charge > 2.5f && ev.preshower1Charge > 2.5f)) return false;

    if (!std::isfinite(ev.leadPz0GeV) || !(ev.leadPz0GeV > 100.0)) return false;
    if (!(ev.leadNLayers >= 7)) return false;
    if (!std::isfinite(ev.leadNDoF) || !(ev.leadNDoF >= 9.0)) return false;
    if (!std::isfinite(ev.leadChi2NDF) || !(ev.leadChi2NDF < 15.0)) return false;
    if (!std::isfinite(ev.leadRMax) || !(ev.leadRMax < 95.0)) return false;
    if (!std::isfinite(ev.leadRIFT) || !(ev.leadRIFT < 95.0)) return false;
    if (!std::isfinite(ev.leadRVetoNu) || !(ev.leadRVetoNu < 120.0)) return false;
    if (!std::isfinite(ev.leadThetaMrad) || !(ev.leadThetaMrad < 25.0)) return false;

    return true;
}

/**
 * Returns true if a VetoNu layer enters Zone B (high charge in either reduced
 * charge or raw charge, conservatively covering datasets without reduced charge).
 */
inline bool isVetoNuZoneBActive(float rawQ, float redQ) {
    const bool rawActive = std::isfinite(rawQ) && (rawQ >= 30.0f);
    const bool redActive = std::isfinite(redQ) && (redQ >= 30.0f);
    return rawActive || redActive;
}

/**
 * Orthogonal SR-ZoneB blinding guard.
 * Returns true when an event is BLINDED and MUST be excluded from inspection/plotting.
 * - MC events and non-colliding BCIDs are unblinded (returns false).
 * - Outside kinematic SR or in Zone A (both VetoNu layers < 30 pC) is unblinded.
 * - In Zone B of kinematic SR collision data:
 *   - If hasCalibratedTime == true: ONLY unblinds CR-Prompt events with valid
 *     downstream reference and every active VetoNu layer having finite dt <= +1.5 ns.
 *   - If hasCalibratedTime == false (pre-calibration raw audit): blinds unless
 *     rawDelayMax_ns is finite and <= +0.5 ns (1.0 ns conservative safety margin).
 */
inline bool isBlindedSRZoneB(const EventKinematicsAndVeto& ev,
                             bool hasCalibratedTime,
                             bool validDownstreamRef,
                             bool validCal0,
                             double dt0_ns,
                             bool validCal1,
                             double dt1_ns,
                             double rawDelayMax_ns = 999.0) {
    if (ev.isMC) return false;
    if (ev.distanceToCollidingBCID != 0) return false;
    if (!isKinematicSignalRegion(ev)) return false;

    const bool act0 = isVetoNuZoneBActive(ev.vetoNu0RawCharge, ev.vetoNu0ReducedCharge);
    const bool act1 = isVetoNuZoneBActive(ev.vetoNu1RawCharge, ev.vetoNu1ReducedCharge);
    if (!act0 && !act1) return false;

    if (hasCalibratedTime) {
        if (!validDownstreamRef) return true;
        if (act0 && (!validCal0 || !std::isfinite(dt0_ns) || dt0_ns > 1.5)) return true;
        if (act1 && (!validCal1 || !std::isfinite(dt1_ns) || dt1_ns > 1.5)) return true;
        return false;
    }

    if (!std::isfinite(rawDelayMax_ns) || rawDelayMax_ns > 0.5) return true;
    return false;
}

} // namespace TimingBlinding

#endif // TIMING_BLINDING_GUARD_H
