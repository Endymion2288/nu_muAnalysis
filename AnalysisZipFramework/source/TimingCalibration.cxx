#include "TimingCalibration.h"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <limits>
#include <nlohmann/json.hpp>
#include <stdexcept>

namespace TimingCalib {

using json = nlohmann::json;

namespace {

uint64_t splitmix64(uint64_t x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}

double u64ToUniform01(uint64_t x) {
    // 53-bit precision uniform in (0, 1)
    constexpr double kInv2Pow53 = 1.0 / 9007199254740992.0;
    const uint64_t top53 = x >> 11;
    const uint64_t safe = (top53 == 0) ? 1ULL : top53;
    return static_cast<double>(safe) * kInv2Pow53;
}

double evalPiecewiseLinear(const std::vector<double>& qs,
                           const std::vector<double>& dts,
                           double qRawPC) {
    if (qs.empty() || qs.size() != dts.size() || !std::isfinite(qRawPC)) return 0.0;
    if (qRawPC <= qs.front()) return dts.front();
    if (qRawPC >= qs.back()) return dts.back();
    auto it = std::upper_bound(qs.begin(), qs.end(), qRawPC);
    const std::size_t idx = static_cast<std::size_t>(it - qs.begin());
    const double q0 = qs[idx - 1], q1 = qs[idx];
    const double frac = (q1 > q0) ? ((qRawPC - q0) / (q1 - q0)) : 0.0;
    return dts[idx - 1] + frac * (dts[idx] - dts[idx - 1]);
}

int selectAnchorChannel(const std::array<bool, TimingCalib::kNumChannels>& eligible,
                        const std::array<TimingCalib::RawChannelInput, TimingCalib::kNumChannels>& inputs) {
    using TimingCalib::TimingChannel;
    const int iT01 = static_cast<int>(TimingChannel::Timing01);
    const int iT23 = static_cast<int>(TimingChannel::Timing23);
    if (eligible[iT01] || eligible[iT23]) {
        if (eligible[iT01] && eligible[iT23]) {
            return (inputs[iT23].rawCharge >= inputs[iT01].rawCharge) ? iT23 : iT01;
        }
        return eligible[iT23] ? iT23 : iT01;
    }
    int anc = -1;
    double bestQ = -1.0;
    for (int c : {static_cast<int>(TimingChannel::Veto20),
                  static_cast<int>(TimingChannel::Veto21),
                  static_cast<int>(TimingChannel::Veto10),
                  static_cast<int>(TimingChannel::Veto11),
                  static_cast<int>(TimingChannel::Muon0),
                  static_cast<int>(TimingChannel::Muon1),
                  static_cast<int>(TimingChannel::Preshower0),
                  static_cast<int>(TimingChannel::Preshower1)}) {
        if (eligible[c] && inputs[c].rawCharge > bestQ) {
            bestQ = inputs[c].rawCharge;
            anc = c;
        }
    }
    return anc;
}

} // namespace

const std::array<ChannelMeta, kNumChannels>& TimingCalibrator::channelMetadata() {
    static const std::array<ChannelMeta, kNumChannels> kMeta = {{
        {TimingChannel::VetoNu0,    "VetoNu0",    -3.123, 63.3,  0.53},
        {TimingChannel::VetoNu1,    "VetoNu1",    -3.102, 64.1,  0.54},
        {TimingChannel::Veto10,     "Veto10",     -1.790, 61.2,  0.23},
        {TimingChannel::Veto11,     "Veto11",     -1.770, 59.0,  0.23},
        {TimingChannel::Veto20,     "Veto20",     -1.620, 59.2,  0.23},
        {TimingChannel::Veto21,     "Veto21",     -1.599, 57.0,  0.24},
        {TimingChannel::Timing01,   "Timing01",   -0.022, 35.0,  0.35},
        {TimingChannel::Timing23,   "Timing23",   -0.037, 35.0,  0.35},
        {TimingChannel::Preshower0, "Preshower0",  2.583, 3.50,  0.28},
        {TimingChannel::Preshower1, "Preshower1",  2.658, 3.12,  0.28},
        {TimingChannel::Preshower2, "Preshower2",  2.583, 0.90,  0.30},
        {TimingChannel::Preshower3, "Preshower3",  2.658, 0.60,  0.32},
        {TimingChannel::Muon0,      "Muon0",       3.825, 35.0,  0.35},
        {TimingChannel::Muon1,      "Muon1",       4.005, 35.0,  0.35},
    }};
    return kMeta;
}

std::string TimingCalibrator::periodForDataRun(int run) {
    if (run < 10000) return "2022";
    if (run < 13000) return "2023";
    if (run < 15821) return "2024_preCaloNu";
    if (run <= 16924) return "2024_CaloNu";
    if (run < 18500) return "2024_postCaloNu";
    if (run < 21500) return "2025";
    return "2026";
}

std::string TimingCalibrator::mcFamilyForRun(int run) {
    if ((run >= 200080 && run <= 200090) || (run >= 200104 && run <= 200115)) {
        return "genie_2022_2023";
    }
    if ((run >= 200091 && run <= 200101) || (run >= 200160 && run <= 200171)) {
        return "genie_2024_noCaloNu";
    }
    if ((run >= 200137 && run <= 200147) || (run >= 200172 && run <= 200183)) {
        return "genie_2024_CaloNu";
    }
    if (run >= 210000 && run <= 210007) {
        return "fluka_mc22_s0010";
    }
    if (run == 210008 || run == 210009) {
        return "fluka_mc22_s0012";
    }
    if (run >= 210010) {
        return "fluka_mc24";
    }
    return "genie_2024_noCaloNu";
}

std::string TimingCalibrator::targetDataPeriodForMC(int run, int64_t eventID) {
    // Runs matching 2024 CaloNu geometry map deterministically to 2024_CaloNu
    if ((run >= 200137 && run <= 200147) || (run >= 200172 && run <= 200183)) {
        return "2024_CaloNu";
    }
    const uint64_t h = splitmix64(
        static_cast<uint64_t>(run) * 0x9e3779b97f4a7c15ULL ^
        static_cast<uint64_t>(eventID) ^
        0xa0761d6478bd642fULL);
    const double u = u64ToUniform01(h);
    // 2024 non-CaloNu geometry (preCaloNu 42.50 fb^-1 vs postCaloNu 12.45 fb^-1 -> 0.77343)
    if ((run >= 200091 && run <= 200101) || (run >= 200160 && run <= 200171) || run >= 210010) {
        return (u < 0.77343) ? "2024_preCaloNu" : "2024_postCaloNu";
    }
    // 2022-2023 geometry (2022 36.35 fb^-1 vs 2023 29.70 fb^-1 -> 0.55034)
    return (u < 0.55034) ? "2022" : "2023";
}

double TimingCalibrator::wrap25(double dtNs) {
    return dtNs - kBunchSpacingNs * std::round(dtNs / kBunchSpacingNs);
}

RawChannelInput TimingCalibrator::combineTimingPair(
    bool good0, double bcid0, double trig0, double loc0, double qRaw0, double width0,
    bool good1, double bcid1, double trig1, double loc1, double qRaw1, double width1,
    double xMm, double yMm, bool validPos) {

    RawChannelInput out;
    out.xMm = xMm;
    out.yMm = yMm;
    out.validPos = validPos;
    out.present = good0 && good1;
    if (!out.present) return out;
    if (!std::isfinite(bcid0) || !std::isfinite(bcid1) ||
        !std::isfinite(trig0) || !std::isfinite(trig1) ||
        !std::isfinite(qRaw0) || !std::isfinite(qRaw1)) {
        return out;
    }

    const double deltaBA = wrap25(bcid1 - bcid0);
    if (std::abs(deltaBA) > 8.5 || std::abs(trig1 - trig0) > 10.0) {
        return out;
    }

    double avgBcid = std::fmod(bcid0 + 0.5 * deltaBA + 10.0 * kBunchSpacingNs, kBunchSpacingNs);
    if (avgBcid < 0.0) avgBcid += kBunchSpacingNs;

    out.goodStatus = true;
    out.bcidTime = avgBcid;
    out.triggerTime = 0.5 * (trig0 + trig1);
    out.localTime = 0.5 * (loc0 + loc1);
    out.rawCharge = qRaw0 + qRaw1;
    out.width = 0.5 * (width0 + width1);
    return out;
}

RawChannelInput TimingCalibrator::combineTimingPairMC(
    bool good0, double loc0, double qRaw0, double width0,
    bool good1, double loc1, double qRaw1, double width1,
    double xMm, double yMm, bool validPos) {

    RawChannelInput out;
    out.xMm = xMm;
    out.yMm = yMm;
    out.validPos = validPos;
    out.present = good0 && good1;
    if (!out.present) return out;
    if (!std::isfinite(loc0) || !std::isfinite(loc1) ||
        loc0 <= 100.0 || loc1 <= 100.0 ||
        !std::isfinite(qRaw0) || !std::isfinite(qRaw1)) {
        return out;
    }
    if (std::abs(loc1 - loc0) > 10.0) {
        return out;
    }

    out.goodStatus = true;
    out.localTime = 0.5 * (loc0 + loc1);
    out.rawCharge = qRaw0 + qRaw1;
    out.width = 0.5 * (width0 + width1);
    return out;
}

void TimingCalibrator::loadFromDirectory(const std::string& calibDir) {
    namespace fs = std::filesystem;
    const fs::path dir(calibDir);
    const fs::path offsetsPath = dir / "ref_offsets_run3.json";
    const fs::path tofPath = dir / "tof_maps_run3.json";
    const fs::path mcPath = dir / "mc_timing_calib.json";
    if (fs::exists(offsetsPath)) {
        loadOffsetsJson(offsetsPath.string());
    } else {
        throw std::runtime_error("TimingCalibrator: missing " + offsetsPath.string());
    }
    if (fs::exists(tofPath)) {
        loadTofMapsJson(tofPath.string());
    }
    if (fs::exists(mcPath)) {
        loadMcCalibJson(mcPath.string());
    }
}

void TimingCalibrator::loadOffsetsJson(const std::string& path) {
    std::ifstream ifs(path);
    if (!ifs.is_open()) {
        throw std::runtime_error("TimingCalibrator: could not open offsets file " + path);
    }
    const json root = json::parse(ifs);
    const auto& runsNode = root.at("runs");
    const auto& meta = channelMetadata();

    m_runOffsets.clear();
    for (auto it = runsNode.begin(); it != runsNode.end(); ++it) {
        const int run = std::stoi(it.key());
        const json& rObj = it.value();
        RunOffsets ro;
        ro.run = run;
        ro.period = rObj.value("period", periodForDataRun(run));

        const json& chs = rObj.at("channels");
        for (int c = 0; c < kNumChannels; ++c) {
            const char* cname = meta[c].name;
            if (!chs.contains(cname)) continue;
            const json& cObj = chs.at(cname);
            if (cObj.contains("t_ref_bcid") && !cObj.at("t_ref_bcid").is_null()) {
                ro.hasBcidRef[c] = true;
                ro.tRefBcid[c] = cObj.at("t_ref_bcid").get<double>();
            }
            if (cObj.contains("t_trig_rel_ref") && !cObj.at("t_trig_rel_ref").is_null()) {
                ro.hasTrigRef[c] = true;
                ro.tTrigRelRef[c] = cObj.at("t_trig_rel_ref").get<double>();
            }
        }
        m_runOffsets.emplace(run, std::move(ro));
    }
}

void TimingCalibrator::loadTofMapsJson(const std::string& path) {
    std::ifstream ifs(path);
    if (!ifs.is_open()) {
        throw std::runtime_error("TimingCalibrator: could not open TOF maps file " + path);
    }
    const json root = json::parse(ifs);
    const auto& periodsNode = root.at("periods");
    const auto& meta = channelMetadata();

    m_periodMaps.clear();
    for (auto it = periodsNode.begin(); it != periodsNode.end(); ++it) {
        const std::string per = it.key();
        const json& pObj = it.value();
        PeriodTofMap pmap;
        pmap.period = per;

        for (int c = 0; c < kNumChannels; ++c) {
            pmap.tBar[c].fill(0.0);
            pmap.sigma2D[c].fill(meta[c].defaultSigmaNs);
            pmap.ampA[c].fill(0.0);
            pmap.powerA[c].fill(0.0);
            pmap.floorC[c].fill(meta[c].defaultSigmaNs);
            pmap.hasPowerLaw[c].fill(false);

            const char* cname = meta[c].name;
            if (!pObj.contains("channels") || !pObj.at("channels").contains(cname)) continue;
            const json& cObj = pObj.at("channels").at(cname);

            const auto& tb = cObj.at("t_bar");
            const auto& sg = cObj.at("sigma_2d");
            const int nCells = kGridN * kGridN;
            for (int k = 0; k < nCells; ++k) {
                pmap.tBar[c][k] = tb.at(k).get<double>();
                pmap.sigma2D[c][k] = sg.at(k).get<double>();
            }
            if (cObj.contains("amp_a") && cObj.contains("power_a") && cObj.contains("floor_c")) {
                const auto& aa = cObj.at("amp_a");
                const auto& pa = cObj.at("power_a");
                const auto& fc = cObj.at("floor_c");
                const auto& hpl = cObj.at("has_power_law");
                for (int k = 0; k < nCells; ++k) {
                    pmap.ampA[c][k] = aa.at(k).get<double>();
                    pmap.powerA[c][k] = pa.at(k).get<double>();
                    pmap.floorC[c][k] = fc.at(k).get<double>();
                    pmap.hasPowerLaw[c][k] = hpl.at(k).get<bool>();
                }
            }
            if (cObj.contains("time_walk_q") && cObj.contains("time_walk_dt")) {
                pmap.timeWalkQ[c] = cObj.at("time_walk_q").get<std::vector<double>>();
                pmap.timeWalkDt[c] = cObj.at("time_walk_dt").get<std::vector<double>>();
            }
        }
        m_periodMaps.emplace(per, std::move(pmap));
    }
}

const RunOffsets* TimingCalibrator::findRunOffsets(int run) const {
    auto it = m_runOffsets.find(run);
    if (it != m_runOffsets.end()) return &it->second;
    return nullptr;
}

const PeriodTofMap* TimingCalibrator::findPeriodMap(const std::string& period) const {
    auto it = m_periodMaps.find(period);
    if (it != m_periodMaps.end()) return &it->second;
    return nullptr;
}

const McFamilyModel* TimingCalibrator::findMcFamily(const std::string& family) const {
    auto it = m_mcFamilies.find(family);
    if (it != m_mcFamilies.end()) return &it->second;
    return nullptr;
}

const McRunOverride* TimingCalibrator::findMcRunOverride(int run) const {
    auto it = m_mcRunOverrides.find(run);
    if (it != m_mcRunOverrides.end()) return &it->second;
    return nullptr;
}

void TimingCalibrator::loadMcCalibJson(const std::string& path) {
    std::ifstream ifs(path);
    if (!ifs.is_open()) {
        throw std::runtime_error("TimingCalibrator: could not open MC timing calib file " + path);
    }
    const json root = json::parse(ifs);
    const auto& meta = channelMetadata();

    m_mcFamilies.clear();
    const auto& famNode = root.at("families");
    for (auto it = famNode.begin(); it != famNode.end(); ++it) {
        McFamilyModel fm;
        fm.name = it.key();
        const json& fObj = it.value();
        if (fObj.contains("channels")) {
            const json& chs = fObj.at("channels");
            for (int c = 0; c < kNumChannels; ++c) {
                const char* cname = meta[c].name;
                if (!chs.contains(cname)) continue;
                const json& cObj = chs.at(cname);
                auto& mc = fm.channels[c];
                if (cObj.contains("t_mc_ref") && !cObj.at("t_mc_ref").is_null()) {
                    mc.valid = true;
                    mc.tMcRefNs = cObj.at("t_mc_ref").get<double>();
                }
                mc.slopeXNsPerMm = cObj.value("slope_x_ns_per_mm", 0.0);
                mc.slopeYNsPerMm = cObj.value("slope_y_ns_per_mm", 0.0);
                mc.ampA = cObj.value("amp_a", 0.0);
                mc.powerA = cObj.value("power_a", 0.5);
                mc.floorC = cObj.value("floor_c", 0.025);
                mc.hasPowerLaw = cObj.value("has_power_law", false);
                if (cObj.contains("time_walk_q") && cObj.contains("time_walk_dt")) {
                    mc.timeWalkQ = cObj.at("time_walk_q").get<std::vector<double>>();
                    mc.timeWalkDt = cObj.at("time_walk_dt").get<std::vector<double>>();
                }
            }
        }
        m_mcFamilies.emplace(fm.name, std::move(fm));
    }

    m_mcRunOverrides.clear();
    if (root.contains("runs")) {
        const auto& runsNode = root.at("runs");
        for (auto it = runsNode.begin(); it != runsNode.end(); ++it) {
            const int run = std::stoi(it.key());
            const json& rObj = it.value();
            McRunOverride ro;
            ro.run = run;
            ro.family = rObj.value("family", mcFamilyForRun(run));
            if (rObj.contains("channels")) {
                const json& chs = rObj.at("channels");
                for (int c = 0; c < kNumChannels; ++c) {
                    const char* cname = meta[c].name;
                    if (!chs.contains(cname)) continue;
                    const json& cObj = chs.at(cname);
                    if (cObj.contains("t_mc_ref") && !cObj.at("t_mc_ref").is_null()) {
                        ro.hasTRef[c] = true;
                        ro.tRefNs[c] = cObj.at("t_mc_ref").get<double>();
                    }
                }
            }
            m_mcRunOverrides.emplace(run, std::move(ro));
        }
    }
}

int TimingCalibrator::gridIndex(double xMm, double yMm) {
    int ix = static_cast<int>(std::floor((xMm - kGridMinMm) / kGridStepMm));
    int iy = static_cast<int>(std::floor((yMm - kGridMinMm) / kGridStepMm));
    ix = std::clamp(ix, 0, kGridN - 1);
    iy = std::clamp(iy, 0, kGridN - 1);
    return ix * kGridN + iy;
}

double TimingCalibrator::evalTimeWalk(const PeriodTofMap& pmap, int chIdx, double qRawPC) {
    return evalPiecewiseLinear(pmap.timeWalkQ[chIdx], pmap.timeWalkDt[chIdx], qRawPC);
}

double TimingCalibrator::evalMcTimeWalk(const McChannelCalib& mc, double qRawPC) {
    return evalPiecewiseLinear(mc.timeWalkQ, mc.timeWalkDt, qRawPC);
}

double TimingCalibrator::evalMcSigma(const McChannelCalib& mc, double qRawPC) {
    if (!mc.hasPowerLaw || qRawPC <= 1.0 || !std::isfinite(qRawPC)) {
        return std::max(0.015, mc.floorC);
    }
    const double pl = mc.ampA * std::pow(qRawPC, -mc.powerA);
    const double sig = std::sqrt(pl * pl + mc.floorC * mc.floorC);
    return std::isfinite(sig) ? std::max(0.015, sig) : std::max(0.015, mc.floorC);
}

void TimingCalibrator::lookupPoint(
    const std::string& period,
    int chIdx,
    double xMm,
    double yMm,
    double qRawPC,
    double& tBarOut,
    double& timeWalkOut,
    double& sigmaOut) const {

    const auto& meta = channelMetadata();
    tBarOut = 0.0;
    timeWalkOut = 0.0;
    sigmaOut = meta[chIdx].defaultSigmaNs;

    const PeriodTofMap* pmap = findPeriodMap(period);
    if (!pmap) return;

    const int cell = gridIndex(xMm, yMm);
    tBarOut = pmap->tBar[chIdx][cell];
    timeWalkOut = evalTimeWalk(*pmap, chIdx, qRawPC);
    const bool isVetoNu = (chIdx == static_cast<int>(TimingChannel::VetoNu0) ||
                           chIdx == static_cast<int>(TimingChannel::VetoNu1));
    if (pmap->hasPowerLaw[chIdx][cell] && qRawPC > 1.0 && std::isfinite(qRawPC)) {
        const double pl = pmap->ampA[chIdx][cell] * std::pow(qRawPC, -pmap->powerA[chIdx][cell]);
        const double fl = pmap->floorC[chIdx][cell];
        sigmaOut = std::sqrt(pl * pl + fl * fl);
    } else {
        sigmaOut = pmap->sigma2D[chIdx][cell];
    }
    if (isVetoNu && std::isfinite(pmap->sigma2D[chIdx][cell])) {
        // Guard high-Q Landau extrapolation against collapsing below PMT transit-time floor (~0.82 * sigma_2d)
        sigmaOut = std::max(sigmaOut, 0.82 * pmap->sigma2D[chIdx][cell]);
    }
    if (!std::isfinite(sigmaOut) || sigmaOut < 0.05) {
        sigmaOut = meta[chIdx].defaultSigmaNs;
    }
}

EventTimingOutput TimingCalibrator::calibrateDataEvent(
    int run,
    const std::array<RawChannelInput, kNumChannels>& inputs,
    bool applyTofMap,
    bool allowSubMipVetoNu) const {

    EventTimingOutput out;
    const RunOffsets* ro = findRunOffsets(run);
    if (!ro) return out;
    const auto& meta = channelMetadata();

    std::array<bool, kNumChannels> eligibleForStep1{};
    std::array<bool, kNumChannels> eligibleForAnchor{};
    std::array<bool, kNumChannels> aboveMipArr{};
    std::array<double, kNumChannels> tTrigRel{};

    for (int c = 0; c < kNumChannels; ++c) {
        const auto& in = inputs[c];
        if (!in.present || !in.goodStatus) continue;
        if (!ro->hasBcidRef[c] || !ro->hasTrigRef[c]) continue;
        if (!std::isfinite(in.bcidTime) || !std::isfinite(in.triggerTime) || !std::isfinite(in.rawCharge)) continue;
        const bool isVetoNu = (c == static_cast<int>(TimingChannel::VetoNu0) || c == static_cast<int>(TimingChannel::VetoNu1));
        const bool aboveMip = (in.rawCharge > meta[c].mipThresholdPC);
        const double minQ = (isVetoNu && allowSubMipVetoNu) ? 10.0 : meta[c].mipThresholdPC;
        if (in.rawCharge <= minQ) continue;

        eligibleForStep1[c] = true;
        eligibleForAnchor[c] = aboveMip;
        aboveMipArr[c] = aboveMip;
        out.channels[c].t1Ns = wrap25(in.bcidTime - ro->tRefBcid[c]);
        tTrigRel[c] = in.triggerTime - ro->tTrigRelRef[c];
    }

    const int anc = selectAnchorChannel(eligibleForAnchor, inputs);
    if (anc < 0) return out;
    out.anchorChannel = anc;

    const std::string& period = ro->period;
    for (int c = 0; c < kNumChannels; ++c) {
        if (!eligibleForStep1[c]) continue;
        auto& cres = out.channels[c];
        const double dTrig = tTrigRel[c] - tTrigRel[anc];
        const double dt = wrap25(cres.t1Ns - out.channels[anc].t1Ns);
        const long long nShift = std::llround((dTrig - dt) / kBunchSpacingNs);
        const double rUnwrap = std::abs(dTrig - (dt + kBunchSpacingNs * static_cast<double>(nShift)));
        cres.rUnwrapNs = rUnwrap;
        cres.t2Ns = out.channels[anc].t1Ns + dt + kBunchSpacingNs * static_cast<double>(nShift);

        if (rUnwrap > kMaxUnwrapResidualNs || !std::isfinite(cres.t2Ns)) {
            cres.unwrapFailed = true;
            cres.valid = false;
            continue;
        }

        cres.valid = true;
        cres.aboveMip = aboveMipArr[c];
        if (applyTofMap && inputs[c].validPos) {
            double tBar = 0.0, tw = 0.0, sig = meta[c].defaultSigmaNs;
            lookupPoint(period, c, inputs[c].xMm, inputs[c].yMm, inputs[c].rawCharge, tBar, tw, sig);
            cres.tCalNs = cres.t2Ns - tBar - tw;
            cres.sigmaCalNs = sig;
        } else {
            cres.tCalNs = cres.t2Ns;
            cres.sigmaCalNs = meta[c].defaultSigmaNs;
        }
    }
    return out;
}

EventTimingOutput TimingCalibrator::calibrateMCEvent(
    int run,
    int64_t eventID,
    const std::array<RawChannelInput, kNumChannels>& inputs,
    bool applySmearing,
    bool allowSubMipVetoNu) const {

    EventTimingOutput out;
    const McRunOverride* rOv = findMcRunOverride(run);
    const std::string famName = (rOv && !rOv->family.empty()) ? rOv->family : mcFamilyForRun(run);
    const McFamilyModel* fm = findMcFamily(famName);
    if (!fm) fm = findMcFamily("genie_2024_noCaloNu");
    if (!fm) fm = findMcFamily("fluka_mc24");
    if (!fm) return out;

    const auto& meta = channelMetadata();
    const std::string targetPeriod = targetDataPeriodForMC(run, eventID);
    std::array<bool, kNumChannels> validAboveMip{};

    for (int c = 0; c < kNumChannels; ++c) {
        const auto& in = inputs[c];
        if (!in.present || !in.goodStatus) continue;
        if (!std::isfinite(in.localTime) || in.localTime <= 100.0 || !std::isfinite(in.rawCharge)) continue;
        const auto& mc = fm->channels[c];
        const bool hasOverrideRef = (rOv && rOv->hasTRef[c]);
        if (!mc.valid && !hasOverrideRef) continue;

        const bool isVetoNu = (c == static_cast<int>(TimingChannel::VetoNu0) || c == static_cast<int>(TimingChannel::VetoNu1));
        const bool aboveMip = (in.rawCharge > meta[c].mipThresholdPC);
        const double minQ = (isVetoNu && allowSubMipVetoNu) ? 10.0 : meta[c].mipThresholdPC;
        if (in.rawCharge <= minQ) continue;

        const double tRef = hasOverrideRef ? rOv->tRefNs[c] : mc.tMcRefNs;
        const double slopeTerm = in.validPos ? (mc.slopeXNsPerMm * in.xMm + mc.slopeYNsPerMm * in.yMm) : 0.0;
        const double twMc = evalMcTimeWalk(mc, in.rawCharge);
        const double t0Mc = in.localTime - tRef - slopeTerm - twMc;
        if (!std::isfinite(t0Mc)) continue;

        const double sigmaMc = evalMcSigma(mc, in.rawCharge);
        double tBarDummy = 0.0, twDummy = 0.0, sigmaData = meta[c].defaultSigmaNs;
        const double xEff = in.validPos ? in.xMm : 0.0;
        const double yEff = in.validPos ? in.yMm : 0.0;
        lookupPoint(targetPeriod, c, xEff, yEff, in.rawCharge, tBarDummy, twDummy, sigmaData);
        const double sigmaSmear = std::sqrt(std::max(0.0, sigmaData * sigmaData - sigmaMc * sigmaMc));

        auto& cres = out.channels[c];
        cres.valid = true;
        cres.unwrapFailed = false;
        cres.aboveMip = aboveMip;
        cres.t2Ns = t0Mc;
        cres.t1Ns = sigmaSmear;
        cres.rUnwrapNs = 0.0;
        cres.tCalNs = applySmearing ? (t0Mc + deterministicNormal(run, eventID, c, sigmaSmear)) : t0Mc;
        cres.sigmaCalNs = applySmearing ? sigmaData : sigmaMc;
        validAboveMip[c] = aboveMip;
    }

    out.anchorChannel = selectAnchorChannel(validAboveMip, inputs);
    return out;
}

RegionCalibResult TimingCalibrator::calibrateCircularRegion(
    const std::string& period,
    int chIdx,
    double t2Ns,
    double qRawPC,
    double xCenterMm,
    double yCenterMm,
    double radiusMm) const {

    RegionCalibResult res;
    if (!std::isfinite(t2Ns) || !std::isfinite(xCenterMm) || !std::isfinite(yCenterMm) || radiusMm <= 0.0) {
        return res;
    }
    const PeriodTofMap* pmap = findPeriodMap(period);
    if (!pmap) return res;

    // 25x25 sub-cell quadrature over each 25x25 mm calibration bin overlapping the disk
    constexpr int kSubN = 5;
    const double subStep = kGridStepMm / kSubN;
    const double r2 = radiusMm * radiusMm;

    std::vector<double> binAreas(kGridN * kGridN, 0.0);
    double totalArea = 0.0;

    for (int ix = 0; ix < kGridN; ++ix) {
        const double bx0 = kGridMinMm + ix * kGridStepMm;
        const double bx1 = bx0 + kGridStepMm;
        if (bx1 < xCenterMm - radiusMm || bx0 > xCenterMm + radiusMm) continue;
        for (int iy = 0; iy < kGridN; ++iy) {
            const double by0 = kGridMinMm + iy * kGridStepMm;
            const double by1 = by0 + kGridStepMm;
            if (by1 < yCenterMm - radiusMm || by0 > yCenterMm + radiusMm) continue;

            int insideCount = 0;
            for (int sx = 0; sx < kSubN; ++sx) {
                const double px = bx0 + (sx + 0.5) * subStep;
                const double dx = px - xCenterMm;
                for (int sy = 0; sy < kSubN; ++sy) {
                    const double py = by0 + (sy + 0.5) * subStep;
                    const double dy = py - yCenterMm;
                    if (dx * dx + dy * dy <= r2) {
                        ++insideCount;
                    }
                }
            }
            if (insideCount > 0) {
                const double a = static_cast<double>(insideCount) * subStep * subStep;
                binAreas[ix * kGridN + iy] = a;
                totalArea += a;
            }
        }
    }

    if (totalArea <= 0.0) {
        double tBar = 0.0, tw = 0.0, sig = 0.53;
        lookupPoint(period, chIdx, xCenterMm, yCenterMm, qRawPC, tBar, tw, sig);
        res.valid = true;
        res.tBarEffNs = tBar;
        res.sigmaSpatialNs = 0.0;
        res.tCalNs = t2Ns - tBar - tw;
        res.sigmaCalNs = sig;
        return res;
    }

    const bool isVetoNu = (chIdx == static_cast<int>(TimingChannel::VetoNu0) ||
                           chIdx == static_cast<int>(TimingChannel::VetoNu1));
    double tBarEff = 0.0;
    double sigEff = 0.0;
    for (int k = 0; k < kGridN * kGridN; ++k) {
        if (binAreas[k] <= 0.0) continue;
        const double f = binAreas[k] / totalArea;
        tBarEff += f * pmap->tBar[chIdx][k];
        double sigK = pmap->sigma2D[chIdx][k];
        if (pmap->hasPowerLaw[chIdx][k] && qRawPC > 1.0 && std::isfinite(qRawPC)) {
            const double pl = pmap->ampA[chIdx][k] * std::pow(qRawPC, -pmap->powerA[chIdx][k]);
            const double fl = pmap->floorC[chIdx][k];
            sigK = std::sqrt(pl * pl + fl * fl);
        }
        if (isVetoNu && std::isfinite(pmap->sigma2D[chIdx][k])) {
            sigK = std::max(sigK, 0.82 * pmap->sigma2D[chIdx][k]);
        }
        sigEff += f * sigK;
    }

    double varSpatial = 0.0;
    for (int k = 0; k < kGridN * kGridN; ++k) {
        if (binAreas[k] <= 0.0) continue;
        const double f = binAreas[k] / totalArea;
        const double diff = pmap->tBar[chIdx][k] - tBarEff;
        varSpatial += f * diff * diff;
    }

    const double tw = evalTimeWalk(*pmap, chIdx, qRawPC);
    res.valid = true;
    res.tBarEffNs = tBarEff;
    res.sigmaSpatialNs = std::sqrt(varSpatial);
    res.tCalNs = t2Ns - tBarEff - tw;
    res.sigmaCalNs = std::sqrt(sigEff * sigEff + varSpatial);
    return res;
}

DownstreamRefResult TimingCalibrator::fitDownstreamReference(
    const EventTimingOutput& evt,
    uint32_t allowedMask,
    uint32_t excludeMask) {

    DownstreamRefResult res;
    double sumW = 0.0;
    double sumWT = 0.0;
    int nUsed = 0;
    uint32_t mask = 0;

    for (int c = 0; c < kNumChannels; ++c) {
        const uint32_t bit = (1u << c);
        if ((allowedMask & bit) == 0 || (excludeMask & bit) != 0) continue;
        const auto& cr = evt.channels[c];
        if (!cr.valid || !std::isfinite(cr.tCalNs) || !std::isfinite(cr.sigmaCalNs) || cr.sigmaCalNs <= 0.0) continue;
        const double w = 1.0 / (cr.sigmaCalNs * cr.sigmaCalNs);
        sumW += w;
        sumWT += w * cr.tCalNs;
        mask |= bit;
        ++nUsed;
    }

    if (nUsed == 0 || sumW <= 0.0) return res;
    const double t0 = sumWT / sumW;
    double chi2 = 0.0;
    for (int c = 0; c < kNumChannels; ++c) {
        if ((mask & (1u << c)) == 0) continue;
        const auto& cr = evt.channels[c];
        const double r = (cr.tCalNs - t0) / cr.sigmaCalNs;
        chi2 += r * r;
    }

    res.valid = true;
    res.nUsed = nUsed;
    res.t0Ns = t0;
    res.sigmaT0Ns = 1.0 / std::sqrt(sumW);
    res.chi2 = chi2;
    res.ndof = std::max(0, nUsed - 1);
    res.usedMask = mask;
    return res;
}

DownstreamRefResult TimingCalibrator::fitDownstreamReferenceMode(
    const EventTimingOutput& evt,
    DownstreamMode mode,
    double leadYAtTrigMm,
    const std::array<RawChannelInput, kNumChannels>* inputs,
    uint32_t allowedMask,
    uint32_t excludeMask) {

    uint32_t effExclude = excludeMask;
    const int iT01 = static_cast<int>(TimingChannel::Timing01);
    const int iT23 = static_cast<int>(TimingChannel::Timing23);
    if (mode != DownstreamMode::AllValid) {
        const bool has01 = evt.channels[iT01].valid && ((allowedMask & (1u << iT01)) != 0);
        const bool has23 = evt.channels[iT23].valid && ((allowedMask & (1u << iT23)) != 0);
        if (has01 && has23) {
            if (std::isfinite(leadYAtTrigMm) && leadYAtTrigMm > 20.0) {
                effExclude |= (1u << iT01);
            } else if (std::isfinite(leadYAtTrigMm) && leadYAtTrigMm < -20.0) {
                effExclude |= (1u << iT23);
            } else if (inputs != nullptr) {
                if ((*inputs)[iT23].rawCharge >= (*inputs)[iT01].rawCharge) {
                    effExclude |= (1u << iT01);
                } else {
                    effExclude |= (1u << iT23);
                }
            }
        }
    }

    DownstreamRefResult res = fitDownstreamReference(evt, allowedMask, effExclude);
    if (mode != DownstreamMode::Trimmed3Sigma || !res.valid || res.nUsed < 3) {
        return res;
    }

    // Iterative single-worst > 3.5 sigma downstream outlier removal (never dropping below 2 channels)
    DownstreamRefResult cur = res;
    for (int step = 0; step < 3 && cur.nUsed >= 3; ++step) {
        int worstC = -1;
        double worstPull = 3.5;
        for (int c = 0; c < kNumChannels; ++c) {
            if ((cur.usedMask & (1u << c)) == 0) continue;
            const auto& cr = evt.channels[c];
            // Compute LOO pull relative to remaining downstream channels
            const double wC = 1.0 / (cr.sigmaCalNs * cr.sigmaCalNs);
            const double wTot = 1.0 / (cur.sigmaT0Ns * cur.sigmaT0Ns);
            const double wLoo = wTot - wC;
            if (wLoo <= 0.0) continue;
            const double tLoo = (wTot * cur.t0Ns - wC * cr.tCalNs) / wLoo;
            const double pull = std::abs(cr.tCalNs - tLoo) / std::sqrt(cr.sigmaCalNs * cr.sigmaCalNs + 1.0 / wLoo);
            if (pull > worstPull) {
                worstPull = pull;
                worstC = c;
            }
        }
        if (worstC < 0) break;
        effExclude |= (1u << worstC);
        cur = fitDownstreamReference(evt, allowedMask, effExclude);
    }
    return cur;
}

BackwardHypoResult TimingCalibrator::evaluateBackwardHypothesis(
    const EventTimingOutput& evt,
    const DownstreamRefResult& down,
    bool active0,
    bool active1) {

    BackwardHypoResult res;
    res.dtCombNs = std::numeric_limits<double>::quiet_NaN();
    res.zComb = std::numeric_limits<double>::quiet_NaN();
    res.dt10Ns = std::numeric_limits<double>::quiet_NaN();

    const auto& c0 = evt.channels[static_cast<int>(TimingChannel::VetoNu0)];
    const auto& c1 = evt.channels[static_cast<int>(TimingChannel::VetoNu1)];
    if (c0.valid && c1.valid && std::isfinite(c0.tCalNs) && std::isfinite(c1.tCalNs)) {
        res.dt10Ns = c1.tCalNs - c0.tCalNs;
    }

    res.nActiveLayers = (active0 ? 1 : 0) + (active1 ? 1 : 0);
    if (!down.valid || down.sigmaT0Ns <= 0.0 || res.nActiveLayers == 0) {
        return res;
    }

    const bool use0 = active0 && c0.valid && std::isfinite(c0.tCalNs) && c0.sigmaCalNs > 0.0;
    const bool use1 = active1 && c1.valid && std::isfinite(c1.tCalNs) && c1.sigmaCalNs > 0.0;
    res.nValidLayers = (use0 ? 1 : 0) + (use1 ? 1 : 0);
    if (res.nValidLayers == 0) {
        return res;
    }

    double sumWV = 0.0;
    double sumWTV = 0.0;
    auto accum = [&](const CalibratedChannelResult& cr) {
        const double w = 1.0 / (cr.sigmaCalNs * cr.sigmaCalNs);
        sumWV += w;
        sumWTV += w * cr.tCalNs;
    };
    if (use0) accum(c0);
    if (use1) accum(c1);

    const double tV = sumWTV / sumWV;
    const double dtComb = tV - down.t0Ns;
    const double wD = 1.0 / (down.sigmaT0Ns * down.sigmaT0Ns);
    const double sigComb = std::sqrt(1.0 / sumWV + 1.0 / wD);
    const double zComb = dtComb / sigComb;

    double chi2IntV = 0.0;
    if (use0) {
        const double r = (c0.tCalNs - tV) / c0.sigmaCalNs;
        chi2IntV += r * r;
    }
    if (use1) {
        const double r = (c1.tCalNs - tV) / c1.sigmaCalNs;
        chi2IntV += r * r;
    }

    const double chi2Mu = down.chi2 + chi2IntV + zComb * zComb;
    const double chi2NuBack = (dtComb > 0.0) ? (down.chi2 + chi2IntV) : chi2Mu;

    res.valid = true;
    res.dtCombNs = dtComb;
    res.zComb = zComb;
    res.chi2Mu = chi2Mu;
    res.chi2NuBack = chi2NuBack;
    res.deltaChi2Back = std::max(0.0, chi2Mu - chi2NuBack);
    return res;
}

DownstreamRefResult TimingCalibrator::fitLeaveOneOutArrival(
    const EventTimingOutput& evt,
    int targetCh,
    uint32_t allowedMask) {
    return fitDownstreamReference(evt, allowedMask, (1u << targetCh));
}

SpeedFitResult TimingCalibrator::fitSpeedAndArrival(
    const EventTimingOutput& evt,
    uint32_t allowedMask) {

    SpeedFitResult res;
    const auto& meta = channelMetadata();
    double S = 0.0, Sd = 0.0, St = 0.0, Sdd = 0.0, Sdt = 0.0;
    int nUsed = 0;

    for (int c = 0; c < kNumChannels; ++c) {
        if ((allowedMask & (1u << c)) == 0) continue;
        const auto& cr = evt.channels[c];
        if (!cr.valid || !cr.aboveMip || !std::isfinite(cr.tCalNs) || !std::isfinite(cr.sigmaCalNs) || cr.sigmaCalNs <= 0.0) continue;
        const double w = 1.0 / (cr.sigmaCalNs * cr.sigmaCalNs);
        const double d = meta[c].zMeters;
        const double t = cr.tCalNs;
        S += w;
        Sd += w * d;
        St += w * t;
        Sdd += w * d * d;
        Sdt += w * d * t;
        ++nUsed;
    }

    if (nUsed < 3 || S <= 0.0) return res;
    const double det = S * Sdd - Sd * Sd;
    if (det <= 1e-12) return res;

    const double t0 = (Sdd * St - Sd * Sdt) / det;
    const double sRel = (S * Sdt - Sd * St) / det;
    const double invC = 1.0 / kSpeedOfLightMPerNs;
    const double invV = sRel + invC;
    const double beta = (invV > 1e-9) ? (invC / invV) : 99.0;
    const double varT0 = Sdd / det;
    const double varS = S / det;

    double chi2 = 0.0;
    for (int c = 0; c < kNumChannels; ++c) {
        if ((allowedMask & (1u << c)) == 0) continue;
        const auto& cr = evt.channels[c];
        if (!cr.valid || !cr.aboveMip) continue;
        const double pred = t0 + sRel * meta[c].zMeters;
        const double r = (cr.tCalNs - pred) / cr.sigmaCalNs;
        chi2 += r * r;
    }

    res.valid = true;
    res.nUsed = nUsed;
    res.t0Ns = t0;
    res.sigmaT0Ns = std::sqrt(varT0);
    res.sRelNsPerM = sRel;
    res.beta = beta;
    res.sigmaBeta = (invV > 1e-9) ? (beta * beta / invC) * std::sqrt(varS) : 0.0;
    res.chi2 = chi2;
    res.ndof = nUsed - 2;
    return res;
}

double TimingCalibrator::deterministicNormal(int run, int64_t eventID, int chIdx, double sigmaNs) {
    if (sigmaNs <= 0.0 || !std::isfinite(sigmaNs)) return 0.0;
    const uint64_t seedBase =
        splitmix64(static_cast<uint64_t>(run) * 0x9e3779b97f4a7c15ULL ^
                   static_cast<uint64_t>(eventID) ^
                   (static_cast<uint64_t>(chIdx + 17) << 48));
    const double u1 = u64ToUniform01(splitmix64(seedBase));
    const double u2 = u64ToUniform01(splitmix64(seedBase ^ 0x517cc1b727220a95ULL));
    constexpr double kTwoPi = 6.28318530717958647692;
    const double z = std::sqrt(-2.0 * std::log(u1)) * std::cos(kTwoPi * u2);
    return z * sigmaNs;
}

} // namespace TimingCalib
