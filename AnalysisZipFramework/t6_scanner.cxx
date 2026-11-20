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
#include <TH2D.h>
#include <TROOT.h>
#include <TTree.h>

#include <nlohmann/json.hpp>

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <glob.h>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace {

using json = nlohmann::json;
using TimingCalib::TimingChannel;
using TimingCalib::TimingCalibrator;
using TimingCalib::DownstreamMode;
using TimingCalib::kNumChannels;
using RawInputArray = std::array<TimingCalib::RawChannelInput, kNumChannels>;

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();
constexpr float kNaNF = std::numeric_limits<float>::quiet_NaN();
constexpr float kPsScale2025 = 0.928f;

constexpr uint32_t kMaskDownWithPS23 = TimingCalibrator::defaultDownstreamMask();
constexpr uint32_t kMaskDownNoPS23 = TimingCalibrator::legacyNoPreshower23DownstreamMask();
constexpr uint32_t kMaskDownA =
    (1u << static_cast<int>(TimingChannel::Veto10)) |
    (1u << static_cast<int>(TimingChannel::Veto11)) |
    (1u << static_cast<int>(TimingChannel::Veto20)) |
    (1u << static_cast<int>(TimingChannel::Veto21));
constexpr uint32_t kMaskDownBNoPS23 =
    (1u << static_cast<int>(TimingChannel::Timing01)) |
    (1u << static_cast<int>(TimingChannel::Timing23)) |
    (1u << static_cast<int>(TimingChannel::Preshower0)) |
    (1u << static_cast<int>(TimingChannel::Preshower1));
constexpr uint32_t kMaskDownBWithPS23 =
    kMaskDownBNoPS23 |
    (1u << static_cast<int>(TimingChannel::Preshower2)) |
    (1u << static_cast<int>(TimingChannel::Preshower3));

enum T6Region : uint8_t {
    REG_KIN_SR = 1,
    REG_CR_GEOM_OUTER = 2,
    REG_CR_GEOM_HITHETA = 3,
    REG_CR_EDGE_VN = 4,
    REG_CR_HALO_VN = 8,
};

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

bool inCaloNuPMTExact(double z) {
    return (z >= -2928.0 && z <= -2812.0);
}

bool isGenieCaloNuRun(int run) {
    return (run >= 200137 && run <= 200147) || (run >= 200172 && run <= 200183);
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
        throw std::runtime_error("Cannot open list file: " + path);
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

std::string toXrootdUrl(const std::string& p) {
    if (p.rfind("root://", 0) == 0) return p;
    if (p.rfind("/eos/user/x/", 0) == 0) return "root://eoshome-x.cern.ch/" + p;
    if (p.rfind("/eos/user/", 0) == 0) return "root://eosuser.cern.ch/" + p;
    if (p.rfind("/eos/experiment/", 0) == 0) return "root://eospublic.cern.ch/" + p;
    return p;
}

std::vector<std::string> expandLocalGlob(const std::string& pattern) {
    glob_t gbuf{};
    std::vector<std::string> out;
    if (::glob(pattern.c_str(), GLOB_TILDE, nullptr, &gbuf) == 0) {
        out.reserve(gbuf.gl_pathc);
        for (size_t i = 0; i < gbuf.gl_pathc; ++i) {
            out.emplace_back(gbuf.gl_pathv[i]);
        }
    }
    ::globfree(&gbuf);
    std::sort(out.begin(), out.end());
    return out;
}

struct AuxLookupRow {
    uint64_t key{0};
    float q0{std::numeric_limits<float>::quiet_NaN()};
    float q1{std::numeric_limits<float>::quiet_NaN()};
    bool operator<(const AuxLookupRow& o) const { return key < o.key; }
};

inline uint64_t makeAuxLookupKey(int32_t runNum, int32_t eventID) {
    return (static_cast<uint64_t>(static_cast<uint32_t>(runNum)) << 32) |
           static_cast<uint64_t>(static_cast<uint32_t>(eventID));
}

std::vector<AuxLookupRow> loadAuxRows(const std::vector<std::string>& auxFiles, int requestedThreads) {
    std::vector<AuxLookupRow> allRows;
    if (auxFiles.empty()) return allRows;
    const size_t nThreads = std::min<size_t>(
        auxFiles.size(), static_cast<size_t>(std::max(1, std::min(requestedThreads, 16))));
    std::atomic<size_t> nextIdx{0};
    std::vector<std::vector<AuxLookupRow>> perThread(nThreads);
    std::exception_ptr firstErr;
    std::mutex errMtx;

    auto worker = [&](size_t tid) {
        try {
            auto& local = perThread[tid];
            while (true) {
                const size_t i = nextIdx.fetch_add(1, std::memory_order_relaxed);
                if (i >= auxFiles.size()) break;
                const std::string& path = auxFiles[i];
                std::unique_ptr<TFile> tf(TFile::Open(path.c_str(), "READ"));
                if (!tf || tf->IsZombie()) {
                    throw std::runtime_error("Cannot open aux ROOT file: " + path);
                }
                auto* tree = tf->Get<TTree>("tree");
                if (!tree) {
                    throw std::runtime_error("Missing 'tree' in aux ROOT file: " + path);
                }
                tree->SetBranchStatus("*", 0);
                for (const char* b : {"run", "event", "myVetoNu0_rawCharge35", "myVetoNu1_rawCharge35"}) {
                    if (!tree->GetBranch(b)) {
                        throw std::runtime_error(std::string("Missing branch '") + b + "' in aux ROOT file: " + path);
                    }
                    tree->SetBranchStatus(b, 1);
                }
                Int_t rVal = 0;
                Int_t evVal = 0;
                Float_t q0 = 0.0f;
                Float_t q1 = 0.0f;
                tree->SetBranchAddress("run", &rVal);
                tree->SetBranchAddress("event", &evVal);
                tree->SetBranchAddress("myVetoNu0_rawCharge35", &q0);
                tree->SetBranchAddress("myVetoNu1_rawCharge35", &q1);
                const Long64_t nEnt = tree->GetEntries();
                if (nEnt > 0) {
                    local.reserve(local.size() + static_cast<size_t>(nEnt));
                    for (Long64_t e = 0; e < nEnt; ++e) {
                        if (tree->GetEntry(e) > 0) {
                            local.push_back(AuxLookupRow{makeAuxLookupKey(rVal, evVal), q0, q1});
                        }
                    }
                }
            }
        } catch (...) {
            std::lock_guard<std::mutex> lk(errMtx);
            if (!firstErr) firstErr = std::current_exception();
        }
    };

    std::vector<std::thread> pool;
    pool.reserve(nThreads);
    for (size_t t = 0; t < nThreads; ++t) pool.emplace_back(worker, t);
    for (auto& th : pool) th.join();
    if (firstErr) std::rethrow_exception(firstErr);

    size_t tot = 0;
    for (const auto& v : perThread) tot += v.size();
    allRows.reserve(tot);
    for (auto& v : perThread) {
        allRows.insert(allRows.end(), v.begin(), v.end());
        std::vector<AuxLookupRow>().swap(v);
    }
    std::sort(allRows.begin(), allRows.end());
    return allRows;
}

struct SchemaSignature {
    bool hasVetoSt{false};
    bool hasTimeNotLocaltime{false};
    bool hasNativeVeto11{false};
    bool hasPreshower23{false};
    bool hasMuon{false};
    bool hasReducedCharge{false};
    bool hasVetoGm{false};
    bool hasCrossingAngle{false};
    bool hasFillNumber{false};
    bool hasTruth{false};
    std::string eventTimeType{"UInt_t"};
    std::string nLayersType{"ROOT::VecOps::RVec<unsigned int>"};

    std::string key() const {
        return std::string(hasVetoSt ? "1" : "0") +
               (hasTimeNotLocaltime ? "1" : "0") +
               (hasNativeVeto11 ? "1" : "0") +
               (hasPreshower23 ? "1" : "0") +
               (hasMuon ? "1" : "0") +
               (hasReducedCharge ? "1" : "0") +
               (hasVetoGm ? "1" : "0") +
               (hasCrossingAngle ? "1" : "0") +
               (hasFillNumber ? "1" : "0") +
               (hasTruth ? "1" : "0") + "|" +
               eventTimeType + "|" + nLayersType;
    }
};

bool probeFileSchema(const std::string& fpath, SchemaSignature& sigOut, int* firstRunOut = nullptr) {
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
    sig.hasReducedCharge = (br.count("VetoNu0_reduced_charge") > 0) && (br.count("VetoNu1_reduced_charge") > 0);
    sig.hasVetoGm = (br.count("VetoGm0_raw_charge") > 0) && (br.count("VetoGm1_raw_charge") > 0);
    sig.hasCrossingAngle = br.count("crossingAngle") > 0;
    sig.hasFillNumber = br.count("fillNumber") > 0;
    sig.hasTruth = (br.count("truth_pdg") > 0) && (br.count("truth_dec_z") > 0);

    ROOT::RDataFrame probeDf(*tree);
    sig.eventTimeType = br.count("eventTime") ? probeDf.GetColumnType("eventTime") : "UInt_t";
    sig.nLayersType = probeDf.GetColumnType("Track_nLayers");
    if (firstRunOut && br.count("run")) {
        auto rFirst = probeDf.Filter("run > 0").Range(0, 1).Take<Int_t>("run");
        if (!rFirst->empty()) *firstRunOut = rFirst->at(0);
        if (*firstRunOut <= 0) {
            const auto pos = fpath.find("Faser-Physics-");
            if (pos != std::string::npos && pos + 20 <= fpath.size()) {
                try {
                    *firstRunOut = std::stoi(fpath.substr(pos + 14, 6));
                } catch (...) {}
            }
        }
    }
    sigOut = sig;
    return true;
}

struct FastHist1D {
    int nb{0};
    double xmin{0.0}, xmax{1.0}, invStep{1.0};
    std::vector<uint64_t> bins;

    void init(int n, double lo, double hi) {
        nb = n;
        xmin = lo;
        xmax = hi;
        invStep = static_cast<double>(n) / (hi - lo);
        bins.assign(static_cast<size_t>(n + 2), 0ULL); // 0=underflow, 1..n=in-range, n+1=overflow
    }

    void fill(double x) {
        if (!std::isfinite(x)) return;
        if (x < xmin) { ++bins[0]; return; }
        if (x >= xmax) { ++bins[nb + 1]; return; }
        const int b = std::min(nb, std::max(1, 1 + static_cast<int>((x - xmin) * invStep)));
        ++bins[b];
    }

    void addFrom(const FastHist1D& o) {
        if (bins.empty()) { *this = o; return; }
        for (size_t i = 0; i < bins.size(); ++i) bins[i] += o.bins[i];
    }

    std::unique_ptr<TH1D> toTH1D(const std::string& name, const std::string& title) const {
        auto h = std::make_unique<TH1D>(name.c_str(), title.c_str(), nb, xmin, xmax);
        for (int i = 0; i <= nb + 1; ++i) {
            if (bins[i] > 0) h->SetBinContent(i, static_cast<double>(bins[i]));
        }
        return h;
    }
};

struct FastHist2D {
    int nx{0}, ny{0};
    double xmin{0.0}, xmax{1.0}, invX{1.0};
    double ymin{0.0}, ymax{1.0}, invY{1.0};
    std::vector<uint64_t> bins;

    void init(int nxb, double xlo, double xhi, int nyb, double ylo, double yhi) {
        nx = nxb; xmin = xlo; xmax = xhi; invX = static_cast<double>(nx) / (xhi - xlo);
        ny = nyb; ymin = ylo; ymax = yhi; invY = static_cast<double>(ny) / (yhi - ylo);
        bins.assign(static_cast<size_t>(nx * ny), 0ULL);
    }

    void fill(double x, double y) {
        if (!std::isfinite(x) || !std::isfinite(y)) return;
        if (x < xmin || x >= xmax || y < ymin || y >= ymax) return;
        const int ix = std::min(nx - 1, std::max(0, static_cast<int>((x - xmin) * invX)));
        const int iy = std::min(ny - 1, std::max(0, static_cast<int>((y - ymin) * invY)));
        ++bins[static_cast<size_t>(ix * ny + iy)];
    }

    void addFrom(const FastHist2D& o) {
        if (bins.empty()) { *this = o; return; }
        for (size_t i = 0; i < bins.size(); ++i) bins[i] += o.bins[i];
    }

    std::unique_ptr<TH2D> toTH2D(const std::string& name, const std::string& title) const {
        auto h = std::make_unique<TH2D>(name.c_str(), title.c_str(), nx, xmin, xmax, ny, ymin, ymax);
        for (int ix = 0; ix < nx; ++ix) {
            for (int iy = 0; iy < ny; ++iy) {
                const uint64_t v = bins[static_cast<size_t>(ix * ny + iy)];
                if (v > 0) h->SetBinContent(ix + 1, iy + 1, static_cast<double>(v));
            }
        }
        return h;
    }
};

struct RunPreStats {
    bool initialized{false};
    int run{0};
    uint64_t nTotal{0};
    uint64_t nGrlPass{0};
    uint64_t nColliding{0};
    uint64_t nPhysTrig{0};
    uint64_t nLongTrk{0};
    uint64_t nTrigBit8{0}, nTrigBit16{0}, nTrigBit32{0}, nTrigBit64{0};
    double caSum{0.0}, caSum2{0.0};
    uint64_t caCnt{0};
    std::unordered_map<int32_t, uint64_t> fillCounts;

    void mergeFrom(const RunPreStats& o) {
        if (!initialized && o.initialized) { initialized = true; run = o.run; }
        nTotal += o.nTotal;
        nGrlPass += o.nGrlPass;
        nColliding += o.nColliding;
        nPhysTrig += o.nPhysTrig;
        nLongTrk += o.nLongTrk;
        nTrigBit8 += o.nTrigBit8;
        nTrigBit16 += o.nTrigBit16;
        nTrigBit32 += o.nTrigBit32;
        nTrigBit64 += o.nTrigBit64;
        caSum += o.caSum;
        caSum2 += o.caSum2;
        caCnt += o.caCnt;
        for (const auto& [fl, cnt] : o.fillCounts) {
            fillCounts[fl] += cnt;
        }
    }
};

struct T6RunStats {
    bool initialized{false};
    int run{0};
    bool isMC{false};
    bool hasReducedCharge{false};
    bool hasPs23{false};
    bool hasVetoGm{false};
    bool brokenPsP0013{false};
    bool deadVetoNuHv{false};

    RunPreStats pre;
    uint64_t nBlinded{0};
    uint64_t nNoOffsets{0};

    // Yield counters (nominal PS0/1_charge > 2.5 vs broken_p0013-repaired PS0/1_charge_eff > 2.5)
    uint64_t nClean1TrkNom{0}, nClean1TrkEff{0};
    uint64_t nCrPromptAllNom{0}, nCrPrompt2HitNom{0}, nCrPromptU1p0Nom{0};
    uint64_t nCrPromptAllEff{0}, nCrPrompt2HitEff{0};
    uint64_t nSrZoneARed30Nom{0}, nSrZoneARaw40Nom{0}, nSrZoneAEraNom{0};
    uint64_t nSrZoneARed30Eff{0}, nSrZoneAEraEff{0};
    uint64_t nCrGeomAllNom{0}, nCrGeomPromptNom{0}, nCrGeomZoneANom{0};
    uint64_t nCrGeomWpPrimaryWithNom{0}, nCrGeomWpPrimaryNoNom{0};
    uint64_t nCrGeomAllEff{0}, nCrGeomPromptEff{0}, nCrGeomWpPrimaryEff{0};
    uint64_t nCrEdgeVnAllNom{0}, nCrEdgeVnZoneANom{0}, nCrEdgeVnZoneBNom{0}, nCrEdgeVnWpPrimaryNom{0};
    uint64_t nCrEdgeVnAllEff{0};

    // Per-run timing moments on clean prompt core |dt| < 2.5 ns (withPS23 vs noPS23)
    uint64_t dt0WithCnt{0}, dt1WithCnt{0}, dt0NoCnt{0}, dt1NoCnt{0};
    double dt0WithSum{0.0}, dt0WithSum2{0.0}, dt1WithSum{0.0}, dt1WithSum2{0.0};
    double dt0NoSum{0.0}, dt0NoSum2{0.0}, dt1NoSum{0.0}, dt1NoSum2{0.0};
    uint64_t downWithCnt{0}, downNoCnt{0}, downWithGe2{0}, downWithGe3{0}, downNoGe2{0}, downNoGe3{0};
    double sigT0WithSum{0.0}, sigT0WithSum2{0.0}, sigT0NoSum{0.0}, sigT0NoSum2{0.0};
    uint64_t shiftCnt{0};
    double shiftT0Sum{0.0}, shiftT0Sum2{0.0};
    uint64_t nV2Sat{0}, nV2SatDownWith{0}, nV2SatDownNo{0};
    uint64_t nNoMuon{0}, nNoMuonDownWith{0}, nNoMuonDownNo{0};
    uint64_t nDownBWithGe1{0}, nDownBWithGe2{0}, nDownBNoGe1{0}, nDownBNoGe2{0};

    // Per-run VetoGm0/1 outer-halo activity telemetry (when hasVetoGm)
    uint64_t nGmDenom{0}, nGm0Q10{0}, nGm0Q20{0}, nGm1Q10{0}, nGm1Q20{0};
    double gm0QMax{-999.0}, gm1QMax{-999.0};

    void init(int r, bool mc, bool redQ, bool ps23, bool gm, bool bps, bool dvn) {
        if (initialized) return;
        initialized = true;
        run = r;
        isMC = mc;
        hasReducedCharge = redQ;
        hasPs23 = ps23;
        hasVetoGm = gm;
        brokenPsP0013 = bps;
        deadVetoNuHv = dvn;
        pre.initialized = true;
        pre.run = r;
    }

    void mergeFrom(const T6RunStats& o) {
        if (!initialized) {
            init(o.run, o.isMC, o.hasReducedCharge, o.hasPs23, o.hasVetoGm, o.brokenPsP0013, o.deadVetoNuHv);
        }
        hasReducedCharge = hasReducedCharge || o.hasReducedCharge;
        hasPs23 = hasPs23 || o.hasPs23;
        hasVetoGm = hasVetoGm || o.hasVetoGm;
        brokenPsP0013 = brokenPsP0013 || o.brokenPsP0013;
        deadVetoNuHv = deadVetoNuHv || o.deadVetoNuHv;
        pre.mergeFrom(o.pre);
        nBlinded += o.nBlinded;
        nNoOffsets += o.nNoOffsets;
        nClean1TrkNom += o.nClean1TrkNom;
        nClean1TrkEff += o.nClean1TrkEff;
        nCrPromptAllNom += o.nCrPromptAllNom;
        nCrPrompt2HitNom += o.nCrPrompt2HitNom;
        nCrPromptU1p0Nom += o.nCrPromptU1p0Nom;
        nCrPromptAllEff += o.nCrPromptAllEff;
        nCrPrompt2HitEff += o.nCrPrompt2HitEff;
        nSrZoneARed30Nom += o.nSrZoneARed30Nom;
        nSrZoneARaw40Nom += o.nSrZoneARaw40Nom;
        nSrZoneAEraNom += o.nSrZoneAEraNom;
        nSrZoneARed30Eff += o.nSrZoneARed30Eff;
        nSrZoneAEraEff += o.nSrZoneAEraEff;
        nCrGeomAllNom += o.nCrGeomAllNom;
        nCrGeomPromptNom += o.nCrGeomPromptNom;
        nCrGeomZoneANom += o.nCrGeomZoneANom;
        nCrGeomWpPrimaryWithNom += o.nCrGeomWpPrimaryWithNom;
        nCrGeomWpPrimaryNoNom += o.nCrGeomWpPrimaryNoNom;
        nCrGeomAllEff += o.nCrGeomAllEff;
        nCrGeomPromptEff += o.nCrGeomPromptEff;
        nCrGeomWpPrimaryEff += o.nCrGeomWpPrimaryEff;
        nCrEdgeVnAllNom += o.nCrEdgeVnAllNom;
        nCrEdgeVnZoneANom += o.nCrEdgeVnZoneANom;
        nCrEdgeVnZoneBNom += o.nCrEdgeVnZoneBNom;
        nCrEdgeVnWpPrimaryNom += o.nCrEdgeVnWpPrimaryNom;
        nCrEdgeVnAllEff += o.nCrEdgeVnAllEff;
        dt0WithCnt += o.dt0WithCnt;
        dt1WithCnt += o.dt1WithCnt;
        dt0NoCnt += o.dt0NoCnt;
        dt1NoCnt += o.dt1NoCnt;
        dt0WithSum += o.dt0WithSum;
        dt0WithSum2 += o.dt0WithSum2;
        dt1WithSum += o.dt1WithSum;
        dt1WithSum2 += o.dt1WithSum2;
        dt0NoSum += o.dt0NoSum;
        dt0NoSum2 += o.dt0NoSum2;
        dt1NoSum += o.dt1NoSum;
        dt1NoSum2 += o.dt1NoSum2;
        downWithCnt += o.downWithCnt;
        downNoCnt += o.downNoCnt;
        downWithGe2 += o.downWithGe2;
        downWithGe3 += o.downWithGe3;
        downNoGe2 += o.downNoGe2;
        downNoGe3 += o.downNoGe3;
        sigT0WithSum += o.sigT0WithSum;
        sigT0WithSum2 += o.sigT0WithSum2;
        sigT0NoSum += o.sigT0NoSum;
        sigT0NoSum2 += o.sigT0NoSum2;
        shiftCnt += o.shiftCnt;
        shiftT0Sum += o.shiftT0Sum;
        shiftT0Sum2 += o.shiftT0Sum2;
        nV2Sat += o.nV2Sat;
        nV2SatDownWith += o.nV2SatDownWith;
        nV2SatDownNo += o.nV2SatDownNo;
        nNoMuon += o.nNoMuon;
        nNoMuonDownWith += o.nNoMuonDownWith;
        nNoMuonDownNo += o.nNoMuonDownNo;
        nDownBWithGe1 += o.nDownBWithGe1;
        nDownBWithGe2 += o.nDownBWithGe2;
        nDownBNoGe1 += o.nDownBNoGe1;
        nDownBNoGe2 += o.nDownBNoGe2;
        nGmDenom += o.nGmDenom;
        nGm0Q10 += o.nGm0Q10;
        nGm0Q20 += o.nGm0Q20;
        nGm1Q10 += o.nGm1Q10;
        nGm1Q20 += o.nGm1Q20;
        gm0QMax = std::max(gm0QMax, o.gm0QMax);
        gm1QMax = std::max(gm1QMax, o.gm1QMax);
    }
};

constexpr int kNPsStrata = 4; // 0: all, 1: v2sat, 2: nomuon, 3: v2sat_nomuon
constexpr std::array<const char*, kNPsStrata> kPsStrataNames = {{"all", "v2sat", "nomuon", "v2sat_nomuon"}};

struct T6Ps23Group {
    bool initialized{false};
    std::string groupName;
    std::array<FastHist1D, kNPsStrata> hSigt0No, hSigt0With;
    std::array<FastHist1D, kNPsStrata> hNdownNo, hNdownWith;
    std::array<FastHist1D, kNPsStrata> hShiftT0;
    std::array<FastHist1D, kNPsStrata> hTim01LooNo, hTim01LooWith;
    std::array<FastHist1D, kNPsStrata> hDt0PromptNo, hDt0PromptWith;
    std::array<FastHist1D, kNPsStrata> hDt1PromptNo, hDt1PromptWith;
    std::array<FastHist1D, kNPsStrata> hDt0CrNo, hDt0CrWith;
    std::array<FastHist1D, kNPsStrata> hDt1CrNo, hDt1CrWith;
    std::array<FastHist1D, kNPsStrata> hU1DownBNo, hU1DownBWith;

    void init(const std::string& g) {
        if (initialized) return;
        initialized = true;
        groupName = g;
        for (int s = 0; s < kNPsStrata; ++s) {
            hSigt0No[s].init(200, 0.0, 1.0);
            hSigt0With[s].init(200, 0.0, 1.0);
            hNdownNo[s].init(12, 0.0, 12.0);
            hNdownWith[s].init(12, 0.0, 12.0);
            hShiftT0[s].init(200, -2.0, 2.0);
            hTim01LooNo[s].init(320, -4.0, 4.0);
            hTim01LooWith[s].init(320, -4.0, 4.0);
            hDt0PromptNo[s].init(200, -2.5, 2.5);
            hDt0PromptWith[s].init(200, -2.5, 2.5);
            hDt1PromptNo[s].init(200, -2.5, 2.5);
            hDt1PromptWith[s].init(200, -2.5, 2.5);
            hDt0CrNo[s].init(320, -8.0, 8.0);
            hDt0CrWith[s].init(320, -8.0, 8.0);
            hDt1CrNo[s].init(320, -8.0, 8.0);
            hDt1CrWith[s].init(320, -8.0, 8.0);
            hU1DownBNo[s].init(320, -8.0, 8.0);
            hU1DownBWith[s].init(320, -8.0, 8.0);
        }
    }

    void mergeFrom(const T6Ps23Group& o) {
        if (!initialized) init(o.groupName);
        for (int s = 0; s < kNPsStrata; ++s) {
            hSigt0No[s].addFrom(o.hSigt0No[s]);
            hSigt0With[s].addFrom(o.hSigt0With[s]);
            hNdownNo[s].addFrom(o.hNdownNo[s]);
            hNdownWith[s].addFrom(o.hNdownWith[s]);
            hShiftT0[s].addFrom(o.hShiftT0[s]);
            hTim01LooNo[s].addFrom(o.hTim01LooNo[s]);
            hTim01LooWith[s].addFrom(o.hTim01LooWith[s]);
            hDt0PromptNo[s].addFrom(o.hDt0PromptNo[s]);
            hDt0PromptWith[s].addFrom(o.hDt0PromptWith[s]);
            hDt1PromptNo[s].addFrom(o.hDt1PromptNo[s]);
            hDt1PromptWith[s].addFrom(o.hDt1PromptWith[s]);
            hDt0CrNo[s].addFrom(o.hDt0CrNo[s]);
            hDt0CrWith[s].addFrom(o.hDt0CrWith[s]);
            hDt1CrNo[s].addFrom(o.hDt1CrNo[s]);
            hDt1CrWith[s].addFrom(o.hDt1CrWith[s]);
            hU1DownBNo[s].addFrom(o.hU1DownBNo[s]);
            hU1DownBWith[s].addFrom(o.hU1DownBWith[s]);
        }
    }
};

struct T6VetoGmMaps {
    bool initialized{false};
    std::string eraName; // "live_2025_p0014" or "hv_off_2026_p0015"
    FastHist2D h2VnDenom, h2VnGm0Q20, h2VnGm1Q20, h2VnGmAnyQ20;
    FastHist2D h2V1Denom, h2V1Gm0Q20, h2V1Gm1Q20;
    FastHist1D h1Gm0RawQ, h1Gm1RawQ;
    FastHist1D h1Gm0DtVsDown, h1Gm1DtVsDown;
    FastHist1D h1Gm0LocMinusTim0, h1Gm1LocMinusTim0;
    FastHist1D h1RvnAllDenom, h1RvnGm0Q20, h1RvnGm1Q20, h1RvnGmAnyQ20;

    void init(const std::string& e) {
        if (initialized) return;
        initialized = true;
        eraName = e;
        h2VnDenom.init(104, -260.0, 260.0, 104, -260.0, 260.0);
        h2VnGm0Q20.init(104, -260.0, 260.0, 104, -260.0, 260.0);
        h2VnGm1Q20.init(104, -260.0, 260.0, 104, -260.0, 260.0);
        h2VnGmAnyQ20.init(104, -260.0, 260.0, 104, -260.0, 260.0);
        h2V1Denom.init(104, -260.0, 260.0, 104, -260.0, 260.0);
        h2V1Gm0Q20.init(104, -260.0, 260.0, 104, -260.0, 260.0);
        h2V1Gm1Q20.init(104, -260.0, 260.0, 104, -260.0, 260.0);
        h1Gm0RawQ.init(300, -5.0, 595.0);
        h1Gm1RawQ.init(300, -5.0, 595.0);
        h1Gm0DtVsDown.init(720, -120.0, 60.0);
        h1Gm1DtVsDown.init(720, -120.0, 60.0);
        h1Gm0LocMinusTim0.init(400, -100.0, 100.0);
        h1Gm1LocMinusTim0.init(400, -100.0, 100.0);
        h1RvnAllDenom.init(56, 0.0, 280.0);
        h1RvnGm0Q20.init(56, 0.0, 280.0);
        h1RvnGm1Q20.init(56, 0.0, 280.0);
        h1RvnGmAnyQ20.init(56, 0.0, 280.0);
    }

    void mergeFrom(const T6VetoGmMaps& o) {
        if (!initialized) init(o.eraName);
        h2VnDenom.addFrom(o.h2VnDenom);
        h2VnGm0Q20.addFrom(o.h2VnGm0Q20);
        h2VnGm1Q20.addFrom(o.h2VnGm1Q20);
        h2VnGmAnyQ20.addFrom(o.h2VnGmAnyQ20);
        h2V1Denom.addFrom(o.h2V1Denom);
        h2V1Gm0Q20.addFrom(o.h2V1Gm0Q20);
        h2V1Gm1Q20.addFrom(o.h2V1Gm1Q20);
        h1Gm0RawQ.addFrom(o.h1Gm0RawQ);
        h1Gm1RawQ.addFrom(o.h1Gm1RawQ);
        h1Gm0DtVsDown.addFrom(o.h1Gm0DtVsDown);
        h1Gm1DtVsDown.addFrom(o.h1Gm1DtVsDown);
        h1Gm0LocMinusTim0.addFrom(o.h1Gm0LocMinusTim0);
        h1Gm1LocMinusTim0.addFrom(o.h1Gm1LocMinusTim0);
        h1RvnAllDenom.addFrom(o.h1RvnAllDenom);
        h1RvnGm0Q20.addFrom(o.h1RvnGm0Q20);
        h1RvnGm1Q20.addFrom(o.h1RvnGm1Q20);
        h1RvnGmAnyQ20.addFrom(o.h1RvnGmAnyQ20);
    }
};

struct T6VetoGmRecord {
    int32_t run{0};
    int64_t eventID{0};
    uint8_t region{0};
    uint8_t is_prescaled_prompt{0};
    uint8_t zone_a_era{0};
    uint8_t pass_wp_primary{0};
    float sample_weight{1.0f};
    float pz0_gev{0.0f};
    float r_max{0.0f};
    float r_ift{0.0f};
    float r_vn{0.0f};
    float theta_mrad{0.0f};
    float x_vn{0.0f};
    float y_vn{0.0f};
    float x_v1{0.0f};
    float y_v1{0.0f};
    float q0_raw{0.0f};
    float q1_raw{0.0f};
    float q0_red{0.0f};
    float q1_red{0.0f};
    float dt0{0.0f};
    float dt1{0.0f};
    float w0{0.0f};
    float w1{0.0f};
    float gm0_q_raw{0.0f};
    float gm1_q_raw{0.0f};
    float gm0_q_chg{0.0f};
    float gm1_q_chg{0.0f};
    float gm0_width{0.0f};
    float gm1_width{0.0f};
    float gm0_dt_down{kNaNF};
    float gm1_dt_down{kNaNF};
    float gm0_loc_tim0{kNaNF};
    float gm1_loc_tim0{kNaNF};
    int32_t gm0_status{-1};
    int32_t gm1_status{-1};
};

struct ScannerTrackData {
    int nTracks{0};
    double leadPz0GeV{kNaN};
    double leadNLayers{0.0};
    uint32_t leadNLayersU{0};
    double leadNDoF{kNaN};
    double leadChi2NDF{kNaN};
    double leadRMax{kNaN};
    double leadThetaMrad{kNaN};
    std::array<double, 8> x{};
    std::array<double, 8> y{};
    std::array<bool, 8> validPos{};
};

struct ScannerVetoGmRaw {
    Int_t status0{-1}, status1{-1};
    Float_t bcid0{kNaNF}, trig0{kNaNF}, loc0{kNaNF}, qRaw0{kNaNF}, qChg0{kNaNF}, w0{kNaNF};
    Float_t bcid1{kNaNF}, trig1{kNaNF}, loc1{kNaNF}, qRaw1{kNaNF}, qChg1{kNaNF}, w1{kNaNF};
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
    int32_t vn0Status{0};
    int32_t vn1Status{0};
    int32_t v20Status{0};
    int32_t v21Status{0};
    int32_t ps0Status{0};
    int32_t ps1Status{0};
    int32_t t0Status{0};
    int32_t t1Status{0};
    int32_t t2Status{0};
    int32_t t3Status{0};
    bool genieVetoCaloNu{false};
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
            td.leadNLayersU = (i0 < static_cast<int>(nLayers.size())) ? static_cast<uint32_t>(nLayers[i0]) : 0u;
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

void writeOutput(
    const std::string& outputPath,
    const std::map<int, T6RunStats>& runStats,
    const std::map<std::string, T6Ps23Group>& psGroups,
    const std::map<std::string, T6VetoGmMaps>& gmMaps,
    std::vector<T6VetoGmRecord>& gmRecs) {

    std::unique_ptr<TFile> outFile(TFile::Open(outputPath.c_str(), "RECREATE"));
    if (!outFile || outFile->IsZombie()) {
        throw std::runtime_error("Cannot create T6 output: " + outputPath);
    }

    TTree* st = new TTree("t6_run_summary", "Stage T6 per-run yield, timing resolution, PS2/3 & VetoGm telemetry");
    T6RunStats row;
    std::string period;
    int32_t fillMode = -1;
    uint64_t fillModeCnt = 0;
    std::string fillHist;

    st->Branch("run", &row.run);
    st->Branch("period", &period);
    st->Branch("is_mc", &row.isMC);
    st->Branch("has_reduced_charge", &row.hasReducedCharge);
    st->Branch("has_ps23", &row.hasPs23);
    st->Branch("has_vetogm", &row.hasVetoGm);
    st->Branch("broken_ps_p0013", &row.brokenPsP0013);
    st->Branch("dead_vetonu_hv", &row.deadVetoNuHv);
    st->Branch("fill_mode", &fillMode);
    st->Branch("fill_mode_cnt", &fillModeCnt);
    st->Branch("fill_hist", &fillHist);
    st->Branch("ca_sum", &row.pre.caSum);
    st->Branch("ca_sum2", &row.pre.caSum2);
    st->Branch("ca_cnt", &row.pre.caCnt);
    st->Branch("n_total", &row.pre.nTotal);
    st->Branch("n_grl_pass", &row.pre.nGrlPass);
    st->Branch("n_colliding", &row.pre.nColliding);
    st->Branch("n_phys_trig", &row.pre.nPhysTrig);
    st->Branch("n_long_trk", &row.pre.nLongTrk);
    st->Branch("n_trig_bit8", &row.pre.nTrigBit8);
    st->Branch("n_trig_bit16", &row.pre.nTrigBit16);
    st->Branch("n_trig_bit32", &row.pre.nTrigBit32);
    st->Branch("n_trig_bit64", &row.pre.nTrigBit64);
    st->Branch("n_blinded", &row.nBlinded);
    st->Branch("n_no_offsets", &row.nNoOffsets);

    st->Branch("n_clean_1trk_nom", &row.nClean1TrkNom);
    st->Branch("n_clean_1trk_eff", &row.nClean1TrkEff);
    st->Branch("n_cr_prompt_all_nom", &row.nCrPromptAllNom);
    st->Branch("n_cr_prompt_2hit_nom", &row.nCrPrompt2HitNom);
    st->Branch("n_cr_prompt_u1p0_nom", &row.nCrPromptU1p0Nom);
    st->Branch("n_cr_prompt_all_eff", &row.nCrPromptAllEff);
    st->Branch("n_cr_prompt_2hit_eff", &row.nCrPrompt2HitEff);
    st->Branch("n_sr_zonea_red30_nom", &row.nSrZoneARed30Nom);
    st->Branch("n_sr_zonea_raw40_nom", &row.nSrZoneARaw40Nom);
    st->Branch("n_sr_zonea_era_nom", &row.nSrZoneAEraNom);
    st->Branch("n_sr_zonea_red30_eff", &row.nSrZoneARed30Eff);
    st->Branch("n_sr_zonea_era_eff", &row.nSrZoneAEraEff);
    st->Branch("n_cr_geom_all_nom", &row.nCrGeomAllNom);
    st->Branch("n_cr_geom_prompt_nom", &row.nCrGeomPromptNom);
    st->Branch("n_cr_geom_zonea_nom", &row.nCrGeomZoneANom);
    st->Branch("n_cr_geom_wp_primary_with_nom", &row.nCrGeomWpPrimaryWithNom);
    st->Branch("n_cr_geom_wp_primary_no_nom", &row.nCrGeomWpPrimaryNoNom);
    st->Branch("n_cr_geom_all_eff", &row.nCrGeomAllEff);
    st->Branch("n_cr_geom_prompt_eff", &row.nCrGeomPromptEff);
    st->Branch("n_cr_geom_wp_primary_eff", &row.nCrGeomWpPrimaryEff);
    st->Branch("n_cr_edge_vn_all_nom", &row.nCrEdgeVnAllNom);
    st->Branch("n_cr_edge_vn_zonea_nom", &row.nCrEdgeVnZoneANom);
    st->Branch("n_cr_edge_vn_zoneb_nom", &row.nCrEdgeVnZoneBNom);
    st->Branch("n_cr_edge_vn_wp_primary_nom", &row.nCrEdgeVnWpPrimaryNom);
    st->Branch("n_cr_edge_vn_all_eff", &row.nCrEdgeVnAllEff);

    st->Branch("dt0_with_cnt", &row.dt0WithCnt);
    st->Branch("dt1_with_cnt", &row.dt1WithCnt);
    st->Branch("dt0_no_cnt", &row.dt0NoCnt);
    st->Branch("dt1_no_cnt", &row.dt1NoCnt);
    st->Branch("dt0_with_sum", &row.dt0WithSum);
    st->Branch("dt0_with_sum2", &row.dt0WithSum2);
    st->Branch("dt1_with_sum", &row.dt1WithSum);
    st->Branch("dt1_with_sum2", &row.dt1WithSum2);
    st->Branch("dt0_no_sum", &row.dt0NoSum);
    st->Branch("dt0_no_sum2", &row.dt0NoSum2);
    st->Branch("dt1_no_sum", &row.dt1NoSum);
    st->Branch("dt1_no_sum2", &row.dt1NoSum2);
    st->Branch("down_with_cnt", &row.downWithCnt);
    st->Branch("down_no_cnt", &row.downNoCnt);
    st->Branch("down_with_ge2", &row.downWithGe2);
    st->Branch("down_with_ge3", &row.downWithGe3);
    st->Branch("down_no_ge2", &row.downNoGe2);
    st->Branch("down_no_ge3", &row.downNoGe3);
    st->Branch("sigt0_with_sum", &row.sigT0WithSum);
    st->Branch("sigt0_with_sum2", &row.sigT0WithSum2);
    st->Branch("sigt0_no_sum", &row.sigT0NoSum);
    st->Branch("sigt0_no_sum2", &row.sigT0NoSum2);
    st->Branch("shift_cnt", &row.shiftCnt);
    st->Branch("shift_t0_sum", &row.shiftT0Sum);
    st->Branch("shift_t0_sum2", &row.shiftT0Sum2);
    st->Branch("n_v2_sat", &row.nV2Sat);
    st->Branch("n_v2_sat_down_with", &row.nV2SatDownWith);
    st->Branch("n_v2_sat_down_no", &row.nV2SatDownNo);
    st->Branch("n_no_muon", &row.nNoMuon);
    st->Branch("n_no_muon_down_with", &row.nNoMuonDownWith);
    st->Branch("n_no_muon_down_no", &row.nNoMuonDownNo);
    st->Branch("n_downb_with_ge1", &row.nDownBWithGe1);
    st->Branch("n_downb_with_ge2", &row.nDownBWithGe2);
    st->Branch("n_downb_no_ge1", &row.nDownBNoGe1);
    st->Branch("n_downb_no_ge2", &row.nDownBNoGe2);

    st->Branch("n_gm_denom", &row.nGmDenom);
    st->Branch("n_gm0_q10", &row.nGm0Q10);
    st->Branch("n_gm0_q20", &row.nGm0Q20);
    st->Branch("n_gm1_q10", &row.nGm1Q10);
    st->Branch("n_gm1_q20", &row.nGm1Q20);
    st->Branch("gm0_qmax", &row.gm0QMax);
    st->Branch("gm1_qmax", &row.gm1QMax);

    for (const auto& [r, s] : runStats) {
        row = s;
        period = s.isMC ? TimingCalibrator::mcFamilyForRun(r) : TimingCalibrator::periodForDataRun(r);
        fillMode = -1;
        fillModeCnt = 0;
        std::vector<std::pair<int32_t, uint64_t>> fvec(s.pre.fillCounts.begin(), s.pre.fillCounts.end());
        std::sort(fvec.begin(), fvec.end());
        std::ostringstream fss;
        for (size_t i = 0; i < fvec.size(); ++i) {
            if (i > 0) fss << ',';
            fss << fvec[i].first << ':' << fvec[i].second;
            if (fvec[i].second > fillModeCnt) {
                fillMode = fvec[i].first;
                fillModeCnt = fvec[i].second;
            }
        }
        fillHist = fss.str();
        st->Fill();
    }
    st->Write();

    TDirectory* psRoot = outFile->mkdir("preshower23_study");
    for (const auto& [gname, grp] : psGroups) {
        TDirectory* gdir = psRoot->mkdir(gname.c_str());
        gdir->cd();
        for (int s = 0; s < kNPsStrata; ++s) {
            const std::string sn(kPsStrataNames[s]);
            grp.hSigt0No[s].toTH1D("h_sigt0_no_" + sn, "sigma(t0_down) noPS23;ns")->Write();
            grp.hSigt0With[s].toTH1D("h_sigt0_with_" + sn, "sigma(t0_down) withPS23;ns")->Write();
            grp.hNdownNo[s].toTH1D("h_ndown_no_" + sn, "n_down_used noPS23;N")->Write();
            grp.hNdownWith[s].toTH1D("h_ndown_with_" + sn, "n_down_used withPS23;N")->Write();
            grp.hShiftT0[s].toTH1D("h_shift_t0_" + sn, "t0_with - t0_no;ns")->Write();
            grp.hTim01LooNo[s].toTH1D("h_tim01_loo_no_" + sn, "Timing01 LOO noPS23;ns")->Write();
            grp.hTim01LooWith[s].toTH1D("h_tim01_loo_with_" + sn, "Timing01 LOO withPS23;ns")->Write();
            grp.hDt0PromptNo[s].toTH1D("h_dt0_prompt_no_" + sn, "dt0 prompt noPS23;ns")->Write();
            grp.hDt0PromptWith[s].toTH1D("h_dt0_prompt_with_" + sn, "dt0 prompt withPS23;ns")->Write();
            grp.hDt1PromptNo[s].toTH1D("h_dt1_prompt_no_" + sn, "dt1 prompt noPS23;ns")->Write();
            grp.hDt1PromptWith[s].toTH1D("h_dt1_prompt_with_" + sn, "dt1 prompt withPS23;ns")->Write();
            grp.hDt0CrNo[s].toTH1D("h_dt0_cr_no_" + sn, "dt0 CR noPS23;ns")->Write();
            grp.hDt0CrWith[s].toTH1D("h_dt0_cr_with_" + sn, "dt0 CR withPS23;ns")->Write();
            grp.hDt1CrNo[s].toTH1D("h_dt1_cr_no_" + sn, "dt1 CR noPS23;ns")->Write();
            grp.hDt1CrWith[s].toTH1D("h_dt1_cr_with_" + sn, "dt1 CR withPS23;ns")->Write();
            grp.hU1DownBNo[s].toTH1D("h_u1_downb_no_" + sn, "u1(DownB) noPS23;ns")->Write();
            grp.hU1DownBWith[s].toTH1D("h_u1_downb_with_" + sn, "u1(DownB) withPS23;ns")->Write();
        }
        outFile->cd();
    }

    TDirectory* gmRoot = outFile->mkdir("vetogm_study");
    for (const auto& [ename, gm] : gmMaps) {
        TDirectory* edir = gmRoot->mkdir(ename.c_str());
        edir->cd();
        gm.h2VnDenom.toTH2D("h2_vn_denom", "Denom (xVN,yVN);x [mm];y [mm]")->Write();
        gm.h2VnGm0Q20.toTH2D("h2_vn_gm0_q20", "VetoGm0 rawQ>20;x [mm];y [mm]")->Write();
        gm.h2VnGm1Q20.toTH2D("h2_vn_gm1_q20", "VetoGm1 rawQ>20;x [mm];y [mm]")->Write();
        gm.h2VnGmAnyQ20.toTH2D("h2_vn_gmany_q20", "VetoGm0|1 rawQ>20;x [mm];y [mm]")->Write();
        gm.h2V1Denom.toTH2D("h2_v1_denom", "Denom (xV1,yV1);x [mm];y [mm]")->Write();
        gm.h2V1Gm0Q20.toTH2D("h2_v1_gm0_q20", "VetoGm0 rawQ>20 at V1;x [mm];y [mm]")->Write();
        gm.h2V1Gm1Q20.toTH2D("h2_v1_gm1_q20", "VetoGm1 rawQ>20 at V1;x [mm];y [mm]")->Write();
        gm.h1Gm0RawQ.toTH1D("h1_gm0_raw_q", "VetoGm0 raw charge;pC")->Write();
        gm.h1Gm1RawQ.toTH1D("h1_gm1_raw_q", "VetoGm1 raw charge;pC")->Write();
        gm.h1Gm0DtVsDown.toTH1D("h1_gm0_dt_down", "VetoGm0 t2 - t0_down;ns")->Write();
        gm.h1Gm1DtVsDown.toTH1D("h1_gm1_dt_down", "VetoGm1 t2 - t0_down;ns")->Write();
        gm.h1Gm0LocMinusTim0.toTH1D("h1_gm0_loc_tim0", "VetoGm0 loc - Timing0 loc;ns")->Write();
        gm.h1Gm1LocMinusTim0.toTH1D("h1_gm1_loc_tim0", "VetoGm1 loc - Timing0 loc;ns")->Write();
        gm.h1RvnAllDenom.toTH1D("h1_rvn_denom", "rVN denom;mm")->Write();
        gm.h1RvnGm0Q20.toTH1D("h1_rvn_gm0_q20", "rVN VetoGm0 rawQ>20;mm")->Write();
        gm.h1RvnGm1Q20.toTH1D("h1_rvn_gm1_q20", "rVN VetoGm1 rawQ>20;mm")->Write();
        gm.h1RvnGmAnyQ20.toTH1D("h1_rvn_gmany_q20", "rVN VetoGm0|1 rawQ>20;mm")->Write();
        outFile->cd();
    }

    if (!gmRecs.empty()) {
        std::sort(gmRecs.begin(), gmRecs.end(), [](const T6VetoGmRecord& a, const T6VetoGmRecord& b) {
            if (a.run != b.run) return a.run < b.run;
            return a.eventID < b.eventID;
        });
        TTree* gt = new TTree("t6_vetogm_events", "Stage T6 unblinded SR-ZoneA / CR / EdgeVN VetoGm audit records");
        T6VetoGmRecord r{};
        gt->Branch("run", &r.run);
        gt->Branch("eventID", &r.eventID);
        gt->Branch("region", &r.region);
        gt->Branch("is_prescaled_prompt", &r.is_prescaled_prompt);
        gt->Branch("zone_a_era", &r.zone_a_era);
        gt->Branch("pass_wp_primary", &r.pass_wp_primary);
        gt->Branch("sample_weight", &r.sample_weight);
        gt->Branch("pz0_gev", &r.pz0_gev);
        gt->Branch("r_max", &r.r_max);
        gt->Branch("r_ift", &r.r_ift);
        gt->Branch("r_vn", &r.r_vn);
        gt->Branch("theta_mrad", &r.theta_mrad);
        gt->Branch("x_vn", &r.x_vn);
        gt->Branch("y_vn", &r.y_vn);
        gt->Branch("x_v1", &r.x_v1);
        gt->Branch("y_v1", &r.y_v1);
        gt->Branch("q0_raw", &r.q0_raw);
        gt->Branch("q1_raw", &r.q1_raw);
        gt->Branch("q0_red", &r.q0_red);
        gt->Branch("q1_red", &r.q1_red);
        gt->Branch("dt0", &r.dt0);
        gt->Branch("dt1", &r.dt1);
        gt->Branch("w0", &r.w0);
        gt->Branch("w1", &r.w1);
        gt->Branch("gm0_q_raw", &r.gm0_q_raw);
        gt->Branch("gm1_q_raw", &r.gm1_q_raw);
        gt->Branch("gm0_q_chg", &r.gm0_q_chg);
        gt->Branch("gm1_q_chg", &r.gm1_q_chg);
        gt->Branch("gm0_width", &r.gm0_width);
        gt->Branch("gm1_width", &r.gm1_width);
        gt->Branch("gm0_dt_down", &r.gm0_dt_down);
        gt->Branch("gm1_dt_down", &r.gm1_dt_down);
        gt->Branch("gm0_loc_tim0", &r.gm0_loc_tim0);
        gt->Branch("gm1_loc_tim0", &r.gm1_loc_tim0);
        gt->Branch("gm0_status", &r.gm0_status);
        gt->Branch("gm1_status", &r.gm1_status);
        for (const auto& item : gmRecs) {
            r = item;
            gt->Fill();
        }
        gt->Write();
    }

    outFile->Close();
}

void printUsage(const char* argv0) {
    std::cerr << "Usage: " << argv0
              << " --mode data|fluka|genie --output <out.root> --timing-calib <dir>"
              << " [(--task-ids <id1,id2,...> --manifest <json>) | --input-list <list.txt> | --input-files <f1,f2,...>]"
              << " [--aux-list <list.txt> | --aux-files <f1,f2,...>]"
              << " [--grl-config <yaml>] [--threads <n>] [--max-events <n>] [--summary-json <path>]\n";
}

} // namespace

int main(int argc, char* argv[]) {
    ROOT::EnableThreadSafety();
    TH1::AddDirectory(false);

    std::string mode;
    std::string outputPath;
    std::string summaryJsonPath;
    std::string calibDir = "AnalysisZipFramework/config/timing_calib";
    std::string manifestPath = "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json";
    std::string grlConfigPath = "AnalysisZipFramework/config/grl_config_run3_full.yaml";
    std::string taskIdsArg;
    std::string inputFilesArg;
    std::string inputListArg;
    std::string auxFilesArg;
    std::string auxListArg;
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
        else if (arg == "--summary-json") summaryJsonPath = needVal(arg);
        else if (arg == "--timing-calib") calibDir = needVal(arg);
        else if (arg == "--manifest") manifestPath = needVal(arg);
        else if (arg == "--grl-config") grlConfigPath = needVal(arg);
        else if (arg == "--task-ids") taskIdsArg = needVal(arg);
        else if (arg == "--input-files") inputFilesArg = needVal(arg);
        else if (arg == "--input-list") inputListArg = needVal(arg);
        else if (arg == "--aux-files") auxFilesArg = needVal(arg);
        else if (arg == "--aux-list") auxListArg = needVal(arg);
        else if (arg == "--threads" || arg == "-j") threads = std::stoi(needVal(arg));
        else if (arg == "--max-events") maxEvents = std::stoll(needVal(arg));
        else { printUsage(argv[0]); return 1; }
    }

    if ((mode != "data" && mode != "fluka" && mode != "genie") || outputPath.empty() ||
        (taskIdsArg.empty() && inputFilesArg.empty() && inputListArg.empty())) {
        printUsage(argv[0]);
        return 1;
    }

    const bool isMC = (mode != "data");
    const bool isGenie = (mode == "genie");
    const auto wallStart = std::chrono::steady_clock::now();

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

    std::unordered_set<int> brokenPsP0013Runs;
    std::unordered_set<int> deadVetoNuHvRuns = {20667, 20668, 20675, 20677};
    std::unordered_set<int> vetoGmActiveRuns;
    std::unordered_map<int, std::string> runWaveformGlobs;
    json manifestJson;
    bool hasManifestJson = false;
    if (!manifestPath.empty() && std::filesystem::exists(manifestPath)) {
        std::ifstream mifs(manifestPath);
        if (!mifs.is_open()) throw std::runtime_error("Cannot open manifest: " + manifestPath);
        manifestJson = json::parse(mifs);
        hasManifestJson = true;
        if (manifestJson.contains("runs")) {
            for (auto itR = manifestJson.at("runs").begin(); itR != manifestJson.at("runs").end(); ++itR) {
                const int r = std::stoi(itR.key());
                const auto& meta = itR.value();
                if (meta.value("broken_ps_p0013", false)) brokenPsP0013Runs.insert(r);
                if (meta.value("dead_vetonu_hv", false)) deadVetoNuHvRuns.insert(r);
                if (meta.value("vetogm_active", false)) vetoGmActiveRuns.insert(r);
                const std::string wg = meta.value("waveform_glob", std::string(""));
                if (!wg.empty()) runWaveformGlobs[r] = wg;
            }
        }
    }

    std::shared_ptr<const GRLUtils::GRLTimes> grlTimes;
    if (!isMC) {
        const auto grlCfg = ConfigUtils::readGRLConfig(grlConfigPath);
        grlTimes = std::make_shared<const GRLUtils::GRLTimes>(
            GRLUtils::readGRLTimes(GRLUtils::toTStringVector(grlCfg.grlJsons)));
    }

    std::vector<std::string> files;
    std::set<int> autoAuxRuns;
    if (!inputFilesArg.empty()) {
        auto s = splitCommaList(inputFilesArg);
        files.insert(files.end(), s.begin(), s.end());
    }
    if (!inputListArg.empty()) {
        auto s = readListFile(inputListArg);
        files.insert(files.end(), s.begin(), s.end());
    }
    if (!taskIdsArg.empty()) {
        if (!hasManifestJson) throw std::runtime_error("Cannot open manifest: " + manifestPath);
        const std::string dqPath = manifestJson.at("source_dq_manifest").get<std::string>();
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
            if (dqTasks.at(tid).contains("run")) autoAuxRuns.insert(dqTasks.at(tid).at("run").get<int>());
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
        int firstRun = 0;
        if (!probeFileSchema(f, sig, &firstRun)) {
            ++nSkippedEmpty;
            continue;
        }
        if (firstRun > 0) autoAuxRuns.insert(firstRun);
        auto& g = groups[sig.key()];
        g.sig = sig;
        g.files.push_back(f);
    }

    std::vector<std::string> auxFilesRaw;
    if (!auxFilesArg.empty()) {
        auto s = splitCommaList(auxFilesArg);
        auxFilesRaw.insert(auxFilesRaw.end(), s.begin(), s.end());
    }
    if (!auxListArg.empty()) {
        auto s = readListFile(auxListArg);
        auxFilesRaw.insert(auxFilesRaw.end(), s.begin(), s.end());
    }
    if (!isMC && auxFilesRaw.empty()) {
        for (int r : autoAuxRuns) {
            auto itWg = runWaveformGlobs.find(r);
            if (itWg == runWaveformGlobs.end()) continue;
            for (const auto& matched : expandLocalGlob(itWg->second)) {
                auxFilesRaw.push_back(toXrootdUrl(matched));
            }
        }
    }
    std::vector<std::string> auxFiles;
    {
        std::unordered_set<std::string> seenAux;
        for (const auto& af : auxFilesRaw) {
            if (seenAux.insert(af).second) auxFiles.push_back(af);
        }
    }
    if (!isMC && !groups.empty() && auxFiles.empty()) {
        throw std::runtime_error(
            "Data mode requires aux reduced-charge files (--aux-files, --aux-list, or waveform_glob in manifest).");
    }

    const auto auxLoadStart = std::chrono::steady_clock::now();
    const std::vector<AuxLookupRow> auxRows = groups.empty() ? std::vector<AuxLookupRow>{} : loadAuxRows(auxFiles, threads);
    const double auxLoadS = std::chrono::duration<double>(std::chrono::steady_clock::now() - auxLoadStart).count();
    if (!auxFiles.empty()) {
        INFO("Loaded ", auxRows.size(), " aux reduced-charge rows from ", auxFiles.size(),
             " files in ", auxLoadS, " s");
    }
    const bool hasAux = !auxRows.empty();
    std::atomic<uint64_t> nMissingAux{0};
    std::mutex missingAuxMtx;
    std::string firstMissingAuxMsg;

    if (threads > 1 && maxEvents <= 0) {
        ROOT::EnableImplicitMT(static_cast<unsigned int>(threads));
    } else if (threads > 1 && maxEvents > 0) {
        threads = 1;
    }
    const unsigned int nSlots = std::max(1u, ROOT::GetThreadPoolSize());

    std::map<int, T6RunStats> mergedRuns;
    std::map<std::string, T6Ps23Group> mergedPsGroups;
    std::map<std::string, T6VetoGmMaps> mergedGmMaps;
    std::vector<T6VetoGmRecord> mergedGmRecs;

    const int iVN0 = static_cast<int>(TimingChannel::VetoNu0);
    const int iVN1 = static_cast<int>(TimingChannel::VetoNu1);
    const int iTim01 = static_cast<int>(TimingChannel::Timing01);
    const int iPS0 = static_cast<int>(TimingChannel::Preshower0);
    const int iPS1 = static_cast<int>(TimingChannel::Preshower1);
    const int iPS2 = static_cast<int>(TimingChannel::Preshower2);
    const int iPS3 = static_cast<int>(TimingChannel::Preshower3);
    const int iMuon0 = static_cast<int>(TimingChannel::Muon0);
    const int iMuon1 = static_cast<int>(TimingChannel::Muon1);

    for (const auto& [skey, grp] : groups) {
        const SchemaSignature sig = grp.sig;
        const bool effectiveHasRedQ = sig.hasReducedCharge || hasAux;
        TChain chain("nt");
        for (const auto& f : grp.files) chain.Add(f.c_str());
        INFO("T6 mode=", mode, " group (", skey, "): ", grp.files.size(), " files, slots=", nSlots);

        ROOT::RDF::RNode df = ROOT::RDataFrame(chain);
        if (maxEvents > 0) df = df.Range(static_cast<ULong64_t>(maxEvents));

        const auto allCols = df.GetColumnNames();
        std::unordered_set<std::string> colSet(allCols.begin(), allCols.end());
        auto hasCol = [&](const std::string& name) { return colSet.count(name) > 0; };

        if (sig.hasVetoSt) {
            for (const auto& c : allCols) {
                if (c.rfind("VetoSt", 0) != 0) continue;
                const std::string alias = "Veto" + c.substr(6);
                if (!hasCol(alias)) {
                    df = df.Alias(alias, c);
                    colSet.insert(alias);
                }
            }
        }
        if (sig.hasTimeNotLocaltime) {
            for (const char* p : {"VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21",
                                  "Timing0", "Timing1", "Timing2", "Timing3",
                                  "Preshower0", "Preshower1", "Preshower2", "Preshower3",
                                  "Muon0", "Muon1"}) {
                const std::string loc = std::string(p) + "_localtime";
                const std::string tm = std::string(p) + "_time";
                if (!hasCol(loc) && hasCol(tm)) {
                    df = df.Alias(loc, tm);
                    colSet.insert(loc);
                }
            }
        }

        auto ensureInt = [&](const std::string& name, Int_t val) {
            if (!hasCol(name)) {
                df = df.Define(name, [val]() -> Int_t { return val; }, {});
                colSet.insert(name);
            }
        };
        auto ensureFloat = [&](const std::string& name, Float_t val) {
            if (!hasCol(name)) {
                df = df.Define(name, [val]() -> Float_t { return val; }, {});
                colSet.insert(name);
            }
        };
        auto ensureRVecD = [&](const std::string& name) {
            if (!hasCol(name)) {
                df = df.Define(name, []() { return ROOT::VecOps::RVec<double>{}; }, {});
                colSet.insert(name);
            }
        };

        ensureInt("distanceToCollidingBCID", 0);
        ensureInt("inputBits", 0);
        ensureFloat("crossingAngle", 0.0f);
        ensureInt("fillNumber", -1);

        if (sig.eventTimeType == "Int_t" || sig.eventTimeType == "int") {
            df = attachGrlGoodColumn<Int_t>(df, grlTimes, isMC);
        } else if (sig.eventTimeType == "UInt_t" || sig.eventTimeType == "unsigned int") {
            df = attachGrlGoodColumn<UInt_t>(df, grlTimes, isMC);
        } else if (sig.eventTimeType == "Long64_t" || sig.eventTimeType == "long long") {
            df = attachGrlGoodColumn<Long64_t>(df, grlTimes, isMC);
        } else {
            df = attachGrlGoodColumn<ULong64_t>(df, grlTimes, isMC);
        }

        // Upstream scalar pre-statistics + filter: avoids deserializing heavy track/waveform branches on ~95% of events
        std::vector<std::unordered_map<int, RunPreStats>> slotPre(nSlots);
        df = df.Define("_keep_pre",
            [&slotPre, isMC](unsigned int slot, Int_t run, bool grlGood,
                             Int_t distColl, Int_t inputBits, Int_t longTracks,
                             Float_t ca, Int_t fillNum) -> bool {
                auto& ps = slotPre[slot][run];
                if (!ps.initialized) { ps.initialized = true; ps.run = run; }
                ++ps.nTotal;
                if (!isMC && !grlGood) return false;
                ++ps.nGrlPass;
                const bool isColl = isMC || (distColl == 0);
                if (isColl) {
                    ++ps.nColliding;
                    if (std::isfinite(ca) && std::abs(ca) > 1.0f && std::abs(ca) < 1000.0f) {
                        ps.caSum += ca;
                        ps.caSum2 += static_cast<double>(ca) * ca;
                        ++ps.caCnt;
                    }
                    if (fillNum > 0) {
                        ++ps.fillCounts[fillNum];
                    }
                }
                const bool passTrig = isMC ||
                    ((inputBits & 0x8) != 0) || ((inputBits & 0x10) != 0) ||
                    ((inputBits & 0x20) != 0) || ((inputBits & 0x40) != 0);
                if (isColl && passTrig) {
                    ++ps.nPhysTrig;
                    if ((inputBits & 0x8) != 0) ++ps.nTrigBit8;
                    if ((inputBits & 0x10) != 0) ++ps.nTrigBit16;
                    if ((inputBits & 0x20) != 0) ++ps.nTrigBit32;
                    if ((inputBits & 0x40) != 0) ++ps.nTrigBit64;
                }
                if (!(isColl && passTrig && longTracks > 0)) return false;
                ++ps.nLongTrk;
                return true;
            },
            {"rdfslot_", "run", "_grl_good", "distanceToCollidingBCID", "inputBits", "longTracks", "crossingAngle", "fillNumber"})
            .Filter([](bool k) { return k; }, {"_keep_pre"});

        for (const char* p : {"VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21",
                              "Timing0", "Timing1", "Timing2", "Timing3",
                              "Preshower0", "Preshower1", "Preshower2", "Preshower3",
                              "Muon0", "Muon1", "VetoGm0", "VetoGm1"}) {
            const std::string sp(p);
            ensureInt(sp + "_status", -1);
            ensureFloat(sp + "_bcidtime", kNaNF);
            ensureFloat(sp + "_triggertime", kNaNF);
            ensureFloat(sp + "_localtime", kNaNF);
            ensureFloat(sp + "_raw_charge", kNaNF);
            ensureFloat(sp + "_width", kNaNF);
            ensureFloat(sp + "_charge", kNaNF);
        }
        ensureFloat("VetoNu0_reduced_charge", -1.0f);
        ensureFloat("VetoNu1_reduced_charge", -1.0f);
        ensureRVecD("Track_X_atMuon1"); ensureRVecD("Track_Y_atMuon1");
        ensureRVecD("Track_X_atMuon2"); ensureRVecD("Track_Y_atMuon2");
        ensureRVecD("truth_dec_z");

        if (sig.nLayersType.find("unsigned") != std::string::npos || sig.nLayersType.find("uint") != std::string::npos) {
            df = attachTrackDataColumn<unsigned int>(df);
        } else {
            df = attachTrackDataColumn<int>(df);
        }

        auto fillSlot = [](TimingCalib::RawChannelInput& slotIn,
                           bool present, int planeIdx, const ScannerTrackData& tk,
                           Int_t st, Float_t bcid, Float_t trig, Float_t loc, Float_t qRaw, Float_t w) {
            slotIn.present = present;
            slotIn.goodStatus = present && TimingCalibrator::isGoodWaveformStatus(st);
            slotIn.bcidTime = bcid;
            slotIn.triggerTime = trig;
            slotIn.localTime = loc;
            slotIn.rawCharge = qRaw;
            slotIn.width = w;
            slotIn.xMm = tk.x[planeIdx];
            slotIn.yMm = tk.y[planeIdx];
            slotIn.validPos = tk.validPos[planeIdx];
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

        df = df.Define("_gm",
            [](Int_t g0_st, Float_t g0_b, Float_t g0_t, Float_t g0_l, Float_t g0_qr, Float_t g0_qc, Float_t g0_w,
               Int_t g1_st, Float_t g1_b, Float_t g1_t, Float_t g1_l, Float_t g1_qr, Float_t g1_qc, Float_t g1_w) -> ScannerVetoGmRaw {
                return ScannerVetoGmRaw{g0_st, g1_st, g0_b, g0_t, g0_l, g0_qr, g0_qc, g0_w,
                                        g1_b, g1_t, g1_l, g1_qr, g1_qc, g1_w};
            },
            {"VetoGm0_status", "VetoGm0_bcidtime", "VetoGm0_triggertime", "VetoGm0_localtime", "VetoGm0_raw_charge", "VetoGm0_charge", "VetoGm0_width",
             "VetoGm1_status", "VetoGm1_bcidtime", "VetoGm1_triggertime", "VetoGm1_localtime", "VetoGm1_raw_charge", "VetoGm1_charge", "VetoGm1_width"});

        df = df.Define("_aux",
            [sig, isGenie](Int_t run,
                           Float_t v20, Float_t v21,
                           Float_t t0, Float_t t1, Float_t t2, Float_t t3,
                           Float_t p0, Float_t p1,
                           Float_t vn0red, Float_t vn1red,
                           Int_t vn0st, Int_t vn1st, Int_t v20st, Int_t v21st,
                           Int_t ps0st, Int_t ps1st,
                           Int_t t0st, Int_t t1st, Int_t t2st, Int_t t3st,
                           const ROOT::VecOps::RVec<double>& tdz) -> ScannerEventAux {
                ScannerEventAux a;
                a.veto20Charge = v20;
                a.veto21Charge = v21;
                a.timingBottomCharge = t0 + t1;
                a.timingTopCharge = t2 + t3;
                a.preshower0Charge = p0;
                a.preshower1Charge = p1;
                a.vetoNu0ReducedCharge = sig.hasReducedCharge ? vn0red : -1.0f;
                a.vetoNu1ReducedCharge = sig.hasReducedCharge ? vn1red : -1.0f;
                a.vn0Status = vn0st;
                a.vn1Status = vn1st;
                a.v20Status = v20st;
                a.v21Status = v21st;
                a.ps0Status = ps0st;
                a.ps1Status = ps1st;
                a.t0Status = t0st;
                a.t1Status = t1st;
                a.t2Status = t2st;
                a.t3Status = t3st;
                a.genieVetoCaloNu = isGenie && isGenieCaloNuRun(run) && !tdz.empty() && inCaloNuPMTExact(tdz[0]);
                return a;
            },
            {"run",
             "Veto20_charge", "Veto21_charge",
             "Timing0_charge", "Timing1_charge", "Timing2_charge", "Timing3_charge",
             "Preshower0_charge", "Preshower1_charge",
             "VetoNu0_reduced_charge", "VetoNu1_reduced_charge",
             "VetoNu0_status", "VetoNu1_status", "Veto20_status", "Veto21_status",
             "Preshower0_status", "Preshower1_status",
             "Timing0_status", "Timing1_status", "Timing2_status", "Timing3_status",
             "truth_dec_z"});

        std::vector<std::unordered_map<int, T6RunStats>> slotRuns(nSlots);
        std::vector<std::unordered_map<std::string, T6Ps23Group>> slotPsGroups(nSlots);
        std::vector<std::unordered_map<std::string, T6VetoGmMaps>> slotGmMaps(nSlots);
        std::vector<std::vector<T6VetoGmRecord>> slotGmRecs(nSlots);

        df.ForeachSlot(
            [&](unsigned int slot,
                Int_t run,
                Int_t eventID,
                const ScannerTrackData& tk,
                const RawInputArray& raw,
                const ScannerVetoGmRaw& gm,
                const ScannerEventAux& aux) {

                const bool brokenPs = !isMC && !sig.hasReducedCharge && (brokenPsP0013Runs.count(run) > 0);
                const bool deadVn = !isMC && (deadVetoNuHvRuns.count(run) > 0);
                auto& rs = slotRuns[slot][run];
                if (!rs.initialized) {
                    rs.init(run, isMC, effectiveHasRedQ, sig.hasPreshower23, sig.hasVetoGm, brokenPs, deadVn);
                }

                if (isGenie && aux.genieVetoCaloNu) return;

                const bool hasRunOffsets = isMC || (calibratedDataRuns.count(run) > 0);
                if (!hasRunOffsets) ++rs.nNoOffsets;

                const bool passCaloNuClean = isMC ||
                    !(15821 <= run && run <= 16924) ||
                    (!(aux.v20Status == 528 || aux.v21Status == 528) &&
                     (((aux.vn0Status == 0 || aux.vn0Status == 1) && (aux.vn1Status == 0 || aux.vn1Status == 1)) ||
                      (aux.vn0Status == 0 && aux.vn1Status == 16)));
                if (!passCaloNuClean) return;

                const bool hitsTimingNom = tk.validPos[3] && std::isfinite(tk.y[3]) && (
                    (tk.y[3] > 20.0 && std::isfinite(aux.timingTopCharge) && aux.timingTopCharge > 20.0f) ||
                    (tk.y[3] < -20.0 && std::isfinite(aux.timingBottomCharge) && aux.timingBottomCharge > 20.0f) ||
                    (std::abs(tk.y[3]) <= 20.0 &&
                     std::isfinite(aux.timingTopCharge) && std::isfinite(aux.timingBottomCharge) &&
                     (aux.timingTopCharge + aux.timingBottomCharge) > 20.0f));
                if (!hitsTimingNom) return;

                if (!std::isfinite(aux.veto20Charge) || aux.veto20Charge <= 40.0f ||
                    !std::isfinite(aux.veto21Charge) || aux.veto21Charge <= 40.0f) {
                    return;
                }

                const float ps0Eff = (brokenPs && (!std::isfinite(aux.preshower0Charge) || aux.preshower0Charge <= 0.0f) &&
                                      std::isfinite(raw[iPS0].rawCharge))
                    ? (kPsScale2025 * static_cast<float>(raw[iPS0].rawCharge))
                    : aux.preshower0Charge;
                const float ps1Eff = (brokenPs && (!std::isfinite(aux.preshower1Charge) || aux.preshower1Charge <= 0.0f) &&
                                      std::isfinite(raw[iPS1].rawCharge))
                    ? (kPsScale2025 * static_cast<float>(raw[iPS1].rawCharge))
                    : aux.preshower1Charge;

                const bool passPsNom = std::isfinite(aux.preshower0Charge) && aux.preshower0Charge > 2.5f &&
                                       std::isfinite(aux.preshower1Charge) && aux.preshower1Charge > 2.5f;
                const bool passPsEff = std::isfinite(ps0Eff) && ps0Eff > 2.5f &&
                                       std::isfinite(ps1Eff) && ps1Eff > 2.5f;
                if (!passPsNom && !passPsEff) return;

                const bool passLeadTrk =
                    tk.nTracks > 0 &&
                    std::isfinite(tk.leadPz0GeV) && tk.leadPz0GeV > 100.0 &&
                    tk.leadNLayersU >= 7 &&
                    std::isfinite(tk.leadNDoF) && tk.leadNDoF >= 9.0 &&
                    std::isfinite(tk.leadChi2NDF) && tk.leadChi2NDF < 15.0;
                if (!passLeadTrk) return;

                const double rMax = tk.leadRMax;
                const double rIFT = tk.validPos[2] ? std::hypot(tk.x[2], tk.y[2]) : kNaN;
                const double rVN = tk.validPos[0] ? std::hypot(tk.x[0], tk.y[0]) : kNaN;
                const double theta = tk.leadThetaMrad;
                if (!std::isfinite(rMax) || !std::isfinite(rIFT) || !std::isfinite(rVN) || !std::isfinite(theta)) {
                    return;
                }

                uint8_t region = 0;
                if (rMax < 95.0 && rIFT < 95.0 && theta < 25.0 && rVN < 120.0) {
                    region = REG_KIN_SR;
                } else if (rVN < 120.0 && theta < 25.0 && rMax < 135.0 && rIFT < 135.0 &&
                           ((rMax >= 95.0 && rMax < 135.0) || (rIFT >= 95.0 && rIFT < 135.0))) {
                    region = REG_CR_GEOM_OUTER;
                } else if (rVN < 120.0 && rMax < 135.0 && rIFT < 135.0 && theta >= 25.0 && theta < 55.0) {
                    region = REG_CR_GEOM_HITHETA;
                } else if (rMax < 95.0 && rIFT < 95.0 && theta < 25.0 && rVN >= 120.0 && rVN < 180.0) {
                    region = REG_CR_EDGE_VN;
                } else if (sig.hasVetoGm && rMax < 135.0 && rIFT < 135.0 && theta < 55.0 && rVN >= 120.0 && rVN < 280.0) {
                    region = REG_CR_HALO_VN;
                }
                if (region == 0) return;

                // Resolve aux reduced charge BEFORE blinding check
                float vn0RedVal = aux.vetoNu0ReducedCharge;
                float vn1RedVal = aux.vetoNu1ReducedCharge;
                if (hasAux) {
                    const uint64_t aKey = makeAuxLookupKey(run, eventID);
                    auto itAux = std::lower_bound(auxRows.begin(), auxRows.end(), AuxLookupRow{aKey, 0.0f, 0.0f});
                    if (itAux == auxRows.end() || itAux->key != aKey) {
                        const uint64_t prevMiss = nMissingAux.fetch_add(1, std::memory_order_relaxed);
                        if (prevMiss == 0) {
                            std::lock_guard<std::mutex> lk(missingAuxMtx);
                            firstMissingAuxMsg = "run=" + std::to_string(run) + ", eventID=" + std::to_string(eventID);
                        }
                        vn0RedVal = -99999.0f;
                        vn1RedVal = -99999.0f;
                    } else {
                        auto isStrictGoodStatus = [](int32_t st) { return (st & ~512) == 0; };
                        const bool v20Good = isStrictGoodStatus(aux.v20Status);
                        const bool v21Good = isStrictGoodStatus(aux.v21Status);
                        const bool psGood = isStrictGoodStatus(aux.ps0Status) ||
                                            isStrictGoodStatus(aux.ps1Status);
                        const bool trigGood = isStrictGoodStatus(aux.t0Status) ||
                                              isStrictGoodStatus(aux.t1Status) ||
                                              isStrictGoodStatus(aux.t2Status) ||
                                              isStrictGoodStatus(aux.t3Status);
                        const bool timingOK = (run < 18500)
                            ? (v20Good || v21Good || psGood)
                            : (v20Good || v21Good || trigGood || (!brokenPs && psGood));
                        const bool isZeroBug0 = (itAux->q0 == 0.0f) && (raw[iVN0].rawCharge > 30.0);
                        const bool isZeroBug1 = (itAux->q1 == 0.0f) && (raw[iVN1].rawCharge > 30.0);
                        vn0RedVal = (!timingOK || std::isnan(itAux->q0) || isZeroBug0) ? -1.0f : std::max(itAux->q0, 0.0f);
                        vn1RedVal = (!timingOK || std::isnan(itAux->q1) || isZeroBug1) ? -1.0f : std::max(itAux->q1, 0.0f);
                    }
                }

                // Calibrate event timing under both downstream masks (withPS23 vs noPS23)
                const TimingCalib::EventTimingOutput evt = isMC
                    ? calib->calibrateMCEvent(run, static_cast<int64_t>(eventID), raw, true, true)
                    : (hasRunOffsets
                        ? calib->calibrateDataEvent(run, raw, calib->hasTofMaps(), true)
                        : TimingCalib::EventTimingOutput{});
                const double leadYTrig = tk.validPos[3] ? tk.y[3] : kNaN;
                const auto downW = TimingCalibrator::fitDownstreamReferenceMode(
                    evt, DownstreamMode::Trimmed3Sigma, leadYTrig, &raw, kMaskDownWithPS23, 0u);
                const auto downN = TimingCalibrator::fitDownstreamReferenceMode(
                    evt, DownstreamMode::Trimmed3Sigma, leadYTrig, &raw, kMaskDownNoPS23, 0u);

                const bool c0V = evt.channels[iVN0].valid;
                const bool c1V = evt.channels[iVN1].valid;
                const double dt0W = (downW.valid && c0V) ? (evt.channels[iVN0].tCalNs - downW.t0Ns) : kNaN;
                const double dt1W = (downW.valid && c1V) ? (evt.channels[iVN1].tCalNs - downW.t0Ns) : kNaN;
                const double dt0N = (downN.valid && c0V) ? (evt.channels[iVN0].tCalNs - downN.t0Ns) : kNaN;
                const double dt1N = (downN.valid && c1V) ? (evt.channels[iVN1].tCalNs - downN.t0Ns) : kNaN;

                // MANDATORY SUPERSET ORTHOGONAL BLINDING CHECK FOR COLLISION DATA
                auto makeBlindStruct = [&](float ps0Val, float ps1Val) {
                    TimingBlinding::EventKinematicsAndVeto ev;
                    ev.isMC = isMC;
                    ev.distanceToCollidingBCID = 0;
                    ev.longTracks = tk.nTracks;
                    ev.veto20Charge = aux.veto20Charge;
                    ev.veto21Charge = aux.veto21Charge;
                    ev.timingChargeTop = aux.timingTopCharge;
                    ev.timingChargeBottom = aux.timingBottomCharge;
                    ev.preshower0Charge = ps0Val;
                    ev.preshower1Charge = ps1Val;
                    ev.leadYatTrig = leadYTrig;
                    ev.leadPz0GeV = tk.leadPz0GeV;
                    ev.leadNLayers = tk.leadNLayersU;
                    ev.leadNDoF = tk.leadNDoF;
                    ev.leadChi2NDF = tk.leadChi2NDF;
                    ev.leadRMax = rMax;
                    ev.leadRIFT = rIFT;
                    ev.leadRVetoNu = rVN;
                    ev.leadThetaMrad = theta;
                    ev.vetoNu0RawCharge = static_cast<float>(raw[iVN0].rawCharge);
                    ev.vetoNu1RawCharge = static_cast<float>(raw[iVN1].rawCharge);
                    ev.vetoNu0ReducedCharge = vn0RedVal;
                    ev.vetoNu1ReducedCharge = vn1RedVal;
                    return ev;
                };
                const auto blindNom = makeBlindStruct(aux.preshower0Charge, aux.preshower1Charge);
                const auto blindEff = makeBlindStruct(ps0Eff, ps1Eff);
                const bool blinded =
                    TimingBlinding::isBlindedSRZoneB(blindNom, true, downW.valid, c0V, dt0W, c1V, dt1W) ||
                    TimingBlinding::isBlindedSRZoneB(blindNom, true, downN.valid, c0V, dt0N, c1V, dt1N) ||
                    TimingBlinding::isBlindedSRZoneB(blindEff, true, downW.valid, c0V, dt0W, c1V, dt1W) ||
                    TimingBlinding::isBlindedSRZoneB(blindEff, true, downN.valid, c0V, dt0N, c1V, dt1N);
                if (blinded) {
                    ++rs.nBlinded;
                    return;
                }

                const bool za0Red = effectiveHasRedQ
                    ? ((vn0RedVal >= 0.0f) ? (vn0RedVal < 30.0f) : (raw[iVN0].rawCharge < 40.0))
                    : (raw[iVN0].rawCharge < 40.0);
                const bool za1Red = effectiveHasRedQ
                    ? ((vn1RedVal >= 0.0f) ? (vn1RedVal < 30.0f) : (raw[iVN1].rawCharge < 40.0))
                    : (raw[iVN1].rawCharge < 40.0);
                const bool za0Raw = (raw[iVN0].rawCharge < 40.0);
                const bool za1Raw = (raw[iVN1].rawCharge < 40.0);
                const bool zoneARed = za0Red && za1Red;
                const bool zoneARaw = za0Raw && za1Raw;
                const bool useRaw40Era = !effectiveHasRedQ;
                const bool za0Era = useRaw40Era ? za0Raw : za0Red;
                const bool za1Era = useRaw40Era ? za1Raw : za1Red;
                const bool zoneAEra = za0Era && za1Era;

                if (region == REG_KIN_SR && !isMC) {
                    const bool bAct0 = TimingBlinding::isVetoNuZoneBActive(static_cast<float>(raw[iVN0].rawCharge), vn0RedVal);
                    const bool bAct1 = TimingBlinding::isVetoNuZoneBActive(static_cast<float>(raw[iVN1].rawCharge), vn1RedVal);
                    if ((bAct0 && (!c0V || !downW.valid || !downN.valid || !std::isfinite(dt0W) || !std::isfinite(dt0N) || dt0W > 1.5 || dt0N > 1.5)) ||
                        (bAct1 && (!c1V || !downW.valid || !downN.valid || !std::isfinite(dt1W) || !std::isfinite(dt1N) || dt1W > 1.5 || dt1N > 1.5))) {
                        throw std::logic_error("TimingBlinding invariant violated in T6 REG_KIN_SR!");
                    }
                    if (!zoneAEra && (!downW.valid || !downN.valid || !c0V || !c1V || dt0W > 1.5 || dt1W > 1.5 || dt0N > 1.5 || dt1N > 1.5)) {
                        ++rs.nBlinded;
                        return;
                    }
                }

                // Downstream reference quality + WP_Primary evaluator helper
                auto evalDownOk = [](const TimingCalib::DownstreamRefResult& d) -> bool {
                    const double c2nd = d.valid ? (d.chi2 / static_cast<double>(std::max(1, d.ndof))) : kNaN;
                    return d.valid && d.nUsed >= 2 && std::isfinite(d.t0Ns) && std::abs(d.t0Ns) < 2.5 &&
                           (d.ndof <= 0 || c2nd < 10.0);
                };
                const bool downOkW = evalDownOk(downW);
                const bool downOkN = evalDownOk(downN);

                const double qMaxVn = std::max(raw[iVN0].rawCharge, raw[iVN1].rawCharge);
                auto waveOk16 = [&](int idx, double dtVal) -> bool {
                    return evt.channels[idx].valid && std::isfinite(dtVal) &&
                           std::isfinite(raw[idx].width) && raw[idx].width > 1.5 && raw[idx].width < 16.0;
                };

                auto passWpPrimary = [&](bool downOkFlag, double dt0Val, double dt1Val) -> bool {
                    if (zoneAEra) return true;
                    if (!downOkFlag) return false;
                    const bool actWaveOk = (za0Era || waveOk16(iVN0, dt0Val)) && (za1Era || waveOk16(iVN1, dt1Val));
                    if (!actWaveOk) return false;
                    const int nAct = (za0Era ? 0 : 1) + (za1Era ? 0 : 1);
                    if (nAct == 2) {
                        return (qMaxVn < 180.0) && (dt0Val > 4.0 && dt0Val < 18.0) && (dt1Val > 4.0 && dt1Val < 18.0);
                    }
                    if (nAct == 1) {
                        const double dtAct = (!za0Era) ? dt0Val : dt1Val;
                        return (dtAct > 3.0 && dtAct < 18.0);
                    }
                    return false;
                };
                const bool wpPrimWith = passWpPrimary(downOkW, dt0W, dt1W);
                const bool wpPrimNo = passWpPrimary(downOkN, dt0N, dt1N);

                const auto downA = TimingCalibrator::fitDownstreamReferenceMode(
                    evt, DownstreamMode::Trimmed3Sigma, leadYTrig, &raw, kMaskDownA, 0u);
                const auto downBn = TimingCalibrator::fitDownstreamReferenceMode(
                    evt, DownstreamMode::Trimmed3Sigma, leadYTrig, &raw, kMaskDownBNoPS23, 0u);
                const auto downBw = TimingCalibrator::fitDownstreamReferenceMode(
                    evt, DownstreamMode::Trimmed3Sigma, leadYTrig, &raw, kMaskDownBWithPS23, 0u);
                const bool downAOk = downA.valid && downA.nUsed >= 1 && (downA.ndof <= 0 || (downA.chi2 / std::max(1, downA.ndof)) < 5.0);
                const bool downBnOk = downBn.valid && downBn.nUsed >= 1 && (downBn.ndof <= 0 || (downBn.chi2 / std::max(1, downBn.ndof)) < 5.0);
                const bool downBwOk = downBw.valid && downBw.nUsed >= 1 && (downBw.ndof <= 0 || (downBw.chi2 / std::max(1, downBw.ndof)) < 5.0);
                const double u0 = (downA.valid && c0V) ? (evt.channels[iVN0].tCalNs - downA.t0Ns) : kNaN;
                const double u1No = (downBn.valid && c1V) ? (evt.channels[iVN1].tCalNs - downBn.t0Ns) : kNaN;
                const double u1With = (downBw.valid && c1V) ? (evt.channels[iVN1].tCalNs - downBw.t0Ns) : kNaN;

                // Per-run yields (clean nominal vs broken-PS repaired)
                if (region == REG_KIN_SR || region == REG_CR_GEOM_OUTER || region == REG_CR_GEOM_HITHETA) {
                    if (passPsNom) ++rs.nClean1TrkNom;
                    if (passPsEff) ++rs.nClean1TrkEff;
                }
                const bool v0Mip = raw[iVN0].present && raw[iVN0].rawCharge >= 30.0;
                const bool v1Mip = raw[iVN1].present && raw[iVN1].rawCharge >= 30.0;

                if (region == REG_KIN_SR) {
                    if (passPsNom) {
                        if (zoneARed) ++rs.nSrZoneARed30Nom;
                        if (zoneARaw) ++rs.nSrZoneARaw40Nom;
                        if (zoneAEra) ++rs.nSrZoneAEraNom;
                        if (!zoneAEra && downOkW && ((c0V && std::abs(dt0W) <= 1.5) || (c1V && std::abs(dt1W) <= 1.5))) {
                            ++rs.nCrPromptAllNom;
                        }
                        if (downOkW && c0V && c1V && v0Mip && v1Mip &&
                            raw[iVN0].width > 1.5 && raw[iVN0].width < 19.5 &&
                            raw[iVN1].width > 1.5 && raw[iVN1].width < 19.5 &&
                            std::abs(dt0W) < 1.5 && std::abs(dt1W) < 1.5) {
                            ++rs.nCrPrompt2HitNom;
                        }
                        if (downAOk && downBwOk && c0V && c1V && v0Mip && v1Mip &&
                            std::abs(u0) < 1.0 && std::abs(u1With) < 1.0) {
                            ++rs.nCrPromptU1p0Nom;
                        }
                    }
                    if (passPsEff) {
                        if (zoneARed) ++rs.nSrZoneARed30Eff;
                        if (zoneAEra) ++rs.nSrZoneAEraEff;
                        if (!zoneAEra && downOkW && ((c0V && std::abs(dt0W) <= 1.5) || (c1V && std::abs(dt1W) <= 1.5))) {
                            ++rs.nCrPromptAllEff;
                        }
                        if (downOkW && c0V && c1V && v0Mip && v1Mip &&
                            raw[iVN0].width > 1.5 && raw[iVN0].width < 19.5 &&
                            raw[iVN1].width > 1.5 && raw[iVN1].width < 19.5 &&
                            std::abs(dt0W) < 1.5 && std::abs(dt1W) < 1.5) {
                            ++rs.nCrPrompt2HitEff;
                        }
                    }
                } else if (region == REG_CR_GEOM_OUTER || region == REG_CR_GEOM_HITHETA) {
                    if (passPsNom) {
                        ++rs.nCrGeomAllNom;
                        if (zoneAEra) ++rs.nCrGeomZoneANom;
                        if (downOkW && c0V && c1V && v0Mip && v1Mip && std::abs(dt0W) < 1.5 && std::abs(dt1W) < 1.5) {
                            ++rs.nCrGeomPromptNom;
                        }
                        if (!zoneAEra && wpPrimWith) ++rs.nCrGeomWpPrimaryWithNom;
                        if (!zoneAEra && wpPrimNo) ++rs.nCrGeomWpPrimaryNoNom;
                    }
                    if (passPsEff) {
                        ++rs.nCrGeomAllEff;
                        if (downOkW && c0V && c1V && v0Mip && v1Mip && std::abs(dt0W) < 1.5 && std::abs(dt1W) < 1.5) {
                            ++rs.nCrGeomPromptEff;
                        }
                        if (!zoneAEra && wpPrimWith) ++rs.nCrGeomWpPrimaryEff;
                    }
                } else if (region == REG_CR_EDGE_VN) {
                    if (passPsNom) {
                        ++rs.nCrEdgeVnAllNom;
                        if (zoneAEra) ++rs.nCrEdgeVnZoneANom;
                        else ++rs.nCrEdgeVnZoneBNom;
                        if (!zoneAEra && wpPrimWith) ++rs.nCrEdgeVnWpPrimaryNom;
                    }
                    if (passPsEff) {
                        ++rs.nCrEdgeVnAllEff;
                    }
                }

                // Per-run timing resolution moments & PS2/3 comparison (use passPsEff so p0013 broken runs have full muon statistics)
                const bool isPromptMuonLike = passPsEff &&
                    (region == REG_KIN_SR || region == REG_CR_GEOM_OUTER || region == REG_CR_GEOM_HITHETA || region == REG_CR_EDGE_VN) &&
                    !zoneAEra;
                const bool isV2Sat = ((aux.v20Status & 4) != 0) || ((aux.v21Status & 4) != 0);
                const bool isNoMuon = (!evt.channels[iMuon0].valid) && (!evt.channels[iMuon1].valid);

                if (isPromptMuonLike) {
                    if (downOkW) {
                        ++rs.downWithCnt;
                        if (downW.nUsed >= 2) ++rs.downWithGe2;
                        if (downW.nUsed >= 3) ++rs.downWithGe3;
                        if (std::isfinite(downW.sigmaT0Ns)) {
                            rs.sigT0WithSum += downW.sigmaT0Ns;
                            rs.sigT0WithSum2 += downW.sigmaT0Ns * downW.sigmaT0Ns;
                        }
                    }
                    if (downOkN) {
                        ++rs.downNoCnt;
                        if (downN.nUsed >= 2) ++rs.downNoGe2;
                        if (downN.nUsed >= 3) ++rs.downNoGe3;
                        if (std::isfinite(downN.sigmaT0Ns)) {
                            rs.sigT0NoSum += downN.sigmaT0Ns;
                            rs.sigT0NoSum2 += downN.sigmaT0Ns * downN.sigmaT0Ns;
                        }
                    }
                    if (downOkW && downOkN && std::isfinite(downW.t0Ns) && std::isfinite(downN.t0Ns)) {
                        const double sh = downW.t0Ns - downN.t0Ns;
                        if (std::abs(sh) < 3.0) {
                            ++rs.shiftCnt;
                            rs.shiftT0Sum += sh;
                            rs.shiftT0Sum2 += sh * sh;
                        }
                    }
                    if (isV2Sat) {
                        ++rs.nV2Sat;
                        if (downOkW) ++rs.nV2SatDownWith;
                        if (downOkN) ++rs.nV2SatDownNo;
                    }
                    if (isNoMuon) {
                        ++rs.nNoMuon;
                        if (downOkW) ++rs.nNoMuonDownWith;
                        if (downOkN) ++rs.nNoMuonDownNo;
                    }
                    if (downBw.valid && downBw.nUsed >= 1) ++rs.nDownBWithGe1;
                    if (downBw.valid && downBw.nUsed >= 2) ++rs.nDownBWithGe2;
                    if (downBn.valid && downBn.nUsed >= 1) ++rs.nDownBNoGe1;
                    if (downBn.valid && downBn.nUsed >= 2) ++rs.nDownBNoGe2;

                    if (downOkW && c0V && std::abs(dt0W) < 2.5) {
                        ++rs.dt0WithCnt;
                        rs.dt0WithSum += dt0W;
                        rs.dt0WithSum2 += dt0W * dt0W;
                    }
                    if (downOkW && c1V && std::abs(dt1W) < 2.5) {
                        ++rs.dt1WithCnt;
                        rs.dt1WithSum += dt1W;
                        rs.dt1WithSum2 += dt1W * dt1W;
                    }
                    if (downOkN && c0V && std::abs(dt0N) < 2.5) {
                        ++rs.dt0NoCnt;
                        rs.dt0NoSum += dt0N;
                        rs.dt0NoSum2 += dt0N * dt0N;
                    }
                    if (downOkN && c1V && std::abs(dt1N) < 2.5) {
                        ++rs.dt1NoCnt;
                        rs.dt1NoSum += dt1N;
                        rs.dt1NoSum2 += dt1N * dt1N;
                    }

                    // Preshower2/3 detailed study histograms on 2025/2026 & MC groups
                    std::string psGrp;
                    if (!isMC) {
                        if (run >= 18500 && run < 21500) {
                            if (sig.hasReducedCharge) {
                                psGrp = "y2025_p0014";
                            } else if (brokenPs) {
                                psGrp = "y2025_p0013_brokenPS";
                            } else {
                                psGrp = "y2025_p0013_healthy";
                            }
                        } else if (run >= 21500) {
                            double dummyB = 0.0, dummyT = 0.0;
                            psGrp = calib->getChannelRunOffsets(run, iPS3, dummyB, dummyT)
                                ? "y2026_p0015_earlyPS3"
                                : "y2026_p0015_lateNoPS3";
                        }
                    } else {
                        psGrp = isGenie ? "genie_mc24" : "fluka_mc24";
                    }

                    if (!psGrp.empty()) {
                        auto& pg = slotPsGroups[slot][psGrp];
                        if (!pg.initialized) pg.init(psGrp);

                        const auto downLooTim01No = TimingCalibrator::fitDownstreamReferenceMode(
                            evt, DownstreamMode::Trimmed3Sigma, leadYTrig, &raw,
                            kMaskDownNoPS23, (1u << iTim01));
                        const auto downLooTim01With = TimingCalibrator::fitDownstreamReferenceMode(
                            evt, DownstreamMode::Trimmed3Sigma, leadYTrig, &raw,
                            kMaskDownWithPS23, (1u << iTim01));
                        const bool tim01V = evt.channels[iTim01].valid;

                        auto fillStratum = [&](int si) {
                            if (downN.valid) {
                                pg.hSigt0No[si].fill(downN.sigmaT0Ns);
                                pg.hNdownNo[si].fill(static_cast<double>(downN.nUsed) + 0.5);
                            } else {
                                pg.hNdownNo[si].fill(0.5);
                            }
                            if (downW.valid) {
                                pg.hSigt0With[si].fill(downW.sigmaT0Ns);
                                pg.hNdownWith[si].fill(static_cast<double>(downW.nUsed) + 0.5);
                            } else {
                                pg.hNdownWith[si].fill(0.5);
                            }
                            if (downW.valid && downN.valid) {
                                pg.hShiftT0[si].fill(downW.t0Ns - downN.t0Ns);
                            }
                            if (tim01V && downLooTim01No.valid && downLooTim01No.nUsed >= 2) {
                                pg.hTim01LooNo[si].fill(evt.channels[iTim01].tCalNs - downLooTim01No.t0Ns);
                            }
                            if (tim01V && downLooTim01With.valid && downLooTim01With.nUsed >= 2) {
                                pg.hTim01LooWith[si].fill(evt.channels[iTim01].tCalNs - downLooTim01With.t0Ns);
                            }
                            if (region == REG_KIN_SR && c0V && c1V) {
                                if (downOkN) { pg.hDt0PromptNo[si].fill(dt0N); pg.hDt1PromptNo[si].fill(dt1N); }
                                if (downOkW) { pg.hDt0PromptWith[si].fill(dt0W); pg.hDt1PromptWith[si].fill(dt1W); }
                            } else if (region == REG_CR_GEOM_OUTER || region == REG_CR_GEOM_HITHETA || region == REG_CR_EDGE_VN) {
                                if (c0V && downOkN) pg.hDt0CrNo[si].fill(dt0N);
                                if (c0V && downOkW) pg.hDt0CrWith[si].fill(dt0W);
                                if (c1V && downOkN) pg.hDt1CrNo[si].fill(dt1N);
                                if (c1V && downOkW) pg.hDt1CrWith[si].fill(dt1W);
                                if (c1V && downBnOk) pg.hU1DownBNo[si].fill(u1No);
                                if (c1V && downBwOk) pg.hU1DownBWith[si].fill(u1With);
                            }
                        };
                        fillStratum(0);
                        if (isV2Sat) fillStratum(1);
                        if (isNoMuon) fillStratum(2);
                        if (isV2Sat && isNoMuon) fillStratum(3);
                    }
                }

                // VetoGm0/1 in-situ calibration, spatial acceptance maps & grazing-muon cross-check
                if (!isMC && sig.hasVetoGm && !deadVn && passPsNom) {
                    if (rVN >= 120.0 && rVN < 240.0) {
                        ++rs.nGmDenom;
                        if (std::isfinite(gm.qRaw0)) {
                            rs.gm0QMax = std::max(rs.gm0QMax, static_cast<double>(gm.qRaw0));
                            if (gm.qRaw0 > 10.0f) ++rs.nGm0Q10;
                            if (gm.qRaw0 > 20.0f) ++rs.nGm0Q20;
                        }
                        if (std::isfinite(gm.qRaw1)) {
                            rs.gm1QMax = std::max(rs.gm1QMax, static_cast<double>(gm.qRaw1));
                            if (gm.qRaw1 > 10.0f) ++rs.nGm1Q10;
                            if (gm.qRaw1 > 20.0f) ++rs.nGm1Q20;
                        }
                    }

                    const std::string gmEra = (run < 21500)
                        ? (vetoGmActiveRuns.count(run) ? "live_2025_p0014" : "inactive_2025_p0014")
                        : "hv_off_2026_p0015";
                    auto& gmm = slotGmMaps[slot][gmEra];
                    if (!gmm.initialized) gmm.init(gmEra);

                    const bool g0Hit = std::isfinite(gm.qRaw0) && gm.qRaw0 > 20.0f;
                    const bool g1Hit = std::isfinite(gm.qRaw1) && gm.qRaw1 > 20.0f;
                    const bool gAnyHit = g0Hit || g1Hit;

                    gmm.h1Gm0RawQ.fill(gm.qRaw0);
                    gmm.h1Gm1RawQ.fill(gm.qRaw1);
                    if (rMax < 135.0 && rIFT < 135.0 && theta < 55.0) {
                        gmm.h1RvnAllDenom.fill(rVN);
                        if (g0Hit) gmm.h1RvnGm0Q20.fill(rVN);
                        if (g1Hit) gmm.h1RvnGm1Q20.fill(rVN);
                        if (gAnyHit) gmm.h1RvnGmAnyQ20.fill(rVN);
                    }
                    if (tk.validPos[0]) {
                        gmm.h2VnDenom.fill(tk.x[0], tk.y[0]);
                        if (g0Hit) gmm.h2VnGm0Q20.fill(tk.x[0], tk.y[0]);
                        if (g1Hit) gmm.h2VnGm1Q20.fill(tk.x[0], tk.y[0]);
                        if (gAnyHit) gmm.h2VnGmAnyQ20.fill(tk.x[0], tk.y[0]);
                    }
                    if (tk.validPos[1]) {
                        gmm.h2V1Denom.fill(tk.x[1], tk.y[1]);
                        if (g0Hit) gmm.h2V1Gm0Q20.fill(tk.x[1], tk.y[1]);
                        if (g1Hit) gmm.h2V1Gm1Q20.fill(tk.x[1], tk.y[1]);
                    }

                    // Compute VetoGm relative timing wrt downstream reference & wrt Timing0_localtime
                    float gm0DtDown = kNaNF, gm1DtDown = kNaNF;
                    float gm0LocTim0 = kNaNF, gm1LocTim0 = kNaNF;
                    if (std::isfinite(gm.loc0) && std::isfinite(raw[iTim01].localTime)) {
                        gm0LocTim0 = gm.loc0 - static_cast<float>(raw[iTim01].localTime);
                    }
                    if (std::isfinite(gm.loc1) && std::isfinite(raw[iTim01].localTime)) {
                        gm1LocTim0 = gm.loc1 - static_cast<float>(raw[iTim01].localTime);
                    }
                    const int anc = evt.anchorChannel;
                    if (downW.valid && anc >= 0 && evt.channels[anc].valid &&
                        std::isfinite(raw[anc].triggerTime)) {
                        const double t1Anc = evt.channels[anc].t1Ns;
                        const double tTrigRawAnc = raw[anc].triggerTime;
                        auto computeGmDt = [&](Int_t st, Float_t bc, Float_t tr, Float_t qr) -> float {
                            if (!TimingCalibrator::isGoodWaveformStatus(st) || qr <= 10.0f) return kNaNF;
                            if (!std::isfinite(bc) || !std::isfinite(tr)) return kNaNF;
                            const double shift2 = ((st & 512) != 0) ? 16.0 : 0.0;
                            const double t1Gm = TimingCalibrator::wrap25(static_cast<double>(bc) + shift2);
                            const double dTrig = (static_cast<double>(tr) + shift2) - tTrigRawAnc;
                            const double dMod25 = TimingCalibrator::wrap25(t1Gm - t1Anc);
                            const long long nShift = std::llround((dTrig - dMod25) / 25.0);
                            const double rUnw = std::abs(dTrig - (dMod25 + 25.0 * static_cast<double>(nShift)));
                            if (rUnw > 6.0) return kNaNF;
                            const double t2Gm = t1Anc + dMod25 + 25.0 * static_cast<double>(nShift);
                            return static_cast<float>(t2Gm - downW.t0Ns);
                        };
                        gm0DtDown = computeGmDt(gm.status0, gm.bcid0, gm.trig0, gm.qRaw0);
                        gm1DtDown = computeGmDt(gm.status1, gm.bcid1, gm.trig1, gm.qRaw1);
                    }
                    if (std::isfinite(gm0DtDown)) gmm.h1Gm0DtVsDown.fill(gm0DtDown);
                    if (std::isfinite(gm1DtDown)) gmm.h1Gm1DtVsDown.fill(gm1DtDown);
                    if (g0Hit && std::isfinite(gm0LocTim0)) gmm.h1Gm0LocMinusTim0.fill(gm0LocTim0);
                    if (g1Hit && std::isfinite(gm1LocTim0)) gmm.h1Gm1LocMinusTim0.fill(gm1LocTim0);

                    // Save compact unblinded records:
                    //   100% SR-ZoneA / CR-Geom ZoneA / CR-EdgeVN ZoneA,
                    //   100% CR-EdgeVN / CR-HaloVN / CR-Geom Zone-B delayed (>1.5 ns, valid down+hit),
                    //   1/50 CR-HaloVN ZoneA, 1/100 non-delayed CR-EdgeVN/HaloVN, 1/400 prompt SR/CR-Geom
                    const bool isDelayedSideband =
                        (!zoneAEra) && downOkW &&
                        ((c0V && std::isfinite(dt0W) && dt0W > 1.5) ||
                         (c1V && std::isfinite(dt1W) && dt1W > 1.5));
                    bool keepRec = false;
                    bool isPrescaledPrompt = false;
                    float sampleWt = 1.0f;
                    if (zoneAEra) {
                        if (region == REG_KIN_SR || region == REG_CR_GEOM_OUTER ||
                            region == REG_CR_GEOM_HITHETA || region == REG_CR_EDGE_VN) {
                            keepRec = true;
                        } else if (region == REG_CR_HALO_VN) {
                            if (deterministicUniform01(run, eventID, 0x6162c0de00998877ULL) < 0.02) {
                                keepRec = true;
                                isPrescaledPrompt = true;
                                sampleWt = 50.0f;
                            }
                        }
                    } else if (region != REG_KIN_SR && isDelayedSideband) {
                        keepRec = true;
                    } else if (region == REG_CR_EDGE_VN || region == REG_CR_HALO_VN) {
                        if (deterministicUniform01(run, eventID, 0x6162c0de00112233ULL) < 0.01) {
                            keepRec = true;
                            isPrescaledPrompt = true;
                            sampleWt = 100.0f;
                        }
                    } else {
                        if (deterministicUniform01(run, eventID, 0x6162c0de44556677ULL) < 0.0025) {
                            keepRec = true;
                            isPrescaledPrompt = true;
                            sampleWt = 400.0f;
                        }
                    }

                    if (keepRec) {
                        T6VetoGmRecord rec;
                        rec.run = run;
                        rec.eventID = static_cast<int64_t>(eventID);
                        rec.region = region;
                        rec.is_prescaled_prompt = isPrescaledPrompt ? 1 : 0;
                        rec.zone_a_era = zoneAEra ? 1 : 0;
                        rec.pass_wp_primary = wpPrimWith ? 1 : 0;
                        rec.sample_weight = sampleWt;
                        rec.pz0_gev = static_cast<float>(tk.leadPz0GeV);
                        rec.r_max = static_cast<float>(rMax);
                        rec.r_ift = static_cast<float>(rIFT);
                        rec.r_vn = static_cast<float>(rVN);
                        rec.theta_mrad = static_cast<float>(theta);
                        rec.x_vn = static_cast<float>(tk.x[0]);
                        rec.y_vn = static_cast<float>(tk.y[0]);
                        rec.x_v1 = static_cast<float>(tk.x[1]);
                        rec.y_v1 = static_cast<float>(tk.y[1]);
                        rec.q0_raw = static_cast<float>(raw[iVN0].rawCharge);
                        rec.q1_raw = static_cast<float>(raw[iVN1].rawCharge);
                        rec.q0_red = vn0RedVal;
                        rec.q1_red = vn1RedVal;
                        rec.dt0 = static_cast<float>(dt0W);
                        rec.dt1 = static_cast<float>(dt1W);
                        rec.w0 = static_cast<float>(raw[iVN0].width);
                        rec.w1 = static_cast<float>(raw[iVN1].width);
                        rec.gm0_q_raw = gm.qRaw0;
                        rec.gm1_q_raw = gm.qRaw1;
                        rec.gm0_q_chg = gm.qChg0;
                        rec.gm1_q_chg = gm.qChg1;
                        rec.gm0_width = gm.w0;
                        rec.gm1_width = gm.w1;
                        rec.gm0_dt_down = gm0DtDown;
                        rec.gm1_dt_down = gm1DtDown;
                        rec.gm0_loc_tim0 = gm0LocTim0;
                        rec.gm1_loc_tim0 = gm1LocTim0;
                        rec.gm0_status = gm.status0;
                        rec.gm1_status = gm.status1;
                        slotGmRecs[slot].push_back(rec);
                    }
                }
            },
            {"run", "eventID", "_tk", "_raw", "_gm", "_aux"});

        // Merge pre-filter counters into slotRuns BEFORE merging across slots
        for (unsigned int s = 0; s < nSlots; ++s) {
            for (const auto& [r, pItem] : slotPre[s]) {
                auto& rs = mergedRuns[r];
                if (!rs.initialized) {
                    const bool bps = !isMC && !sig.hasReducedCharge && (brokenPsP0013Runs.count(r) > 0);
                    const bool dvn = !isMC && (deadVetoNuHvRuns.count(r) > 0);
                    rs.init(r, isMC, effectiveHasRedQ, sig.hasPreshower23, sig.hasVetoGm, bps, dvn);
                }
                rs.pre.mergeFrom(pItem);
            }
            for (const auto& [r, stItem] : slotRuns[s]) {
                // slotRuns[s] has empty .pre; only merge post-filter fields
                T6RunStats copy = stItem;
                copy.pre = RunPreStats{};
                mergedRuns[r].mergeFrom(copy);
            }
            for (const auto& [gn, gItem] : slotPsGroups[s]) mergedPsGroups[gn].mergeFrom(gItem);
            for (const auto& [en, eItem] : slotGmMaps[s]) mergedGmMaps[en].mergeFrom(eItem);
            mergedGmRecs.insert(mergedGmRecs.end(), slotGmRecs[s].begin(), slotGmRecs[s].end());
        }
    }

    const uint64_t missingAuxCount = nMissingAux.load();
    if (missingAuxCount > 0) {
        ERROR("Missing aux reduced charge for ", missingAuxCount,
              " passing events (first: ", firstMissingAuxMsg, ")");
        throw std::runtime_error("Missing aux reduced-charge rows for passing events.");
    }

    if (!isMC && hasManifestJson && manifestJson.contains("runs")) {
        for (int r : autoAuxRuns) {
            if (mergedRuns[r].initialized) continue;
            const std::string rsKey = std::to_string(r);
            bool ps23 = (r >= 18500);
            bool gm = false;
            bool bps = (brokenPsP0013Runs.count(r) > 0);
            bool dvn = (deadVetoNuHvRuns.count(r) > 0);
            if (manifestJson.at("runs").contains(rsKey)) {
                const auto& meta = manifestJson.at("runs").at(rsKey);
                ps23 = meta.value("has_preshower23", ps23);
                gm = meta.value("has_vetogm", false);
                bps = meta.value("broken_ps_p0013", bps);
                dvn = meta.value("dead_vetonu_hv", dvn);
            }
            mergedRuns[r].init(r, false, true, ps23, gm, bps, dvn);
        }
    }

    writeOutput(outputPath, mergedRuns, mergedPsGroups, mergedGmMaps, mergedGmRecs);

    uint64_t totEvents = 0, totBlinded = 0, totSrZaNom = 0, totSrZaEff = 0;
    for (const auto& [r, stItem] : mergedRuns) {
        totEvents += stItem.pre.nTotal;
        totBlinded += stItem.nBlinded;
        totSrZaNom += stItem.nSrZoneAEraNom;
        totSrZaEff += stItem.nSrZoneAEraEff;
    }

    const double wallS = std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStart).count();
    INFO("Completed T6 scan (", mode, "): files=", files.size(), " (skipped_empty=", nSkippedEmpty,
         "), aux_rows=", auxRows.size(), ", missing_aux=", missingAuxCount,
         ", total_events=", totEvents, ", blinded_sr_zoneb_skipped=", totBlinded,
         ", sr_za_nom=", totSrZaNom, ", sr_za_eff=", totSrZaEff,
         ", vetogm_recs=", mergedGmRecs.size(),
         ", wall=", wallS, " s (", (wallS > 0 ? totEvents / wallS / 1e6 : 0.0), " Mevt/s)");

    if (!summaryJsonPath.empty()) {
        json sj;
        sj["mode"] = mode;
        sj["threads"] = threads;
        sj["n_slots"] = nSlots;
        sj["n_files"] = files.size();
        sj["n_skipped_empty"] = nSkippedEmpty;
        sj["n_aux_files"] = auxFiles.size();
        sj["n_aux_rows"] = auxRows.size();
        sj["n_missing_aux"] = missingAuxCount;
        sj["n_total"] = totEvents;
        sj["n_blinded_sr_zoneb_skipped"] = totBlinded;
        sj["n_sr_zonea_era_nom"] = totSrZaNom;
        sj["n_sr_zonea_era_eff"] = totSrZaEff;
        sj["n_vetogm_records"] = mergedGmRecs.size();
        sj["wall_s"] = wallS;
        sj["mevt_per_s"] = (wallS > 0 ? totEvents / wallS / 1e6 : 0.0);
        std::ofstream ofs(summaryJsonPath);
        ofs << sj.dump(2) << "\n";
    }
    return 0;
}
