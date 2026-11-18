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

using TimingCalib::TimingChannel;
using TimingCalib::TimingCalibrator;
using TimingCalib::kNumChannels;
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
        if (pos == std::string::npos) continue;
        if (line[pos] == '#') continue;
        const auto end = line.find_last_not_of(" \t\r\n");
        out.push_back(line.substr(pos, end - pos + 1));
    }
    return out;
}

struct SchemaSignature {
    bool hasVetoSt{false};
    bool hasTimeNotLocaltime{false};
    bool hasNativeVeto11{false};
    bool hasPreshower23{false};
    bool hasMuon{false};
    bool hasBcidTrig{false};
    bool hasReducedCharge{false};
    std::string eventTimeType{"UInt_t"};
    std::string nLayersType{"ROOT::VecOps::RVec<unsigned int>"};

    std::string key() const {
        return std::string(hasVetoSt ? "1" : "0") +
               (hasTimeNotLocaltime ? "1" : "0") +
               (hasNativeVeto11 ? "1" : "0") +
               (hasPreshower23 ? "1" : "0") +
               (hasMuon ? "1" : "0") +
               (hasBcidTrig ? "1" : "0") +
               (hasReducedCharge ? "1" : "0") + "|" +
               eventTimeType + "|" + nLayersType;
    }
};

SchemaSignature probeFileSchema(const std::string& fpath) {
    std::unique_ptr<TFile> tf(TFile::Open(fpath.c_str(), "READ"));
    if (!tf || tf->IsZombie()) {
        throw std::runtime_error("Cannot open ROOT file: " + fpath);
    }
    auto* tree = tf->Get<TTree>("nt");
    if (!tree) {
        throw std::runtime_error("Missing 'nt' tree in file: " + fpath);
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

    ROOT::RDataFrame probeDf(*tree);
    sig.eventTimeType = br.count("eventTime") ? probeDf.GetColumnType("eventTime") : "UInt_t";
    sig.nLayersType = probeDf.GetColumnType("Track_nLayers");
    return sig;
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

struct TimingPmtsRaw {
    std::array<float, 4> loc{};
    std::array<float, 4> qRaw{};
    std::array<float, 4> width{};
    std::array<int32_t, 4> status{};
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

struct McScanRunData {
    bool initialized{false};
    int run{0};
    uint64_t nTotal{0};
    uint64_t nLt1{0};
    uint64_t nCleanMuon{0};
    uint64_t nKinSr{0};
    bool hasVeto11{false};
    bool hasPreshower23{false};
    bool hasMuon{false};
    bool hasReducedCharge{false};

    std::array<FastHist1D, kNumChannels> hLoc;
    std::array<FastHist1D, 4> hTimingPmtLoc;

    void init(int r) {
        if (initialized) return;
        initialized = true;
        run = r;
        for (int c = 0; c < kNumChannels; ++c) {
            hLoc[c].init(9000, 770.0, 860.0);
        }
        for (int p = 0; p < 4; ++p) {
            hTimingPmtLoc[p].init(9000, 770.0, 860.0);
        }
    }

    void mergeFrom(const McScanRunData& other) {
        if (!initialized) init(other.run);
        nTotal += other.nTotal;
        nLt1 += other.nLt1;
        nCleanMuon += other.nCleanMuon;
        nKinSr += other.nKinSr;
        hasVeto11 = hasVeto11 || other.hasVeto11;
        hasPreshower23 = hasPreshower23 || other.hasPreshower23;
        hasMuon = hasMuon || other.hasMuon;
        hasReducedCharge = hasReducedCharge || other.hasReducedCharge;
        for (int c = 0; c < kNumChannels; ++c) hLoc[c].addFrom(other.hLoc[c]);
        for (int p = 0; p < 4; ++p) hTimingPmtLoc[p].addFrom(other.hTimingPmtLoc[p]);
    }
};

struct McMuonRecord {
    int32_t run{0};
    int64_t eventID{0};
    uint8_t is_kin_sr{0};
    float pz0_lead_gev{0.0f};
    float r_max_mm{0.0f};
    float r_vn_mm{0.0f};
    float theta_mrad{0.0f};
    float trk_x[8]{};
    float trk_y[8]{};
    float loc[kNumChannels]{};
    float q_raw[kNumChannels]{};
    float width[kNumChannels]{};
    uint8_t good_st[kNumChannels]{};
    float tpmt_loc[4]{};
    float tpmt_q[4]{};
    uint8_t tpmt_good[4]{};
};

struct ClosureSummaryStats {
    bool initialized{false};
    int run{0};
    bool isMC{false};
    uint64_t nTotal{0};
    uint64_t nGrlFail{0};
    uint64_t nNonColliding{0};
    uint64_t nBlinded{0};
    uint64_t nClean1Trk{0};
    uint64_t nKinSr{0};
    uint64_t nKinSrValidT0Down{0};
    uint64_t nKinSrValidVeto2Only{0};

    void init(int r, bool mc) {
        if (initialized) return;
        initialized = true;
        run = r;
        isMC = mc;
    }

    void mergeFrom(const ClosureSummaryStats& o) {
        if (!initialized) init(o.run, o.isMC);
        nTotal += o.nTotal;
        nGrlFail += o.nGrlFail;
        nNonColliding += o.nNonColliding;
        nBlinded += o.nBlinded;
        nClean1Trk += o.nClean1Trk;
        nKinSr += o.nKinSr;
        nKinSrValidT0Down += o.nKinSrValidT0Down;
        nKinSrValidVeto2Only += o.nKinSrValidVeto2Only;
    }
};

struct ClosurePeriodHists {
    bool initialized{false};
    std::string period;
    FastHist1D hT0DownAll;
    FastHist1D hT0DownPrompt;
    FastHist1D hSigmaT0Down;
    FastHist1D hNDownUsed;
    FastHist1D hChi2NdofAll;
    FastHist1D hChi2NdofPrompt;
    FastHist1D hChi2NdofGeomSb;
    FastHist1D hChi2NdofShowerSb;
    FastHist1D hVn0DtPrompt;
    FastHist1D hVn1DtPrompt;
    FastHist1D hVn0DtGeom;
    FastHist1D hVn1DtGeom;
    FastHist1D hVn0PullPrompt;
    FastHist1D hVn1PullPrompt;
    FastHist1D hVn0PullGeom;
    FastHist1D hVn1PullGeom;
    FastHist1D hBeta;
    std::array<FastHist1D, kNumChannels> hLooRes;
    std::array<FastHist1D, kNumChannels> hLooPull;

    void init(const std::string& p) {
        if (initialized) return;
        initialized = true;
        period = p;
        hT0DownAll.init(400, -4.0, 4.0);
        hT0DownPrompt.init(400, -4.0, 4.0);
        hSigmaT0Down.init(200, 0.0, 1.0);
        hNDownUsed.init(12, -0.5, 11.5);
        hChi2NdofAll.init(500, 0.0, 10.0);
        hChi2NdofPrompt.init(500, 0.0, 10.0);
        hChi2NdofGeomSb.init(500, 0.0, 10.0);
        hChi2NdofShowerSb.init(500, 0.0, 10.0);
        hVn0DtPrompt.init(400, -4.0, 4.0);
        hVn1DtPrompt.init(400, -4.0, 4.0);
        hVn0DtGeom.init(400, -4.0, 4.0);
        hVn1DtGeom.init(400, -4.0, 4.0);
        hVn0PullPrompt.init(240, -6.0, 6.0);
        hVn1PullPrompt.init(240, -6.0, 6.0);
        hVn0PullGeom.init(240, -6.0, 6.0);
        hVn1PullGeom.init(240, -6.0, 6.0);
        hBeta.init(200, 0.9, 1.1);
        for (int c = 0; c < kNumChannels; ++c) {
            hLooRes[c].init(400, -4.0, 4.0);
            hLooPull[c].init(240, -6.0, 6.0);
        }
    }

    void mergeFrom(const ClosurePeriodHists& o) {
        if (!initialized) init(o.period);
        hT0DownAll.addFrom(o.hT0DownAll);
        hT0DownPrompt.addFrom(o.hT0DownPrompt);
        hSigmaT0Down.addFrom(o.hSigmaT0Down);
        hNDownUsed.addFrom(o.hNDownUsed);
        hChi2NdofAll.addFrom(o.hChi2NdofAll);
        hChi2NdofPrompt.addFrom(o.hChi2NdofPrompt);
        hChi2NdofGeomSb.addFrom(o.hChi2NdofGeomSb);
        hChi2NdofShowerSb.addFrom(o.hChi2NdofShowerSb);
        hVn0DtPrompt.addFrom(o.hVn0DtPrompt);
        hVn1DtPrompt.addFrom(o.hVn1DtPrompt);
        hVn0DtGeom.addFrom(o.hVn0DtGeom);
        hVn1DtGeom.addFrom(o.hVn1DtGeom);
        hVn0PullPrompt.addFrom(o.hVn0PullPrompt);
        hVn1PullPrompt.addFrom(o.hVn1PullPrompt);
        hVn0PullGeom.addFrom(o.hVn0PullGeom);
        hVn1PullGeom.addFrom(o.hVn1PullGeom);
        hBeta.addFrom(o.hBeta);
        for (int c = 0; c < kNumChannels; ++c) {
            hLooRes[c].addFrom(o.hLooRes[c]);
            hLooPull[c].addFrom(o.hLooPull[c]);
        }
    }
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

TimingBlinding::EventKinematicsAndVeto buildBlindStruct(
    bool isMC,
    int distBCID,
    int longTracks,
    const ScannerTrackData& tk,
    const RawInputArray& raw,
    const ScannerBlindCharges& chg) {
    TimingBlinding::EventKinematicsAndVeto ev;
    ev.isMC = isMC;
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
    return ev;
}

ROOT::RDF::RNode prepareNode(
    TChain& chain,
    const SchemaSignature& sig,
    const std::shared_ptr<const GRLUtils::GRLTimes>& grl,
    bool isMC) {

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
    ensureFloat("VetoNu0_reduced_charge", -1.0f);
    ensureFloat("VetoNu1_reduced_charge", -1.0f);
    ensureRVecD("Track_X_atMuon1");
    ensureRVecD("Track_Y_atMuon1");
    ensureRVecD("Track_X_atMuon2");
    ensureRVecD("Track_Y_atMuon2");

    if (sig.eventTimeType == "Int_t" || sig.eventTimeType == "int") {
        df = attachGrlGoodColumn<Int_t>(df, grl, isMC);
    } else if (sig.eventTimeType == "UInt_t" || sig.eventTimeType == "unsigned int") {
        df = attachGrlGoodColumn<UInt_t>(df, grl, isMC);
    } else if (sig.eventTimeType == "Long64_t" || sig.eventTimeType == "long long") {
        df = attachGrlGoodColumn<Long64_t>(df, grl, isMC);
    } else {
        df = attachGrlGoodColumn<ULong64_t>(df, grl, isMC);
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

    df = df.Define("_tpmts",
        [](Int_t t0_st, Float_t t0_l, Float_t t0_q, Float_t t0_w,
           Int_t t1_st, Float_t t1_l, Float_t t1_q, Float_t t1_w,
           Int_t t2_st, Float_t t2_l, Float_t t2_q, Float_t t2_w,
           Int_t t3_st, Float_t t3_l, Float_t t3_q, Float_t t3_w) -> TimingPmtsRaw {
            TimingPmtsRaw r;
            r.loc = {{t0_l, t1_l, t2_l, t3_l}};
            r.qRaw = {{t0_q, t1_q, t2_q, t3_q}};
            r.width = {{t0_w, t1_w, t2_w, t3_w}};
            r.status = {{t0_st, t1_st, t2_st, t3_st}};
            return r;
        },
        {"Timing0_status", "Timing0_localtime", "Timing0_raw_charge", "Timing0_width",
         "Timing1_status", "Timing1_localtime", "Timing1_raw_charge", "Timing1_width",
         "Timing2_status", "Timing2_localtime", "Timing2_raw_charge", "Timing2_width",
         "Timing3_status", "Timing3_localtime", "Timing3_raw_charge", "Timing3_width"});

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

void writeMcScanOutput(const std::string& outputPath,
                       const std::map<int, McScanRunData>& byRun,
                       std::vector<McMuonRecord>& records) {
    std::sort(records.begin(), records.end(), [](const McMuonRecord& a, const McMuonRecord& b) {
        if (a.run != b.run) return a.run < b.run;
        return a.eventID < b.eventID;
    });

    std::unique_ptr<TFile> outFile(TFile::Open(outputPath.c_str(), "RECREATE"));
    if (!outFile || outFile->IsZombie()) {
        throw std::runtime_error("Cannot create mc-scan output: " + outputPath);
    }

    TTree* sum = new TTree("mc_summary", "MC timing scan per-run summary");
    int run = 0;
    uint64_t nTotal = 0, nLt1 = 0, nCleanMuon = 0, nKinSr = 0;
    bool hasVeto11 = false, hasPreshower23 = false, hasMuon = false, hasRedQ = false;
    sum->Branch("run", &run);
    sum->Branch("n_total", &nTotal);
    sum->Branch("n_lt1", &nLt1);
    sum->Branch("n_clean_muon", &nCleanMuon);
    sum->Branch("n_kin_sr", &nKinSr);
    sum->Branch("has_veto11", &hasVeto11);
    sum->Branch("has_preshower23", &hasPreshower23);
    sum->Branch("has_muon", &hasMuon);
    sum->Branch("has_reduced_charge", &hasRedQ);

    const auto& meta = TimingCalibrator::channelMetadata();
    for (const auto& [r, d] : byRun) {
        run = r;
        nTotal = d.nTotal;
        nLt1 = d.nLt1;
        nCleanMuon = d.nCleanMuon;
        nKinSr = d.nKinSr;
        hasVeto11 = d.hasVeto11;
        hasPreshower23 = d.hasPreshower23;
        hasMuon = d.hasMuon;
        hasRedQ = d.hasReducedCharge;
        sum->Fill();

        TDirectory* rdir = outFile->mkdir(("run_" + std::to_string(r)).c_str());
        rdir->cd();
        for (int c = 0; c < kNumChannels; ++c) {
            TH1D h = d.hLoc[c].toTH1D(std::string("h_loc_") + meta[c].name, std::string(meta[c].name) + " localtime;ns;Events");
            if (h.GetEntries() > 0) h.Write();
        }
        for (int p = 0; p < 4; ++p) {
            TH1D h = d.hTimingPmtLoc[p].toTH1D("h_loc_Timing" + std::to_string(p), "Timing" + std::to_string(p) + " localtime;ns;Events");
            if (h.GetEntries() > 0) h.Write();
        }
        outFile->cd();
    }
    sum->Write();

    TTree* ev = new TTree("mc_muons", "Clean MC 1-track muons for slope/resolution calibration");
    McMuonRecord rec;
    ev->Branch("run", &rec.run);
    ev->Branch("eventID", &rec.eventID);
    ev->Branch("is_kin_sr", &rec.is_kin_sr);
    ev->Branch("pz0_lead_gev", &rec.pz0_lead_gev);
    ev->Branch("r_max_mm", &rec.r_max_mm);
    ev->Branch("r_vn_mm", &rec.r_vn_mm);
    ev->Branch("theta_mrad", &rec.theta_mrad);
    ev->Branch("trk_x", rec.trk_x, "trk_x[8]/F");
    ev->Branch("trk_y", rec.trk_y, "trk_y[8]/F");
    ev->Branch("loc", rec.loc, ("loc[" + std::to_string(kNumChannels) + "]/F").c_str());
    ev->Branch("q_raw", rec.q_raw, ("q_raw[" + std::to_string(kNumChannels) + "]/F").c_str());
    ev->Branch("width", rec.width, ("width[" + std::to_string(kNumChannels) + "]/F").c_str());
    ev->Branch("good_st", rec.good_st, ("good_st[" + std::to_string(kNumChannels) + "]/b").c_str());
    ev->Branch("tpmt_loc", rec.tpmt_loc, "tpmt_loc[4]/F");
    ev->Branch("tpmt_q", rec.tpmt_q, "tpmt_q[4]/F");
    ev->Branch("tpmt_good", rec.tpmt_good, "tpmt_good[4]/b");
    for (const auto& item : records) {
        rec = item;
        ev->Fill();
    }
    ev->Write();
    outFile->Close();
}

void writeClosureOutput(const std::string& outputPath,
                        const std::map<int, ClosureSummaryStats>& runStats,
                        const std::map<std::string, ClosurePeriodHists>& perHists) {
    std::unique_ptr<TFile> outFile(TFile::Open(outputPath.c_str(), "RECREATE"));
    if (!outFile || outFile->IsZombie()) {
        throw std::runtime_error("Cannot create closure-eval output: " + outputPath);
    }

    TTree* sum = new TTree("closure_summary", "Data/MC closure scan summary");
    int run = 0;
    bool isMC = false;
    uint64_t nTotal = 0, nGrlFail = 0, nNonColl = 0, nBlinded = 0, nClean1Trk = 0;
    uint64_t nKinSr = 0, nKinSrValidT0Down = 0, nKinSrValidVeto2Only = 0;
    sum->Branch("run", &run);
    sum->Branch("is_mc", &isMC);
    sum->Branch("n_total", &nTotal);
    sum->Branch("n_grl_fail", &nGrlFail);
    sum->Branch("n_non_colliding", &nNonColl);
    sum->Branch("n_blinded", &nBlinded);
    sum->Branch("n_clean_1trk", &nClean1Trk);
    sum->Branch("n_kin_sr", &nKinSr);
    sum->Branch("n_kin_sr_valid_t0down", &nKinSrValidT0Down);
    sum->Branch("n_kin_sr_valid_veto2only", &nKinSrValidVeto2Only);

    for (const auto& [r, s] : runStats) {
        run = r;
        isMC = s.isMC;
        nTotal = s.nTotal;
        nGrlFail = s.nGrlFail;
        nNonColl = s.nNonColliding;
        nBlinded = s.nBlinded;
        nClean1Trk = s.nClean1Trk;
        nKinSr = s.nKinSr;
        nKinSrValidT0Down = s.nKinSrValidT0Down;
        nKinSrValidVeto2Only = s.nKinSrValidVeto2Only;
        sum->Fill();
    }
    sum->Write();

    const auto& meta = TimingCalibrator::channelMetadata();
    for (const auto& [per, h] : perHists) {
        TDirectory* pdir = outFile->mkdir(("period_" + per).c_str());
        pdir->cd();
        h.hT0DownAll.toTH1D("h_t0_down_all", "t0_down (all);ns;Events").Write();
        h.hT0DownPrompt.toTH1D("h_t0_down_prompt", "t0_down (CR-Prompt);ns;Events").Write();
        h.hSigmaT0Down.toTH1D("h_sigma_t0_down", "sigma(t0_down);ns;Events").Write();
        h.hNDownUsed.toTH1D("h_n_down_used", "n_down_used;N;Events").Write();
        h.hChi2NdofAll.toTH1D("h_chi2_ndof_all", "chi2_down/ndof (all);chi2/ndof;Events").Write();
        h.hChi2NdofPrompt.toTH1D("h_chi2_ndof_prompt", "chi2_down/ndof (prompt);chi2/ndof;Events").Write();
        h.hChi2NdofGeomSb.toTH1D("h_chi2_ndof_geom_sb", "chi2_down/ndof (CR-Geom);chi2/ndof;Events").Write();
        h.hChi2NdofShowerSb.toTH1D("h_chi2_ndof_shower_sb", "chi2_down/ndof (shower SB);chi2/ndof;Events").Write();
        h.hVn0DtPrompt.toTH1D("h_vn0_dt_prompt", "VetoNu0 dt (sym prompt);ns;Events").Write();
        h.hVn1DtPrompt.toTH1D("h_vn1_dt_prompt", "VetoNu1 dt (sym prompt);ns;Events").Write();
        h.hVn0DtGeom.toTH1D("h_vn0_dt_geom", "VetoNu0 dt (CR-Geom unblinded);ns;Events").Write();
        h.hVn1DtGeom.toTH1D("h_vn1_dt_geom", "VetoNu1 dt (CR-Geom unblinded);ns;Events").Write();
        h.hVn0PullPrompt.toTH1D("h_vn0_pull_prompt", "VetoNu0 pull (sym prompt);pull;Events").Write();
        h.hVn1PullPrompt.toTH1D("h_vn1_pull_prompt", "VetoNu1 pull (sym prompt);pull;Events").Write();
        h.hVn0PullGeom.toTH1D("h_vn0_pull_geom", "VetoNu0 pull (CR-Geom);pull;Events").Write();
        h.hVn1PullGeom.toTH1D("h_vn1_pull_geom", "VetoNu1 pull (CR-Geom);pull;Events").Write();
        h.hBeta.toTH1D("h_beta", "beta = v/c;beta;Events").Write();
        for (int c = 0; c < kNumChannels; ++c) {
            TH1D hl = h.hLooRes[c].toTH1D(std::string("h_loo_res_") + meta[c].name, std::string(meta[c].name) + " LOO residual;ns;Events");
            if (hl.GetEntries() > 0) hl.Write();
            TH1D hp = h.hLooPull[c].toTH1D(std::string("h_loo_pull_") + meta[c].name, std::string(meta[c].name) + " LOO pull;pull;Events");
            if (hp.GetEntries() > 0) hp.Write();
        }
        outFile->cd();
    }
    outFile->Close();
}

void printUsage(const char* argv0) {
    std::cerr << "Usage: " << argv0
              << " --mode <mc-scan|closure-eval> --output <out.root>"
              << " (--input-files <f1,f2,...> | --input-list <list.txt>)"
              << " [--is-mc] [--timing-calib <dir>] [--grl-config <yaml>]"
              << " [--record-prob <p>] [--threads <n>] [--max-events <n>] [--no-smear]\n";
}

} // namespace

int main(int argc, char* argv[]) {
    ROOT::EnableThreadSafety();
    TH1::AddDirectory(false);

    std::string mode;
    std::string outputPath;
    std::string inputFilesArg;
    std::string inputListArg;
    std::string calibDir;
    std::string grlConfigPath = "AnalysisZipFramework/config/grl_config_run3_full.yaml";
    bool isMC = false;
    bool applySmearing = true;
    double recordProb = 1.0;
    int threads = 1;
    Long64_t maxEvents = -1;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto needVal = [&](const std::string& flag) -> std::string {
            if (i + 1 >= argc) throw std::runtime_error("Missing value for " + flag);
            return argv[++i];
        };
        if (arg == "--mode") mode = needVal(arg);
        else if (arg == "--output" || arg == "-o") outputPath = needVal(arg);
        else if (arg == "--input-files") inputFilesArg = needVal(arg);
        else if (arg == "--input-list") inputListArg = needVal(arg);
        else if (arg == "--timing-calib") calibDir = needVal(arg);
        else if (arg == "--grl-config") grlConfigPath = needVal(arg);
        else if (arg == "--is-mc") isMC = true;
        else if (arg == "--no-smear") applySmearing = false;
        else if (arg == "--record-prob") recordProb = std::stod(needVal(arg));
        else if (arg == "--threads" || arg == "-j") threads = std::stoi(needVal(arg));
        else if (arg == "--max-events") maxEvents = std::stoll(needVal(arg));
        else {
            printUsage(argv[0]);
            return 1;
        }
    }

    if ((mode != "mc-scan" && mode != "closure-eval") || outputPath.empty() ||
        (inputFilesArg.empty() && inputListArg.empty())) {
        printUsage(argv[0]);
        return 1;
    }
    if (mode == "mc-scan") isMC = true;
    if (mode == "closure-eval" && calibDir.empty()) {
        ERROR("--mode closure-eval requires --timing-calib <dir>");
        return 1;
    }

    const auto wallStart = std::chrono::steady_clock::now();
    if (threads > 1 && maxEvents <= 0) {
        ROOT::EnableImplicitMT(static_cast<unsigned int>(threads));
    } else if (threads > 1 && maxEvents > 0) {
        threads = 1;
    }
    const unsigned int nSlots = std::max(1u, ROOT::GetThreadPoolSize());

    std::vector<std::string> files;
    if (!inputFilesArg.empty()) {
        auto s = splitCommaList(inputFilesArg);
        files.insert(files.end(), s.begin(), s.end());
    }
    if (!inputListArg.empty()) {
        auto s = readListFile(inputListArg);
        files.insert(files.end(), s.begin(), s.end());
    }
    if (files.empty()) {
        ERROR("No input files resolved.");
        return 1;
    }

    std::shared_ptr<const GRLUtils::GRLTimes> grlTimes;
    if (!isMC) {
        const auto grlCfg = ConfigUtils::readGRLConfig(grlConfigPath);
        grlTimes = std::make_shared<const GRLUtils::GRLTimes>(
            GRLUtils::readGRLTimes(GRLUtils::toTStringVector(grlCfg.grlJsons)));
    }

    std::shared_ptr<const TimingCalibrator> calib;
    if (!calibDir.empty()) {
        auto c = std::make_shared<TimingCalibrator>();
        c->loadFromDirectory(calibDir);
        calib = std::move(c);
    }

    // Group files by exact TTree schema signature
    struct Group {
        SchemaSignature sig;
        std::vector<std::string> files;
    };
    std::map<std::string, Group> groups;
    for (const auto& f : files) {
        const SchemaSignature sig = probeFileSchema(f);
        auto& g = groups[sig.key()];
        g.sig = sig;
        g.files.push_back(f);
    }

    std::map<int, McScanRunData> mergedMc;
    std::vector<McMuonRecord> mergedMcRecs;
    std::map<int, ClosureSummaryStats> mergedClosureRuns;
    std::map<std::string, ClosurePeriodHists> mergedClosurePers;
    uint64_t totalLoops = 0;

    for (const auto& [skey, grp] : groups) {
        TChain chain("nt");
        for (const auto& f : grp.files) chain.Add(f.c_str());
        INFO("MC/Closure scanner group (", skey, "): ", grp.files.size(), " files, slots=", nSlots, ", mode=", mode);

        ROOT::RDF::RNode df = prepareNode(chain, grp.sig, grlTimes, isMC);
        if (maxEvents > 0) df = df.Range(static_cast<ULong64_t>(maxEvents));

        if (mode == "mc-scan") {
            std::vector<std::unordered_map<int, McScanRunData>> slotMaps(nSlots);
            std::vector<std::vector<McMuonRecord>> slotRecs(nSlots);

            df.ForeachSlot(
                [&](unsigned int slot,
                    Int_t run,
                    Int_t eventID,
                    Int_t distBCID,
                    Int_t longTracks,
                    const ScannerTrackData& tk,
                    const RawInputArray& raw,
                    const ScannerBlindCharges& chg,
                    const TimingPmtsRaw& tpmts) {
                    auto& rd = slotMaps[slot][run];
                    if (!rd.initialized) {
                        rd.init(run);
                        rd.hasVeto11 = grp.sig.hasNativeVeto11;
                        rd.hasPreshower23 = grp.sig.hasPreshower23;
                        rd.hasMuon = grp.sig.hasMuon;
                        rd.hasReducedCharge = grp.sig.hasReducedCharge;
                    }
                    ++rd.nTotal;
                    if (longTracks == 1) ++rd.nLt1;

                    const auto blindEv = buildBlindStruct(true, distBCID, longTracks, tk, raw, chg);
                    const bool isKinSr = TimingBlinding::isKinematicSignalRegion(blindEv);
                    if (isKinSr) ++rd.nKinSr;

                    const bool isClean1Trk =
                        (longTracks == 1) &&
                        std::isfinite(tk.leadPz0GeV) && tk.leadPz0GeV > 30.0 &&
                        tk.leadNLayers >= 6 &&
                        std::isfinite(tk.leadNDoF) && tk.leadNDoF >= 9.0 &&
                        std::isfinite(tk.leadChi2NDF) && tk.leadChi2NDF < 15.0 &&
                        tk.validPos[3];
                    if (!isClean1Trk) return;
                    ++rd.nCleanMuon;

                    const auto& meta = TimingCalibrator::channelMetadata();
                    for (int c = 0; c < kNumChannels; ++c) {
                        const auto& in = raw[c];
                        if (!in.present || !in.goodStatus) continue;
                        const int pIdx = kChannelPlaneIdx[c];
                        if (!tk.validPos[pIdx] || std::abs(in.xMm) >= 120.0 || std::abs(in.yMm) >= 120.0) continue;
                        if (in.rawCharge <= meta[c].mipThresholdPC || !std::isfinite(in.localTime) || in.localTime <= 100.0) continue;
                        if (c == static_cast<int>(TimingChannel::Timing01) && in.yMm >= -5.0) continue;
                        if (c == static_cast<int>(TimingChannel::Timing23) && in.yMm <= 5.0) continue;
                        rd.hLoc[c].fill(in.localTime);
                    }
                    for (int p = 0; p < 4; ++p) {
                        if (!TimingCalibrator::isGoodWaveformStatus(tpmts.status[p])) continue;
                        if (!std::isfinite(tpmts.loc[p]) || tpmts.loc[p] <= 100.0 || tpmts.qRaw[p] <= 20.0) continue;
                        if (std::abs(tk.x[3]) >= 120.0 || std::abs(tk.y[3]) >= 120.0) continue;
                        if (p < 2 && tk.y[3] >= -5.0) continue;
                        if (p >= 2 && tk.y[3] <= 5.0) continue;
                        rd.hTimingPmtLoc[p].fill(tpmts.loc[p]);
                    }

                    if (recordProb < 1.0 && deterministicUniform01(run, eventID, 0x2468ace13579bdf0ULL) >= recordProb) {
                        return;
                    }

                    McMuonRecord rec;
                    rec.run = run;
                    rec.eventID = static_cast<int64_t>(eventID);
                    rec.is_kin_sr = isKinSr ? 1 : 0;
                    rec.pz0_lead_gev = static_cast<float>(tk.leadPz0GeV);
                    rec.r_max_mm = static_cast<float>(tk.leadRMax);
                    rec.r_vn_mm = tk.validPos[0] ? static_cast<float>(std::hypot(tk.x[0], tk.y[0])) : static_cast<float>(kNaN);
                    rec.theta_mrad = static_cast<float>(tk.leadThetaMrad);
                    for (int p = 0; p < 8; ++p) {
                        rec.trk_x[p] = static_cast<float>(tk.x[p]);
                        rec.trk_y[p] = static_cast<float>(tk.y[p]);
                    }
                    for (int c = 0; c < kNumChannels; ++c) {
                        rec.loc[c] = raw[c].present ? static_cast<float>(raw[c].localTime) : static_cast<float>(kNaN);
                        rec.q_raw[c] = raw[c].present ? static_cast<float>(raw[c].rawCharge) : static_cast<float>(kNaN);
                        rec.width[c] = raw[c].present ? static_cast<float>(raw[c].width) : static_cast<float>(kNaN);
                        rec.good_st[c] = (raw[c].present && raw[c].goodStatus) ? 1 : 0;
                    }
                    for (int p = 0; p < 4; ++p) {
                        rec.tpmt_loc[p] = tpmts.loc[p];
                        rec.tpmt_q[p] = tpmts.qRaw[p];
                        rec.tpmt_good[p] = TimingCalibrator::isGoodWaveformStatus(tpmts.status[p]) ? 1 : 0;
                    }
                    slotRecs[slot].push_back(rec);
                },
                {"run", "eventID", "distanceToCollidingBCID", "longTracks", "_tk", "_raw", "_chg", "_tpmts"});

            totalLoops += df.GetNRuns();
            for (unsigned int s = 0; s < nSlots; ++s) {
                for (const auto& [r, sd] : slotMaps[s]) mergedMc[r].mergeFrom(sd);
                mergedMcRecs.insert(mergedMcRecs.end(), slotRecs[s].begin(), slotRecs[s].end());
            }
        } else {
            // closure-eval
            std::vector<std::unordered_map<int, ClosureSummaryStats>> slotRuns(nSlots);
            std::vector<std::unordered_map<std::string, ClosurePeriodHists>> slotPers(nSlots);

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
                    auto& rs = slotRuns[slot][run];
                    if (!rs.initialized) rs.init(run, isMC);
                    ++rs.nTotal;
                    if (!grlGood) { ++rs.nGrlFail; return; }
                    if (!isMC && distBCID != 0) { ++rs.nNonColliding; return; }

                    const auto evt = isMC
                        ? calib->calibrateMCEvent(run, static_cast<int64_t>(eventID), raw, applySmearing, true)
                        : calib->calibrateDataEvent(run, raw, calib->hasTofMaps(), true);
                    const auto down = TimingCalibrator::fitDownstreamReference(evt);
                    const auto speed = TimingCalibrator::fitSpeedAndArrival(evt);

                    const int i0 = static_cast<int>(TimingChannel::VetoNu0);
                    const int i1 = static_cast<int>(TimingChannel::VetoNu1);
                    const double dt0 = (down.valid && evt.channels[i0].valid) ? (evt.channels[i0].tCalNs - down.t0Ns) : kNaN;
                    const double dt1 = (down.valid && evt.channels[i1].valid) ? (evt.channels[i1].tCalNs - down.t0Ns) : kNaN;

                    const auto blindEv = buildBlindStruct(isMC, distBCID, longTracks, tk, raw, chg);
                    if (TimingBlinding::isBlindedSRZoneB(
                            blindEv, true, down.valid,
                            evt.channels[i0].valid, dt0,
                            evt.channels[i1].valid, dt1)) {
                        ++rs.nBlinded;
                        return;
                    }

                    const bool isKinSr = TimingBlinding::isKinematicSignalRegion(blindEv);
                    if (isKinSr) {
                        ++rs.nKinSr;
                        if (down.valid && down.nUsed >= 2) ++rs.nKinSrValidT0Down;
                        const int iV20 = static_cast<int>(TimingChannel::Veto20);
                        const int iV21 = static_cast<int>(TimingChannel::Veto21);
                        if (evt.channels[iV20].valid || evt.channels[iV21].valid) ++rs.nKinSrValidVeto2Only;
                    }

                    const bool isClean1Trk =
                        (longTracks == 1) &&
                        std::isfinite(tk.leadPz0GeV) && tk.leadPz0GeV > 30.0 &&
                        tk.leadNLayers >= 6 &&
                        std::isfinite(tk.leadNDoF) && tk.leadNDoF >= 9.0 &&
                        std::isfinite(tk.leadChi2NDF) && tk.leadChi2NDF < 15.0 &&
                        tk.validPos[3];
                    if (!isClean1Trk) return;
                    ++rs.nClean1Trk;

                    const std::string per = isMC
                        ? TimingCalibrator::targetDataPeriodForMC(run, static_cast<int64_t>(eventID))
                        : TimingCalibrator::periodForDataRun(run);
                    auto& ph = slotPers[slot][per];
                    if (!ph.initialized) ph.init(per);
                    if (down.valid) {
                        ph.hT0DownAll.fill(down.t0Ns);
                        ph.hSigmaT0Down.fill(down.sigmaT0Ns);
                        ph.hNDownUsed.fill(static_cast<double>(down.nUsed));
                        if (down.ndof >= 1) {
                            const double c2nd = down.chi2 / static_cast<double>(down.ndof);
                            ph.hChi2NdofAll.fill(c2nd);
                            if (raw[8].present && raw[9].present &&
                                (raw[8].rawCharge + raw[9].rawCharge > 20.0)) {
                                ph.hChi2NdofShowerSb.fill(c2nd);
                            }
                        }
                    }
                    if (speed.valid) ph.hBeta.fill(speed.beta);

                    // CR-Geom unblinded sideband (full [-4, +4] ns range open in both Data and MC)
                    const bool isCrGeom =
                        std::isfinite(tk.leadRMax) && std::isfinite(tk.leadThetaMrad) &&
                        ((tk.leadRMax >= 95.0 && tk.leadRMax < 130.0) || (tk.leadThetaMrad >= 25.0 && tk.leadThetaMrad < 55.0)) &&
                        tk.validPos[0] && std::abs(tk.x[0]) < 120.0 && std::abs(tk.y[0]) < 120.0;

                    if (isCrGeom && down.valid) {
                        if (down.ndof >= 1) ph.hChi2NdofGeomSb.fill(down.chi2 / static_cast<double>(down.ndof));
                        if (evt.channels[i0].valid && evt.channels[i0].aboveMip) {
                            ph.hVn0DtGeom.fill(dt0);
                            const double s0 = std::hypot(evt.channels[i0].sigmaCalNs, down.sigmaT0Ns);
                            if (s0 > 0.0) ph.hVn0PullGeom.fill(dt0 / s0);
                        }
                        if (evt.channels[i1].valid && evt.channels[i1].aboveMip) {
                            ph.hVn1DtGeom.fill(dt1);
                            const double s1 = std::hypot(evt.channels[i1].sigmaCalNs, down.sigmaT0Ns);
                            if (s1 > 0.0) ph.hVn1PullGeom.fill(dt1 / s1);
                        }
                    }

                    // Symmetric core CR-Prompt (above MIP VetoNu hits with |dt| <= 1.5 ns in both Data & MC)
                    const bool inVnFid = tk.validPos[0] && std::abs(tk.x[0]) < 120.0 && std::abs(tk.y[0]) < 120.0;
                    if (down.valid && inVnFid) {
                        const bool p0Ok = evt.channels[i0].valid && evt.channels[i0].aboveMip && std::abs(dt0) <= 1.5;
                        const bool p1Ok = evt.channels[i1].valid && evt.channels[i1].aboveMip && std::abs(dt1) <= 1.5;
                        if (p0Ok && p1Ok) {
                            ph.hT0DownPrompt.fill(down.t0Ns);
                            if (down.ndof >= 1) ph.hChi2NdofPrompt.fill(down.chi2 / static_cast<double>(down.ndof));
                        }
                        if (p0Ok) {
                            ph.hVn0DtPrompt.fill(dt0);
                            const double s0 = std::hypot(evt.channels[i0].sigmaCalNs, down.sigmaT0Ns);
                            if (s0 > 0.0) ph.hVn0PullPrompt.fill(dt0 / s0);
                        }
                        if (p1Ok) {
                            ph.hVn1DtPrompt.fill(dt1);
                            const double s1 = std::hypot(evt.channels[i1].sigmaCalNs, down.sigmaT0Ns);
                            if (s1 > 0.0) ph.hVn1PullPrompt.fill(dt1 / s1);
                        }
                    }

                    // Downstream LOO residuals across all valid MIP hits
                    for (int c = 2; c < kNumChannels; ++c) {
                        const auto& cr = evt.channels[c];
                        if (!cr.valid || !cr.aboveMip) continue;
                        const int pIdx = kChannelPlaneIdx[c];
                        if (!tk.validPos[pIdx] || std::abs(raw[c].xMm) >= 120.0 || std::abs(raw[c].yMm) >= 120.0) continue;
                        if (c == static_cast<int>(TimingChannel::Timing01) && raw[c].yMm >= -5.0) continue;
                        if (c == static_cast<int>(TimingChannel::Timing23) && raw[c].yMm <= 5.0) continue;
                        const auto loo = TimingCalibrator::fitLeaveOneOutArrival(evt, c);
                        if (!loo.valid || loo.nUsed < 2) continue;
                        const double r = cr.tCalNs - loo.t0Ns;
                        const double sTot = std::hypot(cr.sigmaCalNs, loo.sigmaT0Ns);
                        ph.hLooRes[c].fill(r);
                        if (sTot > 0.0) ph.hLooPull[c].fill(r / sTot);
                    }
                },
                {"run", "eventID", "distanceToCollidingBCID", "longTracks", "_grl_good", "_tk", "_raw", "_chg"});

            totalLoops += df.GetNRuns();
            for (unsigned int s = 0; s < nSlots; ++s) {
                for (const auto& [r, sd] : slotRuns[s]) mergedClosureRuns[r].mergeFrom(sd);
                for (const auto& [p, pd] : slotPers[s]) mergedClosurePers[p].mergeFrom(pd);
            }
        }
    }

    const auto parentDir = std::filesystem::path(outputPath).parent_path();
    if (!parentDir.empty()) std::filesystem::create_directories(parentDir);

    if (mode == "mc-scan") {
        writeMcScanOutput(outputPath, mergedMc, mergedMcRecs);
    } else {
        writeClosureOutput(outputPath, mergedClosureRuns, mergedClosurePers);
    }

    const double wallS = std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStart).count();
    uint64_t nTot = 0;
    if (mode == "mc-scan") {
        for (const auto& [r, d] : mergedMc) nTot += d.nTotal;
    } else {
        for (const auto& [r, d] : mergedClosureRuns) nTot += d.nTotal;
    }
    INFO("[STAT] mode=", mode, " threads=", threads, " slots=", nSlots,
         " event_loops=", totalLoops, " wall_s=", wallS,
         " n_total=", nTot, " n_mc_recs=", mergedMcRecs.size(), " output=", outputPath);
    return 0;
}
