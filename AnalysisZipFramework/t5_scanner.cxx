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
#include <TH3D.h>
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
constexpr double kDistLosMm = 480000.0;
constexpr double kLosYShiftMm = 12.3;
constexpr double kConeRadiusMm = 75.0;
constexpr double kChargeRef01LG = 0.07129999995231628;
constexpr double kChargeRef03LG = 0.07569999992847443;
constexpr double kScale03Over01 = kChargeRef03LG / kChargeRef01LG;
constexpr uint64_t kWaveInvalidMask = (8ULL | 128ULL | 256ULL);
constexpr uint64_t kCaloFitInvalidMask = (kWaveInvalidMask | 16ULL | 32ULL | 4ULL);

// Disjoint 4-station masks for zero-covariance split ABCD
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

enum T5Region : uint8_t {
    REG_KIN_SR = 1,
    REG_CR_GEOM_OUTER = 2,
    REG_CR_GEOM_HITHETA = 3,
    REG_CR_EDGE_VN = 4,
    REG_NONCOLL_B1 = 5,
    REG_NONCOLL_UNPAIRED = 6,
    REG_NONCOLL_EMPTY = 7,
    REG_RELAXED_SR_ONLY = 9,
};

constexpr uint16_t kFlagHasRedQ = 1u << 0;
constexpr uint16_t kFlagPassPhysTrig = 1u << 1;
constexpr uint16_t kFlagDownOk = 1u << 2;
constexpr uint16_t kFlagDownAValid = 1u << 3;
constexpr uint16_t kFlagDownBValid = 1u << 4;
constexpr uint16_t kFlagDownAGE2 = 1u << 5;
constexpr uint16_t kFlagDownBGE2 = 1u << 6;
constexpr uint16_t kFlagVn0Valid = 1u << 7;
constexpr uint16_t kFlagVn1Valid = 1u << 8;
constexpr uint16_t kFlagZoneARed = 1u << 9;
constexpr uint16_t kFlagZoneARaw = 1u << 10;
constexpr uint16_t kFlagZoneAEra = 1u << 11;
constexpr uint16_t kFlagVn0ActiveEra = 1u << 12;
constexpr uint16_t kFlagVn1ActiveEra = 1u << 13;
constexpr uint16_t kFlagPassLeadTrk = 1u << 14;
constexpr uint16_t kFlagPassNominalSR = 1u << 15;

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

double deterministicStdNormal(int32_t run, int64_t eventID, uint64_t salt) {
    const double u1 = std::max(1e-12, 1.0 - deterministicUniform01(run, eventID, salt));
    const double u2 = deterministicUniform01(run, eventID, salt ^ 0x517cc1b727220a95ULL);
    return std::sqrt(-2.0 * std::log(u1)) * std::cos(2.0 * M_PI * u2);
}

double defaultMcCrossingAngleUrad(int run) {
    // 2022-2023 MC runs: -160 urad; 2024 MC runs: +150/+160 urad
    if ((run >= 200080 && run <= 200090) || (run >= 200104 && run <= 200115)) {
        return -160.0;
    }
    return 150.0;
}

int rapidityBin5(double y) {
    if (!std::isfinite(y) || y < 8.5) return -1;
    if (y < 9.0) return 0;
    if (y < 9.25) return 1;
    if (y < 9.5) return 2;
    if (y < 10.0) return 3;
    return 4;
}

int invEnergyBin6(double qOverE) {
    // q_lep / E_GeV in GeV^-1: [-1/100, -1/300, -1/600, -1/1000, +1/1000, +1/300, +1/100]
    if (!std::isfinite(qOverE)) return -1;
    constexpr double b0 = -1.0 / 100.0;
    constexpr double b1 = -1.0 / 300.0;
    constexpr double b2 = -1.0 / 600.0;
    constexpr double b3 = -1.0 / 1000.0;
    constexpr double b4 = +1.0 / 1000.0;
    constexpr double b5 = +1.0 / 300.0;
    constexpr double b6 = +1.0 / 100.0;
    if (qOverE < b0 || qOverE > b6) return -1;
    if (qOverE < b1) return 0;
    if (qOverE < b2) return 1;
    if (qOverE < b3) return 2;
    if (qOverE < b4) return 3;
    if (qOverE < b5) return 4;
    return 5;
}

int computeBin30(double y, double qOverE) {
    const int iy = rapidityBin5(y);
    const int ie = invEnergyBin6(qOverE);
    if (iy < 0 || ie < 0) return -1;
    return iy * 6 + ie;
}

double computeRapidityLOS(double xMm, double yMm, double caUrad, double losOffsetSignMm) {
    if (!std::isfinite(xMm) || !std::isfinite(yMm)) return kNaN;
    const double yLos = kDistLosMm * std::tan(caUrad * 1e-6) + losOffsetSignMm;
    const double rRel = std::hypot(xMm, yMm - yLos);
    if (rRel <= 0.0) return 20.0;
    const double theta = std::atan2(rRel, kDistLosMm);
    return -std::log(std::tan(0.5 * theta));
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
    bool hasBcidTrig{false};
    bool hasReducedCharge{false};
    bool hasVetoGm{false};
    bool hasInboundB1{false};
    bool hasUnpairedB1{false};
    bool hasUnpairedB2{false};
    bool hasTruth{false};
    bool hasCrossingAngle{false};
    bool hasMlFull{false};
    double calo01LgScale{1.0};
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
               (hasTruth ? "1" : "0") +
               (hasCrossingAngle ? "1" : "0") +
               (hasMlFull ? "1" : "0") + "|" +
               eventTimeType + "|" + nLayersType + "|" +
               (calo01LgScale > 1.01 ? "C03" : "C01");
    }
};

bool probeFileSchema(const std::string& fpath, bool isGenie, SchemaSignature& sigOut, int* firstRunOut = nullptr) {
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
    sig.hasCrossingAngle = br.count("crossingAngle") > 0;
    sig.hasMlFull = isGenie &&
        (br.count("Track_PropagationError") > 0) &&
        (br.count("Track_module_eta0") > 0) &&
        (br.count("SpacePoint_x") > 0) &&
        (br.count("Calo0_E_EM") > 0);

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

    if (isGenie && br.count("Calo0_charge") && br.count("Calo0_E_EM") && br.count("Calo0_status") && br.count("run")) {
        auto rHead = probeDf.Range(0, 10).Take<Int_t>("run");
        auto qHead = probeDf.Range(0, 1500).Take<Float_t>("Calo0_charge");
        auto eHead = probeDf.Range(0, 1500).Take<Float_t>("Calo0_E_EM");
        auto sHead = probeDf.Range(0, 1500).Take<Int_t>("Calo0_status");
        const int runVal = rHead->empty() ? 0 : rHead->at(0);
        bool detected = false;
        const size_t nChk = std::min(qHead->size(), std::min(eHead->size(), sHead->size()));
        for (size_t i = 0; i < nChk; ++i) {
            if (sHead->at(i) == 0 && std::isfinite(qHead->at(i)) && std::isfinite(eHead->at(i)) &&
                std::abs(qHead->at(i)) > 1.0) {
                const double ratio = eHead->at(i) / qHead->at(i);
                const double r01 = 330.0 / kChargeRef01LG;
                const double r03 = 330.0 / kChargeRef03LG;
                if (std::abs(ratio - r01) / r01 < 1e-4) {
                    sig.calo01LgScale = 1.0;
                    detected = true;
                    break;
                } else if (std::abs(ratio - r03) / r03 < 1e-4) {
                    sig.calo01LgScale = kScale03Over01;
                    detected = true;
                    break;
                }
            }
        }
        if (!detected) {
            sig.calo01LgScale = (runVal >= 200080 && runVal <= 200090) ? 1.0 : kScale03Over01;
        }
    }

    sigOut = sig;
    return true;
}

// Fine bins for differential B1/B2 ABCD closure on (r_VN, Q, |u| or z)
constexpr int kNRvnFine = 6;
constexpr std::array<double, kNRvnFine + 1> kRvnFineEdges = {{0.0, 60.0, 90.0, 105.0, 115.0, 120.0, 180.0}};
constexpr int kNQFine = 5;
constexpr std::array<double, kNQFine + 1> kQFineEdges = {{0.0, 55.0, 130.0, 150.0, 180.0, 1e9}};

// 32 differential time edges [1.0 .. 22.0] ns
constexpr int kNTEdges = 33;
constexpr std::array<double, kNTEdges> kTEdges = {{
    1.00, 1.25, 1.50, 1.75, 2.00, 2.25, 2.50, 2.75,
    3.00, 3.25, 3.50, 3.75, 4.00, 4.25, 4.50, 4.75,
    5.00, 5.25, 5.50, 5.75, 6.00, 6.25, 6.50, 6.75,
    7.00, 7.25, 7.50, 7.75, 8.00, 10.00, 12.00, 16.00, 22.00
}};

// 29 differential pull edges [2.0 .. 12.0]
constexpr int kNZEdges = 29;
constexpr std::array<double, kNZEdges> kZEdges = {{
    2.00, 2.25, 2.50, 2.75, 3.00, 3.25, 3.50, 3.75,
    4.00, 4.25, 4.50, 4.75, 5.00, 5.25, 5.50, 5.75,
    6.00, 6.25, 6.50, 6.75, 7.00, 7.25, 7.50, 7.75,
    8.00, 8.50, 9.00, 10.00, 12.00
}};

constexpr int kNWCap = 3; // 0: <19.5 ns, 1: <16.0 ns, 2: <12.0 ns
constexpr std::array<double, kNWCap> kWCaps = {{19.5, 16.0, 12.0}};
constexpr std::array<const char*, kNWCap> kWCapNames = {{"w19p5", "w16p0", "w12p0"}};

struct FastGrid3D {
    int nx{0}, ny{0}, nz{0};
    std::vector<double> xEdges, yEdges, zEdges;
    std::vector<uint64_t> data;

    void init(std::vector<double> xe, std::vector<double> ye, std::vector<double> ze) {
        xEdges = std::move(xe);
        yEdges = std::move(ye);
        zEdges = std::move(ze);
        nx = static_cast<int>(xEdges.size()) - 1;
        ny = static_cast<int>(yEdges.size()) - 1;
        nz = static_cast<int>(zEdges.size()) - 1;
        data.assign(static_cast<size_t>(nx * ny * nz), 0ULL);
    }

    static int findBin(const std::vector<double>& edges, double val) {
        if (!std::isfinite(val) || val < edges.front() || val >= edges.back()) return -1;
        auto it = std::upper_bound(edges.begin(), edges.end(), val);
        int b = static_cast<int>(it - edges.begin()) - 1;
        if (b < 0 || b >= static_cast<int>(edges.size()) - 1) return -1;
        return b;
    }

    void fill(double x, double y, double z) {
        const int ix = findBin(xEdges, x);
        const int iy = findBin(yEdges, y);
        const int iz = findBin(zEdges, z);
        if (ix < 0 || iy < 0 || iz < 0) return;
        ++data[static_cast<size_t>((ix * ny + iy) * nz + iz)];
    }

    void addFrom(const FastGrid3D& o) {
        if (data.empty()) { *this = o; return; }
        for (size_t i = 0; i < data.size(); ++i) data[i] += o.data[i];
    }

    std::unique_ptr<TH3D> toTH3D(const std::string& name, const std::string& title) const {
        auto h = std::make_unique<TH3D>(
            name.c_str(), title.c_str(),
            nx, xEdges.data(), ny, yEdges.data(), nz, zEdges.data());
        for (int ix = 0; ix < nx; ++ix) {
            for (int iy = 0; iy < ny; ++iy) {
                for (int iz = 0; iz < nz; ++iz) {
                    const uint64_t v = data[static_cast<size_t>((ix * ny + iy) * nz + iz)];
                    if (v > 0) h->SetBinContent(ix + 1, iy + 1, iz + 1, static_cast<double>(v));
                }
            }
        }
        return h;
    }
};

struct FastGrid2D {
    int nx{0}, ny{0};
    std::vector<double> xEdges, yEdges;
    std::vector<uint64_t> data;

    void init(std::vector<double> xe, std::vector<double> ye) {
        xEdges = std::move(xe);
        yEdges = std::move(ye);
        nx = static_cast<int>(xEdges.size()) - 1;
        ny = static_cast<int>(yEdges.size()) - 1;
        data.assign(static_cast<size_t>(nx * ny), 0ULL);
    }

    void fill(double x, double y) {
        const int ix = FastGrid3D::findBin(xEdges, x);
        const int iy = FastGrid3D::findBin(yEdges, y);
        if (ix < 0 || iy < 0) return;
        ++data[static_cast<size_t>(ix * ny + iy)];
    }

    void addFrom(const FastGrid2D& o) {
        if (data.empty()) { *this = o; return; }
        for (size_t i = 0; i < data.size(); ++i) data[i] += o.data[i];
    }

    std::unique_ptr<TH2D> toTH2D(const std::string& name, const std::string& title) const {
        auto h = std::make_unique<TH2D>(
            name.c_str(), title.c_str(), nx, xEdges.data(), ny, yEdges.data());
        for (int ix = 0; ix < nx; ++ix) {
            for (int iy = 0; iy < ny; ++iy) {
                const uint64_t v = data[static_cast<size_t>(ix * ny + iy)];
                if (v > 0) h->SetBinContent(ix + 1, iy + 1, static_cast<double>(v));
            }
        }
        return h;
    }
};

struct T5RunStats {
    bool initialized{false};
    int run{0};
    bool isMC{false};
    bool hasReducedCharge{false};
    uint64_t nTotal{0};
    uint64_t nGrlFail{0};
    uint64_t nBlinded{0};
    uint64_t nNoOffsets{0};
    uint64_t nColliding{0};
    uint64_t nBeam1{0};
    uint64_t nUnpaired{0};
    uint64_t nEmpty{0};
    uint64_t nAccDenomBeam1{0};
    uint64_t nAccDenomUnpaired{0};
    uint64_t nAccDenomEmpty{0};
    uint64_t nSrZoneARed30{0};
    uint64_t nSrZoneARaw40{0};
    uint64_t nSrZoneAEra{0};
    uint64_t nSrPrompt2HitU1p0{0};
    uint64_t nSrPrompt2HitDt1p0{0};
    uint64_t nSr1Hit0Era{0};
    uint64_t nSr1Hit1Era{0};
    uint64_t nGeomAll{0};
    uint64_t nGeomZoneAEra{0};
    uint64_t nGeomPrompt2HitU1p0{0};
    uint64_t nGeomPrompt2HitDt1p0{0};
    uint64_t nEdgeVnAll{0};
    uint64_t nEdgeVnZoneAEra{0};
    uint64_t nEdgeVnZoneBEra{0};
    uint64_t nFidBox{0};
    uint64_t nFidLead{0};

    void init(int r, bool mc, bool redQ) {
        if (initialized) return;
        initialized = true;
        run = r;
        isMC = mc;
        hasReducedCharge = redQ;
    }

    void mergeFrom(const T5RunStats& o) {
        if (!initialized) init(o.run, o.isMC, o.hasReducedCharge);
        hasReducedCharge = hasReducedCharge || o.hasReducedCharge;
        nTotal += o.nTotal;
        nGrlFail += o.nGrlFail;
        nBlinded += o.nBlinded;
        nNoOffsets += o.nNoOffsets;
        nColliding += o.nColliding;
        nBeam1 += o.nBeam1;
        nUnpaired += o.nUnpaired;
        nEmpty += o.nEmpty;
        nAccDenomBeam1 += o.nAccDenomBeam1;
        nAccDenomUnpaired += o.nAccDenomUnpaired;
        nAccDenomEmpty += o.nAccDenomEmpty;
        nSrZoneARed30 += o.nSrZoneARed30;
        nSrZoneARaw40 += o.nSrZoneARaw40;
        nSrZoneAEra += o.nSrZoneAEra;
        nSrPrompt2HitU1p0 += o.nSrPrompt2HitU1p0;
        nSrPrompt2HitDt1p0 += o.nSrPrompt2HitDt1p0;
        nSr1Hit0Era += o.nSr1Hit0Era;
        nSr1Hit1Era += o.nSr1Hit1Era;
        nGeomAll += o.nGeomAll;
        nGeomZoneAEra += o.nGeomZoneAEra;
        nGeomPrompt2HitU1p0 += o.nGeomPrompt2HitU1p0;
        nGeomPrompt2HitDt1p0 += o.nGeomPrompt2HitDt1p0;
        nEdgeVnAll += o.nEdgeVnAll;
        nEdgeVnZoneAEra += o.nEdgeVnZoneAEra;
        nEdgeVnZoneBEra += o.nEdgeVnZoneBEra;
        nFidBox += o.nFidBox;
        nFidLead += o.nFidLead;
    }
};

struct T5PeriodGrid {
    bool initialized{false};
    std::string period;

    std::array<FastGrid2D, kNWCap> denSrU, denSrDt, denGeomU, denGeomDt;
    std::array<FastGrid3D, kNWCap> tailGeomU0Pos, tailGeomU1Pos, tailGeomDt0Pos, tailGeomDt1Pos;
    std::array<FastGrid3D, kNWCap> tailGeomZu0Pos, tailGeomZu1Pos;
    std::array<FastGrid3D, kNWCap> tailSrU0Neg, tailSrU1Neg, tailSrDt0Neg, tailSrDt1Neg;
    std::array<FastGrid3D, kNWCap> tailSrZu0Neg, tailSrZu1Neg;
    std::array<FastGrid2D, kNWCap> accBeam1Vn0, accBeam1Vn1, accEmpUnpVn0, accEmpUnpVn1;

    void init(const std::string& p) {
        if (initialized) return;
        initialized = true;
        period = p;
        std::vector<double> rvnE(kRvnFineEdges.begin(), kRvnFineEdges.end());
        std::vector<double> qE(kQFineEdges.begin(), kQFineEdges.end());
        std::vector<double> tE(kTEdges.begin(), kTEdges.end());
        std::vector<double> zE(kZEdges.begin(), kZEdges.end());
        std::vector<double> wAccE = {1.5, 8.0, 10.0, 12.0, 14.0, 16.0, 19.5, 25.0};
        for (int wi = 0; wi < kNWCap; ++wi) {
            denSrU[wi].init(rvnE, qE);
            denSrDt[wi].init(rvnE, qE);
            denGeomU[wi].init(rvnE, qE);
            denGeomDt[wi].init(rvnE, qE);
            tailGeomU0Pos[wi].init(rvnE, qE, tE);
            tailGeomU1Pos[wi].init(rvnE, qE, tE);
            tailGeomDt0Pos[wi].init(rvnE, qE, tE);
            tailGeomDt1Pos[wi].init(rvnE, qE, tE);
            tailGeomZu0Pos[wi].init(rvnE, qE, zE);
            tailGeomZu1Pos[wi].init(rvnE, qE, zE);
            tailSrU0Neg[wi].init(rvnE, qE, tE);
            tailSrU1Neg[wi].init(rvnE, qE, tE);
            tailSrDt0Neg[wi].init(rvnE, qE, tE);
            tailSrDt1Neg[wi].init(rvnE, qE, tE);
            tailSrZu0Neg[wi].init(rvnE, qE, zE);
            tailSrZu1Neg[wi].init(rvnE, qE, zE);
            accBeam1Vn0[wi].init(tE, qE);
            accBeam1Vn1[wi].init(tE, qE);
            accEmpUnpVn0[wi].init(tE, qE);
            accEmpUnpVn1[wi].init(tE, qE);
        }
        (void)wAccE;
    }

    void mergeFrom(const T5PeriodGrid& o) {
        if (!initialized) init(o.period);
        for (int wi = 0; wi < kNWCap; ++wi) {
            denSrU[wi].addFrom(o.denSrU[wi]);
            denSrDt[wi].addFrom(o.denSrDt[wi]);
            denGeomU[wi].addFrom(o.denGeomU[wi]);
            denGeomDt[wi].addFrom(o.denGeomDt[wi]);
            tailGeomU0Pos[wi].addFrom(o.tailGeomU0Pos[wi]);
            tailGeomU1Pos[wi].addFrom(o.tailGeomU1Pos[wi]);
            tailGeomDt0Pos[wi].addFrom(o.tailGeomDt0Pos[wi]);
            tailGeomDt1Pos[wi].addFrom(o.tailGeomDt1Pos[wi]);
            tailGeomZu0Pos[wi].addFrom(o.tailGeomZu0Pos[wi]);
            tailGeomZu1Pos[wi].addFrom(o.tailGeomZu1Pos[wi]);
            tailSrU0Neg[wi].addFrom(o.tailSrU0Neg[wi]);
            tailSrU1Neg[wi].addFrom(o.tailSrU1Neg[wi]);
            tailSrDt0Neg[wi].addFrom(o.tailSrDt0Neg[wi]);
            tailSrDt1Neg[wi].addFrom(o.tailSrDt1Neg[wi]);
            tailSrZu0Neg[wi].addFrom(o.tailSrZu0Neg[wi]);
            tailSrZu1Neg[wi].addFrom(o.tailSrZu1Neg[wi]);
            accBeam1Vn0[wi].addFrom(o.accBeam1Vn0[wi]);
            accBeam1Vn1[wi].addFrom(o.accBeam1Vn1[wi]);
            accEmpUnpVn0[wi].addFrom(o.accEmpUnpVn0[wi]);
            accEmpUnpVn1[wi].addFrom(o.accEmpUnpVn1[wi]);
        }
    }
};

struct T5TruthHists {
    bool initialized{false};
    int run{0};
    std::array<double, 30> bin30BoxM12{};
    std::array<double, 30> bin30LeadM12{};
    std::array<double, 30> bin30BoxP12{};
    std::array<double, 30> bin30LeadP12{};
    // 6D marginals matching Stage T3: E_nu(24), pz_mu(24), y_inel(20), z_vtx(30), r_vtx(20), q_mu(2)
    std::array<double, 24> fidEnu{};
    std::array<double, 24> fidPzMu{};
    std::array<double, 20> fidYInel{};
    std::array<double, 30> fidZVtx{};
    std::array<double, 20> fidRVtx{};
    std::array<double, 2> fidQMu{};

    void init(int r) {
        if (initialized) return;
        initialized = true;
        run = r;
        bin30BoxM12.fill(0.0);
        bin30LeadM12.fill(0.0);
        bin30BoxP12.fill(0.0);
        bin30LeadP12.fill(0.0);
        fidEnu.fill(0.0);
        fidPzMu.fill(0.0);
        fidYInel.fill(0.0);
        fidZVtx.fill(0.0);
        fidRVtx.fill(0.0);
        fidQMu.fill(0.0);
    }

    void mergeFrom(const T5TruthHists& o) {
        if (!initialized) init(o.run);
        for (int i = 0; i < 30; ++i) {
            bin30BoxM12[i] += o.bin30BoxM12[i];
            bin30LeadM12[i] += o.bin30LeadM12[i];
            bin30BoxP12[i] += o.bin30BoxP12[i];
            bin30LeadP12[i] += o.bin30LeadP12[i];
            fidZVtx[i] += o.fidZVtx[i];
        }
        for (int i = 0; i < 24; ++i) {
            fidEnu[i] += o.fidEnu[i];
            fidPzMu[i] += o.fidPzMu[i];
        }
        for (int i = 0; i < 20; ++i) {
            fidYInel[i] += o.fidYInel[i];
            fidRVtx[i] += o.fidRVtx[i];
        }
        fidQMu[0] += o.fidQMu[0];
        fidQMu[1] += o.fidQMu[1];
    }
};

struct T5BkgRecord {
    int32_t run{0};
    int64_t eventID{0};
    uint8_t region{0};
    uint8_t is_prompt_sub{0};
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
    float dt0{0.0f};
    float dt1{0.0f};
    float sig_dt0{0.0f};
    float sig_dt1{0.0f};
    float w0{0.0f};
    float w1{0.0f};
    float chi2_ndof_down{0.0f};
    float t0_down{0.0f};
    float sig_t0_down{0.0f};
    float pull0{0.0f};
    float pull1{0.0f};
    float u0{0.0f};
    float u1{0.0f};
    float zu0{0.0f};
    float zu1{0.0f};
    float dchi2_back{0.0f};
    float z_comb{0.0f};
};

struct T5McRecord {
    int32_t run{0};
    int64_t eventID{0};
    uint8_t region{0};
    uint8_t genie_class{0};
    uint8_t in_lead_block{0};
    uint8_t primary_valid{0};
    uint8_t confirmed{0};
    uint16_t flags{0};
    int16_t truth_pdg{0};
    int16_t truth_bin30_m12{-1};
    int16_t truth_bin30_p12{-1};
    float incoming_px_mev{0.0f};
    float incoming_py_mev{0.0f};
    float incoming_pz_mev{0.0f};
    float truth_E_gev{0.0f};
    float truth_pz_mu_gev{0.0f};
    float truth_y_inel{0.0f};
    float truth_x_mm{0.0f};
    float truth_y_mm{0.0f};
    float truth_z_mm{0.0f};
    float truth_r_mm{0.0f};
    float crossing_angle_urad{0.0f};
    float pz0_gev{0.0f};
    float p0_gev{0.0f};
    float lead_q{0.0f};
    float theta_mrad{0.0f};
    float r_max{0.0f};
    float r_ift{0.0f};
    float r_vn{0.0f};
    float chi2_ndf{0.0f};
    float x_vn_mm{0.0f};
    float y_vn_mm{0.0f};
    float x_v1_mm{0.0f};
    float y_v1_mm{0.0f};
    float v20_q{0.0f};
    float v21_q{0.0f};
    float tim_q_match{0.0f};
    float ps0_q{0.0f};
    float ps1_q{0.0f};
    float q0_raw{0.0f};
    float q1_raw{0.0f};
    float q0_red{0.0f};
    float q1_red{0.0f};
    float w0{0.0f};
    float w1{0.0f};
    float dt0{0.0f};
    float dt1{0.0f};
    float sig_dt0{0.0f};
    float sig_dt1{0.0f};
    float dt0_unsmeared{0.0f};
    float dt1_unsmeared{0.0f};
    float dt0_cone75{0.0f};
    float dt1_cone75{0.0f};
    float sig_dt0_cone75{0.0f};
    float sig_dt1_cone75{0.0f};
    float u0{0.0f};
    float u1{0.0f};
    float pull0{0.0f};
    float pull1{0.0f};
    float zu0{0.0f};
    float zu1{0.0f};
    float t0_down{0.0f};
    float sig_t0_down{0.0f};
    float chi2_ndof_down{0.0f};
    float dchi2_back{0.0f};
    float z_comb{0.0f};
    float z_misalign{0.0f};
    std::array<float, 62> x_ml{};
};

struct ScannerTrackData {
    int nTracks{0};
    int leadIdx{-1};
    double leadPz0GeV{kNaN};
    double leadP0GeV{kNaN};
    double leadPx0GeV{kNaN};
    double leadPy0GeV{kNaN};
    double leadCharge{kNaN};
    uint32_t leadNLayers{0};
    double leadNDoF{kNaN};
    double leadChi2NDF{kNaN};
    double leadRMax{kNaN};
    double leadThetaMrad{kNaN};
    std::array<double, 8> x{};
    std::array<double, 8> y{};
    std::array<bool, 8> validPos{};
    // Full ML track fields (populated if isGenie)
    double x0{kNaN}, y0{kNaN}, z0{kNaN};
    double xCalo{kNaN}, yCalo{kNaN};
    double px1GeV{kNaN}, py1GeV{kNaN}, pz1GeV{kNaN}, p1GeV{kNaN};
    double x1{kNaN}, y1{kNaN}, z1{kNaN};
    double moduleEta0{kNaN}, modulePhi0{kNaN}, zAtMaxRadius{kNaN};
};

struct ScannerGenieInfo {
    uint8_t genieClass{0}; // 1=fid numu CC, 2=nonfid numu CC, 3=nue CC, 4=nutau CC, 5=NC
    bool vetoCaloNuPmt{false};
    bool inLeadBlock{false};
    bool primaryValid{false};
    bool confirmed{false};
    int16_t pdg{0};
    double pxMeV{kNaN}, pyMeV{kNaN}, pzMeV{kNaN}, massMeV{kNaN};
    double truthEGeV{kNaN}, truthPzMuGeV{kNaN}, truthYInel{kNaN};
    double xMm{kNaN}, yMm{kNaN}, zMm{kNaN}, rMm{kNaN};
    double crossingAngleUrad{0.0};
    int16_t bin30M12{-1}, bin30P12{-1};
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
    std::array<float, 62> xMl{};
    ScannerGenieInfo genie;
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

double sanitizeSentinel(double v, double sent = 999999.0) {
    if (!std::isfinite(v) || v == sent) return kNaN;
    return v;
}

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
ROOT::RDF::RNode attachTrackDataColumn(ROOT::RDF::RNode node, bool isGenie) {
    if (!isGenie) {
        return node.Define("_tk",
            [](const ROOT::VecOps::RVec<double>& pz0,
               const ROOT::VecOps::RVec<double>& p0,
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
                td.leadIdx = i0;
                td.leadPz0GeV = pz0[i0] * 1e-3;
                td.leadP0GeV = (i0 < static_cast<int>(p0.size())) ? (p0[i0] * 1e-3) : kNaN;
                td.leadPx0GeV = (i0 < static_cast<int>(px0.size())) ? (px0[i0] * 1e-3) : kNaN;
                td.leadPy0GeV = (i0 < static_cast<int>(py0.size())) ? (py0[i0] * 1e-3) : kNaN;
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
            {"Track_pz0", "Track_p0", "Track_px0", "Track_py0", "Track_nLayers", "Track_nDoF", "Track_Chi2", "Track_r_atMaxRadius",
             "Track_X_atVetoNu", "Track_Y_atVetoNu",
             "Track_X_atVetoStation1", "Track_Y_atVetoStation1",
             "Track_X_atVetoStation2", "Track_Y_atVetoStation2",
             "Track_X_atTrig", "Track_Y_atTrig",
             "Track_X_atPreshower1", "Track_Y_atPreshower1",
             "Track_X_atPreshower2", "Track_Y_atPreshower2",
             "Track_X_atMuon1", "Track_Y_atMuon1",
             "Track_X_atMuon2", "Track_Y_atMuon2"});
    }

    return node.Define("_tk",
        [](const ROOT::VecOps::RVec<double>& pz0,
           const ROOT::VecOps::RVec<double>& p0,
           const ROOT::VecOps::RVec<double>& px0,
           const ROOT::VecOps::RVec<double>& py0,
           const ROOT::VecOps::RVec<int>& charge,
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
           const ROOT::VecOps::RVec<double>& xM2, const ROOT::VecOps::RVec<double>& yM2,
           const ROOT::VecOps::RVec<double>& tx0, const ROOT::VecOps::RVec<double>& ty0, const ROOT::VecOps::RVec<double>& tz0,
           const ROOT::VecOps::RVec<double>& xCa, const ROOT::VecOps::RVec<double>& yCa,
           const ROOT::VecOps::RVec<double>& p1, const ROOT::VecOps::RVec<double>& px1,
           const ROOT::VecOps::RVec<double>& py1, const ROOT::VecOps::RVec<double>& pz1,
           const ROOT::VecOps::RVec<double>& tx1, const ROOT::VecOps::RVec<double>& ty1, const ROOT::VecOps::RVec<double>& tz1,
           const ROOT::VecOps::RVec<int>& eta0, const ROOT::VecOps::RVec<int>& phi0,
           const ROOT::VecOps::RVec<double>& zMaxR) -> ScannerTrackData {
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
            td.leadIdx = i0;
            td.leadCharge = (i0 < static_cast<int>(charge.size())) ? static_cast<double>(charge[i0]) : kNaN;
            td.leadNLayers = (i0 < static_cast<int>(nLayers.size())) ? static_cast<uint32_t>(nLayers[i0]) : 0u;
            td.leadNDoF = (i0 < static_cast<int>(ndof.size())) ? ndof[i0] : kNaN;
            td.leadChi2NDF = (i0 < static_cast<int>(chi2.size()) && td.leadNDoF > 0.0) ? (chi2[i0] / td.leadNDoF) : kNaN;
            td.leadRMax = (i0 < static_cast<int>(rmax.size())) ? rmax[i0] : kNaN;

            auto atD = [&](const ROOT::VecOps::RVec<double>& v) -> double {
                return (i0 < static_cast<int>(v.size())) ? sanitizeSentinel(v[i0]) : kNaN;
            };
            td.leadPz0GeV = atD(pz0) * 1e-3;
            td.leadP0GeV = atD(p0) * 1e-3;
            td.leadPx0GeV = atD(px0) * 1e-3;
            td.leadPy0GeV = atD(py0) * 1e-3;
            td.leadThetaMrad = (std::isfinite(td.leadPz0GeV) && std::isfinite(td.leadPx0GeV) && std::isfinite(td.leadPy0GeV))
                ? std::atan2(std::hypot(td.leadPx0GeV, td.leadPy0GeV), td.leadPz0GeV) * 1000.0 : kNaN;
            td.x0 = atD(tx0); td.y0 = atD(ty0); td.z0 = atD(tz0);
            td.xCalo = atD(xCa); td.yCalo = atD(yCa);
            td.p1GeV = atD(p1) * 1e-3;
            td.px1GeV = atD(px1) * 1e-3;
            td.py1GeV = atD(py1) * 1e-3;
            td.pz1GeV = atD(pz1) * 1e-3;
            td.x1 = atD(tx1); td.y1 = atD(ty1); td.z1 = atD(tz1);
            td.moduleEta0 = (i0 < static_cast<int>(eta0.size()) && eta0[i0] != 999999) ? static_cast<double>(eta0[i0]) : kNaN;
            td.modulePhi0 = (i0 < static_cast<int>(phi0.size()) && phi0[i0] != 999999) ? static_cast<double>(phi0[i0]) : kNaN;
            td.zAtMaxRadius = atD(zMaxR);

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
        {"Track_pz0", "Track_p0", "Track_px0", "Track_py0", "Track_charge",
         "Track_nLayers", "Track_nDoF", "Track_Chi2", "Track_r_atMaxRadius",
         "Track_X_atVetoNu", "Track_Y_atVetoNu",
         "Track_X_atVetoStation1", "Track_Y_atVetoStation1",
         "Track_X_atVetoStation2", "Track_Y_atVetoStation2",
         "Track_X_atTrig", "Track_Y_atTrig",
         "Track_X_atPreshower1", "Track_Y_atPreshower1",
         "Track_X_atPreshower2", "Track_Y_atPreshower2",
         "Track_X_atMuon1", "Track_Y_atMuon1",
         "Track_X_atMuon2", "Track_Y_atMuon2",
         "Track_x0", "Track_y0", "Track_z0",
         "Track_X_atCalo", "Track_Y_atCalo",
         "Track_p1", "Track_px1", "Track_py1", "Track_pz1",
         "Track_x1", "Track_y1", "Track_z1",
         "Track_module_eta0", "Track_module_phi0", "Track_z_atMaxRadius"});
}

ROOT::RDF::RNode prepareNode(
    TChain& chain,
    const SchemaSignature& sig,
    const std::shared_ptr<const GRLUtils::GRLTimes>& grl,
    bool bypassGrl,
    bool isMC,
    bool isGenie) {

    ROOT::RDF::RNode df = ROOT::RDataFrame(chain);
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
    auto ensureDouble = [&](const std::string& name, Double_t val) {
        if (!hasCol(name)) {
            df = df.Define(name, [val]() -> Double_t { return val; }, {});
            colSet.insert(name);
        }
    };
    auto ensureRVecD = [&](const std::string& name) {
        if (!hasCol(name)) {
            df = df.Define(name, []() { return ROOT::VecOps::RVec<double>{}; }, {});
            colSet.insert(name);
        }
    };
    auto ensureRVecI = [&](const std::string& name) {
        if (!hasCol(name)) {
            df = df.Define(name, []() { return ROOT::VecOps::RVec<int>{}; }, {});
            colSet.insert(name);
        }
    };

    for (const char* p : {"VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21",
                          "Timing0", "Timing1", "Timing2", "Timing3",
                          "Preshower0", "Preshower1", "Preshower2", "Preshower3", "Muon0", "Muon1"}) {
        const std::string sp(p);
        ensureInt(sp + "_status", -1);
        ensureFloat(sp + "_bcidtime", 0.0f);
        ensureFloat(sp + "_triggertime", 0.0f);
        ensureFloat(sp + "_localtime", 0.0f);
        ensureFloat(sp + "_raw_charge", 0.0f);
        ensureFloat(sp + "_width", 0.0f);
        ensureFloat(sp + "_charge", 0.0f);
    }

    ensureInt("distanceToCollidingBCID", 0);
    ensureInt("distanceToInboundB1", -9999);
    ensureInt("distanceToUnpairedB1", -9999);
    ensureInt("distanceToUnpairedB2", -9999);
    ensureInt("inputBits", 0);
    ensureFloat("VetoNu0_reduced_charge", -1.0f);
    ensureFloat("VetoNu1_reduced_charge", -1.0f);
    ensureRVecD("Track_X_atMuon1"); ensureRVecD("Track_Y_atMuon1");
    ensureRVecD("Track_X_atMuon2"); ensureRVecD("Track_Y_atMuon2");

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
        df = attachTrackDataColumn<unsigned int>(df, isGenie);
    } else {
        df = attachTrackDataColumn<int>(df, isGenie);
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

    if (!isGenie) {
        df = df.Define("_aux",
            [sig](Float_t v20, Float_t v21,
                  Float_t t0, Float_t t1, Float_t t2, Float_t t3,
                  Float_t p0, Float_t p1,
                  Float_t vn0red, Float_t vn1red,
                  Int_t vn0st, Int_t vn1st, Int_t v20st, Int_t v21st,
                  Int_t ps0st, Int_t ps1st,
                  Int_t t0st, Int_t t1st, Int_t t2st, Int_t t3st) -> ScannerEventAux {
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
                a.xMl.fill(kNaNF);
                return a;
            },
            {"Veto20_charge", "Veto21_charge",
             "Timing0_charge", "Timing1_charge", "Timing2_charge", "Timing3_charge",
             "Preshower0_charge", "Preshower1_charge",
             "VetoNu0_reduced_charge", "VetoNu1_reduced_charge",
             "VetoNu0_status", "VetoNu1_status", "Veto20_status", "Veto21_status",
             "Preshower0_status", "Preshower1_status",
             "Timing0_status", "Timing1_status", "Timing2_status", "Timing3_status"});
        return df;
    }

    ensureFloat("crossingAngle", 0.0f);
    ensureInt("truthBarcode", -1);
    df = df.Define("_genie",
        [sig](Int_t run,
              Float_t crossingAngle,
              const ScannerTrackData& tk,
              const ROOT::VecOps::RVec<int>& tpdg,
              const ROOT::VecOps::RVec<double>& tpx,
              const ROOT::VecOps::RVec<double>& tpy,
              const ROOT::VecOps::RVec<double>& tpz,
              const ROOT::VecOps::RVec<double>& tm,
              const ROOT::VecOps::RVec<double>& tpxVtx,
              const ROOT::VecOps::RVec<double>& tpyVtx,
              const ROOT::VecOps::RVec<double>& tpzVtx,
              const ROOT::VecOps::RVec<double>& tdx,
              const ROOT::VecOps::RVec<double>& tdy,
              const ROOT::VecOps::RVec<double>& tdz,
              const ROOT::VecOps::RVec<int>& tkTpdg,
              const ROOT::VecOps::RVec<int>& tkTpdgPar,
              const ROOT::VecOps::RVec<int>& tkTbPar,
              Int_t truthBarcode) -> ScannerGenieInfo {
            ScannerGenieInfo g;
            g.crossingAngleUrad = (sig.hasCrossingAngle && std::isfinite(crossingAngle) && std::abs(crossingAngle) > 1.0f)
                ? static_cast<double>(crossingAngle) : defaultMcCrossingAngleUrad(run);
            if (!sig.hasTruth || tpdg.empty() || tdx.empty() || tdy.empty() || tdz.empty() || tpz.empty()) {
                return g;
            }
            const int pdg0 = tpdg[0];
            g.pdg = static_cast<int16_t>(pdg0);
            g.pxMeV = tpx[0];
            g.pyMeV = tpy[0];
            g.pzMeV = tpz[0];
            g.massMeV = (!tm.empty()) ? tm[0] : 0.0;
            g.xMm = tdx[0];
            g.yMm = tdy[0];
            g.zMm = tdz[0];
            g.rMm = std::hypot(g.xMm, g.yMm);
            g.truthEGeV = std::sqrt(g.pxMeV * g.pxMeV + g.pyMeV * g.pyMeV + g.pzMeV * g.pzMeV + g.massMeV * g.massMeV) * 1e-3;

            bool isCC = false;
            for (int p : tpdg) {
                const int ap = std::abs(p);
                if (ap == 11 || ap == 13 || ap == 15) { isCC = true; break; }
            }
            g.vetoCaloNuPmt = isGenieCaloNuRun(run) && inCaloNuPMTExact(g.zMm);
            const bool inBox = inFaserNuBoxExact(g.xMm, g.yMm, g.zMm);
            const bool inLead = inLeadBlockExact(g.xMm, g.yMm, g.zMm);
            g.inLeadBlock = inLead;
            const double pzGeV = g.pzMeV * 1e-3;
            const int ap0 = std::abs(pdg0);

            if (isCC && ap0 == 14 && (inBox || inLead) && g.rMm < 100.0 && pzGeV > 100.0) {
                g.genieClass = 1;
            } else if (isCC && ap0 == 14) {
                g.genieClass = 2;
            } else if (isCC && ap0 == 12) {
                g.genieClass = 3;
            } else if (isCC && ap0 == 16) {
                g.genieClass = 4;
            } else {
                g.genieClass = 5;
            }

            // Primary outgoing lepton (match ml/frozen_evaluation.py truth_diagnostics)
            const int targetLepPdg = (pdg0 > 0) ? (pdg0 - 1) : (pdg0 + 1);
            int candIdx = -1;
            int nCand = 0;
            for (size_t i = 0; i < tpdg.size(); ++i) {
                if (tpdg[i] != targetLepPdg) continue;
                if (i < tpxVtx.size() && i < tpyVtx.size() && i < tpzVtx.size() &&
                    std::abs(tpxVtx[i] - g.xMm) <= 1e-4 &&
                    std::abs(tpyVtx[i] - g.yMm) <= 1e-4 &&
                    std::abs(tpzVtx[i] - g.zMm) <= 1e-4) {
                    candIdx = static_cast<int>(i);
                    ++nCand;
                }
            }
            if (nCand == 1 && candIdx >= 0) {
                g.primaryValid = true;
                const double lpx = tpx[candIdx], lpy = tpy[candIdx], lpz = tpz[candIdx];
                const double lm = (candIdx < static_cast<int>(tm.size())) ? tm[candIdx] : 105.658;
                const double le = std::sqrt(lpx * lpx + lpy * lpy + lpz * lpz + lm * lm) * 1e-3;
                g.truthPzMuGeV = lpz * 1e-3;
                g.truthYInel = 1.0 - le / std::max(g.truthEGeV, 1e-6);
                const int i0 = tk.leadIdx;
                if (i0 >= 0 &&
                    i0 < static_cast<int>(tkTpdg.size()) &&
                    i0 < static_cast<int>(tkTpdgPar.size()) &&
                    i0 < static_cast<int>(tkTbPar.size())) {
                    g.confirmed = (tkTpdg[i0] == tpdg[candIdx]) &&
                                  (tkTpdgPar[i0] == pdg0) &&
                                  (truthBarcode < 0 || tkTbPar[i0] == truthBarcode);
                }
            }

            if (g.genieClass == 1 && std::isfinite(g.truthEGeV) && g.truthEGeV > 0.0) {
                const double qLep = (pdg0 > 0) ? -1.0 : +1.0;
                const double qOverE = qLep / g.truthEGeV;
                const double yM12 = computeRapidityLOS(g.xMm, g.yMm, g.crossingAngleUrad, -kLosYShiftMm);
                const double yP12 = computeRapidityLOS(g.xMm, g.yMm, g.crossingAngleUrad, +kLosYShiftMm);
                g.bin30M12 = static_cast<int16_t>(computeBin30(yM12, qOverE));
                g.bin30P12 = static_cast<int16_t>(computeBin30(yP12, qOverE));
            }
            return g;
        },
        {"run", "crossingAngle", "_tk",
         "truth_pdg", "truth_px", "truth_py", "truth_pz", "truth_m",
         "truth_prod_x", "truth_prod_y", "truth_prod_z",
         "truth_dec_x", "truth_dec_y", "truth_dec_z",
         "t_pdg", "t_pdg_parent", "t_barcode_parent", "truthBarcode"});

    df = df.Define("_ml_ev",
        [sig](const ScannerTrackData& tk,
              Int_t nC0, Int_t nC1, Int_t nC2, Int_t nC3,
              Int_t sp, Int_t tseg, Int_t ltrk, Int_t propErr,
              const ROOT::VecOps::RVec<double>& spX, const ROOT::VecOps::RVec<double>& spY,
              Float_t c0E, Float_t c1E, Float_t c2E, Float_t c3E,
              Int_t c0S, Int_t c1S, Int_t c2S, Int_t c3S) -> std::array<float, 62> {
            std::array<float, 62> x{};
            x.fill(kNaNF);
            auto setPos = [&](int idx, double v) { x[idx] = (std::isfinite(v) && v > 0.0) ? static_cast<float>(v) : kNaNF; };
            auto setNonNeg = [&](int idx, double v) { x[idx] = (std::isfinite(v) && v >= 0.0) ? static_cast<float>(v) : kNaNF; };
            auto setSigned = [&](int idx, double v) { x[idx] = std::isfinite(v) ? static_cast<float>(v) : kNaNF; };
            auto setSent = [&](int idx, double v) {
                const double s = sanitizeSentinel(v);
                x[idx] = std::isfinite(s) ? static_cast<float>(s) : kNaNF;
            };
            auto setCount = [&](int idx, Int_t v) {
                x[idx] = (v >= 0) ? static_cast<float>(v) : kNaNF;
            };

            setPos(0, tk.leadPz0GeV);
            setSigned(1, tk.leadPx0GeV);
            setSigned(2, tk.leadPy0GeV);
            x[3] = (tk.leadCharge == -1.0 || tk.leadCharge == 1.0) ? static_cast<float>(tk.leadCharge) : kNaNF;
            setNonNeg(4, tk.leadThetaMrad);
            setNonNeg(5, tk.leadChi2NDF);
            setNonNeg(6, (std::isfinite(tk.leadNDoF) && tk.leadNDoF == std::floor(tk.leadNDoF)) ? tk.leadNDoF : kNaN);
            x[7] = (tk.nTracks > 0) ? static_cast<float>(tk.leadNLayers) : kNaNF;
            setNonNeg(8, tk.leadRMax);
            const double rVn = tk.validPos[0] ? std::hypot(tk.x[0], tk.y[0])
                : ((tk.nTracks > 0 && std::isfinite(tk.x[0]) && std::isfinite(tk.y[0])) ? std::hypot(tk.x[0], tk.y[0]) : kNaN);
            setNonNeg(9, rVn);
            setSent(10, tk.x0);
            setSent(11, tk.y0);
            setSent(12, tk.z0);
            setSent(13, tk.x[0]);
            setSent(14, tk.y[0]);
            setSent(15, tk.xCalo);
            setSent(16, tk.yCalo);

            setCount(17, nC0);
            setCount(18, nC1);
            setCount(19, nC2);
            setCount(20, nC3);
            setCount(21, sp);
            setCount(22, tseg);
            setCount(23, ltrk);

            // Scintillators [24..36] populated in _aux
            // Calo [37..41] scaled to WAVE-Calibration-01-LG and masked with kCaloFitInvalidMask
            auto calVal = [&](Double_t e, Int_t st) -> double {
                if (!std::isfinite(e) || (static_cast<uint64_t>(st) & kCaloFitInvalidMask) != 0ULL) return kNaN;
                return (e * 1e-3) * sig.calo01LgScale;
            };
            const double ce0 = calVal(c0E, c0S), ce1 = calVal(c1E, c1S), ce2 = calVal(c2E, c2S), ce3 = calVal(c3E, c3S);
            setSigned(37, ce0);
            setSigned(38, ce1);
            setSigned(39, ce2);
            setSigned(40, ce3);
            setSigned(41, ce0 + ce1 + ce2 + ce3); // NaN if any module is NaN

            // SpacePoints [42..45]
            if (!spX.empty()) {
                double sx = 0.0, sxx = 0.0;
                for (double v : spX) { sx += v; sxx += v * v; }
                const double mx = sx / static_cast<double>(spX.size());
                const double rx = std::sqrt(std::max(0.0, sxx / static_cast<double>(spX.size()) - mx * mx));
                setSent(42, mx);
                setNonNeg(43, rx);
            }
            if (!spY.empty()) {
                double sy = 0.0, syy = 0.0;
                for (double v : spY) { sy += v; syy += v * v; }
                const double my = sy / static_cast<double>(spY.size());
                const double ry = std::sqrt(std::max(0.0, syy / static_cast<double>(spY.size()) - my * my));
                setSent(44, my);
                setNonNeg(45, ry);
            }

            // Track station-1 and bends [46..61]
            setSigned(46, tk.px1GeV);
            setSigned(47, tk.py1GeV);
            const double x0c = sanitizeSentinel(tk.x0), y0c = sanitizeSentinel(tk.y0), z0c = sanitizeSentinel(tk.z0);
            const double x1c = sanitizeSentinel(tk.x1), y1c = sanitizeSentinel(tk.y1), z1c = sanitizeSentinel(tk.z1);
            setSigned(48, x1c);
            setSigned(49, y1c);
            setSigned(50, z1c);
            const bool goodQ = (tk.leadCharge == -1.0 || tk.leadCharge == 1.0);
            if (goodQ && std::isfinite(tk.leadP0GeV) && tk.leadP0GeV > 0.0) {
                setSigned(51, tk.leadCharge / tk.leadP0GeV);
            }
            if (goodQ && std::isfinite(tk.p1GeV) && tk.p1GeV > 0.0) {
                setSigned(52, tk.leadCharge / tk.p1GeV);
            }
            const double dz = z1c - z0c;
            if (std::isfinite(dz) && dz > 0.0) {
                setPos(53, dz);
                setSigned(56, (x1c - x0c) / dz);
                setSigned(57, (y1c - y0c) / dz);
            }
            if (std::isfinite(tk.leadPz0GeV) && tk.leadPz0GeV > 0.0 && std::isfinite(tk.pz1GeV) && tk.pz1GeV > 0.0) {
                setSigned(54, tk.px1GeV / tk.pz1GeV - tk.leadPx0GeV / tk.leadPz0GeV);
                setSigned(55, tk.py1GeV / tk.pz1GeV - tk.leadPy0GeV / tk.leadPz0GeV);
            }
            if (tk.moduleEta0 == -1.0 || tk.moduleEta0 == 1.0) x[58] = static_cast<float>(tk.moduleEta0);
            if (tk.modulePhi0 == 0.0 || tk.modulePhi0 == 1.0 || tk.modulePhi0 == 2.0 || tk.modulePhi0 == 3.0) {
                x[59] = static_cast<float>(tk.modulePhi0);
            }
            setSent(60, tk.zAtMaxRadius);
            if (propErr == 0 || propErr == 1) x[61] = static_cast<float>(propErr);
            return x;
        },
        {"_tk",
         "nClusters0", "nClusters1", "nClusters2", "nClusters3",
         "SpacePoints", "TrackSegments", "longTracks", "Track_PropagationError",
         "SpacePoint_x", "SpacePoint_y",
         "Calo0_E_EM", "Calo1_E_EM", "Calo2_E_EM", "Calo3_E_EM",
         "Calo0_status", "Calo1_status", "Calo2_status", "Calo3_status"});

    df = df.Define("_aux",
        [sig](const ScannerGenieInfo& g,
              std::array<float, 62> xMl,
              Float_t v20c, Float_t v21c,
              Float_t t0c, Float_t t1c, Float_t t2c, Float_t t3c,
              Float_t p0c, Float_t p1c,
              Float_t vn0r, Float_t vn1r, Float_t v10r, Float_t v20r, Float_t v21r,
              Float_t t0r, Float_t t1r, Float_t t2r, Float_t t3r, Float_t p0r, Float_t p1r,
              Int_t vn0s, Int_t vn1s, Int_t v10s, Int_t v20s, Int_t v21s,
              Int_t t0s, Int_t t1s, Int_t t2s, Int_t t3s, Int_t p0s, Int_t p1s,
              Float_t vn0red, Float_t vn1red) -> ScannerEventAux {
            ScannerEventAux a;
            a.veto20Charge = v20c;
            a.veto21Charge = v21c;
            a.timingBottomCharge = t0c + t1c;
            a.timingTopCharge = t2c + t3c;
            a.preshower0Charge = p0c;
            a.preshower1Charge = p1c;
            a.vetoNu0ReducedCharge = sig.hasReducedCharge ? vn0red : -1.0f;
            a.vetoNu1ReducedCharge = sig.hasReducedCharge ? vn1red : -1.0f;
            a.vn0Status = vn0s;
            a.vn1Status = vn1s;
            a.v20Status = v20s;
            a.v21Status = v21s;
            a.ps0Status = p0s;
            a.ps1Status = p1s;
            a.t0Status = t0s;
            a.t1Status = t1s;
            a.t2Status = t2s;
            a.t3Status = t3s;
            a.genie = g;

            auto rawVal = [](Float_t q, Int_t st) -> float {
                if (!std::isfinite(q) || (static_cast<uint64_t>(st) & kWaveInvalidMask) != 0ULL) return kNaNF;
                return q;
            };
            xMl[24] = rawVal(vn0r, vn0s);
            xMl[25] = rawVal(vn1r, vn1s);
            xMl[26] = rawVal(v10r, v10s);
            xMl[27] = rawVal(v20r, v20s);
            xMl[28] = rawVal(v21r, v21s);
            xMl[29] = rawVal(t0r, t0s);
            xMl[30] = rawVal(t1r, t1s);
            xMl[31] = rawVal(t2r, t2s);
            xMl[32] = rawVal(t3r, t3s);
            xMl[33] = rawVal(p0r, p0s);
            xMl[34] = rawVal(p1r, p1s);
            xMl[35] = rawVal(vn0red, vn0s);
            xMl[36] = rawVal(vn1red, vn1s);
            a.xMl = xMl;
            return a;
        },
        {"_genie", "_ml_ev",
         "Veto20_charge", "Veto21_charge",
         "Timing0_charge", "Timing1_charge", "Timing2_charge", "Timing3_charge",
         "Preshower0_charge", "Preshower1_charge",
         "VetoNu0_raw_charge", "VetoNu1_raw_charge", "Veto10_raw_charge", "Veto20_raw_charge", "Veto21_raw_charge",
         "Timing0_raw_charge", "Timing1_raw_charge", "Timing2_raw_charge", "Timing3_raw_charge",
         "Preshower0_raw_charge", "Preshower1_raw_charge",
         "VetoNu0_status", "VetoNu1_status", "Veto10_status", "Veto20_status", "Veto21_status",
         "Timing0_status", "Timing1_status", "Timing2_status", "Timing3_status", "Preshower0_status", "Preshower1_status",
         "VetoNu0_reduced_charge", "VetoNu1_reduced_charge"});
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

void writeOutput(
    const std::string& outputPath,
    bool isGenie,
    const std::map<int, T5RunStats>& runStats,
    const std::map<std::string, T5PeriodGrid>& perGrids,
    const std::map<int, T5TruthHists>& truthHists,
    std::vector<T5BkgRecord>& bkgRecs,
    std::vector<T5McRecord>& mcRecs) {

    std::unique_ptr<TFile> outFile(TFile::Open(outputPath.c_str(), "RECREATE"));
    if (!outFile || outFile->IsZombie()) {
        throw std::runtime_error("Cannot create T5 output: " + outputPath);
    }

    TTree* st = new TTree("t5_run_summary", "Stage T5 per-run summary and blinding telemetry");
    T5RunStats row;
    std::string period;
    st->Branch("run", &row.run);
    st->Branch("period", &period);
    st->Branch("is_mc", &row.isMC);
    st->Branch("has_reduced_charge", &row.hasReducedCharge);
    st->Branch("n_total", &row.nTotal);
    st->Branch("n_grl_fail", &row.nGrlFail);
    st->Branch("n_blinded", &row.nBlinded);
    st->Branch("n_no_offsets", &row.nNoOffsets);
    st->Branch("n_colliding", &row.nColliding);
    st->Branch("n_beam1", &row.nBeam1);
    st->Branch("n_unpaired", &row.nUnpaired);
    st->Branch("n_empty", &row.nEmpty);
    st->Branch("n_acc_denom_beam1", &row.nAccDenomBeam1);
    st->Branch("n_acc_denom_unpaired", &row.nAccDenomUnpaired);
    st->Branch("n_acc_denom_empty", &row.nAccDenomEmpty);
    st->Branch("n_sr_zonea_red30", &row.nSrZoneARed30);
    st->Branch("n_sr_zonea_raw40", &row.nSrZoneARaw40);
    st->Branch("n_sr_zonea_era", &row.nSrZoneAEra);
    st->Branch("n_sr_prompt_2hit_u1p0", &row.nSrPrompt2HitU1p0);
    st->Branch("n_sr_prompt_2hit_dt1p0", &row.nSrPrompt2HitDt1p0);
    st->Branch("n_sr_1hit0_era", &row.nSr1Hit0Era);
    st->Branch("n_sr_1hit1_era", &row.nSr1Hit1Era);
    st->Branch("n_geom_all", &row.nGeomAll);
    st->Branch("n_geom_zonea_era", &row.nGeomZoneAEra);
    st->Branch("n_geom_prompt_2hit_u1p0", &row.nGeomPrompt2HitU1p0);
    st->Branch("n_geom_prompt_2hit_dt1p0", &row.nGeomPrompt2HitDt1p0);
    st->Branch("n_edge_vn_all", &row.nEdgeVnAll);
    st->Branch("n_edge_vn_zonea_era", &row.nEdgeVnZoneAEra);
    st->Branch("n_edge_vn_zoneb_era", &row.nEdgeVnZoneBEra);
    st->Branch("n_fid_box", &row.nFidBox);
    st->Branch("n_fid_lead", &row.nFidLead);
    for (const auto& [r, s] : runStats) {
        row = s;
        period = s.isMC ? TimingCalibrator::mcFamilyForRun(r) : TimingCalibrator::periodForDataRun(r);
        st->Fill();
    }
    st->Write();

    if (!isGenie) {
        std::sort(bkgRecs.begin(), bkgRecs.end(), [](const T5BkgRecord& a, const T5BkgRecord& b) {
            if (a.run != b.run) return a.run < b.run;
            return a.eventID < b.eventID;
        });
        TTree* bt = new TTree("t5_bkg_events", "Stage T5 unblinded Zone-B/tail events for WP & S3 optimization");
        T5BkgRecord rec;
        bt->Branch("run", &rec.run);
        bt->Branch("eventID", &rec.eventID);
        bt->Branch("region", &rec.region);
        bt->Branch("is_prompt_sub", &rec.is_prompt_sub);
        bt->Branch("flags", &rec.flags);
        bt->Branch("pz0_gev", &rec.pz0_gev);
        bt->Branch("r_max", &rec.r_max);
        bt->Branch("r_ift", &rec.r_ift);
        bt->Branch("r_vn", &rec.r_vn);
        bt->Branch("theta_mrad", &rec.theta_mrad);
        bt->Branch("q0_raw", &rec.q0_raw);
        bt->Branch("q1_raw", &rec.q1_raw);
        bt->Branch("q0_red", &rec.q0_red);
        bt->Branch("q1_red", &rec.q1_red);
        bt->Branch("dt0", &rec.dt0);
        bt->Branch("dt1", &rec.dt1);
        bt->Branch("sig_dt0", &rec.sig_dt0);
        bt->Branch("sig_dt1", &rec.sig_dt1);
        bt->Branch("w0", &rec.w0);
        bt->Branch("w1", &rec.w1);
        bt->Branch("chi2_ndof_down", &rec.chi2_ndof_down);
        bt->Branch("t0_down", &rec.t0_down);
        bt->Branch("sig_t0_down", &rec.sig_t0_down);
        bt->Branch("pull0", &rec.pull0);
        bt->Branch("pull1", &rec.pull1);
        bt->Branch("u0", &rec.u0);
        bt->Branch("u1", &rec.u1);
        bt->Branch("zu0", &rec.zu0);
        bt->Branch("zu1", &rec.zu1);
        bt->Branch("dchi2_back", &rec.dchi2_back);
        bt->Branch("z_comb", &rec.z_comb);
        for (const auto& item : bkgRecs) {
            rec = item;
            bt->Fill();
        }
        bt->Write();

        for (const auto& [per, g] : perGrids) {
            TDirectory* pdir = outFile->mkdir(("period_" + per).c_str());
            pdir->cd();
            for (int wi = 0; wi < kNWCap; ++wi) {
                const std::string wn(kWCapNames[wi]);
                g.denSrU[wi].toTH2D("h_den_sr_u_" + wn, "SR prompt u;r_VN;Q_max")->Write();
                g.denSrDt[wi].toTH2D("h_den_sr_dt_" + wn, "SR prompt dt;r_VN;Q_max")->Write();
                g.denGeomU[wi].toTH2D("h_den_geom_u_" + wn, "CR-Geom prompt u;r_VN;Q_max")->Write();
                g.denGeomDt[wi].toTH2D("h_den_geom_dt_" + wn, "CR-Geom prompt dt;r_VN;Q_max")->Write();
                g.tailGeomU0Pos[wi].toTH3D("h_tail_geom_u0_pos_" + wn, "CR-Geom u0+;r_VN;Q_max;u0")->Write();
                g.tailGeomU1Pos[wi].toTH3D("h_tail_geom_u1_pos_" + wn, "CR-Geom u1+;r_VN;Q_max;u1")->Write();
                g.tailGeomDt0Pos[wi].toTH3D("h_tail_geom_dt0_pos_" + wn, "CR-Geom dt0+;r_VN;Q_max;dt0")->Write();
                g.tailGeomDt1Pos[wi].toTH3D("h_tail_geom_dt1_pos_" + wn, "CR-Geom dt1+;r_VN;Q_max;dt1")->Write();
                g.tailGeomZu0Pos[wi].toTH3D("h_tail_geom_zu0_pos_" + wn, "CR-Geom zu0+;r_VN;Q_max;zu0")->Write();
                g.tailGeomZu1Pos[wi].toTH3D("h_tail_geom_zu1_pos_" + wn, "CR-Geom zu1+;r_VN;Q_max;zu1")->Write();
                g.tailSrU0Neg[wi].toTH3D("h_tail_sr_u0_neg_" + wn, "SR u0-;r_VN;Q_max;|u0|")->Write();
                g.tailSrU1Neg[wi].toTH3D("h_tail_sr_u1_neg_" + wn, "SR u1-;r_VN;Q_max;|u1|")->Write();
                g.tailSrDt0Neg[wi].toTH3D("h_tail_sr_dt0_neg_" + wn, "SR dt0-;r_VN;Q_max;|dt0|")->Write();
                g.tailSrDt1Neg[wi].toTH3D("h_tail_sr_dt1_neg_" + wn, "SR dt1-;r_VN;Q_max;|dt1|")->Write();
                g.tailSrZu0Neg[wi].toTH3D("h_tail_sr_zu0_neg_" + wn, "SR zu0-;r_VN;Q_max;|zu0|")->Write();
                g.tailSrZu1Neg[wi].toTH3D("h_tail_sr_zu1_neg_" + wn, "SR zu1-;r_VN;Q_max;|zu1|")->Write();
                g.accBeam1Vn0[wi].toTH2D("h_acc_b1_vn0_" + wn, "Beam1 VN0 accidental;dt;q0_raw")->Write();
                g.accBeam1Vn1[wi].toTH2D("h_acc_b1_vn1_" + wn, "Beam1 VN1 accidental;dt;q1_raw")->Write();
                g.accEmpUnpVn0[wi].toTH2D("h_acc_eu_vn0_" + wn, "Emp/Unp VN0 accidental;dt;q0_raw")->Write();
                g.accEmpUnpVn1[wi].toTH2D("h_acc_eu_vn1_" + wn, "Emp/Unp VN1 accidental;dt;q1_raw")->Write();
            }
            outFile->cd();
        }
    } else {
        std::sort(mcRecs.begin(), mcRecs.end(), [](const T5McRecord& a, const T5McRecord& b) {
            if (a.run != b.run) return a.run < b.run;
            return a.eventID < b.eventID;
        });
        TTree* mt = new TTree("t5_mc_events", "Stage T5 GENIE relaxed-SR & CR-Geom events + 62 F7 ML features");
        T5McRecord rec;
        mt->Branch("run", &rec.run);
        mt->Branch("eventID", &rec.eventID);
        mt->Branch("region", &rec.region);
        mt->Branch("genie_class", &rec.genie_class);
        mt->Branch("in_lead_block", &rec.in_lead_block);
        mt->Branch("primary_valid", &rec.primary_valid);
        mt->Branch("confirmed", &rec.confirmed);
        mt->Branch("flags", &rec.flags);
        mt->Branch("truth_pdg", &rec.truth_pdg);
        mt->Branch("truth_bin30_m12", &rec.truth_bin30_m12);
        mt->Branch("truth_bin30_p12", &rec.truth_bin30_p12);
        mt->Branch("incoming_px_mev", &rec.incoming_px_mev);
        mt->Branch("incoming_py_mev", &rec.incoming_py_mev);
        mt->Branch("incoming_pz_mev", &rec.incoming_pz_mev);
        mt->Branch("truth_E_gev", &rec.truth_E_gev);
        mt->Branch("truth_pz_mu_gev", &rec.truth_pz_mu_gev);
        mt->Branch("truth_y_inel", &rec.truth_y_inel);
        mt->Branch("truth_x_mm", &rec.truth_x_mm);
        mt->Branch("truth_y_mm", &rec.truth_y_mm);
        mt->Branch("truth_z_mm", &rec.truth_z_mm);
        mt->Branch("truth_r_mm", &rec.truth_r_mm);
        mt->Branch("crossing_angle_urad", &rec.crossing_angle_urad);
        mt->Branch("pz0_gev", &rec.pz0_gev);
        mt->Branch("p0_gev", &rec.p0_gev);
        mt->Branch("lead_q", &rec.lead_q);
        mt->Branch("theta_mrad", &rec.theta_mrad);
        mt->Branch("r_max", &rec.r_max);
        mt->Branch("r_ift", &rec.r_ift);
        mt->Branch("r_vn", &rec.r_vn);
        mt->Branch("chi2_ndf", &rec.chi2_ndf);
        mt->Branch("x_vn_mm", &rec.x_vn_mm);
        mt->Branch("y_vn_mm", &rec.y_vn_mm);
        mt->Branch("x_v1_mm", &rec.x_v1_mm);
        mt->Branch("y_v1_mm", &rec.y_v1_mm);
        mt->Branch("v20_q", &rec.v20_q);
        mt->Branch("v21_q", &rec.v21_q);
        mt->Branch("tim_q_match", &rec.tim_q_match);
        mt->Branch("ps0_q", &rec.ps0_q);
        mt->Branch("ps1_q", &rec.ps1_q);
        mt->Branch("q0_raw", &rec.q0_raw);
        mt->Branch("q1_raw", &rec.q1_raw);
        mt->Branch("q0_red", &rec.q0_red);
        mt->Branch("q1_red", &rec.q1_red);
        mt->Branch("w0", &rec.w0);
        mt->Branch("w1", &rec.w1);
        mt->Branch("dt0", &rec.dt0);
        mt->Branch("dt1", &rec.dt1);
        mt->Branch("sig_dt0", &rec.sig_dt0);
        mt->Branch("sig_dt1", &rec.sig_dt1);
        mt->Branch("dt0_unsmeared", &rec.dt0_unsmeared);
        mt->Branch("dt1_unsmeared", &rec.dt1_unsmeared);
        mt->Branch("dt0_cone75", &rec.dt0_cone75);
        mt->Branch("dt1_cone75", &rec.dt1_cone75);
        mt->Branch("sig_dt0_cone75", &rec.sig_dt0_cone75);
        mt->Branch("sig_dt1_cone75", &rec.sig_dt1_cone75);
        mt->Branch("u0", &rec.u0);
        mt->Branch("u1", &rec.u1);
        mt->Branch("pull0", &rec.pull0);
        mt->Branch("pull1", &rec.pull1);
        mt->Branch("zu0", &rec.zu0);
        mt->Branch("zu1", &rec.zu1);
        mt->Branch("t0_down", &rec.t0_down);
        mt->Branch("sig_t0_down", &rec.sig_t0_down);
        mt->Branch("chi2_ndof_down", &rec.chi2_ndof_down);
        mt->Branch("dchi2_back", &rec.dchi2_back);
        mt->Branch("z_comb", &rec.z_comb);
        mt->Branch("z_misalign", &rec.z_misalign);
        mt->Branch("x_ml", rec.x_ml.data(), "x_ml[62]/F");
        for (const auto& item : mcRecs) {
            rec = item;
            mt->Fill();
        }
        mt->Write();

        TTree* tt = new TTree("t5_truth_denoms", "Stage T5 per-run fiducial 30-bin & 6D truth denominators");
        int trRun = 0;
        std::array<double, 30> bBoxM{}, bLeadM{}, bBoxP{}, bLeadP{};
        std::array<double, 24> fEnu{}, fPzMu{};
        std::array<double, 20> fYInel{}, fRVtx{};
        std::array<double, 30> fZVtx{};
        std::array<double, 2> fQMu{};
        tt->Branch("run", &trRun);
        tt->Branch("bin30_box_m12", bBoxM.data(), "bin30_box_m12[30]/D");
        tt->Branch("bin30_lead_m12", bLeadM.data(), "bin30_lead_m12[30]/D");
        tt->Branch("bin30_box_p12", bBoxP.data(), "bin30_box_p12[30]/D");
        tt->Branch("bin30_lead_p12", bLeadP.data(), "bin30_lead_p12[30]/D");
        tt->Branch("fid_E_nu", fEnu.data(), "fid_E_nu[24]/D");
        tt->Branch("fid_pz_mu", fPzMu.data(), "fid_pz_mu[24]/D");
        tt->Branch("fid_y_inel", fYInel.data(), "fid_y_inel[20]/D");
        tt->Branch("fid_z_vtx", fZVtx.data(), "fid_z_vtx[30]/D");
        tt->Branch("fid_r_vtx", fRVtx.data(), "fid_r_vtx[20]/D");
        tt->Branch("fid_q_mu", fQMu.data(), "fid_q_mu[2]/D");
        for (const auto& [r, th] : truthHists) {
            trRun = r;
            bBoxM = th.bin30BoxM12;
            bLeadM = th.bin30LeadM12;
            bBoxP = th.bin30BoxP12;
            bLeadP = th.bin30LeadP12;
            fEnu = th.fidEnu;
            fPzMu = th.fidPzMu;
            fYInel = th.fidYInel;
            fRVtx = th.fidRVtx;
            fZVtx = th.fidZVtx;
            fQMu = th.fidQMu;
            tt->Fill();
        }
        tt->Write();
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
        if (!probeFileSchema(f, isGenie, sig, &firstRun)) {
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

    std::map<int, T5RunStats> mergedRuns;
    std::map<std::string, T5PeriodGrid> mergedGrids;
    std::map<int, T5TruthHists> mergedTruth;
    std::vector<T5BkgRecord> mergedBkg;
    std::vector<T5McRecord> mergedMc;

    const int iVN0 = static_cast<int>(TimingChannel::VetoNu0);
    const int iVN1 = static_cast<int>(TimingChannel::VetoNu1);

    const std::array<double, 25> eEdges = {{
        100, 150, 200, 250, 300, 400, 500, 650, 800, 1000, 1250, 1500,
        1800, 2200, 2600, 3000, 3600, 4200, 5000, 6000, 7500, 9000, 11000, 15000, 20000
    }};
    const std::array<double, 25> pzEdges = {{
        100, 140, 180, 230, 300, 380, 480, 600, 750, 950, 1200, 1500,
        1900, 2400, 3000, 3800, 4800, 6000, 7500, 9500, 12000, 15000, 18000, 22000, 30000
    }};

    for (const auto& [skey, grp] : groups) {
        const bool effectiveHasRedQ = grp.sig.hasReducedCharge || hasAux;
        TChain chain("nt");
        for (const auto& f : grp.files) chain.Add(f.c_str());
        INFO("T5 mode=", mode, " group (", skey, "): ", grp.files.size(), " files, slots=", nSlots);

        ROOT::RDF::RNode df = prepareNode(chain, grp.sig, grlTimes, isMC, isMC, isGenie);
        if (maxEvents > 0) df = df.Range(static_cast<ULong64_t>(maxEvents));

        std::vector<std::unordered_map<int, T5RunStats>> slotRuns(nSlots);
        std::vector<std::unordered_map<std::string, T5PeriodGrid>> slotGrids(nSlots);
        std::vector<std::unordered_map<int, T5TruthHists>> slotTruth(nSlots);
        std::vector<std::vector<T5BkgRecord>> slotBkg(nSlots);
        std::vector<std::vector<T5McRecord>> slotMc(nSlots);

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
                    rs.init(run, isMC, effectiveHasRedQ);
                }
                ++rs.nTotal;
                if (!isMC && !grlGood) {
                    ++rs.nGrlFail;
                    return;
                }
                if (isGenie && aux.genie.vetoCaloNuPmt) {
                    return;
                }

                // Book truth denominators BEFORE reconstruction cuts
                if (isGenie && aux.genie.genieClass == 1) {
                    if (aux.genie.inLeadBlock) ++rs.nFidLead;
                    else ++rs.nFidBox;

                    auto& th = slotTruth[slot][run];
                    if (!th.initialized) th.init(run);
                    if (aux.genie.bin30M12 >= 0 && aux.genie.bin30M12 < 30) {
                        if (aux.genie.inLeadBlock) th.bin30LeadM12[aux.genie.bin30M12] += 1.0;
                        else th.bin30BoxM12[aux.genie.bin30M12] += 1.0;
                    }
                    if (aux.genie.bin30P12 >= 0 && aux.genie.bin30P12 < 30) {
                        if (aux.genie.inLeadBlock) th.bin30LeadP12[aux.genie.bin30P12] += 1.0;
                        else th.bin30BoxP12[aux.genie.bin30P12] += 1.0;
                    }
                    auto binIdx = [](double val, const auto& edges) -> int {
                        if (!std::isfinite(val) || val < edges.front() || val >= edges.back()) return -1;
                        auto it = std::upper_bound(edges.begin(), edges.end(), val);
                        int b = static_cast<int>(it - edges.begin()) - 1;
                        return (b >= 0 && b < static_cast<int>(edges.size()) - 1) ? b : -1;
                    };
                    const int ibE = binIdx(aux.genie.truthEGeV, eEdges);
                    if (ibE >= 0) th.fidEnu[ibE] += 1.0;
                    const int ibPz = binIdx(aux.genie.truthPzMuGeV, pzEdges);
                    if (ibPz >= 0) th.fidPzMu[ibPz] += 1.0;
                    if (aux.genie.primaryValid && std::isfinite(aux.genie.truthYInel) &&
                        aux.genie.truthYInel >= 0.0 && aux.genie.truthYInel < 1.0) {
                        const int ibY = std::min(19, static_cast<int>(aux.genie.truthYInel * 20.0));
                        th.fidYInel[ibY] += 1.0;
                    }
                    if (std::isfinite(aux.genie.zMm) && aux.genie.zMm >= -3100.0 && aux.genie.zMm < -1600.0) {
                        const int ibZ = std::min(29, static_cast<int>((aux.genie.zMm + 3100.0) / 50.0));
                        th.fidZVtx[ibZ] += 1.0;
                    }
                    if (std::isfinite(aux.genie.rMm) && aux.genie.rMm >= 0.0 && aux.genie.rMm < 100.0) {
                        const int ibR = std::min(19, static_cast<int>(aux.genie.rMm / 5.0));
                        th.fidRVtx[ibR] += 1.0;
                    }
                    th.fidQMu[aux.genie.pdg > 0 ? 0 : 1] += 1.0;
                }

                const bool hasRunOffsets = isMC || (calibratedDataRuns.count(run) > 0);
                if (!hasRunOffsets) ++rs.nNoOffsets;

                const bool passPhysTrig = isMC ||
                    ((inputBits & 0x8) != 0) || ((inputBits & 0x10) != 0) ||
                    ((inputBits & 0x20) != 0) || ((inputBits & 0x40) != 0);

                const bool isColl = isMC || (distColl == 0);
                const bool isNonColl = !isMC && (std::abs(distColl) > 1);
                const bool isBeam1 = isNonColl && grp.sig.hasInboundB1 && (distInB1 == 0);
                const bool isUnpaired = isNonColl && !isBeam1 &&
                    ((grp.sig.hasUnpairedB1 && distUnpB1 == 0) || (grp.sig.hasUnpairedB2 && distUnpB2 == 0));
                const bool isEmpty = isNonColl && !isBeam1 && !isUnpaired;

                if (isColl) ++rs.nColliding;
                else if (isBeam1) ++rs.nBeam1;
                else if (isUnpaired) ++rs.nUnpaired;
                else if (isEmpty) ++rs.nEmpty;

                const std::string per = isMC
                    ? TimingCalibrator::targetDataPeriodForMC(run, static_cast<int64_t>(eventID))
                    : TimingCalibrator::periodForDataRun(run);

                // Quick non-colliding accidental rate book before track cut
                TimingCalib::EventTimingOutput evt;
                bool evtCalibrated = false;
                auto ensureCalib = [&]() {
                    if (evtCalibrated) return;
                    evtCalibrated = true;
                    evt = isMC
                        ? calib->calibrateMCEvent(run, static_cast<int64_t>(eventID), raw, true, true)
                        : (hasRunOffsets
                            ? calib->calibrateDataEvent(run, raw, calib->hasTofMaps(), true)
                            : TimingCalib::EventTimingOutput{});
                };

                if (isNonColl) {
                    if (isBeam1) ++rs.nAccDenomBeam1;
                    else if (isUnpaired) ++rs.nAccDenomUnpaired;
                    else ++rs.nAccDenomEmpty;

                    const bool q0_ge30 = raw[iVN0].present && std::isfinite(raw[iVN0].rawCharge) && raw[iVN0].rawCharge >= 30.0;
                    const bool q1_ge30 = raw[iVN1].present && std::isfinite(raw[iVN1].rawCharge) && raw[iVN1].rawCharge >= 30.0;
                    if (q0_ge30 || q1_ge30) {
                        ensureCalib();
                        auto& pg = slotGrids[slot][per];
                        if (!pg.initialized) pg.init(per);
                        for (int wi = 0; wi < kNWCap; ++wi) {
                            const double wm = kWCaps[wi];
                            if (q0_ge30 && evt.channels[iVN0].valid && raw[iVN0].width > 1.5 && raw[iVN0].width < wm) {
                                if (isBeam1) pg.accBeam1Vn0[wi].fill(evt.channels[iVN0].tCalNs, raw[iVN0].rawCharge);
                                else pg.accEmpUnpVn0[wi].fill(evt.channels[iVN0].tCalNs, raw[iVN0].rawCharge);
                            }
                            if (q1_ge30 && evt.channels[iVN1].valid && raw[iVN1].width > 1.5 && raw[iVN1].width < wm) {
                                if (isBeam1) pg.accBeam1Vn1[wi].fill(evt.channels[iVN1].tCalNs, raw[iVN1].rawCharge);
                                else pg.accEmpUnpVn1[wi].fill(evt.channels[iVN1].tCalNs, raw[iVN1].rawCharge);
                            }
                        }
                    }
                }

                // MANDATORY ENTRY-GATE BLINDING GUARD FOR COLLISION DATA BEFORE FULL DOWNSTREAM SELECTION
                // First fast reject events failing relaxed track/scintillator cuts to maximize throughput!
                const bool passCaloNuClean = isMC ||
                    !(15821 <= run && run <= 16924) ||
                    (!(aux.v20Status == 528 || aux.v21Status == 528) &&
                     (((aux.vn0Status == 0 || aux.vn0Status == 1) && (aux.vn1Status == 0 || aux.vn1Status == 1)) ||
                      (aux.vn0Status == 0 && aux.vn1Status == 16)));

                const bool hitsTimingNom = tk.validPos[3] && std::isfinite(tk.y[3]) && (
                    (tk.y[3] > 20.0 && std::isfinite(aux.timingTopCharge) && aux.timingTopCharge > 20.0f) ||
                    (tk.y[3] < -20.0 && std::isfinite(aux.timingBottomCharge) && aux.timingBottomCharge > 20.0f) ||
                    (std::abs(tk.y[3]) <= 20.0 &&
                     std::isfinite(aux.timingTopCharge) && std::isfinite(aux.timingBottomCharge) &&
                     (aux.timingTopCharge + aux.timingBottomCharge) > 20.0f));

                const bool hitsTimingRelax = tk.validPos[3] && std::isfinite(tk.y[3]) && (
                    (tk.y[3] > 20.0 && std::isfinite(aux.timingTopCharge) && aux.timingTopCharge > 15.0f) ||
                    (tk.y[3] < -20.0 && std::isfinite(aux.timingBottomCharge) && aux.timingBottomCharge > 15.0f) ||
                    (std::abs(tk.y[3]) <= 20.0 &&
                     std::isfinite(aux.timingTopCharge) && std::isfinite(aux.timingBottomCharge) &&
                     (aux.timingTopCharge + aux.timingBottomCharge) > 15.0f));

                const bool passDownScintNom =
                    std::isfinite(aux.veto20Charge) && aux.veto20Charge > 40.0f &&
                    std::isfinite(aux.veto21Charge) && aux.veto21Charge > 40.0f &&
                    hitsTimingNom &&
                    std::isfinite(aux.preshower0Charge) && aux.preshower0Charge > 2.5f &&
                    std::isfinite(aux.preshower1Charge) && aux.preshower1Charge > 2.5f;

                const bool passDownScintRelax =
                    std::isfinite(aux.veto20Charge) && aux.veto20Charge > 30.0f &&
                    std::isfinite(aux.veto21Charge) && aux.veto21Charge > 30.0f &&
                    hitsTimingRelax &&
                    std::isfinite(aux.preshower0Charge) && aux.preshower0Charge > 1.8f &&
                    std::isfinite(aux.preshower1Charge) && aux.preshower1Charge > 1.8f;

                const bool passLeadTrkNom =
                    longTracks > 0 &&
                    std::isfinite(tk.leadPz0GeV) && tk.leadPz0GeV > 100.0 &&
                    tk.leadNLayers >= 7 &&
                    std::isfinite(tk.leadNDoF) && tk.leadNDoF >= 9.0 &&
                    std::isfinite(tk.leadChi2NDF) && tk.leadChi2NDF < 15.0;

                const bool passLeadTrkRelax =
                    longTracks > 0 &&
                    std::isfinite(tk.leadPz0GeV) && tk.leadPz0GeV > 80.0 &&
                    tk.leadNLayers >= 7 &&
                    std::isfinite(tk.leadNDoF) && tk.leadNDoF >= 9.0 &&
                    std::isfinite(tk.leadChi2NDF) && tk.leadChi2NDF < 18.0;

                if (!passCaloNuClean) return;
                if (!isGenie && (!passDownScintNom || !passLeadTrkNom)) return;
                if (isGenie && (!passDownScintRelax || !passLeadTrkRelax)) return;

                const double rMax = tk.leadRMax;
                const double rIFT = tk.validPos[2] ? std::hypot(tk.x[2], tk.y[2]) : kNaN;
                const double rVN = tk.validPos[0] ? std::hypot(tk.x[0], tk.y[0]) : kNaN;
                const double theta = tk.leadThetaMrad;
                if (!std::isfinite(rMax) || !std::isfinite(rIFT) || !std::isfinite(rVN) || !std::isfinite(theta)) {
                    return;
                }

                const bool passNomGeom = passDownScintNom && passLeadTrkNom &&
                    (rMax < 95.0 && rIFT < 95.0 && rVN < 120.0 && theta < 25.0);
                const bool passRelaxGeom = passDownScintRelax && passLeadTrkRelax &&
                    (rMax < 98.0 && rIFT < 100.0 && rVN < 128.0 && theta < 27.0);

                uint8_t region = 0;
                if (isNonColl) {
                    if (isBeam1) region = REG_NONCOLL_B1;
                    else if (isUnpaired) region = REG_NONCOLL_UNPAIRED;
                    else region = REG_NONCOLL_EMPTY;
                } else if (isColl && passPhysTrig) {
                    if (passNomGeom) {
                        region = REG_KIN_SR;
                    } else if (passDownScintNom && passLeadTrkNom) {
                        const bool isGeomOuter = (rVN < 120.0 && theta < 25.0 && rMax < 135.0 && rIFT < 135.0 &&
                                                  ((rMax >= 95.0 && rMax < 135.0) || (rIFT >= 95.0 && rIFT < 135.0)));
                        const bool isGeomHiTheta = (rVN < 120.0 && rMax < 135.0 && rIFT < 135.0 &&
                                                    theta >= 25.0 && theta < 55.0);
                        const bool isEdgeVn = (rMax < 95.0 && rIFT < 95.0 && theta < 25.0 && rVN >= 120.0 && rVN < 180.0);
                        if (isGeomOuter) region = REG_CR_GEOM_OUTER;
                        else if (isGeomHiTheta) region = REG_CR_GEOM_HITHETA;
                        else if (isEdgeVn) region = REG_CR_EDGE_VN;
                    }
                    if (region == 0 && isGenie && passRelaxGeom) {
                        region = REG_RELAXED_SR_ONLY;
                    }
                }
                if (region == 0) return;

                // Now calibrate full timing
                ensureCalib();
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

                // Resolve calibrated aux reduced charge before blinding & Zone-A/B checks
                float vn0RedVal = aux.vetoNu0ReducedCharge;
                float vn1RedVal = aux.vetoNu1ReducedCharge;
                if (hasAux) {
                    const uint64_t aKey = makeAuxLookupKey(run, eventID);
                    auto itAux = std::lower_bound(auxRows.begin(), auxRows.end(), AuxLookupRow{aKey, 0.0f, 0.0f});
                    if (itAux == auxRows.end() || itAux->key != aKey) {
                        if (longTracks <= 0) {
                            vn0RedVal = -1.0f;
                            vn1RedVal = -1.0f;
                        } else {
                            const uint64_t prevMiss = nMissingAux.fetch_add(1, std::memory_order_relaxed);
                            if (prevMiss == 0) {
                                std::lock_guard<std::mutex> lk(missingAuxMtx);
                                firstMissingAuxMsg = "run=" + std::to_string(run) + ", eventID=" + std::to_string(eventID);
                            }
                            vn0RedVal = -99999.0f;
                            vn1RedVal = -99999.0f;
                        }
                    } else {
                        const bool v20Good = TimingCalibrator::isGoodWaveformStatus(aux.v20Status);
                        const bool v21Good = TimingCalibrator::isGoodWaveformStatus(aux.v21Status);
                        const bool psGood = TimingCalibrator::isGoodWaveformStatus(aux.ps0Status) ||
                                            TimingCalibrator::isGoodWaveformStatus(aux.ps1Status);
                        const bool trigGood = TimingCalibrator::isGoodWaveformStatus(aux.t0Status) ||
                                              TimingCalibrator::isGoodWaveformStatus(aux.t1Status) ||
                                              TimingCalibrator::isGoodWaveformStatus(aux.t2Status) ||
                                              TimingCalibrator::isGoodWaveformStatus(aux.t3Status);
                        const bool brokenPs = (brokenPsP0013Runs.count(run) > 0);
                        const bool timingOK = (run < 18500)
                            ? (v20Good || v21Good || psGood)
                            : (v20Good || v21Good || trigGood || (!brokenPs && psGood));
                        const bool is2024Period = (run >= 14000 && run <= 18499);
                        const bool isZeroBug0 = is2024Period && (itAux->q0 == 0.0f) && (raw[iVN0].rawCharge > 30.0);
                        const bool isZeroBug1 = is2024Period && (itAux->q1 == 0.0f) && (raw[iVN1].rawCharge > 30.0);
                        vn0RedVal = (!timingOK || std::isnan(itAux->q0) || isZeroBug0) ? -1.0f : std::max(itAux->q0, 0.0f);
                        vn1RedVal = (!timingOK || std::isnan(itAux->q1) || isZeroBug1) ? -1.0f : std::max(itAux->q1, 0.0f);
                    }
                }
                ScannerEventAux auxCal = aux;
                auxCal.vetoNu0ReducedCharge = vn0RedVal;
                auxCal.vetoNu1ReducedCharge = vn1RedVal;

                // MANDATORY COLLISION DATA BLINDING CHECK
                const auto blindEv = buildBlindStruct(isMC, distColl, longTracks, tk, raw, auxCal);
                if (TimingBlinding::isBlindedSRZoneB(
                        blindEv, true, down.valid,
                        evt.channels[iVN0].valid, dt0,
                        evt.channels[iVN1].valid, dt1)) {
                    ++rs.nBlinded;
                    return;
                }

                // Guard era-consistent Zone-B in DATA REG_KIN_SR
                const bool za0Red = effectiveHasRedQ
                    ? ((auxCal.vetoNu0ReducedCharge >= 0.0f) ? (auxCal.vetoNu0ReducedCharge < 30.0f) : (raw[iVN0].rawCharge < 40.0))
                    : (raw[iVN0].rawCharge < 40.0);
                const bool za1Red = effectiveHasRedQ
                    ? ((auxCal.vetoNu1ReducedCharge >= 0.0f) ? (auxCal.vetoNu1ReducedCharge < 30.0f) : (raw[iVN1].rawCharge < 40.0))
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
                    const bool bAct0 = TimingBlinding::isVetoNuZoneBActive(static_cast<float>(raw[iVN0].rawCharge), auxCal.vetoNu0ReducedCharge);
                    const bool bAct1 = TimingBlinding::isVetoNuZoneBActive(static_cast<float>(raw[iVN1].rawCharge), auxCal.vetoNu1ReducedCharge);
                    if ((bAct0 && (!evt.channels[iVN0].valid || !down.valid || !std::isfinite(dt0) || dt0 > 1.5)) ||
                        (bAct1 && (!evt.channels[iVN1].valid || !down.valid || !std::isfinite(dt1) || dt1 > 1.5))) {
                        throw std::logic_error("TimingBlinding violation in T5 REG_KIN_SR!");
                    }
                    if (!zoneAEra && ((!down.valid) || !evt.channels[iVN0].valid || !evt.channels[iVN1].valid || dt0 > 1.5 || dt1 > 1.5)) {
                        ++rs.nBlinded;
                        return;
                    }
                }

                const double c2nd = down.valid ? (down.chi2 / static_cast<double>(std::max(1, down.ndof))) : kNaN;
                const bool downOk = down.valid && down.nUsed >= 2 && (down.ndof <= 0 || c2nd < 10.0);
                const bool downOk5 = down.valid && down.nUsed >= 2 && (down.ndof <= 0 || c2nd < 5.0);
                const double c2ndA = downA.valid ? (downA.chi2 / static_cast<double>(std::max(1, downA.ndof))) : kNaN;
                const double c2ndB = downB.valid ? (downB.chi2 / static_cast<double>(std::max(1, downB.ndof))) : kNaN;
                const bool downAOk = downA.valid && downA.nUsed >= 1 && (downA.ndof <= 0 || c2ndA < 5.0);
                const bool downBOk = downB.valid && downB.nUsed >= 1 && (downB.ndof <= 0 || c2ndB < 5.0);

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
                const double qMax = std::max(raw[iVN0].rawCharge, raw[iVN1].rawCharge);

                const auto back = TimingCalibrator::evaluateBackwardHypothesis(evt, down, !za0Era, !za1Era);

                if (region == REG_KIN_SR) {
                    if (zoneARed) ++rs.nSrZoneARed30;
                    if (zoneARaw) ++rs.nSrZoneARaw40;
                    if (zoneAEra) ++rs.nSrZoneAEra;

                    const bool q0Mip = raw[iVN0].present && raw[iVN0].rawCharge >= 30.0;
                    const bool q1Mip = raw[iVN1].present && raw[iVN1].rawCharge >= 30.0;
                    const bool v0Ok = evt.channels[iVN0].valid && raw[iVN0].width > 1.5 && q0Mip;
                    const bool v1Ok = evt.channels[iVN1].valid && raw[iVN1].width > 1.5 && q1Mip;

                    if (downOk5 && v0Ok && v1Ok && raw[iVN0].width < 19.5 && raw[iVN1].width < 19.5 &&
                        std::abs(dt0) < 1.0 && std::abs(dt1) < 1.0) {
                        ++rs.nSrPrompt2HitDt1p0;
                    }
                    if (downAOk && downBOk && v0Ok && v1Ok && raw[iVN0].width < 19.5 && raw[iVN1].width < 19.5 &&
                        std::abs(u0) < 1.0 && std::abs(u1) < 1.0) {
                        ++rs.nSrPrompt2HitU1p0;
                    }
                    if (!za0Era && za1Era && downOk && evt.channels[iVN0].valid && std::abs(dt0) <= 1.0) {
                        ++rs.nSr1Hit0Era;
                    }
                    if (za0Era && !za1Era && downOk && evt.channels[iVN1].valid && std::abs(dt1) <= 1.0) {
                        ++rs.nSr1Hit1Era;
                    }

                    if (!isGenie && v0Ok && v1Ok) {
                        auto& pg = slotGrids[slot][per];
                        if (!pg.initialized) pg.init(per);
                        for (int wi = 0; wi < kNWCap; ++wi) {
                            const double wm = kWCaps[wi];
                            if (raw[iVN0].width >= wm || raw[iVN1].width >= wm) continue;
                            if (downAOk && downBOk && std::abs(u0) < 1.0 && std::abs(u1) < 1.0) pg.denSrU[wi].fill(rVN, qMax);
                            if (downOk5 && std::abs(dt0) < 1.0 && std::abs(dt1) < 1.0) pg.denSrDt[wi].fill(rVN, qMax);
                            if (downAOk && downBOk) {
                                if (u0 < -1.0 && std::abs(u1) < 1.0) {
                                    pg.tailSrU0Neg[wi].fill(rVN, qMax, -u0);
                                    if (std::isfinite(zu0Val) && zu0Val < -2.0) pg.tailSrZu0Neg[wi].fill(rVN, qMax, -zu0Val);
                                }
                                if (u1 < -1.0 && std::abs(u0) < 1.0) {
                                    pg.tailSrU1Neg[wi].fill(rVN, qMax, -u1);
                                    if (std::isfinite(zu1Val) && zu1Val < -2.0) pg.tailSrZu1Neg[wi].fill(rVN, qMax, -zu1Val);
                                }
                            }
                            if (downOk5) {
                                if (dt0 < -1.0 && std::abs(dt1) < 1.0) pg.tailSrDt0Neg[wi].fill(rVN, qMax, -dt0);
                                if (dt1 < -1.0 && std::abs(dt0) < 1.0) pg.tailSrDt1Neg[wi].fill(rVN, qMax, -dt1);
                            }
                        }
                    }
                } else if (region == REG_CR_GEOM_OUTER || region == REG_CR_GEOM_HITHETA) {
                    ++rs.nGeomAll;
                    if (zoneAEra) ++rs.nGeomZoneAEra;

                    const bool q0Mip = raw[iVN0].present && raw[iVN0].rawCharge >= 30.0;
                    const bool q1Mip = raw[iVN1].present && raw[iVN1].rawCharge >= 30.0;
                    const bool v0Ok = evt.channels[iVN0].valid && raw[iVN0].width > 1.5 && q0Mip;
                    const bool v1Ok = evt.channels[iVN1].valid && raw[iVN1].width > 1.5 && q1Mip;

                    if (downOk5 && v0Ok && v1Ok && raw[iVN0].width < 19.5 && raw[iVN1].width < 19.5 &&
                        std::abs(dt0) < 1.0 && std::abs(dt1) < 1.0) {
                        ++rs.nGeomPrompt2HitDt1p0;
                    }
                    if (downAOk && downBOk && v0Ok && v1Ok && raw[iVN0].width < 19.5 && raw[iVN1].width < 19.5 &&
                        std::abs(u0) < 1.0 && std::abs(u1) < 1.0) {
                        ++rs.nGeomPrompt2HitU1p0;
                    }

                    if (!isGenie && v0Ok && v1Ok) {
                        auto& pg = slotGrids[slot][per];
                        if (!pg.initialized) pg.init(per);
                        for (int wi = 0; wi < kNWCap; ++wi) {
                            const double wm = kWCaps[wi];
                            if (raw[iVN0].width >= wm || raw[iVN1].width >= wm) continue;
                            if (downAOk && downBOk && std::abs(u0) < 1.0 && std::abs(u1) < 1.0) pg.denGeomU[wi].fill(rVN, qMax);
                            if (downOk5 && std::abs(dt0) < 1.0 && std::abs(dt1) < 1.0) pg.denGeomDt[wi].fill(rVN, qMax);
                            if (downAOk && downBOk) {
                                if (u0 > 1.0 && std::abs(u1) < 1.0) {
                                    pg.tailGeomU0Pos[wi].fill(rVN, qMax, u0);
                                    if (std::isfinite(zu0Val) && zu0Val > 2.0) pg.tailGeomZu0Pos[wi].fill(rVN, qMax, zu0Val);
                                }
                                if (u1 > 1.0 && std::abs(u0) < 1.0) {
                                    pg.tailGeomU1Pos[wi].fill(rVN, qMax, u1);
                                    if (std::isfinite(zu1Val) && zu1Val > 2.0) pg.tailGeomZu1Pos[wi].fill(rVN, qMax, zu1Val);
                                }
                            }
                            if (downOk5) {
                                if (dt0 > 1.0 && std::abs(dt1) < 1.0) pg.tailGeomDt0Pos[wi].fill(rVN, qMax, dt0);
                                if (dt1 > 1.0 && std::abs(dt0) < 1.0) pg.tailGeomDt1Pos[wi].fill(rVN, qMax, dt1);
                            }
                        }
                    }
                } else if (region == REG_CR_EDGE_VN) {
                    ++rs.nEdgeVnAll;
                    if (zoneAEra) ++rs.nEdgeVnZoneAEra;
                    else ++rs.nEdgeVnZoneBEra;
                }

                uint16_t fl = 0;
                if (effectiveHasRedQ) fl |= kFlagHasRedQ;
                if (passPhysTrig) fl |= kFlagPassPhysTrig;
                if (downOk) fl |= kFlagDownOk;
                if (downAOk) fl |= kFlagDownAValid;
                if (downBOk) fl |= kFlagDownBValid;
                if (downA.valid && downA.nUsed >= 2) fl |= kFlagDownAGE2;
                if (downB.valid && downB.nUsed >= 2) fl |= kFlagDownBGE2;
                if (evt.channels[iVN0].valid) fl |= kFlagVn0Valid;
                if (evt.channels[iVN1].valid) fl |= kFlagVn1Valid;
                if (zoneARed) fl |= kFlagZoneARed;
                if (zoneARaw) fl |= kFlagZoneARaw;
                if (zoneAEra) fl |= kFlagZoneAEra;
                if (!za0Era) fl |= kFlagVn0ActiveEra;
                if (!za1Era) fl |= kFlagVn1ActiveEra;
                if (passLeadTrkNom) fl |= kFlagPassLeadTrk;
                if (passNomGeom) fl |= kFlagPassNominalSR;

                if (!isGenie) {
                    // Save ONLY Zone-B positive 2-hit tails (>=1.6 ns or >=2.5 pull both or dchi2>16), 1-hit events, tiny CR-EdgeVN, extreme neg-SR, & lean prompt subsample
                    const bool oneHitAny = (za0Era != za1Era) || (za0Red != za1Red);
                    const bool pos2Tail =
                        (evt.channels[iVN0].valid && evt.channels[iVN1].valid &&
                         ((dt0 > 1.6 && dt1 > 1.6) || (u0 > 1.6 && u1 > 1.6) ||
                          (pull0Val > 2.5 && pull1Val > 2.5) || (zu0Val > 2.5 && zu1Val > 2.5))) ||
                        (back.valid && back.deltaChi2Back > 16.0);
                    const bool extNegSr =
                        (evt.channels[iVN0].valid && evt.channels[iVN1].valid &&
                         ((dt0 < -2.2 && dt1 < -2.2) || (u0 < -2.2 && u1 < -2.2) ||
                          (pull0Val < -3.0 && pull1Val < -3.0) || (zu0Val < -3.0 && zu1Val < -3.0)));
                    const bool inGeomCR = (region == REG_CR_GEOM_OUTER || region == REG_CR_GEOM_HITHETA);
                    const double pPrompt = isMC ? 0.01 : 0.0005;
                    const bool isPromptSub = (!zoneAEra && inGeomCR && !pos2Tail && !oneHitAny) &&
                        (deterministicUniform01(run, eventID, 0x5435cafe99887766ULL) < pPrompt);
                    const bool keepFlukaSr = (mode == "fluka" && region == REG_KIN_SR && (pos2Tail || oneHitAny || (back.valid && back.deltaChi2Back > 4.0)));
                    const bool keepBkg =
                        keepFlukaSr ||
                        (region == REG_CR_EDGE_VN) ||
                        (region == REG_NONCOLL_B1 && passNomGeom && (!zoneAEra || oneHitAny || pos2Tail)) ||
                        (region == REG_KIN_SR && !isMC && (extNegSr || oneHitAny)) ||
                        (inGeomCR && (pos2Tail || oneHitAny || isPromptSub)) ||
                        ((region == REG_NONCOLL_UNPAIRED || region == REG_NONCOLL_EMPTY) && passNomGeom && (!za0Era || !za1Era) && (pos2Tail || oneHitAny));
                    if (keepBkg) {
                        T5BkgRecord rec;
                        rec.run = run;
                        rec.eventID = static_cast<int64_t>(eventID);
                        rec.region = region;
                        rec.is_prompt_sub = isPromptSub ? 1 : 0;
                        rec.flags = fl;
                        rec.pz0_gev = static_cast<float>(tk.leadPz0GeV);
                        rec.r_max = static_cast<float>(rMax);
                        rec.r_ift = static_cast<float>(rIFT);
                        rec.r_vn = static_cast<float>(rVN);
                        rec.theta_mrad = static_cast<float>(theta);
                        rec.q0_raw = static_cast<float>(raw[iVN0].rawCharge);
                        rec.q1_raw = static_cast<float>(raw[iVN1].rawCharge);
                        rec.q0_red = auxCal.vetoNu0ReducedCharge;
                        rec.q1_red = auxCal.vetoNu1ReducedCharge;
                        rec.dt0 = static_cast<float>(dt0);
                        rec.dt1 = static_cast<float>(dt1);
                        rec.sig_dt0 = static_cast<float>(sig0);
                        rec.sig_dt1 = static_cast<float>(sig1);
                        rec.w0 = static_cast<float>(raw[iVN0].width);
                        rec.w1 = static_cast<float>(raw[iVN1].width);
                        rec.chi2_ndof_down = static_cast<float>(c2nd);
                        rec.t0_down = down.valid ? static_cast<float>(down.t0Ns) : kNaNF;
                        rec.sig_t0_down = down.valid ? static_cast<float>(down.sigmaT0Ns) : kNaNF;
                        rec.pull0 = static_cast<float>(pull0Val);
                        rec.pull1 = static_cast<float>(pull1Val);
                        rec.u0 = static_cast<float>(u0);
                        rec.u1 = static_cast<float>(u1);
                        rec.zu0 = static_cast<float>(zu0Val);
                        rec.zu1 = static_cast<float>(zu1Val);
                        rec.dchi2_back = back.valid ? static_cast<float>(back.deltaChi2Back) : kNaNF;
                        rec.z_comb = back.valid ? static_cast<float>(back.zComb) : kNaNF;
                        slotBkg[slot].push_back(rec);
                    }
                    return;
                }

                // GENIE MC event: compute unsmeared + circular-cone timing lookup
                const auto evtUnsm = calib->calibrateMCEvent(run, static_cast<int64_t>(eventID), raw, false, true);
                const auto downUnsm = TimingCalibrator::fitDownstreamReferenceMode(
                    evtUnsm, DownstreamMode::Trimmed3Sigma, leadYTrig, &raw);
                const double dt0Unsm = (downUnsm.valid && evtUnsm.channels[iVN0].valid)
                    ? (evtUnsm.channels[iVN0].tCalNs - downUnsm.t0Ns) : kNaN;
                const double dt1Unsm = (downUnsm.valid && evtUnsm.channels[iVN1].valid)
                    ? (evtUnsm.channels[iVN1].tCalNs - downUnsm.t0Ns) : kNaN;

                double dt0Cone = dt0, dt1Cone = dt1, sig0Cone = sig0, sig1Cone = sig1;
                if (down.valid && evt.channels[iVN0].valid && raw[iVN0].validPos) {
                    const auto reg0 = calib->calibrateCircularRegion(
                        per, iVN0, evt.channels[iVN0].t2Ns, raw[iVN0].rawCharge, raw[iVN0].xMm, raw[iVN0].yMm, kConeRadiusMm);
                    if (reg0.valid) {
                        double tb0 = 0.0, tw0 = 0.0, sPt0 = evt.channels[iVN0].sigmaCalNs;
                        calib->lookupPoint(per, iVN0, raw[iVN0].xMm, raw[iVN0].yMm, raw[iVN0].rawCharge, tb0, tw0, sPt0);
                        // Preserve MC smeared shift wrt t0_mc (already in evt.channels[iVN0].tCalNs) plus cone-vs-point spatial delta & sigma
                        dt0Cone = evt.channels[iVN0].tCalNs - (reg0.tBarEffNs - tb0) - down.t0Ns;
                        sig0Cone = std::hypot(reg0.sigmaCalNs, down.sigmaT0Ns);
                    }
                }
                if (down.valid && evt.channels[iVN1].valid && raw[iVN1].validPos) {
                    const auto reg1 = calib->calibrateCircularRegion(
                        per, iVN1, evt.channels[iVN1].t2Ns, raw[iVN1].rawCharge, raw[iVN1].xMm, raw[iVN1].yMm, kConeRadiusMm);
                    if (reg1.valid) {
                        double tb1 = 0.0, tw1 = 0.0, sPt1 = evt.channels[iVN1].sigmaCalNs;
                        calib->lookupPoint(per, iVN1, raw[iVN1].xMm, raw[iVN1].yMm, raw[iVN1].rawCharge, tb1, tw1, sPt1);
                        dt1Cone = evt.channels[iVN1].tCalNs - (reg1.tBarEffNs - tb1) - down.t0Ns;
                        sig1Cone = std::hypot(reg1.sigmaCalNs, down.sigmaT0Ns);
                    }
                }

                T5McRecord rec;
                rec.run = run;
                rec.eventID = static_cast<int64_t>(eventID);
                rec.region = region;
                rec.genie_class = aux.genie.genieClass;
                rec.in_lead_block = aux.genie.inLeadBlock ? 1 : 0;
                rec.primary_valid = aux.genie.primaryValid ? 1 : 0;
                rec.confirmed = aux.genie.confirmed ? 1 : 0;
                rec.flags = fl;
                rec.truth_pdg = aux.genie.pdg;
                rec.truth_bin30_m12 = aux.genie.bin30M12;
                rec.truth_bin30_p12 = aux.genie.bin30P12;
                rec.incoming_px_mev = static_cast<float>(aux.genie.pxMeV);
                rec.incoming_py_mev = static_cast<float>(aux.genie.pyMeV);
                rec.incoming_pz_mev = static_cast<float>(aux.genie.pzMeV);
                rec.truth_E_gev = static_cast<float>(aux.genie.truthEGeV);
                rec.truth_pz_mu_gev = static_cast<float>(aux.genie.truthPzMuGeV);
                rec.truth_y_inel = static_cast<float>(aux.genie.truthYInel);
                rec.truth_x_mm = static_cast<float>(aux.genie.xMm);
                rec.truth_y_mm = static_cast<float>(aux.genie.yMm);
                rec.truth_z_mm = static_cast<float>(aux.genie.zMm);
                rec.truth_r_mm = static_cast<float>(aux.genie.rMm);
                rec.crossing_angle_urad = static_cast<float>(aux.genie.crossingAngleUrad);
                rec.pz0_gev = static_cast<float>(tk.leadPz0GeV);
                rec.p0_gev = static_cast<float>(tk.leadP0GeV);
                rec.lead_q = static_cast<float>(tk.leadCharge);
                rec.theta_mrad = static_cast<float>(theta);
                rec.r_max = static_cast<float>(rMax);
                rec.r_ift = static_cast<float>(rIFT);
                rec.r_vn = static_cast<float>(rVN);
                rec.chi2_ndf = static_cast<float>(tk.leadChi2NDF);
                rec.x_vn_mm = static_cast<float>(tk.x[0]);
                rec.y_vn_mm = static_cast<float>(tk.y[0]);
                rec.x_v1_mm = static_cast<float>(tk.x[1]);
                rec.y_v1_mm = static_cast<float>(tk.y[1]);
                rec.v20_q = aux.veto20Charge;
                rec.v21_q = aux.veto21Charge;
                rec.tim_q_match = (tk.y[3] > 20.0) ? aux.timingTopCharge
                    : ((tk.y[3] < -20.0) ? aux.timingBottomCharge
                                           : (aux.timingTopCharge + aux.timingBottomCharge));
                rec.ps0_q = aux.preshower0Charge;
                rec.ps1_q = aux.preshower1Charge;
                rec.q0_raw = static_cast<float>(raw[iVN0].rawCharge);
                rec.q1_raw = static_cast<float>(raw[iVN1].rawCharge);
                rec.q0_red = auxCal.vetoNu0ReducedCharge;
                rec.q1_red = auxCal.vetoNu1ReducedCharge;
                rec.w0 = static_cast<float>(raw[iVN0].width);
                rec.w1 = static_cast<float>(raw[iVN1].width);
                rec.dt0 = static_cast<float>(dt0);
                rec.dt1 = static_cast<float>(dt1);
                rec.sig_dt0 = static_cast<float>(sig0);
                rec.sig_dt1 = static_cast<float>(sig1);
                rec.dt0_unsmeared = static_cast<float>(dt0Unsm);
                rec.dt1_unsmeared = static_cast<float>(dt1Unsm);
                rec.dt0_cone75 = static_cast<float>(dt0Cone);
                rec.dt1_cone75 = static_cast<float>(dt1Cone);
                rec.sig_dt0_cone75 = static_cast<float>(sig0Cone);
                rec.sig_dt1_cone75 = static_cast<float>(sig1Cone);
                rec.u0 = static_cast<float>(u0);
                rec.u1 = static_cast<float>(u1);
                rec.pull0 = static_cast<float>(pull0Val);
                rec.pull1 = static_cast<float>(pull1Val);
                rec.zu0 = static_cast<float>(zu0Val);
                rec.zu1 = static_cast<float>(zu1Val);
                rec.t0_down = down.valid ? static_cast<float>(down.t0Ns) : kNaNF;
                rec.sig_t0_down = down.valid ? static_cast<float>(down.sigmaT0Ns) : kNaNF;
                rec.chi2_ndof_down = static_cast<float>(c2nd);
                rec.dchi2_back = back.valid ? static_cast<float>(back.deltaChi2Back) : kNaNF;
                rec.z_comb = back.valid ? static_cast<float>(back.zComb) : kNaNF;
                rec.z_misalign = static_cast<float>(deterministicStdNormal(run, eventID, 0xd1cefa3411223344ULL));
                rec.x_ml = aux.xMl;
                slotMc[slot].push_back(rec);
            },
            {"run", "eventID", "distanceToCollidingBCID", "distanceToInboundB1",
             "distanceToUnpairedB1", "distanceToUnpairedB2", "inputBits",
             "longTracks", "_grl_good", "_tk", "_raw", "_aux"});

        for (unsigned int s = 0; s < nSlots; ++s) {
            for (const auto& [r, stItem] : slotRuns[s]) mergedRuns[r].mergeFrom(stItem);
            for (const auto& [p, gItem] : slotGrids[s]) mergedGrids[p].mergeFrom(gItem);
            for (const auto& [r, thItem] : slotTruth[s]) mergedTruth[r].mergeFrom(thItem);
            mergedBkg.insert(mergedBkg.end(), slotBkg[s].begin(), slotBkg[s].end());
            mergedMc.insert(mergedMc.end(), slotMc[s].begin(), slotMc[s].end());
        }
    }

    const uint64_t missingAuxCount = nMissingAux.load();
    if (missingAuxCount > 0) {
        ERROR("Missing aux reduced charge for ", missingAuxCount,
              " longTracks>0 events (first: ", firstMissingAuxMsg, ")");
        throw std::runtime_error("Missing aux reduced-charge rows for longTracks>0 events.");
    }

    uint64_t totEvents = 0, totBlinded = 0, totSrZaRed = 0, totSrZaEra = 0;
    for (const auto& [r, stItem] : mergedRuns) {
        totEvents += stItem.nTotal;
        totBlinded += stItem.nBlinded;
        totSrZaRed += stItem.nSrZoneARed30;
        totSrZaEra += stItem.nSrZoneAEra;
    }

    writeOutput(outputPath, isGenie, mergedRuns, mergedGrids, mergedTruth, mergedBkg, mergedMc);

    const double wallS = std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStart).count();
    INFO("Completed T5 scan (", mode, "): files=", files.size(), " (skipped_empty=", nSkippedEmpty,
         "), aux_rows=", auxRows.size(), ", missing_aux=", missingAuxCount,
         ", total_events=", totEvents, ", blinded_sr_zoneb_skipped=", totBlinded,
         ", sr_za_era=", totSrZaEra, ", bkg_recs=", mergedBkg.size(), ", mc_recs=", mergedMc.size(),
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
        sj["n_sr_zonea_red30"] = totSrZaRed;
        sj["n_sr_zonea_era"] = totSrZaEra;
        sj["n_bkg_records"] = mergedBkg.size();
        sj["n_mc_records"] = mergedMc.size();
        sj["wall_s"] = wallS;
        sj["mevt_per_s"] = (wallS > 0 ? totEvents / wallS / 1e6 : 0.0);
        std::ofstream ofs(summaryJsonPath);
        ofs << sj.dump(2) << "\n";
    }
    return 0;
}
