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
using TimingCalib::DownstreamMode;
using TimingCalib::kNumChannels;
using TimingCalib::kBunchSpacingNs;
using RawInputArray = std::array<TimingCalib::RawChannelInput, kNumChannels>;

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

// Disjoint 4-station masks for zero-covariance split ABCD (u0 vs Veto, u1 vs Timing+Preshower)
constexpr uint32_t kMaskDownA =
    (1u << static_cast<int>(TimingChannel::Veto10)) |
    (1u << static_cast<int>(TimingChannel::Veto11)) |
    (1u << static_cast<int>(TimingChannel::Veto20)) |
    (1u << static_cast<int>(TimingChannel::Veto21));

constexpr uint32_t kMaskDownB =
    (1u << static_cast<int>(TimingChannel::Timing01)) |
    (1u << static_cast<int>(TimingChannel::Timing23)) |
    (1u << static_cast<int>(TimingChannel::Preshower0)) |
    (1u << static_cast<int>(TimingChannel::Preshower1));

// Region identifiers stored in t4_tail_events
enum T4Region : uint8_t {
    REG_KIN_SR = 1,
    REG_CR_GEOM_OUTER = 2,
    REG_CR_GEOM_HITHETA = 3,
    REG_CR_EDGE_VN = 4,
    REG_NONCOLL_B1 = 5,
    REG_NONCOLL_UNPAIRED = 6,
    REG_NONCOLL_EMPTY = 7,
    REG_COSMIC = 8,
};

// Flag bitmasks for t4_tail_events.flags
constexpr uint16_t kFlagHasRedQ = 1u << 0;
constexpr uint16_t kFlagPassPhysTrig = 1u << 1;
constexpr uint16_t kFlagDownOk = 1u << 2;
constexpr uint16_t kFlagDownAValid = 1u << 3;
constexpr uint16_t kFlagDownBValid = 1u << 4;
constexpr uint16_t kFlagDownAGE2 = 1u << 5;
constexpr uint16_t kFlagDownBGE2 = 1u << 6;
constexpr uint16_t kFlagVn0Valid = 1u << 7;
constexpr uint16_t kFlagVn1Valid = 1u << 8;
constexpr uint16_t kFlagV20St512 = 1u << 9;
constexpr uint16_t kFlagPromptSub = 1u << 10;
constexpr uint16_t kFlagPassLeadTrk = 1u << 11;

// Exact fiducial / CaloNu geometry boundaries copied from RDFDefines.h
bool inFaserNuBoxExact(double x, double y, double z) {
    return (x > -115.0 && x < 135.0) &&
           (y > -171.0 && y < 129.0) &&
           (z > -3000.0 && z < -1950.0);
}

bool inLeadBlockExact(double x, double y, double z) {
    return (x > -300.0 && x < 300.0) &&
           (y > -300.0 && y < 300.0) &&
           (z > -1769.65 && z < -1619.65);
}

bool inCaloNuPMTExact(double z) {
    return (z >= -2928.0 && z <= -2812.0);
}

bool isGenieCaloNuRun(int run) {
    return (run >= 200137 && run <= 200147) || (run >= 200172 && run <= 200183);
}

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
    return static_cast<double>(h >> 11) * kInv2Pow53;
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

std::vector<std::string> readListFile(const std::string& path) {
    std::ifstream ifs(path);
    if (!ifs.is_open()) {
        throw std::runtime_error("Cannot open input-list file: " + path);
    }
    std::vector<std::string> out;
    std::string line;
    while (std::getline(ifs, line)) {
        const auto pos = line.find_first_not_of(" \t\r\n");
        if (pos == std::string::npos || line[pos] == '#') continue;
        const auto end = line.find_last_not_of(" \t\r\n");
        out.push_back(line.substr(pos, end - pos + 1));
    }
    return out;
}

struct TaskSpec {
    std::string taskId;
    int year{0};
    int run{0};
    std::vector<std::string> files;
};

struct SchemaSignature {
    bool hasVetoSt{false};
    bool hasTimeNotLocaltime{false};
    bool hasNativeVeto11{false};
    bool hasPreshower23{false};
    bool hasMuon{false};
    bool hasBcidTrig{false};
    bool hasReducedCharge{false};
    bool hasVetoGm{false};
    bool hasInboundB1{false};
    bool hasUnpairedB1{false};
    bool hasUnpairedB2{false};
    bool hasTruth{false};
    std::string eventTimeType{"UInt_t"};
    std::string nLayersType{"ROOT::VecOps::RVec<unsigned int>"};

    std::string key() const {
        return std::string(hasVetoSt ? "1" : "0") +
               (hasTimeNotLocaltime ? "1" : "0") +
               (hasNativeVeto11 ? "1" : "0") +
               (hasPreshower23 ? "1" : "0") +
               (hasMuon ? "1" : "0") +
               (hasBcidTrig ? "1" : "0") +
               (hasReducedCharge ? "1" : "0") +
               (hasVetoGm ? "1" : "0") +
               (hasInboundB1 ? "1" : "0") +
               (hasUnpairedB1 ? "1" : "0") +
               (hasUnpairedB2 ? "1" : "0") +
               (hasTruth ? "1" : "0") + "|" +
               eventTimeType + "|" + nLayersType;
    }
};

bool probeFileSchema(const std::string& fpath, SchemaSignature& sigOut) {
    std::unique_ptr<TFile> tf(TFile::Open(fpath.c_str(), "READ"));
    if (!tf || tf->IsZombie()) {
        throw std::runtime_error("Cannot open ROOT file: " + fpath);
    }
    auto* tree = tf->Get<TTree>("nt");
    if (!tree) {
        throw std::runtime_error("Missing 'nt' tree in file: " + fpath);
    }
    if (tree->GetEntries() <= 0) {
        return false;
    }
    std::unordered_set<std::string> br;
    if (auto* blist = tree->GetListOfBranches()) {
        for (int i = 0; i < blist->GetEntries(); ++i) {
            br.insert(blist->At(i)->GetName());
        }
    }
    SchemaSignature sig;
    sig.hasVetoSt = br.count("VetoSt10_raw_charge") > 0;
    sig.hasTimeNotLocaltime = (br.count("VetoNu0_localtime") == 0) && (br.count("VetoNu0_time") > 0);
    sig.hasNativeVeto11 = (br.count("Veto11_raw_charge") > 0) || (br.count("VetoSt11_raw_charge") > 0);
    sig.hasPreshower23 = (br.count("Preshower2_raw_charge") > 0) && (br.count("Preshower3_raw_charge") > 0);
    sig.hasMuon = (br.count("Muon0_raw_charge") > 0) && (br.count("Muon1_raw_charge") > 0) &&
                  (br.count("Track_X_atMuon1") > 0) && (br.count("Track_X_atMuon2") > 0);
    sig.hasBcidTrig = (br.count("VetoNu0_bcidtime") > 0) && (br.count("VetoNu0_triggertime") > 0);
    sig.hasReducedCharge = (br.count("VetoNu0_reduced_charge") > 0) && (br.count("VetoNu1_reduced_charge") > 0);
    sig.hasVetoGm = (br.count("VetoGm0_raw_charge") > 0) && (br.count("VetoGm1_raw_charge") > 0);
    sig.hasInboundB1 = br.count("distanceToInboundB1") > 0;
    sig.hasUnpairedB1 = br.count("distanceToUnpairedB1") > 0;
    sig.hasUnpairedB2 = br.count("distanceToUnpairedB2") > 0;
    sig.hasTruth = (br.count("truth_pdg") > 0) && (br.count("truth_dec_z") > 0) && (br.count("truth_pz") > 0);

    ROOT::RDataFrame probeDf(*tree);
    sig.eventTimeType = br.count("eventTime") ? probeDf.GetColumnType("eventTime") : "UInt_t";
    sig.nLayersType = probeDf.GetColumnType("Track_nLayers");
    sigOut = sig;
    return true;
}

struct ScannerTrackData {
    int nTracks{0};
    double leadPz0GeV{kNaN};
    uint32_t leadNLayers{0};
    double leadNDoF{kNaN};
    double leadChi2NDF{kNaN};
    double leadRMax{kNaN};
    double leadThetaMrad{kNaN};
    std::array<double, 8> x{};
    std::array<double, 8> y{};
    std::array<bool, 8> validPos{};
};

struct ScannerEventAux {
    float veto20Charge{0.0f};
    float veto21Charge{0.0f};
    float timingTopCharge{0.0f};
    float timingBottomCharge{0.0f};
    float preshower0Charge{0.0f};
    float preshower1Charge{0.0f};
    float vetoNu0ReducedCharge{-1.0f};
    float vetoNu1ReducedCharge{-1.0f};
    float vetoGmMaxCharge{-1.0f};
    int32_t vn0Status{0};
    int32_t vn1Status{0};
    int32_t v20Status{0};
    int32_t v21Status{0};
    uint8_t genieClass{0};     // 0: N/A or non-GENIE, 1: fiducial nu_mu CC, 2: other neutrino interaction
    bool vetoCaloNuPmt{false}; // true if MC in CaloNu run and truth_dec_z inside CaloNu PMT
};

constexpr std::array<int, kNumChannels> kChannelPlaneIdx = {{
    0, 0, // VetoNu0, VetoNu1
    1, 1, // Veto10, Veto11
    2, 2, // Veto20, Veto21
    3, 3, // Timing01, Timing23
    4, 5, // Preshower0, Preshower1
    4, 5, // Preshower2, Preshower3
    6, 7  // Muon0, Muon1
}};

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
        if (x < xMin) { ++underflow; return; }
        if (x >= xMax) { ++overflow; return; }
        int b = static_cast<int>((x - xMin) * invWidth);
        if (b < 0) b = 0;
        if (b >= nBins) b = nBins - 1;
        ++bins[static_cast<size_t>(b)];
    }

    void addFrom(const FastHist1D& other) {
        if (bins.empty()) { *this = other; return; }
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

struct CovAccum {
    uint64_t n{0};
    double sx{0.0};
    double sy{0.0};
    double sxx{0.0};
    double syy{0.0};
    double sxy{0.0};

    void fill(double x, double y) {
        if (!std::isfinite(x) || !std::isfinite(y)) return;
        ++n;
        sx += x;
        sy += y;
        sxx += x * x;
        syy += y * y;
        sxy += x * y;
    }

    void addFrom(const CovAccum& o) {
        n += o.n;
        sx += o.sx;
        sy += o.sy;
        sxx += o.sxx;
        syy += o.syy;
        sxy += o.sxy;
    }
};

struct T4RunStats {
    bool initialized{false};
    int run{0};
    bool isMC{false};
    bool isCosmic{false};
    bool hasReducedCharge{false};
    bool hasVetoGm{false};

    uint64_t nTotal{0};
    uint64_t nGrlFail{0};
    uint64_t nNoRunOffsets{0};
    uint64_t nColliding{0};
    uint64_t nCollidingPhysTrig{0};
    uint64_t nBeam1{0};
    uint64_t nBeam1PhysTrig{0};
    uint64_t nUnpaired{0};
    uint64_t nUnpairedPhysTrig{0};
    uint64_t nEmptyBcid{0};
    uint64_t nEmptyBcidPhysTrig{0};

    // Unbiased accidental VetoNu monitor on non-colliding crossings (without downstream track req)
    uint64_t nAccDenomNonColl{0};
    uint64_t nAccVn0Q30{0};
    uint64_t nAccVn1Q30{0};
    uint64_t nAccVnBothQ30{0};
    uint64_t nAccVn0Q40{0};
    uint64_t nAccVn1Q40{0};
    uint64_t nAccVn0DelayedT1{0};
    uint64_t nAccVn1DelayedT1{0};

    uint64_t nBlinded{0};
    uint64_t nCosmicLongTrk{0};
    uint64_t nCosmicDownScintTrk20{0};
    uint64_t nCosmicDownTrk{0};
    uint64_t nCosmicDownTrkNoOff{0};

    // Region counts (passing CaloNuClean + BaseDownTrk)
    uint64_t nSrZoneARed30{0};
    uint64_t nSrZoneARaw40{0};
    uint64_t nSrPrompt2HitDt1p0{0};
    uint64_t nSrPrompt2HitDt1p5{0};
    uint64_t nSrPrompt2HitU1p0{0};
    uint64_t nSrPrompt2HitU1p5{0};
    uint64_t nSrPrompt1Hit0Red30{0};
    uint64_t nSrPrompt1Hit1Red30{0};
    uint64_t nSrPrompt1Hit0Raw40{0};
    uint64_t nSrPrompt1Hit1Raw40{0};

    uint64_t nGeomAll{0};
    uint64_t nGeomZoneARed30{0};
    uint64_t nGeomZoneARaw40{0};
    uint64_t nGeomPrompt2HitU1p0{0};
    uint64_t nGeomPrompt2HitDt1p0{0};
    uint64_t nGeomPrompt1Hit0Red30{0};
    uint64_t nGeomPrompt1Hit1Red30{0};
    uint64_t nGeomPrompt1Hit0Raw40{0};
    uint64_t nGeomPrompt1Hit1Raw40{0};

    uint64_t nEdgeVnAll{0};
    uint64_t nEdgeVnZoneARed30{0};
    uint64_t nEdgeVnZoneBRed30{0};

    uint64_t nNonCollB1DownTrk{0};
    uint64_t nNonCollUnpDownTrk{0};
    uint64_t nNonCollEmptyDownTrk{0};

    // Covariance accumulators for (u0, u1) vs (dt0, dt1)
    CovAccum covSrU1p0;
    CovAccum covSrDt1p0;
    CovAccum covSrU1p5;
    CovAccum covSrDt1p5;
    CovAccum covGeomU1p0;
    CovAccum covGeomDt1p0;
    CovAccum covGeomU1p5;
    CovAccum covGeomDt1p5;
    CovAccum covSrU1p0St512;
    CovAccum covSrDt1p0St512;

    void init(int r, bool mc, bool cos, bool redQ, bool vgm) {
        if (initialized) return;
        initialized = true;
        run = r;
        isMC = mc;
        isCosmic = cos;
        hasReducedCharge = redQ;
        hasVetoGm = vgm;
    }

    void mergeFrom(const T4RunStats& o) {
        if (!initialized) init(o.run, o.isMC, o.isCosmic, o.hasReducedCharge, o.hasVetoGm);
        hasReducedCharge = hasReducedCharge || o.hasReducedCharge;
        hasVetoGm = hasVetoGm || o.hasVetoGm;
        nTotal += o.nTotal;
        nGrlFail += o.nGrlFail;
        nNoRunOffsets += o.nNoRunOffsets;
        nColliding += o.nColliding;
        nCollidingPhysTrig += o.nCollidingPhysTrig;
        nBeam1 += o.nBeam1;
        nBeam1PhysTrig += o.nBeam1PhysTrig;
        nUnpaired += o.nUnpaired;
        nUnpairedPhysTrig += o.nUnpairedPhysTrig;
        nEmptyBcid += o.nEmptyBcid;
        nEmptyBcidPhysTrig += o.nEmptyBcidPhysTrig;

        nAccDenomNonColl += o.nAccDenomNonColl;
        nAccVn0Q30 += o.nAccVn0Q30;
        nAccVn1Q30 += o.nAccVn1Q30;
        nAccVnBothQ30 += o.nAccVnBothQ30;
        nAccVn0Q40 += o.nAccVn0Q40;
        nAccVn1Q40 += o.nAccVn1Q40;
        nAccVn0DelayedT1 += o.nAccVn0DelayedT1;
        nAccVn1DelayedT1 += o.nAccVn1DelayedT1;

        nBlinded += o.nBlinded;
        nCosmicLongTrk += o.nCosmicLongTrk;
        nCosmicDownScintTrk20 += o.nCosmicDownScintTrk20;
        nCosmicDownTrk += o.nCosmicDownTrk;
        nCosmicDownTrkNoOff += o.nCosmicDownTrkNoOff;

        nSrZoneARed30 += o.nSrZoneARed30;
        nSrZoneARaw40 += o.nSrZoneARaw40;
        nSrPrompt2HitDt1p0 += o.nSrPrompt2HitDt1p0;
        nSrPrompt2HitDt1p5 += o.nSrPrompt2HitDt1p5;
        nSrPrompt2HitU1p0 += o.nSrPrompt2HitU1p0;
        nSrPrompt2HitU1p5 += o.nSrPrompt2HitU1p5;
        nSrPrompt1Hit0Red30 += o.nSrPrompt1Hit0Red30;
        nSrPrompt1Hit1Red30 += o.nSrPrompt1Hit1Red30;
        nSrPrompt1Hit0Raw40 += o.nSrPrompt1Hit0Raw40;
        nSrPrompt1Hit1Raw40 += o.nSrPrompt1Hit1Raw40;

        nGeomAll += o.nGeomAll;
        nGeomZoneARed30 += o.nGeomZoneARed30;
        nGeomZoneARaw40 += o.nGeomZoneARaw40;
        nGeomPrompt2HitU1p0 += o.nGeomPrompt2HitU1p0;
        nGeomPrompt2HitDt1p0 += o.nGeomPrompt2HitDt1p0;
        nGeomPrompt1Hit0Red30 += o.nGeomPrompt1Hit0Red30;
        nGeomPrompt1Hit1Red30 += o.nGeomPrompt1Hit1Red30;
        nGeomPrompt1Hit0Raw40 += o.nGeomPrompt1Hit0Raw40;
        nGeomPrompt1Hit1Raw40 += o.nGeomPrompt1Hit1Raw40;

        nEdgeVnAll += o.nEdgeVnAll;
        nEdgeVnZoneARed30 += o.nEdgeVnZoneARed30;
        nEdgeVnZoneBRed30 += o.nEdgeVnZoneBRed30;

        nNonCollB1DownTrk += o.nNonCollB1DownTrk;
        nNonCollUnpDownTrk += o.nNonCollUnpDownTrk;
        nNonCollEmptyDownTrk += o.nNonCollEmptyDownTrk;

        covSrU1p0.addFrom(o.covSrU1p0);
        covSrDt1p0.addFrom(o.covSrDt1p0);
        covSrU1p5.addFrom(o.covSrU1p5);
        covSrDt1p5.addFrom(o.covSrDt1p5);
        covGeomU1p0.addFrom(o.covGeomU1p0);
        covGeomDt1p0.addFrom(o.covGeomDt1p0);
        covGeomU1p5.addFrom(o.covGeomU1p5);
        covGeomDt1p5.addFrom(o.covGeomDt1p5);
        covSrU1p0St512.addFrom(o.covSrU1p0St512);
        covSrDt1p0St512.addFrom(o.covSrDt1p0St512);
    }
};

struct T4PeriodHists {
    bool initialized{false};
    std::string period;

    FastHist1D hSrU0Prompt, hSrU1Prompt, hSrDt0Prompt, hSrDt1Prompt;
    FastHist1D hGeomU0, hGeomU1, hGeomDt0, hGeomDt1;
    FastHist1D hSrRvn2Hit, hSrRvn1Hit0, hSrRvn1Hit1;
    FastHist1D hSrRvn1Hit0Raw40, hSrRvn1Hit1Raw40;
    FastHist1D hGeomRvn2Hit, hGeomRvn1Hit0, hGeomRvn1Hit1;
    FastHist1D hSrQ0Prompt, hSrQ1Prompt, hGeomQ0Prompt, hGeomQ1Prompt;
    FastHist1D hGeomDt0HiQ, hGeomDt1HiQ, hGeomDt0W12, hGeomDt1W12;
    FastHist1D hGeomWidthPrompt, hGeomWidthPosTail;
    FastHist1D hDownT1Sat;

    void init(const std::string& p) {
        if (initialized) return;
        initialized = true;
        period = p;
        // 0.1 ns bins over [-25, +35] ns (Data SR strictly zero above +1.5 ns)
        hSrU0Prompt.init(600, -25.0, 35.0);
        hSrU1Prompt.init(600, -25.0, 35.0);
        hSrDt0Prompt.init(600, -25.0, 35.0);
        hSrDt1Prompt.init(600, -25.0, 35.0);
        hGeomU0.init(600, -25.0, 35.0);
        hGeomU1.init(600, -25.0, 35.0);
        hGeomDt0.init(600, -25.0, 35.0);
        hGeomDt1.init(600, -25.0, 35.0);
        hSrRvn2Hit.init(36, 0.0, 180.0);
        hSrRvn1Hit0.init(36, 0.0, 180.0);
        hSrRvn1Hit1.init(36, 0.0, 180.0);
        hSrRvn1Hit0Raw40.init(36, 0.0, 180.0);
        hSrRvn1Hit1Raw40.init(36, 0.0, 180.0);
        hGeomRvn2Hit.init(36, 0.0, 180.0);
        hGeomRvn1Hit0.init(36, 0.0, 180.0);
        hGeomRvn1Hit1.init(36, 0.0, 180.0);
        hSrQ0Prompt.init(100, 0.0, 500.0);
        hSrQ1Prompt.init(100, 0.0, 500.0);
        hGeomQ0Prompt.init(100, 0.0, 500.0);
        hGeomQ1Prompt.init(100, 0.0, 500.0);
        hGeomDt0HiQ.init(600, -25.0, 35.0);
        hGeomDt1HiQ.init(600, -25.0, 35.0);
        hGeomDt0W12.init(600, -25.0, 35.0);
        hGeomDt1W12.init(600, -25.0, 35.0);
        hGeomWidthPrompt.init(100, 0.0, 25.0);
        hGeomWidthPosTail.init(100, 0.0, 25.0);
        hDownT1Sat.init(500, -12.5, 12.5);
    }

    void mergeFrom(const T4PeriodHists& o) {
        if (!initialized) init(o.period);
        hSrU0Prompt.addFrom(o.hSrU0Prompt);
        hSrU1Prompt.addFrom(o.hSrU1Prompt);
        hSrDt0Prompt.addFrom(o.hSrDt0Prompt);
        hSrDt1Prompt.addFrom(o.hSrDt1Prompt);
        hGeomU0.addFrom(o.hGeomU0);
        hGeomU1.addFrom(o.hGeomU1);
        hGeomDt0.addFrom(o.hGeomDt0);
        hGeomDt1.addFrom(o.hGeomDt1);
        hSrRvn2Hit.addFrom(o.hSrRvn2Hit);
        hSrRvn1Hit0.addFrom(o.hSrRvn1Hit0);
        hSrRvn1Hit1.addFrom(o.hSrRvn1Hit1);
        hSrRvn1Hit0Raw40.addFrom(o.hSrRvn1Hit0Raw40);
        hSrRvn1Hit1Raw40.addFrom(o.hSrRvn1Hit1Raw40);
        hGeomRvn2Hit.addFrom(o.hGeomRvn2Hit);
        hGeomRvn1Hit0.addFrom(o.hGeomRvn1Hit0);
        hGeomRvn1Hit1.addFrom(o.hGeomRvn1Hit1);
        hSrQ0Prompt.addFrom(o.hSrQ0Prompt);
        hSrQ1Prompt.addFrom(o.hSrQ1Prompt);
        hGeomQ0Prompt.addFrom(o.hGeomQ0Prompt);
        hGeomQ1Prompt.addFrom(o.hGeomQ1Prompt);
        hGeomDt0HiQ.addFrom(o.hGeomDt0HiQ);
        hGeomDt1HiQ.addFrom(o.hGeomDt1HiQ);
        hGeomDt0W12.addFrom(o.hGeomDt0W12);
        hGeomDt1W12.addFrom(o.hGeomDt1W12);
        hGeomWidthPrompt.addFrom(o.hGeomWidthPrompt);
        hGeomWidthPosTail.addFrom(o.hGeomWidthPosTail);
        hDownT1Sat.addFrom(o.hDownT1Sat);
    }
};

struct T4TailRecord {
    int32_t run{0};
    int64_t eventID{0};
    uint8_t region{0};
    uint8_t genie_class{0};
    uint16_t flags{0};
    float pz0_gev{0.0f};
    float r_max{0.0f};
    float r_ift{0.0f};
    float r_vn{0.0f};
    float theta_mrad{0.0f};
    float q0_raw{0.0f};
    float q1_raw{0.0f};
    float q0_red{0.0f};
    float q1_red{0.0f};
    float w0{0.0f};
    float w1{0.0f};
    float dt0{0.0f};
    float dt1{0.0f};
    float pull0{0.0f};
    float pull1{0.0f};
    float u0{0.0f};
    float u1{0.0f};
    float zu0{0.0f};
    float zu1{0.0f};
    float t0_down{0.0f};
    float sig_t0_down{0.0f};
    float chi2_ndof_down{0.0f};
    float dchi2_back{0.0f};
    float vgm_max_q{-1.0f};
};

template <typename TTime>
ROOT::RDF::RNode attachGrlGoodColumn(ROOT::RDF::RNode node,
                                      std::shared_ptr<const GRLUtils::GRLTimes> grl,
                                      bool bypassGrl) {
    if (bypassGrl || !grl) {
        return node.Define("_grl_good", []() -> bool { return true; }, {});
    }
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
            int i0 = 0;
            for (int i = 1; i < n; ++i) {
                if (pz0[i] > pz0[i0]) i0 = i;
            }
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

ROOT::RDF::RNode prepareNode(
    TChain& chain,
    const SchemaSignature& sig,
    const std::shared_ptr<const GRLUtils::GRLTimes>& grl,
    bool bypassGrl,
    bool isMC,
    bool isGenie) {

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
    if (sig.hasTimeNotLocaltime) {
        const std::array<const char*, 16> pfxs = {{
            "VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21",
            "Timing0", "Timing1", "Timing2", "Timing3",
            "Preshower0", "Preshower1", "Preshower2", "Preshower3",
            "Muon0", "Muon1"
        }};
        for (const char* p : pfxs) {
            const std::string loc = std::string(p) + "_localtime";
            const std::string tm = std::string(p) + "_time";
            if (!hasCol(loc) && hasCol(tm)) df = df.Alias(loc, tm);
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
    auto ensureRVecI = [&](const std::string& name) {
        if (!hasCol(name)) df = df.Define(name, []() { return ROOT::VecOps::RVec<int>{}; }, {});
    };
    auto ensureChannel = [&](const std::string& pfx) {
        ensureInt(pfx + "_status", -1);
        ensureFloat(pfx + "_bcidtime", 0.0f);
        ensureFloat(pfx + "_triggertime", 0.0f);
        ensureFloat(pfx + "_localtime", 0.0f);
        ensureFloat(pfx + "_raw_charge", 0.0f);
        ensureFloat(pfx + "_width", 0.0f);
    };

    for (const char* p : {"VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21",
                          "Timing0", "Timing1", "Timing2", "Timing3",
                          "Preshower0", "Preshower1", "Preshower2", "Preshower3", "Muon0", "Muon1"}) {
        ensureChannel(p);
    }
    ensureInt("distanceToCollidingBCID", 0);
    ensureInt("distanceToInboundB1", -9999);
    ensureInt("distanceToUnpairedB1", -9999);
    ensureInt("distanceToUnpairedB2", -9999);
    ensureFloat("VetoNu0_reduced_charge", -1.0f);
    ensureFloat("VetoNu1_reduced_charge", -1.0f);
    ensureFloat("VetoGm0_raw_charge", -1.0f);
    ensureFloat("VetoGm1_raw_charge", -1.0f);
    ensureRVecD("Track_X_atMuon1");
    ensureRVecD("Track_Y_atMuon1");
    ensureRVecD("Track_X_atMuon2");
    ensureRVecD("Track_Y_atMuon2");
    ensureRVecI("truth_pdg");
    ensureRVecD("truth_dec_x");
    ensureRVecD("truth_dec_y");
    ensureRVecD("truth_dec_z");
    ensureRVecD("truth_pz");

    if (sig.eventTimeType == "Int_t" || sig.eventTimeType == "int") {
        df = attachGrlGoodColumn<Int_t>(df, grl, bypassGrl);
    } else if (sig.eventTimeType == "UInt_t" || sig.eventTimeType == "unsigned int") {
        df = attachGrlGoodColumn<UInt_t>(df, grl, bypassGrl);
    } else if (sig.eventTimeType == "Long64_t" || sig.eventTimeType == "long long") {
        df = attachGrlGoodColumn<Long64_t>(df, grl, bypassGrl);
    } else {
        df = attachGrlGoodColumn<ULong64_t>(df, grl, bypassGrl);
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

    df = df.Define("_raw",
        [isMC](const RawInputArray& prev, const ScannerTrackData& tk,
               Int_t t0_st, Float_t t0_b, Float_t t0_t, Float_t t0_l, Float_t t0_q, Float_t t0_w,
               Int_t t1_st, Float_t t1_b, Float_t t1_t, Float_t t1_l, Float_t t1_q, Float_t t1_w,
               Int_t t2_st, Float_t t2_b, Float_t t2_t, Float_t t2_l, Float_t t2_q, Float_t t2_w,
               Int_t t3_st, Float_t t3_b, Float_t t3_t, Float_t t3_l, Float_t t3_q, Float_t t3_w) -> RawInputArray {
            RawInputArray arr = prev;
            if (!isMC) {
                arr[6] = TimingCalibrator::combineTimingPair(
                    TimingCalibrator::isGoodWaveformStatus(t0_st), t0_b, t0_t, t0_l, t0_q, t0_w,
                    TimingCalibrator::isGoodWaveformStatus(t1_st), t1_b, t1_t, t1_l, t1_q, t1_w,
                    tk.x[3], tk.y[3], tk.validPos[3]);
                arr[7] = TimingCalibrator::combineTimingPair(
                    TimingCalibrator::isGoodWaveformStatus(t2_st), t2_b, t2_t, t2_l, t2_q, t2_w,
                    TimingCalibrator::isGoodWaveformStatus(t3_st), t3_b, t3_t, t3_l, t3_q, t3_w,
                    tk.x[3], tk.y[3], tk.validPos[3]);
            } else {
                arr[6] = TimingCalibrator::combineTimingPairMC(
                    TimingCalibrator::isGoodWaveformStatus(t0_st), t0_l, t0_q, t0_w,
                    TimingCalibrator::isGoodWaveformStatus(t1_st), t1_l, t1_q, t1_w,
                    tk.x[3], tk.y[3], tk.validPos[3]);
                arr[7] = TimingCalibrator::combineTimingPairMC(
                    TimingCalibrator::isGoodWaveformStatus(t2_st), t2_l, t2_q, t2_w,
                    TimingCalibrator::isGoodWaveformStatus(t3_st), t3_l, t3_q, t3_w,
                    tk.x[3], tk.y[3], tk.validPos[3]);
            }
            return arr;
        },
        {"_raw_c", "_tk",
         "Timing0_status", "Timing0_bcidtime", "Timing0_triggertime", "Timing0_localtime", "Timing0_raw_charge", "Timing0_width",
         "Timing1_status", "Timing1_bcidtime", "Timing1_triggertime", "Timing1_localtime", "Timing1_raw_charge", "Timing1_width",
         "Timing2_status", "Timing2_bcidtime", "Timing2_triggertime", "Timing2_localtime", "Timing2_raw_charge", "Timing2_width",
         "Timing3_status", "Timing3_bcidtime", "Timing3_triggertime", "Timing3_localtime", "Timing3_raw_charge", "Timing3_width"});

    df = df.Define("_aux",
        [sig, isGenie](Int_t run,
                       Float_t v20, Float_t v21,
                       Float_t t0, Float_t t1, Float_t t2, Float_t t3,
                       Float_t p0, Float_t p1,
                       Float_t vn0red, Float_t vn1red,
                       Float_t vgm0, Float_t vgm1,
                       Int_t vn0st, Int_t vn1st, Int_t v20st, Int_t v21st,
                       const ROOT::VecOps::RVec<int>& tpdg,
                       const ROOT::VecOps::RVec<double>& tdx,
                       const ROOT::VecOps::RVec<double>& tdy,
                       const ROOT::VecOps::RVec<double>& tdz,
                       const ROOT::VecOps::RVec<double>& tpz) -> ScannerEventAux {
            ScannerEventAux a;
            a.veto20Charge = v20;
            a.veto21Charge = v21;
            a.timingBottomCharge = t0 + t1;
            a.timingTopCharge = t2 + t3;
            a.preshower0Charge = p0;
            a.preshower1Charge = p1;
            a.vetoNu0ReducedCharge = sig.hasReducedCharge ? vn0red : -1.0f;
            a.vetoNu1ReducedCharge = sig.hasReducedCharge ? vn1red : -1.0f;
            a.vetoGmMaxCharge = sig.hasVetoGm ? std::max(vgm0, vgm1) : -1.0f;
            a.vn0Status = vn0st;
            a.vn1Status = vn1st;
            a.v20Status = v20st;
            a.v21Status = v21st;
            if (isGenie && sig.hasTruth && !tpdg.empty() && !tdx.empty() && !tdy.empty() && !tdz.empty() && !tpz.empty()) {
                const double x0 = tdx[0], y0 = tdy[0], z0 = tdz[0];
                const double pzGeV = tpz[0] * 1e-3;
                const int pdg0 = tpdg[0];
                bool isCC = false;
                for (int p : tpdg) {
                    const int ap = std::abs(p);
                    if (ap == 11 || ap == 13 || ap == 15) { isCC = true; break; }
                }
                a.vetoCaloNuPmt = isGenieCaloNuRun(run) && inCaloNuPMTExact(z0);
                const bool inVol = inFaserNuBoxExact(x0, y0, z0) || inLeadBlockExact(x0, y0, z0);
                const double rDec = std::hypot(x0, y0);
                if (isCC && std::abs(pdg0) == 14 && inVol && rDec < 100.0 && pzGeV > 100.0) {
                    a.genieClass = 1;
                } else {
                    a.genieClass = 2;
                }
            }
            return a;
        },
        {"run",
         "Veto20_charge", "Veto21_charge",
         "Timing0_charge", "Timing1_charge", "Timing2_charge", "Timing3_charge",
         "Preshower0_charge", "Preshower1_charge",
         "VetoNu0_reduced_charge", "VetoNu1_reduced_charge",
         "VetoGm0_raw_charge", "VetoGm1_raw_charge",
         "VetoNu0_status", "VetoNu1_status", "Veto20_status", "Veto21_status",
         "truth_pdg", "truth_dec_x", "truth_dec_y", "truth_dec_z", "truth_pz"});

    return df;
}

TimingBlinding::EventKinematicsAndVeto buildBlindStruct(
    bool isMC,
    int distBCID,
    int longTracks,
    const ScannerTrackData& tk,
    const RawInputArray& raw,
    const ScannerEventAux& aux) {
    TimingBlinding::EventKinematicsAndVeto ev;
    ev.isMC = isMC;
    ev.distanceToCollidingBCID = distBCID;
    ev.longTracks = longTracks;
    ev.veto20Charge = aux.veto20Charge;
    ev.veto21Charge = aux.veto21Charge;
    ev.timingChargeTop = aux.timingTopCharge;
    ev.timingChargeBottom = aux.timingBottomCharge;
    ev.preshower0Charge = aux.preshower0Charge;
    ev.preshower1Charge = aux.preshower1Charge;
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
    ev.vetoNu0ReducedCharge = aux.vetoNu0ReducedCharge;
    ev.vetoNu1ReducedCharge = aux.vetoNu1ReducedCharge;
    return ev;
}

void writeCovBranches(TTree* t, CovAccum& c, const std::string& pfx) {
    t->Branch((pfx + "_n").c_str(), &c.n);
    t->Branch((pfx + "_sx").c_str(), &c.sx);
    t->Branch((pfx + "_sy").c_str(), &c.sy);
    t->Branch((pfx + "_sxx").c_str(), &c.sxx);
    t->Branch((pfx + "_syy").c_str(), &c.syy);
    t->Branch((pfx + "_sxy").c_str(), &c.sxy);
}

void writeOutput(
    const std::string& outputPath,
    const std::map<int, T4RunStats>& runStats,
    const std::map<std::string, T4PeriodHists>& perHists,
    std::vector<T4TailRecord>& records) {

    std::sort(records.begin(), records.end(), [](const T4TailRecord& a, const T4TailRecord& b) {
        if (a.run != b.run) return a.run < b.run;
        if (a.eventID != b.eventID) return a.eventID < b.eventID;
        return a.region < b.region;
    });

    std::unique_ptr<TFile> outFile(TFile::Open(outputPath.c_str(), "RECREATE"));
    if (!outFile || outFile->IsZombie()) {
        throw std::runtime_error("Cannot create T4 output: " + outputPath);
    }

    TTree* st = new TTree("t4_run_summary", "Stage T4 per-run exposure and control-region summary");
    T4RunStats row;
    std::string period;
    st->Branch("run", &row.run);
    st->Branch("period", &period);
    st->Branch("is_mc", &row.isMC);
    st->Branch("is_cosmic", &row.isCosmic);
    st->Branch("has_reduced_charge", &row.hasReducedCharge);
    st->Branch("has_vetogm", &row.hasVetoGm);
    st->Branch("n_total", &row.nTotal);
    st->Branch("n_grl_fail", &row.nGrlFail);
    st->Branch("n_no_run_offsets", &row.nNoRunOffsets);
    st->Branch("n_colliding", &row.nColliding);
    st->Branch("n_colliding_phys_trig", &row.nCollidingPhysTrig);
    st->Branch("n_beam1", &row.nBeam1);
    st->Branch("n_beam1_phys_trig", &row.nBeam1PhysTrig);
    st->Branch("n_unpaired", &row.nUnpaired);
    st->Branch("n_unpaired_phys_trig", &row.nUnpairedPhysTrig);
    st->Branch("n_empty_bcid", &row.nEmptyBcid);
    st->Branch("n_empty_bcid_phys_trig", &row.nEmptyBcidPhysTrig);
    st->Branch("n_acc_denom_noncoll", &row.nAccDenomNonColl);
    st->Branch("n_acc_vn0_q30", &row.nAccVn0Q30);
    st->Branch("n_acc_vn1_q30", &row.nAccVn1Q30);
    st->Branch("n_acc_vnboth_q30", &row.nAccVnBothQ30);
    st->Branch("n_acc_vn0_q40", &row.nAccVn0Q40);
    st->Branch("n_acc_vn1_q40", &row.nAccVn1Q40);
    st->Branch("n_acc_vn0_delayed_t1", &row.nAccVn0DelayedT1);
    st->Branch("n_acc_vn1_delayed_t1", &row.nAccVn1DelayedT1);
    st->Branch("n_blinded", &row.nBlinded);
    st->Branch("n_cosmic_long_trk", &row.nCosmicLongTrk);
    st->Branch("n_cosmic_downscint_trk20", &row.nCosmicDownScintTrk20);
    st->Branch("n_cosmic_downtrk", &row.nCosmicDownTrk);
    st->Branch("n_cosmic_downtrk_nooff", &row.nCosmicDownTrkNoOff);
    st->Branch("n_sr_zonea_red30", &row.nSrZoneARed30);
    st->Branch("n_sr_zonea_raw40", &row.nSrZoneARaw40);
    st->Branch("n_sr_prompt_2hit_dt1p0", &row.nSrPrompt2HitDt1p0);
    st->Branch("n_sr_prompt_2hit_dt1p5", &row.nSrPrompt2HitDt1p5);
    st->Branch("n_sr_prompt_2hit_u1p0", &row.nSrPrompt2HitU1p0);
    st->Branch("n_sr_prompt_2hit_u1p5", &row.nSrPrompt2HitU1p5);
    st->Branch("n_sr_prompt_1hit0_red30", &row.nSrPrompt1Hit0Red30);
    st->Branch("n_sr_prompt_1hit1_red30", &row.nSrPrompt1Hit1Red30);
    st->Branch("n_sr_prompt_1hit0_raw40", &row.nSrPrompt1Hit0Raw40);
    st->Branch("n_sr_prompt_1hit1_raw40", &row.nSrPrompt1Hit1Raw40);
    st->Branch("n_geom_all", &row.nGeomAll);
    st->Branch("n_geom_zonea_red30", &row.nGeomZoneARed30);
    st->Branch("n_geom_zonea_raw40", &row.nGeomZoneARaw40);
    st->Branch("n_geom_prompt_2hit_u1p0", &row.nGeomPrompt2HitU1p0);
    st->Branch("n_geom_prompt_2hit_dt1p0", &row.nGeomPrompt2HitDt1p0);
    st->Branch("n_geom_prompt_1hit0_red30", &row.nGeomPrompt1Hit0Red30);
    st->Branch("n_geom_prompt_1hit1_red30", &row.nGeomPrompt1Hit1Red30);
    st->Branch("n_geom_prompt_1hit0_raw40", &row.nGeomPrompt1Hit0Raw40);
    st->Branch("n_geom_prompt_1hit1_raw40", &row.nGeomPrompt1Hit1Raw40);
    st->Branch("n_edge_vn_all", &row.nEdgeVnAll);
    st->Branch("n_edge_vn_zonea_red30", &row.nEdgeVnZoneARed30);
    st->Branch("n_edge_vn_zoneb_red30", &row.nEdgeVnZoneBRed30);
    st->Branch("n_noncoll_b1_downtrk", &row.nNonCollB1DownTrk);
    st->Branch("n_noncoll_unp_downtrk", &row.nNonCollUnpDownTrk);
    st->Branch("n_noncoll_empty_downtrk", &row.nNonCollEmptyDownTrk);
    writeCovBranches(st, row.covSrU1p0, "cov_sr_u_1p0");
    writeCovBranches(st, row.covSrDt1p0, "cov_sr_dt_1p0");
    writeCovBranches(st, row.covSrU1p5, "cov_sr_u_1p5");
    writeCovBranches(st, row.covSrDt1p5, "cov_sr_dt_1p5");
    writeCovBranches(st, row.covGeomU1p0, "cov_geom_u_1p0");
    writeCovBranches(st, row.covGeomDt1p0, "cov_geom_dt_1p0");
    writeCovBranches(st, row.covGeomU1p5, "cov_geom_u_1p5");
    writeCovBranches(st, row.covGeomDt1p5, "cov_geom_dt_1p5");
    writeCovBranches(st, row.covSrU1p0St512, "cov_sr_u_1p0_st512");
    writeCovBranches(st, row.covSrDt1p0St512, "cov_sr_dt_1p0_st512");

    for (const auto& [r, s] : runStats) {
        row = s;
        if (s.isCosmic) period = "2024_cos";
        else if (s.isMC) period = TimingCalibrator::mcFamilyForRun(r);
        else period = TimingCalibrator::periodForDataRun(r);
        st->Fill();
    }
    st->Write();

    TTree* ev = new TTree("t4_tail_events", "Stage T4 unblinded tails, 1-hit events, sidebands, non-colliding, cosmics & MC");
    T4TailRecord rec;
    ev->Branch("run", &rec.run);
    ev->Branch("eventID", &rec.eventID);
    ev->Branch("region", &rec.region);
    ev->Branch("genie_class", &rec.genie_class);
    ev->Branch("flags", &rec.flags);
    ev->Branch("pz0_gev", &rec.pz0_gev);
    ev->Branch("r_max", &rec.r_max);
    ev->Branch("r_ift", &rec.r_ift);
    ev->Branch("r_vn", &rec.r_vn);
    ev->Branch("theta_mrad", &rec.theta_mrad);
    ev->Branch("q0_raw", &rec.q0_raw);
    ev->Branch("q1_raw", &rec.q1_raw);
    ev->Branch("q0_red", &rec.q0_red);
    ev->Branch("q1_red", &rec.q1_red);
    ev->Branch("w0", &rec.w0);
    ev->Branch("w1", &rec.w1);
    ev->Branch("dt0", &rec.dt0);
    ev->Branch("dt1", &rec.dt1);
    ev->Branch("pull0", &rec.pull0);
    ev->Branch("pull1", &rec.pull1);
    ev->Branch("u0", &rec.u0);
    ev->Branch("u1", &rec.u1);
    ev->Branch("zu0", &rec.zu0);
    ev->Branch("zu1", &rec.zu1);
    ev->Branch("t0_down", &rec.t0_down);
    ev->Branch("sig_t0_down", &rec.sig_t0_down);
    ev->Branch("chi2_ndof_down", &rec.chi2_ndof_down);
    ev->Branch("dchi2_back", &rec.dchi2_back);
    ev->Branch("vgm_max_q", &rec.vgm_max_q);
    for (const auto& item : records) {
        rec = item;
        ev->Fill();
    }
    ev->Write();

    for (const auto& [per, h] : perHists) {
        TDirectory* pdir = outFile->mkdir(("period_" + per).c_str());
        pdir->cd();
        h.hSrU0Prompt.toTH1D("h_sr_u0_prompt", "SR unblinded u0;ns;Events").Write();
        h.hSrU1Prompt.toTH1D("h_sr_u1_prompt", "SR unblinded u1;ns;Events").Write();
        h.hSrDt0Prompt.toTH1D("h_sr_dt0_prompt", "SR unblinded dt0;ns;Events").Write();
        h.hSrDt1Prompt.toTH1D("h_sr_dt1_prompt", "SR unblinded dt1;ns;Events").Write();
        h.hGeomU0.toTH1D("h_geom_u0", "CR-Geom u0;ns;Events").Write();
        h.hGeomU1.toTH1D("h_geom_u1", "CR-Geom u1;ns;Events").Write();
        h.hGeomDt0.toTH1D("h_geom_dt0", "CR-Geom dt0;ns;Events").Write();
        h.hGeomDt1.toTH1D("h_geom_dt1", "CR-Geom dt1;ns;Events").Write();
        h.hSrRvn2Hit.toTH1D("h_sr_rvn_2hit", "SR prompt 2-hit rVetoNu;mm;Events").Write();
        h.hSrRvn1Hit0.toTH1D("h_sr_rvn_1hit0", "SR prompt 1-hit (VN0) rVetoNu;mm;Events").Write();
        h.hSrRvn1Hit1.toTH1D("h_sr_rvn_1hit1", "SR prompt 1-hit (VN1) rVetoNu;mm;Events").Write();
        h.hSrRvn1Hit0Raw40.toTH1D("h_sr_rvn_1hit0_raw40", "SR prompt 1-hit (VN0 raw40) rVetoNu;mm;Events").Write();
        h.hSrRvn1Hit1Raw40.toTH1D("h_sr_rvn_1hit1_raw40", "SR prompt 1-hit (VN1 raw40) rVetoNu;mm;Events").Write();
        h.hGeomRvn2Hit.toTH1D("h_geom_rvn_2hit", "CR-Geom prompt 2-hit rVetoNu;mm;Events").Write();
        h.hGeomRvn1Hit0.toTH1D("h_geom_rvn_1hit0", "CR-Geom prompt 1-hit (VN0) rVetoNu;mm;Events").Write();
        h.hGeomRvn1Hit1.toTH1D("h_geom_rvn_1hit1", "CR-Geom prompt 1-hit (VN1) rVetoNu;mm;Events").Write();
        h.hSrQ0Prompt.toTH1D("h_sr_q0_prompt", "SR prompt VetoNu0 raw_charge;pC;Events").Write();
        h.hSrQ1Prompt.toTH1D("h_sr_q1_prompt", "SR prompt VetoNu1 raw_charge;pC;Events").Write();
        h.hGeomQ0Prompt.toTH1D("h_geom_q0_prompt", "CR-Geom prompt VetoNu0 raw_charge;pC;Events").Write();
        h.hGeomQ1Prompt.toTH1D("h_geom_q1_prompt", "CR-Geom prompt VetoNu1 raw_charge;pC;Events").Write();
        h.hGeomDt0HiQ.toTH1D("h_geom_dt0_hiq", "CR-Geom dt0 (Q>200 pC);ns;Events").Write();
        h.hGeomDt1HiQ.toTH1D("h_geom_dt1_hiq", "CR-Geom dt1 (Q>200 pC);ns;Events").Write();
        h.hGeomDt0W12.toTH1D("h_geom_dt0_w12", "CR-Geom dt0 (width<12 ns);ns;Events").Write();
        h.hGeomDt1W12.toTH1D("h_geom_dt1_w12", "CR-Geom dt1 (width<12 ns);ns;Events").Write();
        h.hGeomWidthPrompt.toTH1D("h_geom_width_prompt", "CR-Geom VetoNu width (|dt|<=1.0);ns;Hits").Write();
        h.hGeomWidthPosTail.toTH1D("h_geom_width_postail", "CR-Geom VetoNu width (dt>1.5);ns;Hits").Write();
        h.hDownT1Sat.toTH1D("h_down_t1_sat", "Downstream t1 (satellite-bunch monitor);ns;Events").Write();
        outFile->cd();
    }
    outFile->Close();
}

void printUsage(const char* argv0) {
    std::cerr << "Usage: " << argv0
              << " --output <out.root> --timing-calib <dir>"
              << " [(--task-ids <id1,id2,...> --manifest <json>) | --input-list <list.txt> | --input-files <f1,f2,...>]"
              << " [--grl-config <yaml>] [--threads <n>] [--is-mc] [--is-genie] [--is-cosmic] [--max-events <n>]\n";
}

} // namespace

int main(int argc, char* argv[]) {
    ROOT::EnableThreadSafety();
    TH1::AddDirectory(false);

    std::string outputPath;
    std::string calibDir;
    std::string manifestPath = "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json";
    std::string grlConfigPath = "AnalysisZipFramework/config/grl_config_run3_full.yaml";
    std::string taskIdsArg;
    std::string inputFilesArg;
    std::string inputListArg;
    int threads = 1;
    bool isMC = false;
    bool isGenie = false;
    bool isCosmic = false;
    Long64_t maxEvents = -1;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto needVal = [&](const std::string& flag) -> std::string {
            if (i + 1 >= argc) throw std::runtime_error("Missing value for " + flag);
            return argv[++i];
        };
        if (arg == "--output" || arg == "-o") outputPath = needVal(arg);
        else if (arg == "--timing-calib") calibDir = needVal(arg);
        else if (arg == "--manifest") manifestPath = needVal(arg);
        else if (arg == "--grl-config") grlConfigPath = needVal(arg);
        else if (arg == "--task-ids") taskIdsArg = needVal(arg);
        else if (arg == "--input-files") inputFilesArg = needVal(arg);
        else if (arg == "--input-list") inputListArg = needVal(arg);
        else if (arg == "--threads" || arg == "-j") threads = std::stoi(needVal(arg));
        else if (arg == "--is-mc") isMC = true;
        else if (arg == "--is-genie") { isMC = true; isGenie = true; }
        else if (arg == "--is-cosmic") isCosmic = true;
        else if (arg == "--max-events") maxEvents = std::stoll(needVal(arg));
        else {
            printUsage(argv[0]);
            return 1;
        }
    }

    if (outputPath.empty() || calibDir.empty() ||
        (taskIdsArg.empty() && inputFilesArg.empty() && inputListArg.empty())) {
        printUsage(argv[0]);
        return 1;
    }

    const auto wallStart = std::chrono::steady_clock::now();
    if (threads > 1 && maxEvents <= 0) {
        ROOT::EnableImplicitMT(static_cast<unsigned int>(threads));
    } else if (threads > 1 && maxEvents > 0) {
        threads = 1;
    }
    const unsigned int nSlots = std::max(1u, ROOT::GetThreadPoolSize());

    auto calib = std::make_shared<TimingCalibrator>();
    calib->loadFromDirectory(calibDir);

    std::unordered_set<int> calibratedDataRuns;
    {
        std::ifstream ifs(std::filesystem::path(calibDir) / "ref_offsets_run3.json");
        if (ifs.is_open()) {
            const json rj = json::parse(ifs);
            for (auto it = rj.at("runs").begin(); it != rj.at("runs").end(); ++it) {
                calibratedDataRuns.insert(std::stoi(it.key()));
            }
        }
    }

    const bool bypassGrl = isMC || isCosmic;
    std::shared_ptr<const GRLUtils::GRLTimes> grlTimes;
    if (!bypassGrl) {
        const auto grlCfg = ConfigUtils::readGRLConfig(grlConfigPath);
        grlTimes = std::make_shared<const GRLUtils::GRLTimes>(
            GRLUtils::readGRLTimes(GRLUtils::toTStringVector(grlCfg.grlJsons)));
    }

    std::vector<std::string> files;
    if (!inputFilesArg.empty()) {
        auto s = splitCommaList(inputFilesArg);
        files.insert(files.end(), s.begin(), s.end());
    }
    if (!inputListArg.empty()) {
        auto s = readListFile(inputListArg);
        files.insert(files.end(), s.begin(), s.end());
    }
    if (!taskIdsArg.empty()) {
        std::ifstream mifs(manifestPath);
        if (!mifs.is_open()) throw std::runtime_error("Cannot open manifest: " + manifestPath);
        const json mJson = json::parse(mifs);
        const std::string dqPath = mJson.at("source_dq_manifest").get<std::string>();
        std::ifstream dqifs(dqPath);
        if (!dqifs.is_open()) throw std::runtime_error("Cannot open source_dq_manifest: " + dqPath);
        const json dqJson = json::parse(dqifs);
        const auto& dqTasks = dqJson.at("tasks");
        std::unordered_set<std::string> unavailSet;
        if (dqJson.contains("config") && dqJson.at("config").contains("unavailable_inputs")) {
            for (auto itU = dqJson.at("config").at("unavailable_inputs").begin();
                 itU != dqJson.at("config").at("unavailable_inputs").end(); ++itU) {
                unavailSet.insert(itU.key());
            }
        }
        for (const auto& tid : splitCommaList(taskIdsArg)) {
            if (!dqTasks.contains(tid)) continue;
            for (const auto& fp : dqTasks.at(tid).at("files").get<std::vector<std::string>>()) {
                if (unavailSet.count(fp) == 0) files.push_back(fp);
            }
        }
    }

    if (files.empty()) {
        ERROR("No input files resolved.");
        return 1;
    }

    struct Group {
        SchemaSignature sig;
        std::vector<std::string> files;
    };
    std::map<std::string, Group> groups;
    size_t nSkippedEmpty = 0;
    for (const auto& f : files) {
        SchemaSignature sig;
        if (!probeFileSchema(f, sig)) {
            ++nSkippedEmpty;
            continue;
        }
        auto& g = groups[sig.key()];
        g.sig = sig;
        g.files.push_back(f);
    }
    if (nSkippedEmpty > 0) {
        INFO("Skipped ", nSkippedEmpty, " zero-entry ROOT files.");
    }

    std::map<int, T4RunStats> mergedRuns;
    std::map<std::string, T4PeriodHists> mergedPers;
    std::vector<T4TailRecord> mergedRecs;
    uint64_t totalLoops = 0;

    const int iVN0 = static_cast<int>(TimingChannel::VetoNu0);
    const int iVN1 = static_cast<int>(TimingChannel::VetoNu1);
    const int iV20 = static_cast<int>(TimingChannel::Veto20);
    const int iT23 = static_cast<int>(TimingChannel::Timing23);

    for (const auto& [skey, grp] : groups) {
        TChain chain("nt");
        for (const auto& f : grp.files) chain.Add(f.c_str());
        INFO("T4 group (", skey, "): ", grp.files.size(), " files, slots=", nSlots);

        ROOT::RDF::RNode df = prepareNode(chain, grp.sig, grlTimes, bypassGrl, isMC, isGenie);
        if (maxEvents > 0) df = df.Range(static_cast<ULong64_t>(maxEvents));

        std::vector<std::unordered_map<int, T4RunStats>> slotRuns(nSlots);
        std::vector<std::unordered_map<std::string, T4PeriodHists>> slotPers(nSlots);
        std::vector<std::vector<T4TailRecord>> slotRecs(nSlots);

        df.ForeachSlot(
            [&](unsigned int slot,
                Int_t run,
                Int_t eventID,
                Int_t distColl,
                Int_t distInB1,
                Int_t distUnpB1,
                Int_t distUnpB2,
                Int_t inputBits,
                Int_t longTracks,
                bool grlGood,
                const ScannerTrackData& tk,
                const RawInputArray& raw,
                const ScannerEventAux& aux) {

                auto& rs = slotRuns[slot][run];
                if (!rs.initialized) {
                    rs.init(run, isMC, isCosmic, grp.sig.hasReducedCharge, grp.sig.hasVetoGm);
                }
                ++rs.nTotal;
                if (!bypassGrl && !grlGood) {
                    ++rs.nGrlFail;
                    return;
                }
                if (isGenie && aux.vetoCaloNuPmt) {
                    return;
                }

                const bool hasRunOffsets = isMC || (calibratedDataRuns.count(run) > 0);
                if (!hasRunOffsets) ++rs.nNoRunOffsets;

                const bool passPhysTrig = isMC || isCosmic ||
                    ((inputBits & 0x8) != 0) || ((inputBits & 0x10) != 0) ||
                    ((inputBits & 0x20) != 0) || ((inputBits & 0x40) != 0);

                const bool isColl = !isCosmic && (isMC || distColl == 0);
                const bool isNonColl = !isMC && !isCosmic && (std::abs(distColl) > 1);
                const bool isBeam1 = isNonColl && grp.sig.hasInboundB1 && (distInB1 == 0);
                const bool isUnpaired = isNonColl && !isBeam1 &&
                    ((grp.sig.hasUnpairedB1 && distUnpB1 == 0) || (grp.sig.hasUnpairedB2 && distUnpB2 == 0));
                const bool isEmpty = isNonColl && !isBeam1 && !isUnpaired;

                if (isColl) {
                    ++rs.nColliding;
                    if (passPhysTrig) ++rs.nCollidingPhysTrig;
                } else if (isBeam1) {
                    ++rs.nBeam1;
                    if (passPhysTrig) ++rs.nBeam1PhysTrig;
                } else if (isUnpaired) {
                    ++rs.nUnpaired;
                    if (passPhysTrig) ++rs.nUnpairedPhysTrig;
                } else if (isEmpty) {
                    ++rs.nEmptyBcid;
                    if (passPhysTrig) ++rs.nEmptyBcidPhysTrig;
                }

                // Unbiased non-colliding accidental VetoNu occupancy monitor
                if (isNonColl) {
                    ++rs.nAccDenomNonColl;
                    const bool q0_30 = raw[iVN0].present && std::isfinite(raw[iVN0].rawCharge) && raw[iVN0].rawCharge >= 30.0;
                    const bool q1_30 = raw[iVN1].present && std::isfinite(raw[iVN1].rawCharge) && raw[iVN1].rawCharge >= 30.0;
                    if (q0_30) ++rs.nAccVn0Q30;
                    if (q1_30) ++rs.nAccVn1Q30;
                    if (q0_30 && q1_30) ++rs.nAccVnBothQ30;
                    if (raw[iVN0].present && raw[iVN0].rawCharge >= 40.0) ++rs.nAccVn0Q40;
                    if (raw[iVN1].present && raw[iVN1].rawCharge >= 40.0) ++rs.nAccVn1Q40;
                }

                // Calibrate timing once per surviving GRL event
                const auto evt = isMC
                    ? calib->calibrateMCEvent(run, static_cast<int64_t>(eventID), raw, true, true)
                    : (hasRunOffsets
                        ? calib->calibrateDataEvent(run, raw, calib->hasTofMaps(), true)
                        : TimingCalib::EventTimingOutput{});

                if (isNonColl) {
                    if (evt.channels[iVN0].valid && raw[iVN0].rawCharge >= 30.0 && evt.channels[iVN0].tCalNs > 2.2) ++rs.nAccVn0DelayedT1;
                    if (evt.channels[iVN1].valid && raw[iVN1].rawCharge >= 30.0 && evt.channels[iVN1].tCalNs > 2.2) ++rs.nAccVn1DelayedT1;
                }

                const double leadYTrig = tk.validPos[3] ? tk.y[3] : kNaN;
                const auto down = TimingCalibrator::fitDownstreamReferenceMode(
                    evt, DownstreamMode::Trimmed3Sigma, leadYTrig, &raw);
                const auto downA = TimingCalibrator::fitDownstreamReferenceMode(
                    evt, DownstreamMode::Trimmed3Sigma, leadYTrig, &raw, kMaskDownA, 0u);
                const auto downB = TimingCalibrator::fitDownstreamReferenceMode(
                    evt, DownstreamMode::Trimmed3Sigma, leadYTrig, &raw, kMaskDownB, 0u);

                const double dt0 = (down.valid && evt.channels[iVN0].valid) ? (evt.channels[iVN0].tCalNs - down.t0Ns) : kNaN;
                const double dt1 = (down.valid && evt.channels[iVN1].valid) ? (evt.channels[iVN1].tCalNs - down.t0Ns) : kNaN;
                const double u0 = (downA.valid && evt.channels[iVN0].valid) ? (evt.channels[iVN0].tCalNs - downA.t0Ns) : kNaN;
                const double u1 = (downB.valid && evt.channels[iVN1].valid) ? (evt.channels[iVN1].tCalNs - downB.t0Ns) : kNaN;

                // MANDATORY ENTRY-GATE BLINDING GUARD BEFORE ANY REGION CLASSIFICATION OR FILL
                const auto blindEv = buildBlindStruct(isMC, isCosmic ? 9999 : distColl, longTracks, tk, raw, aux);
                if (TimingBlinding::isBlindedSRZoneB(
                        blindEv, true, down.valid,
                        evt.channels[iVN0].valid, dt0,
                        evt.channels[iVN1].valid, dt1)) {
                    ++rs.nBlinded;
                    return;
                }

                // Downstream + track kinematics shared by SR, CR-Geom, CR-EdgeVN, NonColl, Cosmic
                const bool passCaloNuClean = isMC || isCosmic ||
                    !(15821 <= run && run <= 16924) ||
                    (!(aux.v20Status == 528 || aux.v21Status == 528) &&
                     (((aux.vn0Status == 0 || aux.vn0Status == 1) && (aux.vn1Status == 0 || aux.vn1Status == 1)) ||
                      (aux.vn0Status == 0 && aux.vn1Status == 16)));

                const bool hitsTiming = tk.validPos[3] && std::isfinite(tk.y[3]) && (
                    (tk.y[3] > 20.0 && std::isfinite(aux.timingTopCharge) && aux.timingTopCharge > 20.0f) ||
                    (tk.y[3] < -20.0 && std::isfinite(aux.timingBottomCharge) && aux.timingBottomCharge > 20.0f) ||
                    (std::abs(tk.y[3]) <= 20.0 &&
                     std::isfinite(aux.timingTopCharge) && std::isfinite(aux.timingBottomCharge) &&
                     (aux.timingTopCharge + aux.timingBottomCharge) > 20.0f));

                const bool passDownScint =
                    std::isfinite(aux.veto20Charge) && aux.veto20Charge > 40.0f &&
                    std::isfinite(aux.veto21Charge) && aux.veto21Charge > 40.0f &&
                    hitsTiming &&
                    std::isfinite(aux.preshower0Charge) && aux.preshower0Charge > 2.5f &&
                    std::isfinite(aux.preshower1Charge) && aux.preshower1Charge > 2.5f;

                if (isCosmic && longTracks > 0) {
                    ++rs.nCosmicLongTrk;
                }

                const bool passLeadTrk =
                    longTracks > 0 &&
                    std::isfinite(tk.leadPz0GeV) && tk.leadPz0GeV > 100.0 &&
                    tk.leadNLayers >= 7 &&
                    std::isfinite(tk.leadNDoF) && tk.leadNDoF >= 9.0 &&
                    std::isfinite(tk.leadChi2NDF) && tk.leadChi2NDF < 15.0;

                const bool passRelaxedCosmic =
                    isCosmic && passDownScint && longTracks > 0 &&
                    std::isfinite(tk.leadPz0GeV) && tk.leadPz0GeV > 20.0 &&
                    tk.leadNLayers >= 6 &&
                    std::isfinite(tk.leadThetaMrad) && tk.leadThetaMrad < 150.0;
                if (passRelaxedCosmic) {
                    ++rs.nCosmicDownScintTrk20;
                }

                if (!passCaloNuClean || !passDownScint || (!passLeadTrk && !passRelaxedCosmic)) {
                    return;
                }

                const double rMax = tk.leadRMax;
                const double rIFT = tk.validPos[2] ? std::hypot(tk.x[2], tk.y[2]) : kNaN;
                const double rVN = tk.validPos[0] ? std::hypot(tk.x[0], tk.y[0]) : kNaN;
                const double theta = tk.leadThetaMrad;
                if (!std::isfinite(rMax) || !std::isfinite(rIFT) || !std::isfinite(rVN) || !std::isfinite(theta)) {
                    return;
                }

                uint8_t region = 0;
                if (isCosmic) {
                    if (passLeadTrk) {
                        ++rs.nCosmicDownTrk;
                        if (!hasRunOffsets) ++rs.nCosmicDownTrkNoOff;
                    }
                    region = REG_COSMIC;
                } else if (isNonColl) {
                    if (isBeam1) {
                        region = REG_NONCOLL_B1;
                        ++rs.nNonCollB1DownTrk;
                    } else if (isUnpaired) {
                        region = REG_NONCOLL_UNPAIRED;
                        ++rs.nNonCollUnpDownTrk;
                    } else {
                        region = REG_NONCOLL_EMPTY;
                        ++rs.nNonCollEmptyDownTrk;
                    }
                } else if (isColl && passPhysTrig) {
                    const bool isKinSr = (rMax < 95.0 && rIFT < 95.0 && rVN < 120.0 && theta < 25.0);
                    const bool isGeomOuter = !isKinSr && (rVN < 120.0 && theta < 25.0 && rMax < 135.0 && rIFT < 135.0 &&
                                              ((rMax >= 95.0 && rMax < 135.0) || (rIFT >= 95.0 && rIFT < 135.0)));
                    const bool isGeomHiTheta = !isKinSr && (rVN < 120.0 && rMax < 135.0 && rIFT < 135.0 &&
                                                theta >= 25.0 && theta < 55.0);
                    const bool isEdgeVn = (rMax < 95.0 && rIFT < 95.0 && theta < 25.0 && rVN >= 120.0 && rVN < 180.0);

                    if (isKinSr) region = REG_KIN_SR;
                    else if (isGeomOuter) region = REG_CR_GEOM_OUTER;
                    else if (isGeomHiTheta) region = REG_CR_GEOM_HITHETA;
                    else if (isEdgeVn) region = REG_CR_EDGE_VN;
                }

                if (region == 0) return;

                // Match Analyis.cxx exact Zone A definitions (reduced_charge < 30 with raw_charge < 40 fallback)
                const bool za0Red = grp.sig.hasReducedCharge
                    ? ((aux.vetoNu0ReducedCharge >= 0.0f) ? (aux.vetoNu0ReducedCharge < 30.0f) : (raw[iVN0].rawCharge < 40.0))
                    : (raw[iVN0].rawCharge < 40.0);
                const bool za1Red = grp.sig.hasReducedCharge
                    ? ((aux.vetoNu1ReducedCharge >= 0.0f) ? (aux.vetoNu1ReducedCharge < 30.0f) : (raw[iVN1].rawCharge < 40.0))
                    : (raw[iVN1].rawCharge < 40.0);
                const bool za0Raw = (raw[iVN0].rawCharge < 40.0);
                const bool za1Raw = (raw[iVN1].rawCharge < 40.0);
                const bool zoneARed = za0Red && za1Red;
                const bool zoneARaw = za0Raw && za1Raw;

                const double c2nd = down.valid ? (down.chi2 / static_cast<double>(std::max(1, down.ndof))) : kNaN;
                const bool downOk = down.valid && down.nUsed >= 2 && (down.ndof <= 0 || c2nd < 5.0);
                const double c2ndA = downA.valid ? (downA.chi2 / static_cast<double>(std::max(1, downA.ndof))) : kNaN;
                const double c2ndB = downB.valid ? (downB.chi2 / static_cast<double>(std::max(1, downB.ndof))) : kNaN;
                const bool downAOk = downA.valid && downA.nUsed >= 1 && (downA.ndof <= 0 || c2ndA < 5.0);
                const bool downBOk = downB.valid && downB.nUsed >= 1 && (downB.ndof <= 0 || c2ndB < 5.0);

                const bool w0Ok = evt.channels[iVN0].valid && std::isfinite(dt0) && raw[iVN0].width > 1.5 && raw[iVN0].width < 19.5;
                const bool w1Ok = evt.channels[iVN1].valid && std::isfinite(dt1) && raw[iVN1].width > 1.5 && raw[iVN1].width < 19.5;
                const bool w0uOk = evt.channels[iVN0].valid && std::isfinite(u0) && raw[iVN0].width > 1.5 && raw[iVN0].width < 19.5;
                const bool w1uOk = evt.channels[iVN1].valid && std::isfinite(u1) && raw[iVN1].width > 1.5 && raw[iVN1].width < 19.5;

                // Defensive blinding assertion inside REG_KIN_SR for collision Data
                if (region == REG_KIN_SR && !isMC) {
                    const bool bAct0 = TimingBlinding::isVetoNuZoneBActive(static_cast<float>(raw[iVN0].rawCharge), aux.vetoNu0ReducedCharge);
                    const bool bAct1 = TimingBlinding::isVetoNuZoneBActive(static_cast<float>(raw[iVN1].rawCharge), aux.vetoNu1ReducedCharge);
                    if ((bAct0 && (!evt.channels[iVN0].valid || !down.valid || !std::isfinite(dt0) || dt0 > 1.5)) ||
                        (bAct1 && (!evt.channels[iVN1].valid || !down.valid || !std::isfinite(dt1) || dt1 > 1.5))) {
                        throw std::logic_error("TimingBlinding violation in T4 REG_KIN_SR!");
                    }
                }

                const std::string per = isCosmic
                    ? std::string("2024_cos")
                    : (isMC ? TimingCalibrator::targetDataPeriodForMC(run, static_cast<int64_t>(eventID))
                            : TimingCalibrator::periodForDataRun(run));
                auto& ph = slotPers[slot][per];
                if (!ph.initialized) ph.init(per);

                const bool v20St512 = (aux.v20Status >= 0) && ((aux.v20Status & 512) != 0);

                if (region == REG_KIN_SR) {
                    if (zoneARed) ++rs.nSrZoneARed30;
                    if (zoneARaw) ++rs.nSrZoneARaw40;

                    const bool q0Mip = raw[iVN0].present && raw[iVN0].rawCharge >= 30.0;
                    const bool q1Mip = raw[iVN1].present && raw[iVN1].rawCharge >= 30.0;
                    const bool promptDt1p0 = downOk && w0Ok && w1Ok && q0Mip && q1Mip && std::abs(dt0) < 1.0 && std::abs(dt1) < 1.0;
                    const bool promptDt1p5 = downOk && w0Ok && w1Ok && q0Mip && q1Mip && std::abs(dt0) <= 1.5 && std::abs(dt1) <= 1.5;
                    const bool promptU1p0 = downAOk && downBOk && w0uOk && w1uOk && q0Mip && q1Mip && std::abs(u0) < 1.0 && std::abs(u1) < 1.0;
                    const bool promptU1p5 = downAOk && downBOk && w0uOk && w1uOk && q0Mip && q1Mip && std::abs(u0) <= 1.5 && std::abs(u1) <= 1.5;

                    if (promptDt1p0) {
                        ++rs.nSrPrompt2HitDt1p0;
                        rs.covSrDt1p0.fill(dt0, dt1);
                        if (v20St512) rs.covSrDt1p0St512.fill(dt0, dt1);
                        ph.hSrRvn2Hit.fill(rVN);
                        ph.hSrQ0Prompt.fill(raw[iVN0].rawCharge);
                        ph.hSrQ1Prompt.fill(raw[iVN1].rawCharge);
                        if (evt.channels[iT23].valid) ph.hDownT1Sat.fill(evt.channels[iT23].t1Ns);
                        else if (evt.channels[iV20].valid) ph.hDownT1Sat.fill(evt.channels[iV20].t1Ns);
                    }
                    if (promptDt1p5) {
                        ++rs.nSrPrompt2HitDt1p5;
                        rs.covSrDt1p5.fill(dt0, dt1);
                    }
                    if (promptU1p0) {
                        ++rs.nSrPrompt2HitU1p0;
                        rs.covSrU1p0.fill(u0, u1);
                        if (v20St512) rs.covSrU1p0St512.fill(u0, u1);
                    }
                    if (promptU1p5) {
                        ++rs.nSrPrompt2HitU1p5;
                        rs.covSrU1p5.fill(u0, u1);
                    }

                    // 1-hit prompt counts (missed-layer + opposite prompt active layer)
                    if (!za0Red && za1Red && downOk && w0Ok && std::abs(dt0) <= 1.0) {
                        ++rs.nSrPrompt1Hit0Red30;
                        ph.hSrRvn1Hit0.fill(rVN);
                    }
                    if (za0Red && !za1Red && downOk && w1Ok && std::abs(dt1) <= 1.0) {
                        ++rs.nSrPrompt1Hit1Red30;
                        ph.hSrRvn1Hit1.fill(rVN);
                    }
                    if (!za0Raw && za1Raw && downOk && w0Ok && std::abs(dt0) <= 1.0) {
                        ++rs.nSrPrompt1Hit0Raw40;
                        ph.hSrRvn1Hit0Raw40.fill(rVN);
                    }
                    if (za0Raw && !za1Raw && downOk && w1Ok && std::abs(dt1) <= 1.0) {
                        ++rs.nSrPrompt1Hit1Raw40;
                        ph.hSrRvn1Hit1Raw40.fill(rVN);
                    }

                    if (downOk && w0Ok && q0Mip && (isMC || dt0 <= 1.5)) ph.hSrDt0Prompt.fill(dt0);
                    if (downOk && w1Ok && q1Mip && (isMC || dt1 <= 1.5)) ph.hSrDt1Prompt.fill(dt1);
                    if (downAOk && w0uOk && q0Mip && (isMC || dt0 <= 1.5)) ph.hSrU0Prompt.fill(u0);
                    if (downBOk && w1uOk && q1Mip && (isMC || dt1 <= 1.5)) ph.hSrU1Prompt.fill(u1);
                } else if (region == REG_CR_GEOM_OUTER || region == REG_CR_GEOM_HITHETA) {
                    ++rs.nGeomAll;
                    if (zoneARed) ++rs.nGeomZoneARed30;
                    if (zoneARaw) ++rs.nGeomZoneARaw40;
                    const bool q0Mip = raw[iVN0].present && raw[iVN0].rawCharge >= 30.0;
                    const bool q1Mip = raw[iVN1].present && raw[iVN1].rawCharge >= 30.0;
                    if (downOk && w0Ok && q0Mip) ph.hGeomDt0.fill(dt0);
                    if (downOk && w1Ok && q1Mip) ph.hGeomDt1.fill(dt1);
                    if (downAOk && w0uOk && q0Mip) ph.hGeomU0.fill(u0);
                    if (downBOk && w1uOk && q1Mip) ph.hGeomU1.fill(u1);
                    if (downOk && w0Ok && raw[iVN0].rawCharge > 200.0) ph.hGeomDt0HiQ.fill(dt0);
                    if (downOk && w1Ok && raw[iVN1].rawCharge > 200.0) ph.hGeomDt1HiQ.fill(dt1);
                    if (downOk && w0Ok && q0Mip && raw[iVN0].width < 12.0) ph.hGeomDt0W12.fill(dt0);
                    if (downOk && w1Ok && q1Mip && raw[iVN1].width < 12.0) ph.hGeomDt1W12.fill(dt1);
                    if (downOk && evt.channels[iVN0].valid && std::isfinite(dt0) && q0Mip) {
                        if (std::abs(dt0) <= 1.0) ph.hGeomWidthPrompt.fill(raw[iVN0].width);
                        else if (dt0 > 1.5) ph.hGeomWidthPosTail.fill(raw[iVN0].width);
                    }
                    if (downOk && evt.channels[iVN1].valid && std::isfinite(dt1) && q1Mip) {
                        if (std::abs(dt1) <= 1.0) ph.hGeomWidthPrompt.fill(raw[iVN1].width);
                        else if (dt1 > 1.5) ph.hGeomWidthPosTail.fill(raw[iVN1].width);
                    }

                    if (downOk && w0Ok && w1Ok && q0Mip && q1Mip && std::abs(dt0) < 1.0 && std::abs(dt1) < 1.0) {
                        ++rs.nGeomPrompt2HitDt1p0;
                        rs.covGeomDt1p0.fill(dt0, dt1);
                        ph.hGeomRvn2Hit.fill(rVN);
                        ph.hGeomQ0Prompt.fill(raw[iVN0].rawCharge);
                        ph.hGeomQ1Prompt.fill(raw[iVN1].rawCharge);
                    }
                    if (downOk && w0Ok && w1Ok && q0Mip && q1Mip && std::abs(dt0) <= 1.5 && std::abs(dt1) <= 1.5) {
                        rs.covGeomDt1p5.fill(dt0, dt1);
                    }
                    if (downAOk && downBOk && w0uOk && w1uOk && q0Mip && q1Mip && std::abs(u0) < 1.0 && std::abs(u1) < 1.0) {
                        ++rs.nGeomPrompt2HitU1p0;
                        rs.covGeomU1p0.fill(u0, u1);
                    }
                    if (downAOk && downBOk && w0uOk && w1uOk && q0Mip && q1Mip && std::abs(u0) <= 1.5 && std::abs(u1) <= 1.5) {
                        rs.covGeomU1p5.fill(u0, u1);
                    }

                    if (!za0Red && za1Red && downOk && w0Ok && std::abs(dt0) <= 1.0) {
                        ++rs.nGeomPrompt1Hit0Red30;
                        ph.hGeomRvn1Hit0.fill(rVN);
                    }
                    if (za0Red && !za1Red && downOk && w1Ok && std::abs(dt1) <= 1.0) {
                        ++rs.nGeomPrompt1Hit1Red30;
                        ph.hGeomRvn1Hit1.fill(rVN);
                    }
                    if (!za0Raw && za1Raw && downOk && w0Ok && std::abs(dt0) <= 1.0) ++rs.nGeomPrompt1Hit0Raw40;
                    if (za0Raw && !za1Raw && downOk && w1Ok && std::abs(dt1) <= 1.0) ++rs.nGeomPrompt1Hit1Raw40;
                } else if (region == REG_CR_EDGE_VN) {
                    ++rs.nEdgeVnAll;
                    if (zoneARed) ++rs.nEdgeVnZoneARed30;
                    else ++rs.nEdgeVnZoneBRed30;
                }

                // Decide whether to persist compact POD record into t4_tail_events (strictly lean: no prompt 2-hit bulk!)
                const double sig0 = (down.valid && evt.channels[iVN0].valid)
                    ? std::hypot(evt.channels[iVN0].sigmaCalNs, down.sigmaT0Ns) : kNaN;
                const double sig1 = (down.valid && evt.channels[iVN1].valid)
                    ? std::hypot(evt.channels[iVN1].sigmaCalNs, down.sigmaT0Ns) : kNaN;
                const double sigA0 = (downA.valid && evt.channels[iVN0].valid)
                    ? std::hypot(evt.channels[iVN0].sigmaCalNs, downA.sigmaT0Ns) : kNaN;
                const double sigB1 = (downB.valid && evt.channels[iVN1].valid)
                    ? std::hypot(evt.channels[iVN1].sigmaCalNs, downB.sigmaT0Ns) : kNaN;
                const double pull0Val = (std::isfinite(sig0) && sig0 > 0.0) ? (dt0 / sig0) : kNaN;
                const double pull1Val = (std::isfinite(sig1) && sig1 > 0.0) ? (dt1 / sig1) : kNaN;
                const double zu0Val = (std::isfinite(sigA0) && sigA0 > 0.0) ? (u0 / sigA0) : kNaN;
                const double zu1Val = (std::isfinite(sigB1) && sigB1 > 0.0) ? (u1 / sigB1) : kNaN;

                const bool oneHitAny = (za0Red != za1Red) || (za0Raw != za1Raw);
                const bool hasTail =
                    (evt.channels[iVN0].valid && (std::abs(dt0) > 1.45 || std::abs(u0) > 1.45 || std::abs(pull0Val) > 2.45 || std::abs(zu0Val) > 2.45)) ||
                    (evt.channels[iVN1].valid && (std::abs(dt1) > 1.45 || std::abs(u1) > 1.45 || std::abs(pull1Val) > 2.45 || std::abs(zu1Val) > 2.45));
                const double pSub = (region == REG_KIN_SR) ? 0.002 : 0.01;
                const bool isPromptSub = (!isMC && region <= REG_CR_GEOM_HITHETA)
                    ? (deterministicUniform01(run, eventID, 0x5434cafe1234abcdULL) < pSub)
                    : false;

                bool keepRec = false;
                if (isCosmic || region >= REG_CR_EDGE_VN || isGenie) {
                    keepRec = true;
                } else if (isMC) {
                    // FLUKA MC: keep all REG_KIN_SR, plus all tails / 1-hit / 5% prompt of CR-Geom
                    keepRec = (region == REG_KIN_SR) || oneHitAny || hasTail ||
                              (deterministicUniform01(run, eventID, 0x9988776655443322ULL) < 0.05);
                } else {
                    keepRec = oneHitAny || hasTail || isPromptSub;
                }

                if (!keepRec) return;

                const auto back = TimingCalibrator::evaluateBackwardHypothesis(evt, down, !za0Red, !za1Red);

                uint16_t fl = 0;
                if (grp.sig.hasReducedCharge) fl |= kFlagHasRedQ;
                if (passPhysTrig) fl |= kFlagPassPhysTrig;
                if (downOk) fl |= kFlagDownOk;
                if (downAOk) fl |= kFlagDownAValid;
                if (downBOk) fl |= kFlagDownBValid;
                if (downA.valid && downA.nUsed >= 2) fl |= kFlagDownAGE2;
                if (downB.valid && downB.nUsed >= 2) fl |= kFlagDownBGE2;
                if (evt.channels[iVN0].valid) fl |= kFlagVn0Valid;
                if (evt.channels[iVN1].valid) fl |= kFlagVn1Valid;
                if (v20St512) fl |= kFlagV20St512;
                if (isPromptSub) fl |= kFlagPromptSub;
                if (passLeadTrk) fl |= kFlagPassLeadTrk;

                T4TailRecord rec;
                rec.run = run;
                rec.eventID = static_cast<int64_t>(eventID);
                rec.region = region;
                rec.genie_class = aux.genieClass;
                rec.flags = fl;
                rec.pz0_gev = static_cast<float>(tk.leadPz0GeV);
                rec.r_max = static_cast<float>(rMax);
                rec.r_ift = static_cast<float>(rIFT);
                rec.r_vn = static_cast<float>(rVN);
                rec.theta_mrad = static_cast<float>(theta);
                rec.q0_raw = static_cast<float>(raw[iVN0].rawCharge);
                rec.q1_raw = static_cast<float>(raw[iVN1].rawCharge);
                rec.q0_red = aux.vetoNu0ReducedCharge;
                rec.q1_red = aux.vetoNu1ReducedCharge;
                rec.w0 = static_cast<float>(raw[iVN0].width);
                rec.w1 = static_cast<float>(raw[iVN1].width);
                rec.dt0 = static_cast<float>(dt0);
                rec.dt1 = static_cast<float>(dt1);
                rec.pull0 = static_cast<float>(pull0Val);
                rec.pull1 = static_cast<float>(pull1Val);
                rec.u0 = static_cast<float>(u0);
                rec.u1 = static_cast<float>(u1);
                rec.zu0 = static_cast<float>(zu0Val);
                rec.zu1 = static_cast<float>(zu1Val);
                rec.t0_down = down.valid ? static_cast<float>(down.t0Ns) : static_cast<float>(kNaN);
                rec.sig_t0_down = down.valid ? static_cast<float>(down.sigmaT0Ns) : static_cast<float>(kNaN);
                rec.chi2_ndof_down = static_cast<float>(c2nd);
                rec.dchi2_back = back.valid ? static_cast<float>(back.deltaChi2Back) : static_cast<float>(kNaN);
                rec.vgm_max_q = aux.vetoGmMaxCharge;
                slotRecs[slot].push_back(rec);
            },
            {"run", "eventID", "distanceToCollidingBCID", "distanceToInboundB1",
             "distanceToUnpairedB1", "distanceToUnpairedB2", "inputBits", "longTracks",
             "_grl_good", "_tk", "_raw", "_aux"});

        totalLoops += df.GetNRuns();
        for (unsigned int s = 0; s < nSlots; ++s) {
            for (const auto& [r, sd] : slotRuns[s]) mergedRuns[r].mergeFrom(sd);
            for (const auto& [p, pd] : slotPers[s]) mergedPers[p].mergeFrom(pd);
            mergedRecs.insert(mergedRecs.end(), slotRecs[s].begin(), slotRecs[s].end());
        }
    }

    const auto parentDir = std::filesystem::path(outputPath).parent_path();
    if (!parentDir.empty()) std::filesystem::create_directories(parentDir);

    writeOutput(outputPath, mergedRuns, mergedPers, mergedRecs);

    const double wallS = std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStart).count();
    uint64_t sumTotal = 0, sumBlinded = 0, sumGeom = 0, sumEdge = 0;
    for (const auto& [r, d] : mergedRuns) {
        sumTotal += d.nTotal;
        sumBlinded += d.nBlinded;
        sumGeom += d.nGeomAll;
        sumEdge += d.nEdgeVnAll;
    }
    INFO("[STAT] threads=", threads, " slots=", nSlots, " event_loops=", totalLoops,
         " wall_s=", wallS, " rate_Mevt_s=", (wallS > 0.0 ? sumTotal * 1e-6 / wallS : 0.0),
         " n_total=", sumTotal, " n_blinded=", sumBlinded,
         " n_geom=", sumGeom, " n_edge_vn=", sumEdge,
         " n_tail_recs=", mergedRecs.size(), " output=", outputPath);
    return 0;
}
