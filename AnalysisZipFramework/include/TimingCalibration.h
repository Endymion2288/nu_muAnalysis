#ifndef TIMING_CALIBRATION_H
#define TIMING_CALIBRATION_H

#include <array>
#include <cmath>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace TimingCalib {

enum class TimingChannel : int {
    VetoNu0 = 0,
    VetoNu1 = 1,
    Veto10 = 2,
    Veto11 = 3,
    Veto20 = 4,
    Veto21 = 5,
    Timing01 = 6,
    Timing23 = 7,
    Preshower0 = 8,
    Preshower1 = 9,
    Preshower2 = 10,
    Preshower3 = 11,
    Muon0 = 12,
    Muon1 = 13,
    kNumChannels = 14
};

constexpr int kNumChannels = static_cast<int>(TimingChannel::kNumChannels);
constexpr int kGridN = 12;
constexpr double kGridMinMm = -150.0;
constexpr double kGridMaxMm = 150.0;
constexpr double kGridStepMm = (kGridMaxMm - kGridMinMm) / kGridN; // 25.0 mm
constexpr double kSpeedOfLightMPerNs = 0.299792458;
constexpr double kBunchSpacingNs = 25.0;
constexpr double kMaxUnwrapResidualNs = 6.25;

struct ChannelMeta {
    TimingChannel id;
    const char* name;
    double zMeters;
    double mipThresholdPC;
    double defaultSigmaNs;
};

struct RawChannelInput {
    bool present{false};
    bool goodStatus{false};
    double bcidTime{0.0};
    double triggerTime{0.0};
    double localTime{0.0};
    double rawCharge{0.0};
    double width{0.0};
    double xMm{999999.0};
    double yMm{999999.0};
    bool validPos{false};
};

struct CalibratedChannelResult {
    bool valid{false};
    bool unwrapFailed{false};
    double t1Ns{0.0};
    double t2Ns{0.0};
    double rUnwrapNs{0.0};
    double tCalNs{0.0};
    double sigmaCalNs{0.0};
};

struct EventTimingOutput {
    int anchorChannel{-1};
    std::array<CalibratedChannelResult, kNumChannels> channels{};
};

struct DownstreamRefResult {
    bool valid{false};
    int nUsed{0};
    double t0Ns{0.0};
    double sigmaT0Ns{0.0};
    double chi2{0.0};
    int ndof{0};
    uint32_t usedMask{0};
};

struct SpeedFitResult {
    bool valid{false};
    int nUsed{0};
    double t0Ns{0.0};
    double sigmaT0Ns{0.0};
    double sRelNsPerM{0.0};
    double beta{1.0};
    double sigmaBeta{0.0};
    double chi2{0.0};
    int ndof{0};
};

struct RegionCalibResult {
    bool valid{false};
    double tBarEffNs{0.0};
    double sigmaSpatialNs{0.0};
    double tCalNs{0.0};
    double sigmaCalNs{0.0};
};

struct RunOffsets {
    int run{0};
    std::string period;
    std::array<bool, kNumChannels> hasBcidRef{};
    std::array<double, kNumChannels> tRefBcid{};
    std::array<bool, kNumChannels> hasTrigRef{};
    std::array<double, kNumChannels> tTrigRelRef{};
};

struct PeriodTofMap {
    std::string period;
    std::array<std::array<double, kGridN * kGridN>, kNumChannels> tBar{};
    std::array<std::array<double, kGridN * kGridN>, kNumChannels> sigma2D{};
    std::array<std::array<double, kGridN * kGridN>, kNumChannels> ampA{};
    std::array<std::array<double, kGridN * kGridN>, kNumChannels> powerA{};
    std::array<std::array<double, kGridN * kGridN>, kNumChannels> floorC{};
    std::array<std::array<bool, kGridN * kGridN>, kNumChannels> hasPowerLaw{};
    std::array<std::vector<double>, kNumChannels> timeWalkQ{};
    std::array<std::vector<double>, kNumChannels> timeWalkDt{};
};

/**
 * Thread-safe compiled scintillator timing calibrator implementing Steps 1-4
 * of the Run 3 VetoNu timing pipeline (Quirk Internal Note Appendix E adapted
 * for nu_mu CC with LeadTrack extrapolation and anti-saturation downstream reference).
 */
class TimingCalibrator {
public:
    TimingCalibrator() = default;

    void loadFromDirectory(const std::string& calibDir);
    void loadOffsetsJson(const std::string& path);
    void loadTofMapsJson(const std::string& path);

    bool hasOffsets() const { return !m_runOffsets.empty(); }
    bool hasTofMaps() const { return !m_periodMaps.empty(); }

    static const std::array<ChannelMeta, kNumChannels>& channelMetadata();
    static std::string periodForDataRun(int run);
    static double wrap25(double dtNs);
    static bool isGoodWaveformStatus(int status) {
        return (status & ~(16 | 512)) == 0;
    }

    /**
     * Circular-safe combination of two PMT channels on the same Timing bar
     * (Timing0+Timing1 -> Timing01, Timing2+Timing3 -> Timing23).
     */
    static RawChannelInput combineTimingPair(
        bool good0, double bcid0, double trig0, double loc0, double qRaw0, double width0,
        bool good1, double bcid1, double trig1, double loc1, double qRaw1, double width1,
        double xMm, double yMm, bool validPos);

    /**
     * Step 1+2+3+4 calibration on a single collision-data event.
     * If applyTofMap is false, tCalNs stops after Step 2 unwrapping (used during LOO map generation).
     */
    EventTimingOutput calibrateDataEvent(
        int run,
        const std::array<RawChannelInput, kNumChannels>& inputs,
        bool applyTofMap = true,
        bool allowSubMipVetoNu = false) const;

    /**
     * Look up 2D TOF offset, time-walk offset, and charge-parameterized uncertainty
     * at position (xMm, yMm) and raw charge qRawPC.
     */
    void lookupPoint(
        const std::string& period,
        int chIdx,
        double xMm,
        double yMm,
        double qRawPC,
        double& tBarOut,
        double& timeWalkOut,
        double& sigmaOut) const;

    /**
     * Quirk Eqs. (E10)-(E15) circular-cone area-weighted calibration for VetoNu0/1
     * when hit position lies within radiusMm around (xCenterMm, yCenterMm).
     */
    RegionCalibResult calibrateCircularRegion(
        const std::string& period,
        int chIdx,
        double t2Ns,
        double qRawPC,
        double xCenterMm,
        double yCenterMm,
        double radiusMm) const;

    /**
     * Inverse-variance weighted v=c downstream arrival time t0_down excluding
     * VetoNu (and any channel with bit excludedMask set).
     */
    static DownstreamRefResult fitDownstreamReference(
        const EventTimingOutput& evt,
        uint32_t allowedMask = defaultDownstreamMask(),
        uint32_t excludeMask = 0);

    /**
     * Leave-One-Out v=c arrival time estimate for channel targetCh using all other
     * valid calibrated planes in allowedMask.
     */
    static DownstreamRefResult fitLeaveOneOutArrival(
        const EventTimingOutput& evt,
        int targetCh,
        uint32_t allowedMask = defaultPrimaryMask());

    /**
     * Weighted linear regression t_cal,i = t0 + s_rel * d_i (Quirk Eqs. 30-32).
     */
    static SpeedFitResult fitSpeedAndArrival(
        const EventTimingOutput& evt,
        uint32_t allowedMask = defaultPrimaryMask());

    static constexpr uint32_t channelBit(TimingChannel ch) {
        return 1u << static_cast<int>(ch);
    }

    static constexpr uint32_t defaultPrimaryMask() {
        return channelBit(TimingChannel::VetoNu0) |
               channelBit(TimingChannel::VetoNu1) |
               channelBit(TimingChannel::Veto10) |
               channelBit(TimingChannel::Veto11) |
               channelBit(TimingChannel::Veto20) |
               channelBit(TimingChannel::Veto21) |
               channelBit(TimingChannel::Timing01) |
               channelBit(TimingChannel::Timing23) |
               channelBit(TimingChannel::Preshower0) |
               channelBit(TimingChannel::Preshower1) |
               channelBit(TimingChannel::Muon0) |
               channelBit(TimingChannel::Muon1);
    }

    static constexpr uint32_t defaultDownstreamMask() {
        return channelBit(TimingChannel::Veto10) |
               channelBit(TimingChannel::Veto11) |
               channelBit(TimingChannel::Veto20) |
               channelBit(TimingChannel::Veto21) |
               channelBit(TimingChannel::Timing01) |
               channelBit(TimingChannel::Timing23) |
               channelBit(TimingChannel::Preshower0) |
               channelBit(TimingChannel::Preshower1) |
               channelBit(TimingChannel::Muon0) |
               channelBit(TimingChannel::Muon1);
    }

    /**
     * Deterministic Gaussian smearing helper for MC (seeded by run, eventID, channel).
     */
    static double deterministicNormal(int run, int64_t eventID, int chIdx, double sigmaNs);

private:
    const RunOffsets* findRunOffsets(int run) const;
    const PeriodTofMap* findPeriodMap(const std::string& period) const;
    static int gridIndex(double xMm, double yMm);
    static double evalTimeWalk(const PeriodTofMap& pmap, int chIdx, double qRawPC);

    std::unordered_map<int, RunOffsets> m_runOffsets;
    std::unordered_map<std::string, PeriodTofMap> m_periodMaps;
};

} // namespace TimingCalib

#endif // TIMING_CALIBRATION_H
