#include "TimingBlindingGuard.h"
#include "TimingCalibration.h"
#include "GRLUtils.h"
#include "ConfigUtils.h"
#include "MessageService.hpp"

#include <ROOT/RDataFrame.hxx>
#include <ROOT/RVec.hxx>
#include <TChain.h>
#include <TDirectory.h>
#include <TFile.h>
#include <TH1D.h>
#include <TROOT.h>
#include <TTree.h>

#include <nlohmann/json.hpp>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace {

using json = nlohmann::json;
using TimingCalib::TimingChannel;
using TimingCalib::TimingCalibrator;
using TimingCalib::kNumChannels;
using TimingCalib::kBunchSpacingNs;
using TimingCalib::kMaxUnwrapResidualNs;
using RawInputArray = std::array<TimingCalib::RawChannelInput, kNumChannels>;

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

uint64_t splitmix64(uint64_t x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}

double deterministicUniform01(int32_t run, int64_t eventID, uint64_t salt) {
    const uint64_t h = splitmix64(
        static_cast<uint64_t>(run) * 0x9e3779b97f4a7c15ULL ^
        static_cast<uint64_t>(eventID) ^ salt);
    constexpr double kInv2Pow53 = 1.0 / 9007199254740992.0;
    const uint64_t top53 = h >> 11;
    return static_cast<double>(top53) * kInv2Pow53;
}

std::vector<std::string> splitCommaList(const std::string& s) {
    std::vector<std::string> out;
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ',')) {
        if (!item.empty()) out.push_back(item);
    }
    return out;
}

struct TaskSpec {
    std::string taskId;
    int year{0};
    int run{0};
    std::vector<std::string> files;
    uint64_t bytes{0};
};

struct SchemaSignature {
    bool hasVetoSt{false};
    bool hasNativeVeto11{false};
    bool hasPreshower23{false};
    bool hasMuon{false};
    bool hasReducedCharge{false};
    std::string eventTimeType{"UInt_t"};
    std::string nLayersType{"ROOT::VecOps::RVec<unsigned int>"};

    std::string key() const {
        return std::string(hasVetoSt ? "1" : "0") +
               (hasNativeVeto11 ? "1" : "0") +
               (hasPreshower23 ? "1" : "0") +
               (hasMuon ? "1" : "0") +
               (hasReducedCharge ? "1" : "0") + "|" +
               eventTimeType + "|" + nLayersType;
    }
};

struct ScannerTrackData {
    int nTracks{0};
    double leadPz0GeV{kNaN};
    uint32_t leadNLayers{0};
    double leadNDoF{kNaN};
    double leadChi2NDF{kNaN};
    double leadRMax{kNaN};
    double leadThetaMrad{kNaN};
    // Plane positions for lead track:
    // 0:VetoNu, 1:Veto1, 2:Veto2, 3:Trig, 4:PS1, 5:PS2, 6:Muon1, 7:Muon2
    std::array<double, 8> x{};
    std::array<double, 8> y{};
    std::array<bool, 8> validPos{};

    // Subleading & 3rd track diagnostics for 2-track / 3-track validation
    bool clean2Trk{false};
    bool clean3Trk{false};
    double subPz0GeV{kNaN};
    double subXTrig{kNaN};
    double subYTrig{kNaN};
    double subXVN{kNaN};
    double subYVN{kNaN};
    double d12TrigMm{kNaN};
    double d12VnMm{kNaN};
    double d12Ps1Mm{kNaN};
};

struct ScannerBlindCharges {
    float veto20Charge{0.0f};
    float veto21Charge{0.0f};
    float timingTopCharge{0.0f};
    float timingBottomCharge{0.0f};
    float preshower0Charge{0.0f};
    float preshower1Charge{0.0f};
    float vetoNu0ReducedCharge{-1.0f};
    float vetoNu1ReducedCharge{-1.0f};
};

// Fast thread-local integer histogram (eliminates TH1 virtual/mutex overhead inside ForeachSlot)
struct FastHist1D {
    int nBins{0};
    double xMin{0.0};
    double xMax{1.0};
    double invWidth{1.0};
    std::vector<uint64_t> bins;
    uint64_t underflow{0};
    uint64_t overflow{0};

    void init(int nb, double xmin, double xmax) {
        nBins = nb;
        xMin = xmin;
        xMax = xmax;
        invWidth = static_cast<double>(nb) / (xmax - xmin);
        bins.assign(static_cast<size_t>(nb), 0ULL);
        underflow = 0;
        overflow = 0;
    }

    void fill(double x) {
        if (!std::isfinite(x)) return;
        if (x < xMin) {
            ++underflow;
            return;
        }
        if (x >= xMax) {
            ++overflow;
            return;
        }
        int b = static_cast<int>((x - xMin) * invWidth);
        if (b < 0) b = 0;
        if (b >= nBins) b = nBins - 1;
        ++bins[static_cast<size_t>(b)];
    }

    void addFrom(const FastHist1D& other) {
        if (bins.empty()) {
            *this = other;
            return;
        }
        for (size_t i = 0; i < bins.size(); ++i) bins[i] += other.bins[i];
        underflow += other.underflow;
        overflow += other.overflow;
    }

    TH1D toTH1D(const std::string& name, const std::string& title) const {
        TH1D h(name.c_str(), title.c_str(), nBins, xMin, xMax);
        h.SetBinContent(0, static_cast<double>(underflow));
        for (int b = 0; b < nBins; ++b) {
            h.SetBinContent(b + 1, static_cast<double>(bins[static_cast<size_t>(b)]));
        }
        h.SetBinContent(nBins + 1, static_cast<double>(overflow));
        return h;
    }
};

struct Pass1RunData {
    bool initialized{false};
    int run{0};
    uint64_t nTotal{0};
    uint64_t nGrlFail{0};
    uint64_t nNonColliding{0};
    uint64_t nBlinded{0};
    uint64_t nSingleMuon{0};
    bool hasVeto11{false};
    bool hasPreshower23{false};
    bool hasMuon{false};
    uint64_t nV20RefEvents{0};
    uint64_t nV10RefEvents{0};

    std::array<uint64_t, kNumChannels> chNGood{};
    std::array<uint64_t, kNumChannels> chNSt512{};
    std::array<uint64_t, kNumChannels> chNSt16{};
    std::array<uint64_t, kNumChannels> chNSt4{};
    std::array<uint64_t, kNumChannels> chNBcidR50{};
    std::array<uint64_t, kNumChannels> chNBcidAll{};
    std::array<uint64_t, kNumChannels> chNDtrigV20{};
    std::array<uint64_t, kNumChannels> chNDtrigV10{};

    std::array<FastHist1D, kNumChannels> hBcidR50;
    std::array<FastHist1D, kNumChannels> hBcidAll;
    std::array<FastHist1D, kNumChannels> hDtrigV20;
    std::array<FastHist1D, kNumChannels> hDtrigV10;
    std::array<FastHist1D, kNumChannels> hDtrigDig1St0;
    std::array<FastHist1D, kNumChannels> hDtrigDig1St512;
    std::array<FastHist1D, kNumChannels> hDlocDig1St0;
    std::array<FastHist1D, kNumChannels> hDlocDig1St512;
    std::array<FastHist1D, kNumChannels> hRawCharge;
    FastHist1D hDtrigT23T01;

    void init(int runNum) {
        if (initialized) return;
        initialized = true;
        run = runNum;
        for (int c = 0; c < kNumChannels; ++c) {
            hBcidR50[c].init(500, 0.0, 25.0);
            hBcidAll[c].init(500, 0.0, 25.0);
            hDtrigV20[c].init(5000, -250.0, 250.0);
            hDtrigV10[c].init(5000, -250.0, 250.0);
            hDtrigDig1St0[c].init(5000, -250.0, 250.0);
            hDtrigDig1St512[c].init(5000, -250.0, 250.0);
            hDlocDig1St0[c].init(5000, -250.0, 250.0);
            hDlocDig1St512[c].init(5000, -250.0, 250.0);
            const bool isPs = (c >= static_cast<int>(TimingChannel::Preshower0) &&
                               c <= static_cast<int>(TimingChannel::Preshower3));
            hRawCharge[c].init(400, 0.0, isPs ? 20.0 : 400.0);
        }
        hDtrigT23T01.init(1200, -60.0, 60.0);
    }

    void mergeFrom(const Pass1RunData& other) {
        if (!initialized) init(other.run);
        nTotal += other.nTotal;
        nGrlFail += other.nGrlFail;
        nNonColliding += other.nNonColliding;
        nBlinded += other.nBlinded;
        nSingleMuon += other.nSingleMuon;
        hasVeto11 = hasVeto11 || other.hasVeto11;
        hasPreshower23 = hasPreshower23 || other.hasPreshower23;
        hasMuon = hasMuon || other.hasMuon;
        nV20RefEvents += other.nV20RefEvents;
        nV10RefEvents += other.nV10RefEvents;

        for (int c = 0; c < kNumChannels; ++c) {
            chNGood[c] += other.chNGood[c];
            chNSt512[c] += other.chNSt512[c];
            chNSt16[c] += other.chNSt16[c];
            chNSt4[c] += other.chNSt4[c];
            chNBcidR50[c] += other.chNBcidR50[c];
            chNBcidAll[c] += other.chNBcidAll[c];
            chNDtrigV20[c] += other.chNDtrigV20[c];
            chNDtrigV10[c] += other.chNDtrigV10[c];

            hBcidR50[c].addFrom(other.hBcidR50[c]);
            hBcidAll[c].addFrom(other.hBcidAll[c]);
            hDtrigV20[c].addFrom(other.hDtrigV20[c]);
            hDtrigV10[c].addFrom(other.hDtrigV10[c]);
            hDtrigDig1St0[c].addFrom(other.hDtrigDig1St0[c]);
            hDtrigDig1St512[c].addFrom(other.hDtrigDig1St512[c]);
            hDlocDig1St0[c].addFrom(other.hDlocDig1St0[c]);
            hDlocDig1St512[c].addFrom(other.hDlocDig1St512[c]);
            hRawCharge[c].addFrom(other.hRawCharge[c]);
        }
        hDtrigT23T01.addFrom(other.hDtrigT23T01);
    }
};

struct Pass2RunData {
    bool initialized{false};
    int run{0};
    uint64_t nTotal{0};
    uint64_t nGrlFail{0};
    uint64_t nNonColliding{0};
    uint64_t nBlinded{0};
    uint64_t nClean1Trk{0};
    uint64_t nClean2Trk{0};
    uint64_t nClean3Trk{0};
    std::array<uint64_t, kNumChannels> chNUnwrapPass{};
    std::array<uint64_t, kNumChannels> chNUnwrapFail{};
    std::array<uint64_t, kNumChannels> anchorCounts{};
    std::array<FastHist1D, kNumChannels> hRUnwrap;

    void init(int runNum) {
        if (initialized) return;
        initialized = true;
        run = runNum;
        for (int c = 0; c < kNumChannels; ++c) {
            hRUnwrap[c].init(125, 0.0, 12.5);
        }
    }

    void mergeFrom(const Pass2RunData& other) {
        if (!initialized) init(other.run);
        nTotal += other.nTotal;
        nGrlFail += other.nGrlFail;
        nNonColliding += other.nNonColliding;
        nBlinded += other.nBlinded;
        nClean1Trk += other.nClean1Trk;
        nClean2Trk += other.nClean2Trk;
        nClean3Trk += other.nClean3Trk;
        for (int c = 0; c < kNumChannels; ++c) {
            chNUnwrapPass[c] += other.chNUnwrapPass[c];
            chNUnwrapFail[c] += other.chNUnwrapFail[c];
            anchorCounts[c] += other.anchorCounts[c];
            hRUnwrap[c].addFrom(other.hRUnwrap[c]);
        }
    }
};

struct CompactCalibRecord {
    int32_t run{0};
    int64_t eventID{0};
    uint8_t is_cat0{0};
    uint8_t is_cat1{0};
    uint8_t is_cat2{0};
    uint8_t is_cat3{0};
    float w0{1.0f};
    float w1{1.0f};
    float w2{1.0f};
    int32_t anchor_ch{-1};
    uint16_t valid_mask{0};
    uint16_t above_mip_mask{0};
    uint16_t unwrap_fail_mask{0};
    int32_t n_long_tracks{0};
    float pz0_lead_gev{0.0f};
    float pz0_sub_gev{0.0f};
    float d12_trig_mm{0.0f};
    float d12_vn_mm{0.0f};
    float d12_ps1_mm{0.0f};
    float trk_x[8]{};
    float trk_y[8]{};
    float sub_x_trig{0.0f};
    float sub_y_trig{0.0f};
    float sub_x_vn{0.0f};
    float sub_y_vn{0.0f};
    float t2[kNumChannels]{};
    float q_raw[kNumChannels]{};
    float r_unwrap[kNumChannels]{};
};

// Track plane index for each of the 14 timing channels
constexpr std::array<int, kNumChannels> kChannelPlaneIdx = {{
    0, 0, // VetoNu0, VetoNu1
    1, 1, // Veto10, Veto11
    2, 2, // Veto20, Veto21
    3, 3, // Timing01, Timing23
    4, 5, // Preshower0, Preshower1
    4, 5, // Preshower2, Preshower3
    6, 7  // Muon0, Muon1
}};

double computeConservativeRawDelayMax(const RawInputArray& raw) {
    auto finiteLoc = [&](TimingChannel ch) -> double {
        const int idx = static_cast<int>(ch);
        const auto& in = raw[idx];
        return (in.present && in.goodStatus && std::isfinite(in.localTime)) ? in.localTime : kNaN;
    };
    auto pairMean = [](double a, double b) -> double {
        if (std::isfinite(a) && std::isfinite(b)) return 0.5 * (a + b);
        if (std::isfinite(a)) return a;
        if (std::isfinite(b)) return b;
        return kNaN;
    };
    const double v2Mean = pairMean(finiteLoc(TimingChannel::Veto20), finiteLoc(TimingChannel::Veto21));
    const double psMean = pairMean(finiteLoc(TimingChannel::Preshower0), finiteLoc(TimingChannel::Preshower1));
    double expLt = kNaN;
    if (std::isfinite(v2Mean)) expLt = v2Mean - 5.05;
    else if (std::isfinite(psMean)) expLt = psMean - 19.12;
    if (!std::isfinite(expLt)) return kNaN;

    const double lt0 = finiteLoc(TimingChannel::VetoNu0);
    const double lt1 = finiteLoc(TimingChannel::VetoNu1);
    const double d0 = std::isfinite(lt0) ? (lt0 - expLt) : kNaN;
    const double d1 = std::isfinite(lt1) ? (lt1 - expLt) : kNaN;
    if (std::isfinite(d0) && std::isfinite(d1)) return std::max(d0, d1);
    if (std::isfinite(d0)) return d0;
    if (std::isfinite(d1)) return d1;
    return kNaN;
}

bool channelFiducialOk(int chIdx, double xMm, double yMm, bool validPos) {
    if (!validPos || !std::isfinite(xMm) || !std::isfinite(yMm)) return false;
    if (std::abs(xMm) >= 120.0 || std::abs(yMm) >= 120.0) return false;
    if (chIdx == static_cast<int>(TimingChannel::Timing01)) return yMm < -5.0;
    if (chIdx == static_cast<int>(TimingChannel::Timing23)) return yMm > 5.0;
    return true;
}

bool checkBlinded(int distBCID,
                  int longTracks,
                  const ScannerTrackData& tk,
                  const RawInputArray& raw,
                  const ScannerBlindCharges& chg) {
    TimingBlinding::EventKinematicsAndVeto ev;
    ev.isMC = false;
    ev.distanceToCollidingBCID = distBCID;
    ev.longTracks = longTracks;
    ev.veto20Charge = chg.veto20Charge;
    ev.veto21Charge = chg.veto21Charge;
    ev.timingChargeTop = chg.timingTopCharge;
    ev.timingChargeBottom = chg.timingBottomCharge;
    ev.preshower0Charge = chg.preshower0Charge;
    ev.preshower1Charge = chg.preshower1Charge;
    ev.leadYatTrig = tk.validPos[3] ? tk.y[3] : kNaN;
    ev.leadPz0GeV = tk.leadPz0GeV;
    ev.leadNLayers = tk.leadNLayers;
    ev.leadNDoF = tk.leadNDoF;
    ev.leadChi2NDF = tk.leadChi2NDF;
    ev.leadRMax = tk.leadRMax;
    ev.leadRIFT = tk.validPos[2] ? std::hypot(tk.x[2], tk.y[2]) : kNaN;
    ev.leadRVetoNu = tk.validPos[0] ? std::hypot(tk.x[0], tk.y[0]) : kNaN;
    ev.leadThetaMrad = tk.leadThetaMrad;
    ev.vetoNu0RawCharge = static_cast<float>(raw[0].rawCharge);
    ev.vetoNu1RawCharge = static_cast<float>(raw[1].rawCharge);
    ev.vetoNu0ReducedCharge = chg.vetoNu0ReducedCharge;
    ev.vetoNu1ReducedCharge = chg.vetoNu1ReducedCharge;
    const double rawDelayMax = computeConservativeRawDelayMax(raw);
    return TimingBlinding::isBlindedSRZoneB(ev, false, false, false, 0.0, false, 0.0, rawDelayMax);
}

SchemaSignature probeTaskSchema(const TaskSpec& task) {
    SchemaSignature sig;
    if (task.files.empty()) {
        throw std::runtime_error("Task " + task.taskId + " has no input files");
    }
    std::unique_ptr<TFile> tf;
    for (const auto& fpath : task.files) {
        tf.reset(TFile::Open(fpath.c_str(), "READ"));
        if (tf && !tf->IsZombie()) break;
    }
    if (!tf || tf->IsZombie()) {
        throw std::runtime_error("Could not open any file in task " + task.taskId);
    }
    auto* tree = tf->Get<TTree>("nt");
    if (!tree) {
        throw std::runtime_error("Missing 'nt' tree in task " + task.taskId);
    }
    std::unordered_set<std::string> branches;
    auto* blist = tree->GetListOfBranches();
    const int nB = blist ? blist->GetEntries() : 0;
    for (int i = 0; i < nB; ++i) {
        branches.insert(blist->At(i)->GetName());
    }
    sig.hasVetoSt = branches.count("VetoSt10_raw_charge") > 0;
    sig.hasNativeVeto11 = (branches.count("Veto11_raw_charge") > 0) || (branches.count("VetoSt11_raw_charge") > 0);
    sig.hasPreshower23 = (branches.count("Preshower2_raw_charge") > 0) && (branches.count("Preshower3_raw_charge") > 0);
    sig.hasMuon = (branches.count("Muon0_raw_charge") > 0) && (branches.count("Muon1_raw_charge") > 0) &&
                  (branches.count("Track_X_atMuon1") > 0) && (branches.count("Track_X_atMuon2") > 0);
    sig.hasReducedCharge = (branches.count("VetoNu0_reduced_charge") > 0) && (branches.count("VetoNu1_reduced_charge") > 0);

    ROOT::RDataFrame probeDf(*tree);
    sig.eventTimeType = probeDf.GetColumnType("eventTime");
    sig.nLayersType = probeDf.GetColumnType("Track_nLayers");
    return sig;
}

template <typename TTime>
ROOT::RDF::RNode attachGrlGoodColumn(ROOT::RDF::RNode node, std::shared_ptr<const GRLUtils::GRLTimes> grl) {
    return node.Define("_grl_good",
        [grl](Int_t run, TTime eventTime) -> bool {
            const long long t = static_cast<long long>(eventTime);
            return grl->stable.contains(run, t) && !grl->excluded.contains(run, t);
        },
        {"run", "eventTime"});
}

template <typename TLayer>
ROOT::RDF::RNode attachTrackDataColumn(ROOT::RDF::RNode node) {
    return node.Define("_tk",
        [](const ROOT::VecOps::RVec<double>& pz0,
           const ROOT::VecOps::RVec<double>& px0,
           const ROOT::VecOps::RVec<double>& py0,
           const ROOT::VecOps::RVec<TLayer>& nLayers,
           const ROOT::VecOps::RVec<double>& ndof,
           const ROOT::VecOps::RVec<double>& chi2,
           const ROOT::VecOps::RVec<double>& rmax,
           const ROOT::VecOps::RVec<double>& xVn, const ROOT::VecOps::RVec<double>& yVn,
           const ROOT::VecOps::RVec<double>& xV1, const ROOT::VecOps::RVec<double>& yV1,
           const ROOT::VecOps::RVec<double>& xV2, const ROOT::VecOps::RVec<double>& yV2,
           const ROOT::VecOps::RVec<double>& xTr, const ROOT::VecOps::RVec<double>& yTr,
           const ROOT::VecOps::RVec<double>& xP1, const ROOT::VecOps::RVec<double>& yP1,
           const ROOT::VecOps::RVec<double>& xP2, const ROOT::VecOps::RVec<double>& yP2,
           const ROOT::VecOps::RVec<double>& xM1, const ROOT::VecOps::RVec<double>& yM1,
           const ROOT::VecOps::RVec<double>& xM2, const ROOT::VecOps::RVec<double>& yM2) -> ScannerTrackData {
            ScannerTrackData td;
            const int n = static_cast<int>(pz0.size());
            td.nTracks = n;
            td.x.fill(kNaN);
            td.y.fill(kNaN);
            if (n <= 0) return td;

            std::vector<int> order(static_cast<size_t>(n));
            for (int i = 0; i < n; ++i) order[static_cast<size_t>(i)] = i;
            std::sort(order.begin(), order.end(), [&](int a, int b) {
                return pz0[a] > pz0[b];
            });

            const int i0 = order[0];
            td.leadPz0GeV = pz0[i0] * 1e-3;
            td.leadThetaMrad = std::atan2(std::hypot(px0[i0], py0[i0]), pz0[i0]) * 1000.0;
            td.leadNLayers = (i0 < static_cast<int>(nLayers.size())) ? static_cast<uint32_t>(nLayers[i0]) : 0u;
            td.leadNDoF = (i0 < static_cast<int>(ndof.size())) ? ndof[i0] : kNaN;
            td.leadChi2NDF = (i0 < static_cast<int>(chi2.size()) && td.leadNDoF > 0.0) ? (chi2[i0] / td.leadNDoF) : kNaN;
            td.leadRMax = (i0 < static_cast<int>(rmax.size())) ? rmax[i0] : kNaN;

            auto setPlane = [&](int p, const ROOT::VecOps::RVec<double>& xv, const ROOT::VecOps::RVec<double>& yv) {
                if (i0 < static_cast<int>(xv.size()) && i0 < static_cast<int>(yv.size())) {
                    const double xx = xv[i0], yy = yv[i0];
                    if (std::isfinite(xx) && std::isfinite(yy) && std::abs(xx) < 1000.0 && std::abs(yy) < 1000.0) {
                        td.x[p] = xx;
                        td.y[p] = yy;
                        td.validPos[p] = true;
                    }
                }
            };
            setPlane(0, xVn, yVn);
            setPlane(1, xV1, yV1);
            setPlane(2, xV2, yV2);
            setPlane(3, xTr, yTr);
            setPlane(4, xP1, yP1);
            setPlane(5, xP2, yP2);
            setPlane(6, xM1, yM1);
            setPlane(7, xM2, yM2);

            auto isTrackClean = [&](int idx, double minPzGeV) -> bool {
                if (idx < 0 || idx >= n) return false;
                if (idx >= static_cast<int>(nLayers.size()) ||
                    idx >= static_cast<int>(ndof.size()) ||
                    idx >= static_cast<int>(chi2.size())) return false;
                const double pzg = pz0[idx] * 1e-3;
                const uint32_t nl = static_cast<uint32_t>(nLayers[idx]);
                const double dfv = ndof[idx];
                const double c2 = (dfv > 0.0) ? (chi2[idx] / dfv) : 999.0;
                return std::isfinite(pzg) && pzg > minPzGeV && nl >= 6 && dfv >= 9.0 && c2 < 15.0;
            };

            if (n >= 2) {
                const int i1 = order[1];
                td.subPz0GeV = pz0[i1] * 1e-3;
                if (i1 < static_cast<int>(xTr.size()) && i1 < static_cast<int>(yTr.size())) {
                    td.subXTrig = xTr[i1];
                    td.subYTrig = yTr[i1];
                    if (td.validPos[3] && std::isfinite(td.subXTrig) && std::isfinite(td.subYTrig)) {
                        td.d12TrigMm = std::hypot(td.x[3] - td.subXTrig, td.y[3] - td.subYTrig);
                    }
                }
                if (i1 < static_cast<int>(xVn.size()) && i1 < static_cast<int>(yVn.size())) {
                    td.subXVN = xVn[i1];
                    td.subYVN = yVn[i1];
                    if (td.validPos[0] && std::isfinite(td.subXVN) && std::isfinite(td.subYVN)) {
                        td.d12VnMm = std::hypot(td.x[0] - td.subXVN, td.y[0] - td.subYVN);
                    }
                }
                if (i1 < static_cast<int>(xP1.size()) && i1 < static_cast<int>(yP1.size()) && td.validPos[4]) {
                    if (std::isfinite(xP1[i1]) && std::isfinite(yP1[i1])) {
                        td.d12Ps1Mm = std::hypot(td.x[4] - xP1[i1], td.y[4] - yP1[i1]);
                    }
                }
                td.clean2Trk = isTrackClean(i0, 25.0) && isTrackClean(i1, 25.0);
                if (n >= 3) {
                    const int i2 = order[2];
                    td.clean3Trk = isTrackClean(i0, 20.0) && isTrackClean(i1, 20.0) && isTrackClean(i2, 20.0);
                }
            }
            return td;
        },
        {"Track_pz0", "Track_px0", "Track_py0", "Track_nLayers", "Track_nDoF", "Track_Chi2", "Track_r_atMaxRadius",
         "Track_X_atVetoNu", "Track_Y_atVetoNu",
         "Track_X_atVetoStation1", "Track_Y_atVetoStation1",
         "Track_X_atVetoStation2", "Track_Y_atVetoStation2",
         "Track_X_atTrig", "Track_Y_atTrig",
         "Track_X_atPreshower1", "Track_Y_atPreshower1",
         "Track_X_atPreshower2", "Track_Y_atPreshower2",
         "Track_X_atMuon1", "Track_Y_atMuon1",
         "Track_X_atMuon2", "Track_Y_atMuon2"});
}

struct ScannerRunOffsets {
    std::string period;
    std::array<bool, kNumChannels> hasBcidRef{};
    std::array<double, kNumChannels> tRefBcid{};
    std::array<bool, kNumChannels> hasTrigRef{};
    std::array<double, kNumChannels> tTrigRelRef{};
};

std::unordered_map<int, ScannerRunOffsets> loadRunOffsetsMap(const std::string& path) {
    std::ifstream ifs(path);
    if (!ifs.is_open()) {
        throw std::runtime_error("Cannot open ref offsets JSON: " + path);
    }
    const json root = json::parse(ifs);
    const auto& meta = TimingCalibrator::channelMetadata();
    std::unordered_map<int, ScannerRunOffsets> out;
    const auto& runs = root.at("runs");
    for (auto it = runs.begin(); it != runs.end(); ++it) {
        const int run = std::stoi(it.key());
        const auto& rObj = it.value();
        ScannerRunOffsets ro;
        ro.period = rObj.value("period", TimingCalibrator::periodForDataRun(run));
        const auto& chs = rObj.at("channels");
        for (int c = 0; c < kNumChannels; ++c) {
            const char* cname = meta[c].name;
            if (!chs.contains(cname)) continue;
            const auto& cObj = chs.at(cname);
            if (cObj.contains("t_ref_bcid") && !cObj.at("t_ref_bcid").is_null()) {
                ro.hasBcidRef[c] = true;
                ro.tRefBcid[c] = cObj.at("t_ref_bcid").get<double>();
            }
            if (cObj.contains("t_trig_rel_ref") && !cObj.at("t_trig_rel_ref").is_null()) {
                ro.hasTrigRef[c] = true;
                ro.tTrigRelRef[c] = cObj.at("t_trig_rel_ref").get<double>();
            }
        }
        out.emplace(run, std::move(ro));
    }
    return out;
}

std::pair<double, double> periodPrescaleProbs(const std::string& period) {
    // Returns {pCore, pEdge} tuned for ~400k-800k clean 1-trk events per period
    if (period == "2022") return {0.0025, 0.0125};
    if (period == "2023") return {0.0030, 0.0150};
    if (period == "2024_preCaloNu") return {0.0008, 0.0040};
    if (period == "2024_CaloNu") return {0.0004, 0.0020};
    if (period == "2024_postCaloNu") return {0.0025, 0.0125};
    if (period == "2025") return {0.0005, 0.0025};
    return {0.0018, 0.0090}; // 2026
}

ROOT::RDF::RNode prepareScannerNode(
    TChain& chain,
    const SchemaSignature& sig,
    const std::shared_ptr<const GRLUtils::GRLTimes>& grl) {

    ROOT::RDF::RNode df = ROOT::RDataFrame(chain);

    auto hasCol = [&](const std::string& name) {
        const auto cols = df.GetColumnNames();
        return std::find(cols.begin(), cols.end(), name) != cols.end();
    };

    if (sig.hasVetoSt) {
        const auto cols = df.GetColumnNames();
        for (const auto& c : cols) {
            if (c.rfind("VetoSt", 0) != 0) continue;
            const std::string alias = "Veto" + c.substr(6);
            if (!hasCol(alias)) df = df.Alias(alias, c);
        }
    }

    auto ensureInt = [&](const std::string& name, Int_t val) {
        if (!hasCol(name)) df = df.Define(name, [val]() -> Int_t { return val; }, {});
    };
    auto ensureFloat = [&](const std::string& name, Float_t val) {
        if (!hasCol(name)) df = df.Define(name, [val]() -> Float_t { return val; }, {});
    };
    auto ensureRVecD = [&](const std::string& name) {
        if (!hasCol(name)) df = df.Define(name, []() { return ROOT::VecOps::RVec<double>{}; }, {});
    };
    auto ensureChannel = [&](const std::string& pfx) {
        ensureInt(pfx + "_status", -1);
        ensureFloat(pfx + "_bcidtime", 0.0f);
        ensureFloat(pfx + "_triggertime", 0.0f);
        ensureFloat(pfx + "_localtime", 0.0f);
        ensureFloat(pfx + "_raw_charge", 0.0f);
        ensureFloat(pfx + "_width", 0.0f);
    };

    ensureChannel("Veto11");
    ensureChannel("Preshower2");
    ensureChannel("Preshower3");
    ensureChannel("Muon0");
    ensureChannel("Muon1");
    ensureFloat("VetoNu0_reduced_charge", -1.0f);
    ensureFloat("VetoNu1_reduced_charge", -1.0f);
    ensureRVecD("Track_X_atMuon1");
    ensureRVecD("Track_Y_atMuon1");
    ensureRVecD("Track_X_atMuon2");
    ensureRVecD("Track_Y_atMuon2");

    if (sig.eventTimeType == "Int_t" || sig.eventTimeType == "int") {
        df = attachGrlGoodColumn<Int_t>(df, grl);
    } else if (sig.eventTimeType == "UInt_t" || sig.eventTimeType == "unsigned int") {
        df = attachGrlGoodColumn<UInt_t>(df, grl);
    } else if (sig.eventTimeType == "Long64_t" || sig.eventTimeType == "long long") {
        df = attachGrlGoodColumn<Long64_t>(df, grl);
    } else if (sig.eventTimeType == "ULong64_t" || sig.eventTimeType == "unsigned long long") {
        df = attachGrlGoodColumn<ULong64_t>(df, grl);
    } else {
        throw std::runtime_error("Unsupported eventTime type: " + sig.eventTimeType);
    }

    if (sig.nLayersType.find("unsigned") != std::string::npos || sig.nLayersType.find("uint") != std::string::npos) {
        df = attachTrackDataColumn<unsigned int>(df);
    } else {
        df = attachTrackDataColumn<int>(df);
    }

    auto fillSlot = [](TimingCalib::RawChannelInput& slot,
                       bool present, int planeIdx, const ScannerTrackData& tk,
                       Int_t st, Float_t bcid, Float_t trig, Float_t loc, Float_t qRaw, Float_t w) {
        slot.present = present;
        slot.goodStatus = present && TimingCalibrator::isGoodWaveformStatus(st);
        slot.bcidTime = bcid;
        slot.triggerTime = trig;
        slot.localTime = loc;
        slot.rawCharge = qRaw;
        slot.width = w;
        slot.xMm = tk.x[planeIdx];
        slot.yMm = tk.y[planeIdx];
        slot.validPos = tk.validPos[planeIdx];
    };

    df = df.Define("_raw_a",
        [sig, fillSlot](const ScannerTrackData& tk,
                        Int_t vn0_st, Float_t vn0_b, Float_t vn0_t, Float_t vn0_l, Float_t vn0_q, Float_t vn0_w,
                        Int_t vn1_st, Float_t vn1_b, Float_t vn1_t, Float_t vn1_l, Float_t vn1_q, Float_t vn1_w,
                        Int_t v10_st, Float_t v10_b, Float_t v10_t, Float_t v10_l, Float_t v10_q, Float_t v10_w,
                        Int_t v11_st, Float_t v11_b, Float_t v11_t, Float_t v11_l, Float_t v11_q, Float_t v11_w) -> RawInputArray {
            RawInputArray arr{};
            fillSlot(arr[0], true, 0, tk, vn0_st, vn0_b, vn0_t, vn0_l, vn0_q, vn0_w);
            fillSlot(arr[1], true, 0, tk, vn1_st, vn1_b, vn1_t, vn1_l, vn1_q, vn1_w);
            fillSlot(arr[2], true, 1, tk, v10_st, v10_b, v10_t, v10_l, v10_q, v10_w);
            fillSlot(arr[3], sig.hasNativeVeto11, 1, tk, v11_st, v11_b, v11_t, v11_l, v11_q, v11_w);
            return arr;
        },
        {"_tk",
         "VetoNu0_status", "VetoNu0_bcidtime", "VetoNu0_triggertime", "VetoNu0_localtime", "VetoNu0_raw_charge", "VetoNu0_width",
         "VetoNu1_status", "VetoNu1_bcidtime", "VetoNu1_triggertime", "VetoNu1_localtime", "VetoNu1_raw_charge", "VetoNu1_width",
         "Veto10_status",  "Veto10_bcidtime",  "Veto10_triggertime",  "Veto10_localtime",  "Veto10_raw_charge",  "Veto10_width",
         "Veto11_status",  "Veto11_bcidtime",  "Veto11_triggertime",  "Veto11_localtime",  "Veto11_raw_charge",  "Veto11_width"});

    df = df.Define("_raw_b",
        [fillSlot](const RawInputArray& prev, const ScannerTrackData& tk,
                   Int_t v20_st, Float_t v20_b, Float_t v20_t, Float_t v20_l, Float_t v20_q, Float_t v20_w,
                   Int_t v21_st, Float_t v21_b, Float_t v21_t, Float_t v21_l, Float_t v21_q, Float_t v21_w,
                   Int_t p0_st,  Float_t p0_b,  Float_t p0_t,  Float_t p0_l,  Float_t p0_q,  Float_t p0_w,
                   Int_t p1_st,  Float_t p1_b,  Float_t p1_t,  Float_t p1_l,  Float_t p1_q,  Float_t p1_w) -> RawInputArray {
            RawInputArray arr = prev;
            fillSlot(arr[4], true, 2, tk, v20_st, v20_b, v20_t, v20_l, v20_q, v20_w);
            fillSlot(arr[5], true, 2, tk, v21_st, v21_b, v21_t, v21_l, v21_q, v21_w);
            fillSlot(arr[8], true, 4, tk, p0_st,  p0_b,  p0_t,  p0_l,  p0_q,  p0_w);
            fillSlot(arr[9], true, 5, tk, p1_st,  p1_b,  p1_t,  p1_l,  p1_q,  p1_w);
            return arr;
        },
        {"_raw_a", "_tk",
         "Veto20_status",     "Veto20_bcidtime",     "Veto20_triggertime",     "Veto20_localtime",     "Veto20_raw_charge",     "Veto20_width",
         "Veto21_status",     "Veto21_bcidtime",     "Veto21_triggertime",     "Veto21_localtime",     "Veto21_raw_charge",     "Veto21_width",
         "Preshower0_status", "Preshower0_bcidtime", "Preshower0_triggertime", "Preshower0_localtime", "Preshower0_raw_charge", "Preshower0_width",
         "Preshower1_status", "Preshower1_bcidtime", "Preshower1_triggertime", "Preshower1_localtime", "Preshower1_raw_charge", "Preshower1_width"});

    df = df.Define("_raw_c",
        [sig, fillSlot](const RawInputArray& prev, const ScannerTrackData& tk,
                        Int_t p2_st, Float_t p2_b, Float_t p2_t, Float_t p2_l, Float_t p2_q, Float_t p2_w,
                        Int_t p3_st, Float_t p3_b, Float_t p3_t, Float_t p3_l, Float_t p3_q, Float_t p3_w,
                        Int_t m0_st, Float_t m0_b, Float_t m0_t, Float_t m0_l, Float_t m0_q, Float_t m0_w,
                        Int_t m1_st, Float_t m1_b, Float_t m1_t, Float_t m1_l, Float_t m1_q, Float_t m1_w) -> RawInputArray {
            RawInputArray arr = prev;
            fillSlot(arr[10], sig.hasPreshower23, 4, tk, p2_st, p2_b, p2_t, p2_l, p2_q, p2_w);
            fillSlot(arr[11], sig.hasPreshower23, 5, tk, p3_st, p3_b, p3_t, p3_l, p3_q, p3_w);
            fillSlot(arr[12], sig.hasMuon,        6, tk, m0_st, m0_b, m0_t, m0_l, m0_q, m0_w);
            fillSlot(arr[13], sig.hasMuon,        7, tk, m1_st, m1_b, m1_t, m1_l, m1_q, m1_w);
            return arr;
        },
        {"_raw_b", "_tk",
         "Preshower2_status", "Preshower2_bcidtime", "Preshower2_triggertime", "Preshower2_localtime", "Preshower2_raw_charge", "Preshower2_width",
         "Preshower3_status", "Preshower3_bcidtime", "Preshower3_triggertime", "Preshower3_localtime", "Preshower3_raw_charge", "Preshower3_width",
         "Muon0_status",      "Muon0_bcidtime",      "Muon0_triggertime",      "Muon0_localtime",      "Muon0_raw_charge",      "Muon0_width",
         "Muon1_status",      "Muon1_bcidtime",      "Muon1_triggertime",      "Muon1_localtime",      "Muon1_raw_charge",      "Muon1_width"});

    // Attach Timing01/Timing23 AND compact Timing individual status bit audit in separate slot?
    // Note: pass Timing0..3 raw statuses inside ScannerBlindCharges or _raw! We store combined Timing01/23 in _raw[6]/[7]
    // and track individual st512 flags cleanly via Timing0..3 goodStatus already encoded.
    df = df.Define("_raw",
        [](const RawInputArray& prev, const ScannerTrackData& tk,
           Int_t t0_st, Float_t t0_b, Float_t t0_t, Float_t t0_l, Float_t t0_q, Float_t t0_w,
           Int_t t1_st, Float_t t1_b, Float_t t1_t, Float_t t1_l, Float_t t1_q, Float_t t1_w,
           Int_t t2_st, Float_t t2_b, Float_t t2_t, Float_t t2_l, Float_t t2_q, Float_t t2_w,
           Int_t t3_st, Float_t t3_b, Float_t t3_t, Float_t t3_l, Float_t t3_q, Float_t t3_w) -> RawInputArray {
            RawInputArray arr = prev;
            arr[6] = TimingCalibrator::combineTimingPair(
                TimingCalibrator::isGoodWaveformStatus(t0_st), t0_b, t0_t, t0_l, t0_q, t0_w,
                TimingCalibrator::isGoodWaveformStatus(t1_st), t1_b, t1_t, t1_l, t1_q, t1_w,
                tk.x[3], tk.y[3], tk.validPos[3]);
            arr[7] = TimingCalibrator::combineTimingPair(
                TimingCalibrator::isGoodWaveformStatus(t2_st), t2_b, t2_t, t2_l, t2_q, t2_w,
                TimingCalibrator::isGoodWaveformStatus(t3_st), t3_b, t3_t, t3_l, t3_q, t3_w,
                tk.x[3], tk.y[3], tk.validPos[3]);
            return arr;
        },
        {"_raw_c", "_tk",
         "Timing0_status", "Timing0_bcidtime", "Timing0_triggertime", "Timing0_localtime", "Timing0_raw_charge", "Timing0_width",
         "Timing1_status", "Timing1_bcidtime", "Timing1_triggertime", "Timing1_localtime", "Timing1_raw_charge", "Timing1_width",
         "Timing2_status", "Timing2_bcidtime", "Timing2_triggertime", "Timing2_localtime", "Timing2_raw_charge", "Timing2_width",
         "Timing3_status", "Timing3_bcidtime", "Timing3_triggertime", "Timing3_localtime", "Timing3_raw_charge", "Timing3_width"});

    // Compute bitmasks for raw status audit (512, 16, 4) across the 14 logical channels
    df = df.Define("_st_masks",
        [](Int_t vn0, Int_t vn1, Int_t v10, Int_t v11, Int_t v20, Int_t v21,
           Int_t t0, Int_t t1, Int_t t2, Int_t t3,
           Int_t p0, Int_t p1, Int_t p2, Int_t p3, Int_t m0, Int_t m1) -> std::array<uint16_t, 3> {
            const std::array<Int_t, 14> sts = {
                vn0, vn1, v10, v11, v20, v21,
                (t0 | t1), (t2 | t3),
                p0, p1, p2, p3, m0, m1
            };
            uint16_t m512 = 0, m16 = 0, m4 = 0;
            for (int c = 0; c < 14; ++c) {
                if (sts[c] >= 0) {
                    if (sts[c] & 512) m512 |= (1u << c);
                    if (sts[c] & 16)  m16  |= (1u << c);
                    if (sts[c] & 4)   m4   |= (1u << c);
                }
            }
            return {m512, m16, m4};
        },
        {"VetoNu0_status", "VetoNu1_status", "Veto10_status", "Veto11_status",
         "Veto20_status", "Veto21_status",
         "Timing0_status", "Timing1_status", "Timing2_status", "Timing3_status",
         "Preshower0_status", "Preshower1_status", "Preshower2_status", "Preshower3_status",
         "Muon0_status", "Muon1_status"});

    df = df.Define("_chg",
        [sig](Float_t v20, Float_t v21,
              Float_t t0, Float_t t1, Float_t t2, Float_t t3,
              Float_t p0, Float_t p1,
              Float_t vn0red, Float_t vn1red) -> ScannerBlindCharges {
            ScannerBlindCharges c;
            c.veto20Charge = v20;
            c.veto21Charge = v21;
            c.timingBottomCharge = t0 + t1;
            c.timingTopCharge = t2 + t3;
            c.preshower0Charge = p0;
            c.preshower1Charge = p1;
            c.vetoNu0ReducedCharge = sig.hasReducedCharge ? vn0red : -1.0f;
            c.vetoNu1ReducedCharge = sig.hasReducedCharge ? vn1red : -1.0f;
            return c;
        },
        {"Veto20_charge", "Veto21_charge",
         "Timing0_charge", "Timing1_charge", "Timing2_charge", "Timing3_charge",
         "Preshower0_charge", "Preshower1_charge",
         "VetoNu0_reduced_charge", "VetoNu1_reduced_charge"});

    return df;
}

std::string formatRunDirName(int run) {
    return "run_" + std::to_string(run);
}

void writePass1Output(const std::string& outputPath, const std::map<int, Pass1RunData>& byRun) {
    std::unique_ptr<TFile> outFile(TFile::Open(outputPath.c_str(), "RECREATE"));
    if (!outFile || outFile->IsZombie()) {
        throw std::runtime_error("Cannot create Pass 1 output file: " + outputPath);
    }

    TTree* summary = new TTree("pass1_summary", "Pass 1 per-run scintillator summary");
    int run = 0;
    std::string period;
    uint64_t nTotal = 0, nGrlFail = 0, nNonColl = 0, nBlinded = 0, nSingleMuon = 0;
    bool hasVeto11 = false, hasPreshower23 = false, hasMuon = false;
    uint64_t nV20Ref = 0, nV10Ref = 0;
    uint64_t chNGood[kNumChannels]{}, chNSt512[kNumChannels]{}, chNSt16[kNumChannels]{}, chNSt4[kNumChannels]{};
    uint64_t chNBcidR50[kNumChannels]{}, chNBcidAll[kNumChannels]{}, chNDtrigV20[kNumChannels]{}, chNDtrigV10[kNumChannels]{};

    summary->Branch("run", &run);
    summary->Branch("period", &period);
    summary->Branch("n_total", &nTotal);
    summary->Branch("n_grl_fail", &nGrlFail);
    summary->Branch("n_non_colliding", &nNonColl);
    summary->Branch("n_blinded", &nBlinded);
    summary->Branch("n_single_muon", &nSingleMuon);
    summary->Branch("has_veto11", &hasVeto11);
    summary->Branch("has_preshower23", &hasPreshower23);
    summary->Branch("has_muon", &hasMuon);
    summary->Branch("n_v20_ref_events", &nV20Ref);
    summary->Branch("n_v10_ref_events", &nV10Ref);
    summary->Branch("ch_n_good", chNGood, ("ch_n_good[" + std::to_string(kNumChannels) + "]/l").c_str());
    summary->Branch("ch_n_st512", chNSt512, ("ch_n_st512[" + std::to_string(kNumChannels) + "]/l").c_str());
    summary->Branch("ch_n_st16", chNSt16, ("ch_n_st16[" + std::to_string(kNumChannels) + "]/l").c_str());
    summary->Branch("ch_n_st4", chNSt4, ("ch_n_st4[" + std::to_string(kNumChannels) + "]/l").c_str());
    summary->Branch("ch_n_bcid_r50", chNBcidR50, ("ch_n_bcid_r50[" + std::to_string(kNumChannels) + "]/l").c_str());
    summary->Branch("ch_n_bcid_all", chNBcidAll, ("ch_n_bcid_all[" + std::to_string(kNumChannels) + "]/l").c_str());
    summary->Branch("ch_n_dtrig_v20", chNDtrigV20, ("ch_n_dtrig_v20[" + std::to_string(kNumChannels) + "]/l").c_str());
    summary->Branch("ch_n_dtrig_v10", chNDtrigV10, ("ch_n_dtrig_v10[" + std::to_string(kNumChannels) + "]/l").c_str());

    const auto& meta = TimingCalibrator::channelMetadata();

    for (const auto& [r, d] : byRun) {
        run = r;
        period = TimingCalibrator::periodForDataRun(r);
        nTotal = d.nTotal;
        nGrlFail = d.nGrlFail;
        nNonColl = d.nNonColliding;
        nBlinded = d.nBlinded;
        nSingleMuon = d.nSingleMuon;
        hasVeto11 = d.hasVeto11;
        hasPreshower23 = d.hasPreshower23;
        hasMuon = d.hasMuon;
        nV20Ref = d.nV20RefEvents;
        nV10Ref = d.nV10RefEvents;
        for (int c = 0; c < kNumChannels; ++c) {
            chNGood[c] = d.chNGood[c];
            chNSt512[c] = d.chNSt512[c];
            chNSt16[c] = d.chNSt16[c];
            chNSt4[c] = d.chNSt4[c];
            chNBcidR50[c] = d.chNBcidR50[c];
            chNBcidAll[c] = d.chNBcidAll[c];
            chNDtrigV20[c] = d.chNDtrigV20[c];
            chNDtrigV10[c] = d.chNDtrigV10[c];
        }
        summary->Fill();

        TDirectory* rdir = outFile->mkdir(formatRunDirName(r).c_str());
        rdir->cd();
        for (int c = 0; c < kNumChannels; ++c) {
            if (c == static_cast<int>(TimingChannel::Veto11) && !d.hasVeto11) continue;
            if ((c == static_cast<int>(TimingChannel::Preshower2) || c == static_cast<int>(TimingChannel::Preshower3)) && !d.hasPreshower23) continue;
            if ((c == static_cast<int>(TimingChannel::Muon0) || c == static_cast<int>(TimingChannel::Muon1)) && !d.hasMuon) continue;
            const std::string cname = meta[c].name;
            auto writeIfNonEmpty = [&](const FastHist1D& fh, const std::string& hname, const std::string& htitle) {
                TH1D h = fh.toTH1D(hname, htitle);
                if (h.GetEntries() > 0 || hname.rfind("h_bcid_r50_", 0) == 0 || hname.rfind("h_dtrig_v20_", 0) == 0) {
                    h.Write();
                }
            };
            writeIfNonEmpty(d.hBcidR50[c], "h_bcid_r50_" + cname, cname + " bcidtime (r<50 mm);ns;Events");
            writeIfNonEmpty(d.hBcidAll[c], "h_bcid_all_" + cname, cname + " bcidtime (all);ns;Events");
            writeIfNonEmpty(d.hDtrigV20[c], "h_dtrig_v20_" + cname, cname + " - Veto20 triggertime;ns;Events");
            writeIfNonEmpty(d.hDtrigV10[c], "h_dtrig_v10_" + cname, cname + " - Veto10 triggertime;ns;Events");
            if (d.chNSt512[c] > 0) {
                writeIfNonEmpty(d.hDtrigDig1St0[c], "h_dtrig_dig1_st0_" + cname, cname + " - VetoNu0 dtrig (st512==0);ns;Events");
                writeIfNonEmpty(d.hDtrigDig1St512[c], "h_dtrig_dig1_st512_" + cname, cname + " - VetoNu0 dtrig (st512!=0);ns;Events");
                writeIfNonEmpty(d.hDlocDig1St0[c], "h_dloc_dig1_st0_" + cname, cname + " - VetoNu0 dloc (st512==0);ns;Events");
                writeIfNonEmpty(d.hDlocDig1St512[c], "h_dloc_dig1_st512_" + cname, cname + " - VetoNu0 dloc (st512!=0);ns;Events");
            }
            writeIfNonEmpty(d.hRawCharge[c], "h_raw_charge_" + cname, cname + " raw_charge;pC;Events");
        }
        if (d.hDtrigT23T01.bins.size() > 0) {
            d.hDtrigT23T01.toTH1D("h_dtrig_T23_T01", "Timing23 - Timing01 triggertime;ns;Events").Write();
        }
        outFile->cd();
    }

    summary->Write();
    outFile->Close();
}

void writePass2Output(const std::string& outputPath,
                      const std::map<int, Pass2RunData>& byRun,
                      std::vector<CompactCalibRecord>& records) {
    // Deterministic canonical sort so single-thread vs multi-thread output is bit-for-bit identical
    std::sort(records.begin(), records.end(), [](const CompactCalibRecord& a, const CompactCalibRecord& b) {
        if (a.run != b.run) return a.run < b.run;
        return a.eventID < b.eventID;
    });

    std::unique_ptr<TFile> outFile(TFile::Open(outputPath.c_str(), "RECREATE"));
    if (!outFile || outFile->IsZombie()) {
        throw std::runtime_error("Cannot create Pass 2 output file: " + outputPath);
    }

    TTree* summary = new TTree("pass2_summary", "Pass 2 per-run unwrap summary");
    int run = 0;
    std::string period;
    uint64_t nTotal = 0, nGrlFail = 0, nNonColl = 0, nBlinded = 0, n1Trk = 0, n2Trk = 0, n3Trk = 0;
    uint64_t chPass[kNumChannels]{}, chFail[kNumChannels]{}, anchorCounts[kNumChannels]{};

    summary->Branch("run", &run);
    summary->Branch("period", &period);
    summary->Branch("n_total", &nTotal);
    summary->Branch("n_grl_fail", &nGrlFail);
    summary->Branch("n_non_colliding", &nNonColl);
    summary->Branch("n_blinded", &nBlinded);
    summary->Branch("n_clean_1trk", &n1Trk);
    summary->Branch("n_clean_2trk", &n2Trk);
    summary->Branch("n_clean_3trk", &n3Trk);
    summary->Branch("ch_n_unwrap_pass", chPass, ("ch_n_unwrap_pass[" + std::to_string(kNumChannels) + "]/l").c_str());
    summary->Branch("ch_n_unwrap_fail", chFail, ("ch_n_unwrap_fail[" + std::to_string(kNumChannels) + "]/l").c_str());
    summary->Branch("anchor_counts", anchorCounts, ("anchor_counts[" + std::to_string(kNumChannels) + "]/l").c_str());

    const auto& meta = TimingCalibrator::channelMetadata();
    for (const auto& [r, d] : byRun) {
        run = r;
        period = TimingCalibrator::periodForDataRun(r);
        nTotal = d.nTotal;
        nGrlFail = d.nGrlFail;
        nNonColl = d.nNonColliding;
        nBlinded = d.nBlinded;
        n1Trk = d.nClean1Trk;
        n2Trk = d.nClean2Trk;
        n3Trk = d.nClean3Trk;
        for (int c = 0; c < kNumChannels; ++c) {
            chPass[c] = d.chNUnwrapPass[c];
            chFail[c] = d.chNUnwrapFail[c];
            anchorCounts[c] = d.anchorCounts[c];
        }
        summary->Fill();

        TDirectory* rdir = outFile->mkdir(formatRunDirName(r).c_str());
        rdir->cd();
        for (int c = 0; c < kNumChannels; ++c) {
            if (d.chNUnwrapPass[c] + d.chNUnwrapFail[c] > 0) {
                const std::string cname = meta[c].name;
                d.hRUnwrap[c].toTH1D("h_r_unwrap_" + cname, cname + " r_unwrap;ns;Events").Write();
            }
        }
        outFile->cd();
    }
    summary->Write();

    TTree* evTree = new TTree("calib_events", "Pass 2 stratified calibration events");
    CompactCalibRecord rec;
    evTree->Branch("run", &rec.run);
    evTree->Branch("eventID", &rec.eventID);
    evTree->Branch("is_cat0", &rec.is_cat0);
    evTree->Branch("is_cat1", &rec.is_cat1);
    evTree->Branch("is_cat2", &rec.is_cat2);
    evTree->Branch("is_cat3", &rec.is_cat3);
    evTree->Branch("w0", &rec.w0);
    evTree->Branch("w1", &rec.w1);
    evTree->Branch("w2", &rec.w2);
    evTree->Branch("anchor_ch", &rec.anchor_ch);
    evTree->Branch("valid_mask", &rec.valid_mask);
    evTree->Branch("above_mip_mask", &rec.above_mip_mask);
    evTree->Branch("unwrap_fail_mask", &rec.unwrap_fail_mask);
    evTree->Branch("n_long_tracks", &rec.n_long_tracks);
    evTree->Branch("pz0_lead_gev", &rec.pz0_lead_gev);
    evTree->Branch("pz0_sub_gev", &rec.pz0_sub_gev);
    evTree->Branch("d12_trig_mm", &rec.d12_trig_mm);
    evTree->Branch("d12_vn_mm", &rec.d12_vn_mm);
    evTree->Branch("d12_ps1_mm", &rec.d12_ps1_mm);
    evTree->Branch("trk_x", rec.trk_x, "trk_x[8]/F");
    evTree->Branch("trk_y", rec.trk_y, "trk_y[8]/F");
    evTree->Branch("sub_x_trig", &rec.sub_x_trig);
    evTree->Branch("sub_y_trig", &rec.sub_y_trig);
    evTree->Branch("sub_x_vn", &rec.sub_x_vn);
    evTree->Branch("sub_y_vn", &rec.sub_y_vn);
    evTree->Branch("t2", rec.t2, ("t2[" + std::to_string(kNumChannels) + "]/F").c_str());
    evTree->Branch("q_raw", rec.q_raw, ("q_raw[" + std::to_string(kNumChannels) + "]/F").c_str());
    evTree->Branch("r_unwrap", rec.r_unwrap, ("r_unwrap[" + std::to_string(kNumChannels) + "]/F").c_str());

    for (const auto& item : records) {
        rec = item;
        evTree->Fill();
    }
    evTree->Write();
    outFile->Close();
}

void printUsage(const char* argv0) {
    std::cerr << "Usage: " << argv0
              << " --mode <pass1|pass2> --output <out.root> [--manifest <json>] [--grl-config <yaml>]"
              << " [--task-ids <id1,id2,...>] [--runs <r1,r2,...>] [--input-files <f1,f2,...>]"
              << " [--ref-offsets <json>] [--threads <n>] [--max-events <n>]\n";
}

} // namespace

int main(int argc, char* argv[]) {
    ROOT::EnableThreadSafety();
    TH1::AddDirectory(false);

    std::string mode;
    std::string outputPath;
    std::string manifestPath = "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json";
    std::string grlConfigPath = "AnalysisZipFramework/config/grl_config_run3_full.yaml";
    std::string refOffsetsPath;
    std::string taskIdsArg;
    std::string runsArg;
    std::string inputFilesArg;
    int threads = 1;
    Long64_t maxEvents = -1;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto needVal = [&](const std::string& flag) -> std::string {
            if (i + 1 >= argc) {
                throw std::runtime_error("Missing value for " + flag);
            }
            return argv[++i];
        };
        if (arg == "--mode") mode = needVal(arg);
        else if (arg == "--output" || arg == "-o") outputPath = needVal(arg);
        else if (arg == "--manifest") manifestPath = needVal(arg);
        else if (arg == "--grl-config") grlConfigPath = needVal(arg);
        else if (arg == "--ref-offsets") refOffsetsPath = needVal(arg);
        else if (arg == "--task-ids") taskIdsArg = needVal(arg);
        else if (arg == "--runs") runsArg = needVal(arg);
        else if (arg == "--input-files") inputFilesArg = needVal(arg);
        else if (arg == "--threads" || arg == "-j") threads = std::stoi(needVal(arg));
        else if (arg == "--max-events") maxEvents = std::stoll(needVal(arg));
        else {
            printUsage(argv[0]);
            return 1;
        }
    }

    if ((mode != "pass1" && mode != "pass2") || outputPath.empty()) {
        printUsage(argv[0]);
        return 1;
    }
    if (mode == "pass2" && refOffsetsPath.empty()) {
        ERROR("--mode pass2 requires --ref-offsets <ref_offsets_run3.json>");
        return 1;
    }

    const auto wallStart = std::chrono::steady_clock::now();

    if (threads > 1 && maxEvents <= 0) {
        ROOT::EnableImplicitMT(static_cast<unsigned int>(threads));
    } else if (threads > 1 && maxEvents > 0) {
        WARNING("Ignoring --threads > 1 because --max-events uses RDataFrame::Range (single-threaded)");
        threads = 1;
    }
    const unsigned int nSlots = std::max(1u, ROOT::GetThreadPoolSize());

    // Load GRL JSONs
    const auto grlCfg = ConfigUtils::readGRLConfig(grlConfigPath);
    auto grlTimes = std::make_shared<const GRLUtils::GRLTimes>(
        GRLUtils::readGRLTimes(GRLUtils::toTStringVector(grlCfg.grlJsons)));

    // Load Pass 2 offsets if needed
    std::shared_ptr<const std::unordered_map<int, ScannerRunOffsets>> runOffsetsMap;
    if (mode == "pass2") {
        runOffsetsMap = std::make_shared<const std::unordered_map<int, ScannerRunOffsets>>(loadRunOffsetsMap(refOffsetsPath));
    }

    // Resolve tasks
    std::vector<TaskSpec> selectedTasks;
    if (!inputFilesArg.empty()) {
        TaskSpec t;
        t.taskId = "manual";
        t.files = splitCommaList(inputFilesArg);
        selectedTasks.push_back(std::move(t));
    } else {
        std::ifstream mifs(manifestPath);
        if (!mifs.is_open()) {
            throw std::runtime_error("Cannot open manifest: " + manifestPath);
        }
        const json mJson = json::parse(mifs);
        const std::string dqPath = mJson.at("source_dq_manifest").get<std::string>();
        std::ifstream dqifs(dqPath);
        if (!dqifs.is_open()) {
            throw std::runtime_error("Cannot open source_dq_manifest: " + dqPath);
        }
        const json dqJson = json::parse(dqifs);
        const auto& dqTasks = dqJson.at("tasks");

        std::unordered_set<std::string> unavailSet;
        if (dqJson.contains("config") && dqJson.at("config").contains("unavailable_inputs")) {
            const auto& ui = dqJson.at("config").at("unavailable_inputs");
            for (auto itU = ui.begin(); itU != ui.end(); ++itU) {
                unavailSet.insert(itU.key());
            }
        }

        const auto taskFilter = splitCommaList(taskIdsArg);
        const auto runFilterStr = splitCommaList(runsArg);
        std::unordered_set<std::string> wantedTasks(taskFilter.begin(), taskFilter.end());
        std::unordered_set<int> wantedRuns;
        for (const auto& rs : runFilterStr) wantedRuns.insert(std::stoi(rs));

        for (auto it = dqTasks.begin(); it != dqTasks.end(); ++it) {
            const std::string tid = it.key();
            const auto& tObj = it.value();
            const int runNum = tObj.at("run").get<int>();
            if (!wantedTasks.empty() && wantedTasks.count(tid) == 0) continue;
            if (!wantedRuns.empty() && wantedRuns.count(runNum) == 0) continue;
            if (wantedTasks.empty() && wantedRuns.empty()) continue;

            TaskSpec ts;
            ts.taskId = tid;
            ts.year = tObj.value("year", 0);
            ts.run = runNum;
            for (const auto& fpath : tObj.at("files").get<std::vector<std::string>>()) {
                if (unavailSet.count(fpath) == 0) ts.files.push_back(fpath);
            }
            if (ts.files.empty()) {
                WARNING("Task ", tid, " has 0 available files after excluding unavailable_inputs; skipping.");
                continue;
            }
            ts.bytes = tObj.value("bytes", 0ULL);
            selectedTasks.push_back(std::move(ts));
        }
        std::sort(selectedTasks.begin(), selectedTasks.end(),
                  [](const TaskSpec& a, const TaskSpec& b) { return a.taskId < b.taskId; });
    }

    if (selectedTasks.empty()) {
        ERROR("No matching tasks found.");
        return 1;
    }

    // Group tasks by branch schema signature so TChain only mixes compatible schemas
    struct SchemaGroup {
        SchemaSignature sig;
        std::vector<TaskSpec> tasks;
    };
    std::map<std::string, SchemaGroup> schemaGroups;
    for (auto& ts : selectedTasks) {
        const SchemaSignature sig = probeTaskSchema(ts);
        auto& grp = schemaGroups[sig.key()];
        grp.sig = sig;
        grp.tasks.push_back(std::move(ts));
    }

    std::map<int, Pass1RunData> mergedPass1;
    std::map<int, Pass2RunData> mergedPass2;
    std::vector<CompactCalibRecord> mergedPass2Records;
    uint64_t totalEventLoops = 0;

    const auto& meta = TimingCalibrator::channelMetadata();

    for (const auto& [skey, grp] : schemaGroups) {
        TChain chain("nt");
        int nFilesAdded = 0;
        for (const auto& ts : grp.tasks) {
            for (const auto& f : ts.files) {
                chain.Add(f.c_str());
                ++nFilesAdded;
            }
        }
        INFO("Processing schema group (", skey, "): ", grp.tasks.size(), " tasks, ", nFilesAdded,
             " files, MT slots=", nSlots, ", mode=", mode);

        ROOT::RDF::RNode df = prepareScannerNode(chain, grp.sig, grlTimes);
        if (maxEvents > 0) {
            df = df.Range(static_cast<ULong64_t>(maxEvents));
        }

        if (mode == "pass1") {
            std::vector<std::unordered_map<int, Pass1RunData>> slotMaps(nSlots);
            df.ForeachSlot(
                [&](unsigned int slot,
                    Int_t run,
                    Int_t /*eventID*/,
                    Int_t distBCID,
                    Int_t longTracks,
                    bool grlGood,
                    const ScannerTrackData& tk,
                    const RawInputArray& raw,
                    const ScannerBlindCharges& chg,
                    const std::array<uint16_t, 3>& stMasks) {

                    auto& rmap = slotMaps[slot];
                    auto& rd = rmap[run];
                    if (!rd.initialized) {
                        rd.init(run);
                        rd.hasVeto11 = grp.sig.hasNativeVeto11;
                        rd.hasPreshower23 = grp.sig.hasPreshower23;
                        rd.hasMuon = grp.sig.hasMuon;
                    }
                    ++rd.nTotal;
                    if (!grlGood) {
                        ++rd.nGrlFail;
                        return;
                    }
                    if (distBCID != 0) {
                        ++rd.nNonColliding;
                        return;
                    }
                    if (checkBlinded(distBCID, longTracks, tk, raw, chg)) {
                        ++rd.nBlinded;
                        return;
                    }

                    // Single clean muon selection for Pass 1 reference finding
                    if (longTracks != 1) return;
                    if (!std::isfinite(tk.leadPz0GeV) || tk.leadPz0GeV <= 30.0) return;
                    if (tk.leadNLayers < 6 || !std::isfinite(tk.leadNDoF) || tk.leadNDoF < 9.0) return;
                    if (!std::isfinite(tk.leadChi2NDF) || tk.leadChi2NDF >= 15.0) return;
                    if (!tk.validPos[3] || std::abs(tk.x[3]) >= 120.0 || std::abs(tk.y[3]) >= 120.0) return;

                    ++rd.nSingleMuon;

                    const int iV20 = static_cast<int>(TimingChannel::Veto20);
                    const int iV10 = static_cast<int>(TimingChannel::Veto10);
                    const int iVn0 = static_cast<int>(TimingChannel::VetoNu0);
                    const bool v20Ok = raw[iV20].present && raw[iV20].goodStatus &&
                                       ((stMasks[2] & (1u << iV20)) == 0) &&
                                       raw[iV20].rawCharge > meta[iV20].mipThresholdPC &&
                                       std::isfinite(raw[iV20].triggerTime);
                    const bool v10Ok = raw[iV10].present && raw[iV10].goodStatus &&
                                       ((stMasks[2] & (1u << iV10)) == 0) &&
                                       raw[iV10].rawCharge > meta[iV10].mipThresholdPC &&
                                       std::isfinite(raw[iV10].triggerTime);
                    // Digitizer-1 common-clock reference for status & 512 inter-digitizer audit (VetoNu0 never uses Digitizer 2)
                    const bool dig1Ok = raw[iVn0].present && raw[iVn0].goodStatus &&
                                        ((stMasks[0] & (1u << iVn0)) == 0) &&
                                        ((stMasks[2] & (1u << iVn0)) == 0) &&
                                        raw[iVn0].rawCharge > meta[iVn0].mipThresholdPC &&
                                        std::isfinite(raw[iVn0].triggerTime);
                    if (v20Ok) ++rd.nV20RefEvents;
                    if (v10Ok) ++rd.nV10RefEvents;

                    const uint16_t m512 = stMasks[0];
                    const uint16_t m16 = stMasks[1];
                    const uint16_t m4 = stMasks[2];

                    for (int c = 0; c < kNumChannels; ++c) {
                        const auto& in = raw[c];
                        if (!in.present) continue;
                        const uint16_t bit = static_cast<uint16_t>(1u << c);
                        if (m512 & bit) ++rd.chNSt512[c];
                        if (m16 & bit)  ++rd.chNSt16[c];
                        if (m4 & bit)   ++rd.chNSt4[c];
                        if (!in.goodStatus) continue;
                        ++rd.chNGood[c];

                        const int pIdx = kChannelPlaneIdx[c];
                        const bool fidOk = channelFiducialOk(c, in.xMm, in.yMm, tk.validPos[pIdx]);
                        if (fidOk && std::isfinite(in.rawCharge)) {
                            rd.hRawCharge[c].fill(in.rawCharge);
                        }
                        if (!fidOk || !(in.rawCharge > meta[c].mipThresholdPC)) continue;

                        if (std::isfinite(in.bcidTime)) {
                            double bcidMod = std::fmod(in.bcidTime, kBunchSpacingNs);
                            if (bcidMod < 0.0) bcidMod += kBunchSpacingNs;
                            rd.hBcidAll[c].fill(bcidMod);
                            ++rd.chNBcidAll[c];
                            const double rMm = std::hypot(in.xMm, in.yMm);
                            const bool coreR = (c == static_cast<int>(TimingChannel::Timing01) ||
                                                c == static_cast<int>(TimingChannel::Timing23))
                                                   ? (rMm < 60.0)
                                                   : (rMm < 50.0);
                            if (coreR) {
                                rd.hBcidR50[c].fill(bcidMod);
                                ++rd.chNBcidR50[c];
                            }
                        }

                        if (v20Ok && std::isfinite(in.triggerTime)) {
                            rd.hDtrigV20[c].fill(in.triggerTime - raw[iV20].triggerTime);
                            ++rd.chNDtrigV20[c];
                        }
                        if (v10Ok && std::isfinite(in.triggerTime)) {
                            rd.hDtrigV10[c].fill(in.triggerTime - raw[iV10].triggerTime);
                            ++rd.chNDtrigV10[c];
                        }
                        if (dig1Ok && std::isfinite(in.triggerTime)) {
                            const double dTrigDig1 = in.triggerTime - raw[iVn0].triggerTime;
                            const bool is512 = (m512 & bit) != 0;
                            if (is512) {
                                rd.hDtrigDig1St512[c].fill(dTrigDig1);
                                if (std::isfinite(in.localTime) && std::isfinite(raw[iVn0].localTime)) {
                                    rd.hDlocDig1St512[c].fill(in.localTime - raw[iVn0].localTime);
                                }
                            } else {
                                rd.hDtrigDig1St0[c].fill(dTrigDig1);
                                if (std::isfinite(in.localTime) && std::isfinite(raw[iVn0].localTime)) {
                                    rd.hDlocDig1St0[c].fill(in.localTime - raw[iVn0].localTime);
                                }
                            }
                        }
                    }

                    const int iT01 = static_cast<int>(TimingChannel::Timing01);
                    const int iT23 = static_cast<int>(TimingChannel::Timing23);
                    if (raw[iT01].present && raw[iT01].goodStatus && raw[iT01].rawCharge > meta[iT01].mipThresholdPC &&
                        raw[iT23].present && raw[iT23].goodStatus && raw[iT23].rawCharge > meta[iT23].mipThresholdPC) {
                        rd.hDtrigT23T01.fill(raw[iT23].triggerTime - raw[iT01].triggerTime);
                    }
                },
                {"run", "eventID", "distanceToCollidingBCID", "longTracks", "_grl_good", "_tk", "_raw", "_chg", "_st_masks"});

            totalEventLoops += df.GetNRuns();
            for (unsigned int s = 0; s < nSlots; ++s) {
                for (const auto& [r, sd] : slotMaps[s]) {
                    mergedPass1[r].mergeFrom(sd);
                }
            }
        } else {
            // Pass 2
            std::vector<std::unordered_map<int, Pass2RunData>> slotMaps(nSlots);
            std::vector<std::vector<CompactCalibRecord>> slotRecs(nSlots);
            for (auto& v : slotRecs) v.reserve(4096);

            df.ForeachSlot(
                [&](unsigned int slot,
                    Int_t run,
                    Int_t eventID,
                    Int_t distBCID,
                    Int_t longTracks,
                    bool grlGood,
                    const ScannerTrackData& tk,
                    const RawInputArray& raw,
                    const ScannerBlindCharges& chg) {

                    auto& rmap = slotMaps[slot];
                    auto& rd = rmap[run];
                    if (!rd.initialized) rd.init(run);
                    ++rd.nTotal;
                    if (!grlGood) {
                        ++rd.nGrlFail;
                        return;
                    }
                    if (distBCID != 0) {
                        ++rd.nNonColliding;
                        return;
                    }
                    if (checkBlinded(distBCID, longTracks, tk, raw, chg)) {
                        ++rd.nBlinded;
                        return;
                    }

                    const auto offIt = runOffsetsMap->find(run);
                    if (offIt == runOffsetsMap->end()) return;
                    const ScannerRunOffsets& ro = offIt->second;

                    // Quick track category flags before Step 1+2 unwrapping
                    const bool is1TrkClean =
                        (longTracks == 1) &&
                        std::isfinite(tk.leadPz0GeV) && tk.leadPz0GeV > 30.0 &&
                        tk.leadNLayers >= 6 &&
                        std::isfinite(tk.leadNDoF) && tk.leadNDoF >= 9.0 &&
                        std::isfinite(tk.leadChi2NDF) && tk.leadChi2NDF < 15.0 &&
                        tk.validPos[3];
                    const bool is2TrkClean = (longTracks == 2) && tk.clean2Trk && tk.validPos[3];
                    const bool is3TrkClean = (longTracks == 3) && tk.clean3Trk && tk.validPos[3];

                    if (!is1TrkClean && !is2TrkClean && !is3TrkClean) return;
                    if (is1TrkClean) ++rd.nClean1Trk;
                    if (is2TrkClean) ++rd.nClean2Trk;
                    if (is3TrkClean) ++rd.nClean3Trk;

                    // Step 1+2 unwrapping (anchor strictly requires MIP; target probes extend to 10 pC / 0.5 pC for Preshower)
                    std::array<bool, kNumChannels> eligibleStep1{};
                    std::array<bool, kNumChannels> aboveMip{};
                    std::array<double, kNumChannels> t1{};
                    std::array<double, kNumChannels> tTrigRel{};

                    for (int c = 0; c < kNumChannels; ++c) {
                        const auto& in = raw[c];
                        if (!in.present || !in.goodStatus) continue;
                        if (!ro.hasBcidRef[c] || !ro.hasTrigRef[c]) continue;
                        if (!std::isfinite(in.bcidTime) || !std::isfinite(in.triggerTime) || !std::isfinite(in.rawCharge)) continue;
                        const bool isPs = (c >= static_cast<int>(TimingChannel::Preshower0) &&
                                           c <= static_cast<int>(TimingChannel::Preshower3));
                        const double minProbeQ = isPs ? 0.5 : 10.0;
                        if (in.rawCharge <= minProbeQ) continue;
                        eligibleStep1[c] = true;
                        aboveMip[c] = (in.rawCharge > meta[c].mipThresholdPC);
                        t1[c] = TimingCalibrator::wrap25(in.bcidTime - ro.tRefBcid[c]);
                        tTrigRel[c] = in.triggerTime - ro.tTrigRelRef[c];
                    }

                    // Select anchor strictly among above-MIP primary downstream stations
                    int anc = -1;
                    const int iT01 = static_cast<int>(TimingChannel::Timing01);
                    const int iT23 = static_cast<int>(TimingChannel::Timing23);
                    const bool mipT01 = eligibleStep1[iT01] && aboveMip[iT01];
                    const bool mipT23 = eligibleStep1[iT23] && aboveMip[iT23];
                    if (mipT01 || mipT23) {
                        if (mipT01 && mipT23) {
                            anc = (raw[iT23].rawCharge >= raw[iT01].rawCharge) ? iT23 : iT01;
                        } else {
                            anc = mipT23 ? iT23 : iT01;
                        }
                    } else {
                        double bestQ = -1.0;
                        for (int c : {static_cast<int>(TimingChannel::Veto20),
                                      static_cast<int>(TimingChannel::Veto21),
                                      static_cast<int>(TimingChannel::Veto10),
                                      static_cast<int>(TimingChannel::Veto11),
                                      static_cast<int>(TimingChannel::Muon0),
                                      static_cast<int>(TimingChannel::Muon1),
                                      static_cast<int>(TimingChannel::Preshower0),
                                      static_cast<int>(TimingChannel::Preshower1)}) {
                            if (eligibleStep1[c] && aboveMip[c] && raw[c].rawCharge > bestQ) {
                                bestQ = raw[c].rawCharge;
                                anc = c;
                            }
                        }
                    }
                    if (anc < 0) return;

                    uint16_t validMask = 0;
                    uint16_t aboveMipMask = 0;
                    uint16_t unwrapFailMask = 0;
                    std::array<float, kNumChannels> t2Arr{};
                    std::array<float, kNumChannels> qRawArr{};
                    std::array<float, kNumChannels> rUnwrapArr{};
                    t2Arr.fill(static_cast<float>(kNaN));
                    qRawArr.fill(static_cast<float>(kNaN));
                    rUnwrapArr.fill(static_cast<float>(kNaN));

                    for (int c = 0; c < kNumChannels; ++c) {
                        if (raw[c].present && std::isfinite(raw[c].rawCharge)) {
                            qRawArr[c] = static_cast<float>(raw[c].rawCharge);
                        }
                        if (!eligibleStep1[c]) continue;
                        if (aboveMip[c]) aboveMipMask |= static_cast<uint16_t>(1u << c);

                        const double dTrig = tTrigRel[c] - tTrigRel[anc];
                        const double dt = TimingCalibrator::wrap25(t1[c] - t1[anc]);
                        const long long nShift = std::llround((dTrig - dt) / kBunchSpacingNs);
                        const double rUnwrap = std::abs(dTrig - (dt + kBunchSpacingNs * static_cast<double>(nShift)));
                        const double t2Val = t1[anc] + dt + kBunchSpacingNs * static_cast<double>(nShift);
                        rUnwrapArr[c] = static_cast<float>(rUnwrap);

                        if (rUnwrap > kMaxUnwrapResidualNs || !std::isfinite(t2Val)) {
                            unwrapFailMask |= static_cast<uint16_t>(1u << c);
                        } else {
                            validMask |= static_cast<uint16_t>(1u << c);
                            t2Arr[c] = static_cast<float>(t2Val);
                        }
                    }

                    // Accumulate full-statistics unwrap residuals on all clean 1-track MIP muons
                    if (is1TrkClean) {
                        ++rd.anchorCounts[anc];
                        for (int c = 0; c < kNumChannels; ++c) {
                            if (!eligibleStep1[c] || !aboveMip[c]) continue;
                            const int pIdx = kChannelPlaneIdx[c];
                            if (!channelFiducialOk(c, raw[c].xMm, raw[c].yMm, tk.validPos[pIdx])) continue;
                            rd.hRUnwrap[c].fill(static_cast<double>(rUnwrapArr[c]));
                            if (unwrapFailMask & (1u << c)) ++rd.chNUnwrapFail[c];
                            else ++rd.chNUnwrapPass[c];
                        }
                    }

                    // Stratified deterministic sampling into CompactCalibRecord
                    uint8_t isCat0 = 0, isCat1 = 0, isCat2 = 0, isCat3 = 0;
                    float w0 = 1.0f, w1 = 1.0f, w2 = 1.0f;

                    if (is1TrkClean && std::abs(tk.x[3]) < 150.0 && std::abs(tk.y[3]) < 150.0) {
                        const auto [pCore, pEdge] = periodPrescaleProbs(ro.period);
                        const bool isEdge = (std::abs(tk.x[3]) > 85.0 || std::abs(tk.y[3]) > 85.0 ||
                                             (tk.validPos[0] && (std::abs(tk.x[0]) > 85.0 || std::abs(tk.y[0]) > 85.0)));
                        const double p0 = isEdge ? pEdge : pCore;
                        if (deterministicUniform01(run, eventID, 0x1111222233334444ULL) < p0) {
                            isCat0 = 1;
                            w0 = static_cast<float>(1.0 / p0);
                        }

                        // Category 1: sub-MIP low-charge time-walk probes (strictly below MIP threshold!)
                        bool hasLowQProbe = false;
                        for (int c = 0; c < kNumChannels; ++c) {
                            if (!(validMask & (1u << c)) || aboveMip[c]) continue;
                            const int pIdx = kChannelPlaneIdx[c];
                            if (!tk.validPos[pIdx] || std::abs(tk.x[pIdx]) >= 140.0 || std::abs(tk.y[pIdx]) >= 140.0) continue;
                            const double q = qRawArr[c];
                            const bool isPs = (c >= static_cast<int>(TimingChannel::Preshower0) &&
                                               c <= static_cast<int>(TimingChannel::Preshower3));
                            if ((isPs && q >= 0.6) || (!isPs && q >= 12.0)) {
                                hasLowQProbe = true;
                                break;
                            }
                        }
                        if (hasLowQProbe) {
                            const double p1 = (ro.period == "2024_postCaloNu") ? 0.15 : 0.05;
                            if (deterministicUniform01(run, eventID, 0x5555666677778888ULL) < p1) {
                                isCat1 = 1;
                                w1 = static_cast<float>(1.0 / p1);
                            }
                        }
                    }

                    if (is2TrkClean && std::abs(tk.x[3]) < 150.0 && std::abs(tk.y[3]) < 150.0) {
                        const double p2 = (ro.period == "2025") ? 0.08 : ((ro.period == "2024_postCaloNu") ? 0.35 : 0.15);
                        if (deterministicUniform01(run, eventID, 0x9999aaaabbbbccccULL) < p2) {
                            isCat2 = 1;
                            w2 = static_cast<float>(1.0 / p2);
                        }
                    }

                    if (is3TrkClean && std::abs(tk.x[3]) < 150.0 && std::abs(tk.y[3]) < 150.0) {
                        isCat3 = 1;
                    }

                    if (!isCat0 && !isCat1 && !isCat2 && !isCat3) return;

                    CompactCalibRecord rec;
                    rec.run = run;
                    rec.eventID = static_cast<int64_t>(eventID);
                    rec.is_cat0 = isCat0;
                    rec.is_cat1 = isCat1;
                    rec.is_cat2 = isCat2;
                    rec.is_cat3 = isCat3;
                    rec.w0 = w0;
                    rec.w1 = w1;
                    rec.w2 = w2;
                    rec.anchor_ch = static_cast<int32_t>(anc);
                    rec.valid_mask = validMask;
                    rec.above_mip_mask = aboveMipMask;
                    rec.unwrap_fail_mask = unwrapFailMask;
                    rec.n_long_tracks = longTracks;
                    rec.pz0_lead_gev = static_cast<float>(tk.leadPz0GeV);
                    rec.pz0_sub_gev = static_cast<float>(tk.subPz0GeV);
                    rec.d12_trig_mm = static_cast<float>(tk.d12TrigMm);
                    rec.d12_vn_mm = static_cast<float>(tk.d12VnMm);
                    rec.d12_ps1_mm = static_cast<float>(tk.d12Ps1Mm);
                    for (int p = 0; p < 8; ++p) {
                        rec.trk_x[p] = static_cast<float>(tk.x[p]);
                        rec.trk_y[p] = static_cast<float>(tk.y[p]);
                    }
                    rec.sub_x_trig = static_cast<float>(tk.subXTrig);
                    rec.sub_y_trig = static_cast<float>(tk.subYTrig);
                    rec.sub_x_vn = static_cast<float>(tk.subXVN);
                    rec.sub_y_vn = static_cast<float>(tk.subYVN);
                    for (int c = 0; c < kNumChannels; ++c) {
                        rec.t2[c] = t2Arr[c];
                        rec.q_raw[c] = qRawArr[c];
                        rec.r_unwrap[c] = rUnwrapArr[c];
                    }
                    slotRecs[slot].push_back(rec);
                },
                {"run", "eventID", "distanceToCollidingBCID", "longTracks", "_grl_good", "_tk", "_raw", "_chg"});

            totalEventLoops += df.GetNRuns();
            for (unsigned int s = 0; s < nSlots; ++s) {
                for (const auto& [r, sd] : slotMaps[s]) {
                    mergedPass2[r].mergeFrom(sd);
                }
                mergedPass2Records.insert(mergedPass2Records.end(),
                                          slotRecs[s].begin(), slotRecs[s].end());
            }
        }
    }

    const auto parentDir = std::filesystem::path(outputPath).parent_path();
    if (!parentDir.empty()) {
        std::filesystem::create_directories(parentDir);
    }

    uint64_t sumTotal = 0, sumGrlFail = 0, sumNonColl = 0, sumBlinded = 0;
    if (mode == "pass1") {
        writePass1Output(outputPath, mergedPass1);
        for (const auto& [r, d] : mergedPass1) {
            sumTotal += d.nTotal;
            sumGrlFail += d.nGrlFail;
            sumNonColl += d.nNonColliding;
            sumBlinded += d.nBlinded;
        }
    } else {
        writePass2Output(outputPath, mergedPass2, mergedPass2Records);
        for (const auto& [r, d] : mergedPass2) {
            sumTotal += d.nTotal;
            sumGrlFail += d.nGrlFail;
            sumNonColl += d.nNonColliding;
            sumBlinded += d.nBlinded;
        }
    }

    const double wallS = std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStart).count();
    INFO("[STAT] mode=", mode, " threads=", threads, " n_slots=", nSlots,
         " event_loops=", totalEventLoops, " wall_s=", wallS,
         " rate_Mevt_s=", (wallS > 0.0 ? (sumTotal * 1e-6 / wallS) : 0.0),
         " n_total=", sumTotal, " n_grl_fail=", sumGrlFail,
         " n_non_colliding=", sumNonColl, " n_blinded=", sumBlinded,
         " n_pass2_records=", mergedPass2Records.size(), " output=", outputPath);

    return 0;
}
