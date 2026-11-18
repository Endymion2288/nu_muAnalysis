#include "TimingCalibration.h"
#include "TimingBlindingGuard.h"
#include "MessageService.hpp"

#include "ScintSimEventTPCnv/ScintHits/ScintHitCollection_p1a.h"
#include "GeneratorObjectsTPCnv/McEventCollection_p6.h"

#include <TChain.h>
#include <TClass.h>
#include <TFile.h>
#include <TH1D.h>
#include <TROOT.h>
#include <TSystem.h>
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
#include <vector>

namespace {

using TimingCalib::TimingChannel;
using TimingCalib::TimingCalibrator;
using TimingCalib::DownstreamMode;
using TimingCalib::kNumChannels;
using TimingCalib::kSpeedOfLightMPerNs;
using RawInputArray = std::array<TimingCalib::RawChannelInput, kNumChannels>;

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();
constexpr double kMuMassMeV = 105.6583755;

// Zero-overhead accessors for protected Athena persistent fields
struct GenEventAcc : public GenEvent_p6 {
    int eventNbr() const { return m_eventNbr; }
    int signalProcessId() const { return m_signalProcessId; }
    int signalProcessVtx() const { return m_signalProcessVtx; }
    unsigned int verticesBegin() const { return m_verticesBegin; }
    unsigned int verticesEnd() const { return m_verticesEnd; }
    unsigned int particlesBegin() const { return m_particlesBegin; }
    unsigned int particlesEnd() const { return m_particlesEnd; }
};

struct GenVertexAcc : public GenVertex_p6 {
    float x() const { return m_x; }
    float y() const { return m_y; }
    float z() const { return m_z; }
    float t() const { return m_t; }
    const std::vector<int>& particlesIn() const { return m_particlesIn; }
    const std::vector<int>& particlesOut() const { return m_particlesOut; }
    int barcode() const { return m_barcode; }
};

struct GenParticleAcc : public GenParticle_p6 {
    float px() const { return m_px; }
    float py() const { return m_py; }
    float pz() const { return m_pz; }
    float m() const { return m_m; }
    int pdgId() const { return m_pdgId; }
    int status() const { return m_status; }
    int prodVtx() const { return m_prodVtx; }
    int endVtx() const { return m_endVtx; }
    int barcode() const { return m_barcode; }
};

struct McEventColAcc : public McEventCollection_p6 {
    const std::vector<GenEvent_p6>& genEvents() const { return m_genEvents; }
    const std::vector<GenVertex_p6>& genVertices() const { return m_genVertices; }
    const std::vector<GenParticle_p6>& genParticles() const { return m_genParticles; }
};

static_assert(sizeof(GenEvent_p6) == 344, "Must compile t3_genie_hits_scanner with -DHEPMC3 to match libGeneratorObjectsTPCnv");
static_assert(sizeof(GenEventAcc) == sizeof(GenEvent_p6), "GenEventAcc layout mismatch");
static_assert(sizeof(GenVertexAcc) == sizeof(GenVertex_p6), "GenVertexAcc layout mismatch");
static_assert(sizeof(GenParticleAcc) == sizeof(GenParticle_p6), "GenParticleAcc layout mismatch");
static_assert(sizeof(McEventColAcc) == sizeof(McEventCollection_p6), "McEventColAcc layout mismatch");

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
    if (!ifs.is_open()) throw std::runtime_error("Cannot open list file: " + path);
    std::vector<std::string> out;
    std::string line;
    while (std::getline(ifs, line)) {
        const auto p0 = line.find_first_not_of(" \t\r\n");
        if (p0 == std::string::npos || line[p0] == '#') continue;
        const auto p1 = line.find_last_not_of(" \t\r\n");
        out.push_back(line.substr(p0, p1 - p0 + 1));
    }
    return out;
}

bool parsePhysSubrange(const std::string& physPath, std::string& runStrOut, std::string& tagOut, int& subStartOut) {
    // Pattern: .../mc24/genie/<run>/bck/<tag>/FaserMC-...-<run>-<subA>-<subB>-<tag>-PHYS.root
    const std::string base = std::filesystem::path(physPath).filename().string();
    std::vector<std::string> toks;
    std::stringstream ss(base);
    std::string tok;
    while (std::getline(ss, tok, '-')) toks.push_back(tok);
    if (toks.size() < 6) return false;
    // Find 6-digit run token starting with "200"
    for (size_t i = 0; i + 4 < toks.size(); ++i) {
        if (toks[i].size() == 6 && toks[i].rfind("200", 0) == 0) {
            runStrOut = toks[i];
            subStartOut = std::stoi(toks[i + 1]);
            tagOut = toks[i + 3];
            return true;
        }
    }
    return false;
}

std::unordered_map<int, std::string> indexHitsFilesForRun(const std::string& runStr, const std::string& simTag) {
    std::unordered_map<int, std::string> mapOut;
    const std::string dir = "/eos/experiment/fasernu-data0/faser/sim/mc24/genie/" + runStr + "/sim/" + simTag;
    if (!std::filesystem::exists(dir)) {
        throw std::runtime_error("Missing HITS directory: " + dir);
    }
    for (const auto& ent : std::filesystem::directory_iterator(dir)) {
        if (!ent.is_regular_file()) continue;
        const std::string fname = ent.path().filename().string();
        if (fname.find("-HITS.root") == std::string::npos) continue;
        std::vector<std::string> toks;
        std::stringstream ss(fname);
        std::string tok;
        while (std::getline(ss, tok, '-')) toks.push_back(tok);
        for (size_t i = 0; i + 2 < toks.size(); ++i) {
            if (toks[i] == runStr) {
                const int sub = std::stoi(toks[i + 1]);
                mapOut[sub] = ent.path().string();
                break;
            }
        }
    }
    return mapOut;
}

// Source categories:
//  0 = no VetoNu hit energy
//  1 = direct backward proton (|pdg|==2212)
//  2 = direct backward pi+- (|pdg|==211)
//  3 = direct backward K+- (|pdg|==321)
//  4 = neutron-induced recoil/fragment inside/near VetoNu (mother==2112 or vertexIn==2112 or nuclear fragment >1e9)
//  5 = photon conversion e+- (|pdg|==11 with mother==22 or vertexIn==22 or local conversion)
//  6 = e+- (non-photon parent / cascade)
//  7 = mu+- (|pdg|==13)
//  8 = unmatched barcode==0 high dE/dx (>0.45 MeV/mm -> nuclear/proton recoil)
//  9 = unmatched barcode==0 low dE/dx (<=0.45 MeV/mm -> MIP/EM)
// 10 = other tracked hadron (hyperon, deuteron, etc.)
struct PlateTruthInfo {
    int nHits{0};
    double sumEMeV{0.0};
    double sumLenMm{0.0};
    double dEdxMeVPerMm{0.0};
    double tEwNs{kNaN};
    double tFirstNs{kNaN};
    double tSpreadNs{0.0};
    double meanLocalX{0.0};
    double meanLocalY{0.0};
    double meanLocalZ{0.0};
    int domSrcCat{0};
    int domPdg{0};
    int domMotherPdg{0};
    double domKeMeV{0.0};
    double domCosBack{0.0};
    double domProdZMm{0.0};
    double fracProtonE{0.0};
    double fracPionE{0.0};
    double fracElecE{0.0};
    double fracRecoilUnmatchedE{0.0};
};

struct VetoNuTruthDissection {
    int mcEventNbr{-1};
    double primX{kNaN}, primY{kNaN}, primZ{kNaN};
    bool hasPrimVtx{false};
    PlateTruthInfo plate[2];
};

VetoNuTruthDissection dissectVetoNuTruth(const ScintHitCollection_p1a* hitsCol,
                                         const McEventCollection_p6* mcCol,
                                         double nomZ0Mm = -3123.0,
                                         double nomZ1Mm = -3102.0) {
    VetoNuTruthDissection out;
    if (!hitsCol) return out;

    const auto* mc = static_cast<const McEventColAcc*>(mcCol);
    std::unordered_map<int, const GenParticleAcc*> partByBc;
    std::unordered_map<int, const GenVertexAcc*> vtxByBc;
    std::vector<const GenVertexAcc*> vnVertices;
    std::vector<const GenParticleAcc*> backParticles;

    if (mc && !mc->genEvents().empty()) {
        const auto& ev0 = static_cast<const GenEventAcc&>(mc->genEvents()[0]);
        out.mcEventNbr = ev0.eventNbr();
        const auto& verts = mc->genVertices();
        const auto& parts = mc->genParticles();
        partByBc.reserve(parts.size() * 2 + 8);
        vtxByBc.reserve(verts.size() * 2 + 8);

        const size_t vBeg = std::min<size_t>(ev0.verticesBegin(), verts.size());
        const size_t vEnd = std::min<size_t>(ev0.verticesEnd(), verts.size());
        for (size_t iv = vBeg; iv < vEnd; ++iv) {
            const auto* gv = static_cast<const GenVertexAcc*>(&verts[iv]);
            vtxByBc[gv->barcode()] = gv;
            if (gv->z() >= -3160.0f && gv->z() <= -3070.0f) {
                vnVertices.push_back(gv);
            }
        }
        const GenVertexAcc* primV = nullptr;
        auto itSig = vtxByBc.find(ev0.signalProcessVtx());
        if (itSig != vtxByBc.end()) {
            primV = itSig->second;
        } else if (vBeg < vEnd) {
            primV = static_cast<const GenVertexAcc*>(&verts[vBeg]);
        }
        if (primV != nullptr) {
            out.primX = primV->x();
            out.primY = primV->y();
            out.primZ = primV->z();
            out.hasPrimVtx = true;
        }
        const size_t pBeg = std::min<size_t>(ev0.particlesBegin(), parts.size());
        const size_t pEnd = std::min<size_t>(ev0.particlesEnd(), parts.size());
        for (size_t ip = pBeg; ip < pEnd; ++ip) {
            const auto* gp = static_cast<const GenParticleAcc*>(&parts[ip]);
            partByBc[gp->barcode()] = gp;
            if (gp->pz() < 0.0f) {
                auto itProd = vtxByBc.find(gp->prodVtx());
                if (itProd != vtxByBc.end() && itProd->second->z() > -3150.0f) {
                    backParticles.push_back(gp);
                }
            }
        }
    }

    struct RawHitDecoded {
        int plate{0};
        double tHit{0.0};
        double xLoc{0.0}, yLoc{0.0}, zLoc{0.0};
        double eneMeV{0.0};
        double lenMm{0.0};
        int barcode{0};
    };
    std::vector<RawHitDecoded> hits;
    hits.reserve(hitsCol->m_hitEne_2b.size());

    constexpr double kEneUnit = 1.0e-5;
    constexpr double kLenUnit = 1.0e-5;
    constexpr double kAngUnit = 1.0e-5;
    constexpr double kHalfMax = 32768.0;
    constexpr unsigned short k2bMax = static_cast<unsigned short>(-1);

    unsigned int hitCount = 0, angleCount = 0;
    unsigned int idxBC = 0, idxId = 0, idxEne4b = 0, idxLen4b = 0;
    unsigned int endHit = 0, endBC = 0, endId = 0;

    for (size_t i = 0; i < hitsCol->m_nHits.size(); ++i) {
        const unsigned int nInStr = hitsCol->m_nHits[i];
        if (!nInStr) continue;
        const unsigned int start = endHit;
        endHit += nInStr;
        const double t0 = hitsCol->m_hit1_meanTime[i];
        const double th0 = hitsCol->m_hit1_theta[i];
        const double ph0 = hitsCol->m_hit1_phi[i];
        double curX = hitsCol->m_hit1_x0[i];
        double curY = hitsCol->m_hit1_y0[i];
        double curZ = hitsCol->m_hit1_z0[i];

        for (unsigned int j = start; j < endHit; ++j) {
            if (idxBC + 1 < hitsCol->m_nBC.size() && j >= endBC + hitsCol->m_nBC[idxBC]) {
                endBC += hitsCol->m_nBC[idxBC++];
            }
            if (idxId + 1 < hitsCol->m_nId.size() && j >= endId + hitsCol->m_nId[idxId]) {
                endId += hitsCol->m_nId[idxId++];
            }
            const unsigned long hid = (idxId < hitsCol->m_id.size()) ? hitsCol->m_id[idxId] : 0UL;
            const int plate = (hid == 43 || hid == 83 || hid >= 40) ? 1 : 0;
            const int bc = (idxBC < hitsCol->m_barcode.size()) ? static_cast<int>(hitsCol->m_barcode[idxBC]) : 0;

            const unsigned short e2 = hitsCol->m_hitEne_2b[hitCount];
            const unsigned short l2 = hitsCol->m_hitLength_2b[hitCount];
            const double ene = (e2 < k2bMax) ? (e2 * kEneUnit) : hitsCol->m_hitEne_4b[idxEne4b++];
            const double len = (l2 < k2bMax) ? (l2 * kLenUnit) : hitsCol->m_hitLength_4b[idxLen4b++];
            const double dTh = (j > start) ? ((static_cast<double>(hitsCol->m_dTheta[angleCount]) - kHalfMax) * kAngUnit) : 0.0;
            const double dPh = (j > start) ? ((static_cast<double>(hitsCol->m_dPhi[angleCount]) - kHalfMax) * kAngUnit) : 0.0;

            hits.push_back({plate, t0, curX, curY, curZ, ene, len, bc});

            const double th = th0 + dTh;
            const double ph = ph0 + dPh;
            curX += len * std::sin(th) * std::cos(ph);
            curY += len * std::sin(th) * std::sin(ph);
            curZ += len * std::cos(th);

            ++hitCount;
            if (j > start) ++angleCount;
        }
    }

    auto classifyHit = [&](const RawHitDecoded& h, int& catOut, int& pdgOut, int& momOut, double& keOut, double& cosOut, double& prodZOut) {
        keOut = 0.0;
        cosOut = 0.0;
        prodZOut = 0.0;
        momOut = 0;

        auto classifyByPdgAndMother = [&](int apdg, int pdg, int momPdg, double momKe, double cBack, double pZ) {
            pdgOut = pdg;
            momOut = momPdg;
            keOut = momKe;
            cosOut = cBack;
            prodZOut = pZ;
            const int amom = std::abs(momPdg);
            if (pdg > 1000000000 || amom == 2112) {
                catOut = 4; // neutron knock-on or nuclear fragment
            } else if (apdg == 2212) {
                catOut = (amom == 2112) ? 4 : 1;
            } else if (apdg == 211) {
                catOut = 2;
            } else if (apdg == 321) {
                catOut = 3;
            } else if (apdg == 11) {
                catOut = (momPdg == 22 || pZ < -3050.0) ? 5 : 6;
            } else if (apdg == 13) {
                catOut = 7;
            } else {
                catOut = 10;
            }
        };

        if (h.barcode > 0) {
            auto itP = partByBc.find(h.barcode);
            if (itP != partByBc.end()) {
                const auto* gp = itP->second;
                const double p2 = static_cast<double>(gp->px()) * gp->px() +
                                  static_cast<double>(gp->py()) * gp->py() +
                                  static_cast<double>(gp->pz()) * gp->pz();
                const double pMag = std::sqrt(p2);
                const double m = std::max(0.0, static_cast<double>(gp->m()));
                const double ke = std::sqrt(p2 + m * m) - m;
                const double cBack = (pMag > 1e-6) ? (-static_cast<double>(gp->pz()) / pMag) : 0.0;
                double pZ = 0.0;
                int momPdg = 0;
                auto itV = vtxByBc.find(gp->prodVtx());
                if (itV != vtxByBc.end()) {
                    const auto* pv = itV->second;
                    pZ = pv->z();
                    if (!pv->particlesIn().empty()) {
                        auto itM = partByBc.find(pv->particlesIn()[0]);
                        if (itM != partByBc.end()) momPdg = itM->second->pdgId();
                    }
                }
                classifyByPdgAndMother(std::abs(gp->pdgId()), gp->pdgId(), momPdg, ke, cBack, pZ);
                return;
            }
        }

        // barcode == 0 or absent: match local GenVertex inside VetoNu first
        const double zWorld = h.zLoc + ((h.plate == 0) ? nomZ0Mm : nomZ1Mm);
        const GenVertexAcc* bestV = nullptr;
        double bestD2 = 30.0 * 30.0;
        for (const auto* gv : vnVertices) {
            const double dz = gv->z() - zWorld;
            const double dxy2 = (gv->x() - h.xLoc) * (gv->x() - h.xLoc) + (gv->y() - h.yLoc) * (gv->y() - h.yLoc);
            const double d2 = dxy2 + dz * dz;
            if (std::abs(dz) < 25.0 && d2 < bestD2) {
                bestD2 = d2;
                bestV = gv;
            }
        }
        if (bestV != nullptr && !bestV->particlesIn().empty()) {
            auto itIn = partByBc.find(bestV->particlesIn()[0]);
            if (itIn != partByBc.end()) {
                const auto* pin = itIn->second;
                const double p2 = static_cast<double>(pin->px()) * pin->px() +
                                  static_cast<double>(pin->py()) * pin->py() +
                                  static_cast<double>(pin->pz()) * pin->pz();
                const double pMag = std::sqrt(p2);
                const double m = std::max(0.0, static_cast<double>(pin->m()));
                const double ke = std::sqrt(p2 + m * m) - m;
                const double cBack = (pMag > 1e-6) ? (-static_cast<double>(pin->pz()) / pMag) : 0.0;
                if (pin->pdgId() == 2112) {
                    catOut = 4;
                    pdgOut = -2112;
                } else if (pin->pdgId() == 22) {
                    catOut = 5;
                    pdgOut = -22;
                } else {
                    const int ap = std::abs(pin->pdgId());
                    catOut = (ap == 2212) ? 1 : ((ap == 211) ? 2 : ((ap == 321) ? 3 : 10));
                    pdgOut = pin->pdgId();
                }
                momOut = pin->pdgId();
                keOut = ke;
                cosOut = cBack;
                prodZOut = bestV->z();
                return;
            }
        }

        // Fall back to backward-exiting particle projection or local dE/dx
        const GenParticleAcc* bestBack = nullptr;
        double bestR = 25.0;
        for (const auto* gp : backParticles) {
            if (gp->pz() >= -1e-3f) continue;
            auto itPv = vtxByBc.find(gp->prodVtx());
            if (itPv == vtxByBc.end()) continue;
            const auto* pv = itPv->second;
            const double dz = zWorld - pv->z();
            if (dz > 5.0) continue; // backward: zWorld < pv->z()
            const double dtSlope = dz / gp->pz();
            const double xExp = pv->x() + gp->px() * dtSlope;
            const double yExp = pv->y() + gp->py() * dtSlope;
            const double dist = std::hypot(xExp - h.xLoc, yExp - h.yLoc);
            if (dist < bestR) {
                bestR = dist;
                bestBack = gp;
            }
        }
        const double hitDedx = h.eneMeV / std::max(0.02, h.lenMm);
        if (bestBack != nullptr) {
            const int ap = std::abs(bestBack->pdgId());
            const double p2 = static_cast<double>(bestBack->px()) * bestBack->px() +
                              static_cast<double>(bestBack->py()) * bestBack->py() +
                              static_cast<double>(bestBack->pz()) * bestBack->pz();
            const double pMag = std::sqrt(p2);
            const double m = std::max(0.0, static_cast<double>(bestBack->m()));
            const double ke = std::sqrt(p2 + m * m) - m;
            const double cBack = (pMag > 1e-6) ? (-static_cast<double>(bestBack->pz()) / pMag) : 0.0;
            if (ap == 2112) {
                catOut = 4; pdgOut = -2112;
            } else if (ap == 22) {
                catOut = 5; pdgOut = -22;
            } else {
                catOut = (ap == 2212) ? 1 : ((ap == 211) ? 2 : ((ap == 321) ? 3 : ((ap == 11) ? 6 : 10)));
                pdgOut = bestBack->pdgId();
            }
            momOut = bestBack->pdgId();
            keOut = ke;
            cosOut = cBack;
            prodZOut = vtxByBc[bestBack->prodVtx()]->z();
            return;
        }
        catOut = (hitDedx > 0.45) ? 8 : 9;
        pdgOut = (catOut == 8) ? 990001 : 990002;
    };

    for (int pl = 0; pl < 2; ++pl) {
        auto& info = out.plate[pl];
        const double zNomM = (pl == 0 ? nomZ0Mm : nomZ1Mm) * 1e-3;
        const double tOffset = zNomM / kSpeedOfLightMPerNs;

        struct SrcBucket {
            int pdg{0};
            int mom{0};
            double sumE{0.0};
            double wKe{0.0}, wCos{0.0}, wPz{0.0};
        };
        std::map<std::pair<int, int>, SrcBucket> buckets;

        double sumE = 0.0, sumLen = 0.0, wT = 0.0, wX = 0.0, wY = 0.0, wZ = 0.0;
        double tMin = 1e9, tMax = -1e9;
        int nH = 0;
        double eP = 0.0, ePi = 0.0, eEl = 0.0, eRec = 0.0;

        for (const auto& h : hits) {
            if (h.plate != pl) continue;
            ++nH;
            const double tCorr = h.tHit - tOffset;
            sumE += h.eneMeV;
            sumLen += h.lenMm;
            wT += h.eneMeV * tCorr;
            wX += h.eneMeV * h.xLoc;
            wY += h.eneMeV * h.yLoc;
            wZ += h.eneMeV * h.zLoc;
            tMin = std::min(tMin, tCorr);
            tMax = std::max(tMax, tCorr);

            int cat = 0, pdg = 0, mom = 0;
            double ke = 0.0, cBack = 0.0, pZ = 0.0;
            classifyHit(h, cat, pdg, mom, ke, cBack, pZ);
            if (cat == 1) eP += h.eneMeV;
            else if (cat == 2) ePi += h.eneMeV;
            else if (cat == 5 || cat == 6) eEl += h.eneMeV;
            else if (cat == 4 || cat == 8) eRec += h.eneMeV;

            auto& b = buckets[{cat, pdg}];
            b.pdg = pdg;
            if (b.mom == 0 && mom != 0) b.mom = mom;
            b.sumE += h.eneMeV;
            b.wKe += h.eneMeV * ke;
            b.wCos += h.eneMeV * cBack;
            b.wPz += h.eneMeV * pZ;
        }

        info.nHits = nH;
        info.sumEMeV = sumE;
        info.sumLenMm = sumLen;
        if (sumLen > 0.0) info.dEdxMeVPerMm = sumE / sumLen;
        if (sumE > 0.0) {
            info.tEwNs = wT / sumE;
            info.tFirstNs = tMin;
            info.tSpreadNs = std::max(0.0, tMax - tMin);
            info.meanLocalX = wX / sumE;
            info.meanLocalY = wY / sumE;
            info.meanLocalZ = wZ / sumE;
            info.fracProtonE = eP / sumE;
            info.fracPionE = ePi / sumE;
            info.fracElecE = eEl / sumE;
            info.fracRecoilUnmatchedE = eRec / sumE;

            double bestE = -1.0;
            for (const auto& [key, b] : buckets) {
                if (b.sumE > bestE) {
                    bestE = b.sumE;
                    info.domSrcCat = key.first;
                    info.domPdg = b.pdg;
                    info.domMotherPdg = b.mom;
                    info.domKeMeV = b.wKe / b.sumE;
                    info.domCosBack = b.wCos / b.sumE;
                    info.domProdZMm = b.wPz / b.sumE;
                }
            }
        }
    }
    return out;
}

template <typename T>
double vecMaxIdxPos(const std::vector<T>& v) {
    if (v.empty()) return -1;
    return static_cast<int>(std::max_element(v.begin(), v.end()) - v.begin());
}

bool isInFaserNuBox(float x, float y, float z) {
    return (x > -115.f && x < 135.f && y > -171.f && y < 129.f && z > -3000.f && z < -1950.f);
}

bool isInLeadBlock(float x, float y, float z) {
    return (x > -300.f && x < 300.f && y > -300.f && y < 300.f && z > -1769.65f && z < -1619.65f);
}

bool isInCaloNuPmt(float z) {
    return (z >= -2928.0f && z <= -2812.0f);
}

// Physical struct mapping all PHYS nt scalar & vector branches
struct PhysReader {
    TTree* t{nullptr};
    bool hasReduced{false};
    bool hasNativeVeto11{false};
    bool hasCalo{false};

    Int_t run{0};
    Int_t eventID{0};
    Int_t longTracks{0};
    Int_t nClusters0{0};

    std::vector<int>* truth_pdg{nullptr};
    std::vector<double>* truth_P{nullptr};
    std::vector<double>* truth_px{nullptr};
    std::vector<double>* truth_py{nullptr};
    std::vector<double>* truth_pz{nullptr};
    std::vector<double>* truth_dec_x{nullptr};
    std::vector<double>* truth_dec_y{nullptr};
    std::vector<double>* truth_dec_z{nullptr};

    std::vector<double>* tk_pz0{nullptr};
    std::vector<double>* tk_px0{nullptr};
    std::vector<double>* tk_py0{nullptr};
    std::vector<unsigned int>* tk_nLayers{nullptr};
    std::vector<double>* tk_nDoF{nullptr};
    std::vector<double>* tk_Chi2{nullptr};
    std::vector<double>* tk_rMax{nullptr};
    std::vector<int>* tk_charge{nullptr};
    std::vector<double>* tk_xVn{nullptr};
    std::vector<double>* tk_yVn{nullptr};
    std::vector<double>* tk_xV1{nullptr};
    std::vector<double>* tk_yV1{nullptr};
    std::vector<double>* tk_xV2{nullptr};
    std::vector<double>* tk_yV2{nullptr};
    std::vector<double>* tk_xTr{nullptr};
    std::vector<double>* tk_yTr{nullptr};
    std::vector<double>* tk_xP1{nullptr};
    std::vector<double>* tk_yP1{nullptr};
    std::vector<double>* tk_xP2{nullptr};
    std::vector<double>* tk_yP2{nullptr};

    Float_t Calo_total_E_EM{0.0f};
    Float_t VetoNu0_reduced_charge{-1.0f};
    Float_t VetoNu1_reduced_charge{-1.0f};
    Float_t Veto20_charge{0.0f}, Veto21_charge{0.0f};
    Float_t Timing0_charge{0.0f}, Timing1_charge{0.0f}, Timing2_charge{0.0f}, Timing3_charge{0.0f};
    Float_t Preshower0_charge{0.0f}, Preshower1_charge{0.0f};

    // Per-scintillator channel arrays matching the 16 physical channels:
    // 0:VN0, 1:VN1, 2:V10, 3:V11, 4:V20, 5:V21, 6:T0, 7:T1, 8:T2, 9:T3, 10:PS0, 11:PS1
    Int_t st[12]{};
    Float_t loc[12]{};
    Float_t qRaw[12]{};
    Float_t w[12]{};

    void attach(TTree* tree, bool vnCalibOnly = false) {
        t = tree;
        t->SetBranchStatus("*", 0);
        auto hasB = [&](const char* name) { return t->GetBranch(name) != nullptr; };
        hasReduced = hasB("VetoNu0_reduced_charge") && hasB("VetoNu1_reduced_charge");
        hasNativeVeto11 = hasB("Veto11_raw_charge");
        hasCalo = hasB("Calo_total_E_EM");

        auto bind = [&](const char* name, auto* addr) {
            if (hasB(name)) {
                t->SetBranchStatus(name, 1);
                const Int_t rc = t->SetBranchAddress(name, addr);
                if (rc < 0) {
                    throw std::runtime_error(std::string("SetBranchAddress failed for ") + name + " (rc=" + std::to_string(rc) + ")");
                }
            }
        };
        bind("run", &run);
        bind("eventID", &eventID);

        const int nBindCh = vnCalibOnly ? 2 : 12;
        const std::array<const char*, 12> pfxs = {{
            "VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21",
            "Timing0", "Timing1", "Timing2", "Timing3", "Preshower0", "Preshower1"
        }};
        for (int i = 0; i < nBindCh; ++i) {
            const std::string p = pfxs[i];
            if (i == 3 && !hasNativeVeto11) { st[i] = -1; loc[i] = 0; qRaw[i] = 0; w[i] = 0; continue; }
            bind((p + "_status").c_str(), &st[i]);
            bind((p + "_localtime").c_str(), &loc[i]);
            bind((p + "_raw_charge").c_str(), &qRaw[i]);
            bind((p + "_width").c_str(), &w[i]);
        }
        if (vnCalibOnly) return;

        bind("longTracks", &longTracks);
        bind("nClusters0", &nClusters0);

        bind("truth_pdg", &truth_pdg);
        bind("truth_P", &truth_P);
        bind("truth_px", &truth_px);
        bind("truth_py", &truth_py);
        bind("truth_pz", &truth_pz);
        bind("truth_dec_x", &truth_dec_x);
        bind("truth_dec_y", &truth_dec_y);
        bind("truth_dec_z", &truth_dec_z);

        bind("Track_pz0", &tk_pz0);
        bind("Track_px0", &tk_px0);
        bind("Track_py0", &tk_py0);
        bind("Track_nLayers", &tk_nLayers);
        bind("Track_nDoF", &tk_nDoF);
        bind("Track_Chi2", &tk_Chi2);
        bind("Track_r_atMaxRadius", &tk_rMax);
        bind("Track_charge", &tk_charge);
        bind("Track_X_atVetoNu", &tk_xVn);
        bind("Track_Y_atVetoNu", &tk_yVn);
        bind("Track_X_atVetoStation1", &tk_xV1);
        bind("Track_Y_atVetoStation1", &tk_yV1);
        bind("Track_X_atVetoStation2", &tk_xV2);
        bind("Track_Y_atVetoStation2", &tk_yV2);
        bind("Track_X_atTrig", &tk_xTr);
        bind("Track_Y_atTrig", &tk_yTr);
        bind("Track_X_atPreshower1", &tk_xP1);
        bind("Track_Y_atPreshower1", &tk_yP1);
        bind("Track_X_atPreshower2", &tk_xP2);
        bind("Track_Y_atPreshower2", &tk_yP2);

        if (hasCalo) bind("Calo_total_E_EM", &Calo_total_E_EM);
        if (hasReduced) {
            bind("VetoNu0_reduced_charge", &VetoNu0_reduced_charge);
            bind("VetoNu1_reduced_charge", &VetoNu1_reduced_charge);
        }
        bind("Veto20_charge", &Veto20_charge);
        bind("Veto21_charge", &Veto21_charge);
        bind("Timing0_charge", &Timing0_charge);
        bind("Timing1_charge", &Timing1_charge);
        bind("Timing2_charge", &Timing2_charge);
        bind("Timing3_charge", &Timing3_charge);
        bind("Preshower0_charge", &Preshower0_charge);
        bind("Preshower1_charge", &Preshower1_charge);
    }

    RawInputArray buildInputs(int leadIdx, double& leadYTrigOut) const {
        RawInputArray arr{};
        auto getPos = [&](const std::vector<double>* xv, const std::vector<double>* yv, double& x, double& y, bool& ok) {
            x = 999999.0; y = 999999.0; ok = false;
            if (leadIdx < 0 || !xv || !yv) return;
            if (leadIdx >= static_cast<int>(xv->size()) || leadIdx >= static_cast<int>(yv->size())) return;
            const double xx = (*xv)[leadIdx], yy = (*yv)[leadIdx];
            if (!std::isfinite(xx) || !std::isfinite(yy) || std::abs(xx) >= 1000.0 || std::abs(yy) >= 1000.0) return;
            x = xx; y = yy; ok = true;
        };
        double xVn, yVn, xV1, yV1, xV2, yV2, xTr, yTr, xP1, yP1, xP2, yP2;
        bool okVn, okV1, okV2, okTr, okP1, okP2;
        getPos(tk_xVn, tk_yVn, xVn, yVn, okVn);
        getPos(tk_xV1, tk_yV1, xV1, yV1, okV1);
        getPos(tk_xV2, tk_yV2, xV2, yV2, okV2);
        getPos(tk_xTr, tk_yTr, xTr, yTr, okTr);
        getPos(tk_xP1, tk_yP1, xP1, yP1, okP1);
        getPos(tk_xP2, tk_yP2, xP2, yP2, okP2);
        leadYTrigOut = okTr ? yTr : kNaN;

        auto fill = [&](int chIdx, int i, bool pres, double x, double y, bool ok) {
            auto& s = arr[chIdx];
            s.present = pres;
            s.goodStatus = pres && TimingCalibrator::isGoodWaveformStatus(st[i]);
            s.localTime = loc[i];
            s.rawCharge = qRaw[i];
            s.width = w[i];
            s.xMm = x; s.yMm = y; s.validPos = ok;
        };
        fill(0, 0, true, xVn, yVn, okVn);
        fill(1, 1, true, xVn, yVn, okVn);
        fill(2, 2, true, xV1, yV1, okV1);
        fill(3, 3, hasNativeVeto11, xV1, yV1, okV1);
        fill(4, 4, true, xV2, yV2, okV2);
        fill(5, 5, true, xV2, yV2, okV2);
        arr[6] = TimingCalibrator::combineTimingPairMC(
            TimingCalibrator::isGoodWaveformStatus(st[6]), loc[6], qRaw[6], w[6],
            TimingCalibrator::isGoodWaveformStatus(st[7]), loc[7], qRaw[7], w[7], xTr, yTr, okTr);
        arr[7] = TimingCalibrator::combineTimingPairMC(
            TimingCalibrator::isGoodWaveformStatus(st[8]), loc[8], qRaw[8], w[8],
            TimingCalibrator::isGoodWaveformStatus(st[9]), loc[9], qRaw[9], w[9], xTr, yTr, okTr);
        fill(8, 10, true, xP1, yP1, okP1);
        fill(9, 11, true, xP2, yP2, okP2);
        return arr;
    }
};

void printUsage(const char* argv0) {
    std::cerr << "Usage: " << argv0
              << " --mode <vn-calib|t3-extract> --output <out.root>"
              << " (--input-files <f1,f2,...> | --input-list <list.txt>)"
              << " [--timing-calib <dir>] [--max-files <n>]\n";
}

} // namespace

int main(int argc, char* argv[]) {
    gSystem->Load("libScintSimEventTPCnv.so");
    gSystem->Load("libGeneratorObjectsTPCnv.so");
    if (auto* tc = TClass::GetClass("GenEvent_p6")) {
        if (static_cast<size_t>(tc->Size()) != sizeof(GenEvent_p6)) {
            throw std::runtime_error("GenEvent_p6 TClass size mismatch: binary ABI incompatible");
        }
    }
    TH1::AddDirectory(false);

    std::string mode;
    std::string outputPath;
    std::string inputFilesArg;
    std::string inputListArg;
    std::string calibDir;
    int maxFiles = -1;

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
        else if (arg == "--max-files") maxFiles = std::stoi(needVal(arg));
        else { printUsage(argv[0]); return 1; }
    }

    if ((mode != "vn-calib" && mode != "t3-extract") || outputPath.empty() ||
        (inputFilesArg.empty() && inputListArg.empty())) {
        printUsage(argv[0]);
        return 1;
    }
    if (mode == "t3-extract" && calibDir.empty()) {
        std::cerr << "ERROR: --mode t3-extract requires --timing-calib <dir>\n";
        return 1;
    }

    std::vector<std::string> physFiles;
    if (!inputFilesArg.empty()) {
        auto v = splitCommaList(inputFilesArg);
        physFiles.insert(physFiles.end(), v.begin(), v.end());
    }
    if (!inputListArg.empty()) {
        auto v = readListFile(inputListArg);
        physFiles.insert(physFiles.end(), v.begin(), v.end());
    }
    std::sort(physFiles.begin(), physFiles.end());
    if (maxFiles > 0 && static_cast<int>(physFiles.size()) > maxFiles) {
        physFiles.resize(static_cast<size_t>(maxFiles));
    }

    std::shared_ptr<TimingCalibrator> calib;
    if (!calibDir.empty()) {
        calib = std::make_shared<TimingCalibrator>();
        calib->loadFromDirectory(calibDir);
    }

    const auto wallStart = std::chrono::steady_clock::now();
    const auto outParent = std::filesystem::path(outputPath).parent_path();
    if (!outParent.empty()) std::filesystem::create_directories(outParent);

    std::unique_ptr<TFile> outFile(TFile::Open(outputPath.c_str(), "RECREATE"));
    if (!outFile || outFile->IsZombie()) {
        throw std::runtime_error("Cannot open output ROOT file: " + outputPath);
    }

    // Cache HITS file indices per (runStr, simTag)
    std::map<std::pair<std::string, std::string>, std::unordered_map<int, std::string>> hitsIndexCache;

    if (mode == "vn-calib") {
        TTree* vnTree = new TTree("vn_hits", "Isolated single-string VetoNu hits in GENIE MC vs HITS");
        Int_t runOut = 0, evtOut = 0, plateOut = 0, statusOut = 0, pdgOut = 0;
        Float_t locOut = 0, tCorrHitOut = 0, residOut = 0, qRawOut = 0, widthOut = 0, eneMeVOut = 0, dedxOut = 0;
        Float_t xLocOut = 0, yLocOut = 0, zLocOut = 0;
        vnTree->Branch("run", &runOut);
        vnTree->Branch("eventID", &evtOut);
        vnTree->Branch("plate", &plateOut);
        vnTree->Branch("status", &statusOut);
        vnTree->Branch("dom_pdg", &pdgOut);
        vnTree->Branch("localtime", &locOut);
        vnTree->Branch("t_hit_corr", &tCorrHitOut);
        vnTree->Branch("t_ref_est", &residOut);
        vnTree->Branch("raw_charge", &qRawOut);
        vnTree->Branch("width", &widthOut);
        vnTree->Branch("ene_mev", &eneMeVOut);
        vnTree->Branch("dedx", &dedxOut);
        vnTree->Branch("x_loc", &xLocOut);
        vnTree->Branch("y_loc", &yLocOut);
        vnTree->Branch("z_loc", &zLocOut);

        uint64_t nEntriesScanned = 0;
        uint64_t nKept0 = 0, nKept1 = 0;
        for (const auto& pf : physFiles) {
            std::string rstr, tag;
            int subStart = 0;
            if (!parsePhysSubrange(pf, rstr, tag, subStart)) continue;
            auto key = std::make_pair(rstr, tag);
            if (!hitsIndexCache.count(key)) hitsIndexCache[key] = indexHitsFilesForRun(rstr, tag);
            const auto& hmap = hitsIndexCache[key];

            std::unique_ptr<TFile> fPhys(TFile::Open(pf.c_str(), "READ"));
            if (!fPhys || fPhys->IsZombie()) continue;
            TTree* nt = fPhys->Get<TTree>("nt");
            if (!nt) continue;
            PhysReader rd;
            rd.attach(nt, true);

            int curSub = -1;
            std::unique_ptr<TFile> fHit;
            TTree* colTree = nullptr;
            ScintHitCollection_p1a* vnHits = nullptr;

            const Long64_t nEnt = nt->GetEntries();
            for (Long64_t i = 0; i < nEnt; ++i) {
                nt->GetEntry(i);
                ++nEntriesScanned;
                const bool ok0 = (rd.loc[0] > 100.0f && TimingCalibrator::isGoodWaveformStatus(rd.st[0]) && rd.qRaw[0] > 8.0f && rd.w[0] < 7.5f);
                const bool ok1 = (rd.loc[1] > 100.0f && TimingCalibrator::isGoodWaveformStatus(rd.st[1]) && rd.qRaw[1] > 8.0f && rd.w[1] < 7.5f);
                if (!ok0 && !ok1) continue;

                const int sub = (rd.eventID >= 0) ? (rd.eventID / 1000) : (subStart + static_cast<int>(i / 1000LL));
                const Long64_t hEntry = (rd.eventID >= 0) ? (rd.eventID % 1000) : (i % 1000LL);
                auto itH = hmap.find(sub);
                if (itH == hmap.end()) continue;
                if (sub != curSub) {
                    fHit.reset(TFile::Open(itH->second.c_str(), "READ"));
                    if (!fHit || fHit->IsZombie()) { colTree = nullptr; curSub = -1; continue; }
                    colTree = fHit->Get<TTree>("CollectionTree");
                    if (!colTree) { curSub = -1; continue; }
                    colTree->SetBranchStatus("*", 0);
                    colTree->SetBranchStatus("*VetoNuHits*", 1);
                    colTree->SetBranchAddress("ScintHitCollection_p1a_VetoNuHits", &vnHits);
                    curSub = sub;
                }
                if (!colTree || hEntry >= colTree->GetEntries()) continue;
                colTree->GetEntry(hEntry);

                const auto dis = dissectVetoNuTruth(vnHits, nullptr);
                for (int pl = 0; pl < 2; ++pl) {
                    const bool okPl = (pl == 0) ? ok0 : ok1;
                    const auto& info = dis.plate[pl];
                    if (!okPl || info.nHits <= 0 || info.sumEMeV <= 0.0 || info.tSpreadNs > 0.25) continue;
                    runOut = rd.run;
                    evtOut = rd.eventID;
                    plateOut = pl;
                    statusOut = rd.st[pl];
                    pdgOut = info.domPdg;
                    locOut = rd.loc[pl];
                    tCorrHitOut = static_cast<float>(info.tEwNs);
                    residOut = static_cast<float>(rd.loc[pl] - info.tEwNs);
                    qRawOut = rd.qRaw[pl];
                    widthOut = rd.w[pl];
                    eneMeVOut = static_cast<float>(info.sumEMeV);
                    dedxOut = static_cast<float>(info.dEdxMeVPerMm);
                    xLocOut = static_cast<float>(info.meanLocalX);
                    yLocOut = static_cast<float>(info.meanLocalY);
                    zLocOut = static_cast<float>(info.meanLocalZ);
                    vnTree->Fill();
                    if (pl == 0) ++nKept0;
                    else ++nKept1;
                }
            }
        }
        outFile->cd();
        vnTree->Write();
        outFile->Close();
        const double wallS = std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStart).count();
        std::cout << "[vn-calib] files=" << physFiles.size() << " scanned=" << nEntriesScanned
                  << " kept_vn0=" << nKept0 << " kept_vn1=" << nKept1
                  << " wall_s=" << wallS << " out=" << outputPath << "\n";
        return 0;
    }

    // --mode t3-extract
    TTree* sumTree = new TTree("run_summary", "Stage T3 per-run truth denominator & cutflow summary");
    Int_t sRun = 0;
    uint64_t nGen = 0, nNoCaloNu = 0, nCc = 0, nNuMuCc = 0, nFidVol = 0, nFidR = 0, nFidPz = 0, nKinSr = 0, nHitsMatched = 0;
    sumTree->Branch("run", &sRun);
    sumTree->Branch("n_gen", &nGen);
    sumTree->Branch("n_no_calonu_pmt", &nNoCaloNu);
    sumTree->Branch("n_cc", &nCc);
    sumTree->Branch("n_numu_cc", &nNuMuCc);
    sumTree->Branch("n_fid_vol", &nFidVol);
    sumTree->Branch("n_fid_r100", &nFidR);
    sumTree->Branch("n_fid_pz100", &nFidPz);
    sumTree->Branch("n_kin_sr", &nKinSr);
    sumTree->Branch("n_hits_matched", &nHitsMatched);

    // 6D Fiducial Truth Denominator Histogram Counters
    // Histograms for exact differential acceptance epsilon(x) = N_sel(x) / N_fid(x):
    TH1D hFidEnu("h_fid_E_nu", "Fiducial nu_mu CC E_nu;GeV;Events", 40, 0.0, 4000.0);
    TH1D hFidPzMu("h_fid_pz_mu", "Fiducial nu_mu CC p_z,mu;GeV;Events", 40, 0.0, 2000.0);
    TH1D hFidY("h_fid_y_inel", "Fiducial nu_mu CC y_inel;y;Events", 20, 0.0, 1.0);
    TH1D hFidZvtx("h_fid_z_vtx", "Fiducial nu_mu CC z_vtx;mm;Events", 35, -3050.0, -1600.0);
    TH1D hFidRvtx("h_fid_r_vtx", "Fiducial nu_mu CC r_vtx;mm;Events", 20, 0.0, 100.0);
    TH1D hFidQmu("h_fid_q_mu", "Fiducial nu_mu CC muon charge;q_mu;Events", 5, -2.5, 2.5);

    TTree* evTree = new TTree("t3_events", "Stage T3 kinematic-SR nu_mu CC events with timing + Geant4 VetoNu truth");
    Int_t eRun = 0, eEventID = 0, eHitMcEvtNbr = -1;
    Bool_t eHitsVtxMatch = false;
    Int_t eNuPdg = 0, eMuPdg = 0, eAnchorCh = -1, eNDown = 0, eNdofDown = 0, eNDownTrigGeom = 0, eNdofDownTrigGeom = 0, eNDownTrim = 0, eNdofDownTrim = 0;
    Int_t eNClus0 = 0;
    Float_t eEnuGeV = 0, ePzMuGeV = 0, eYInel = 0, eTruthX = 0, eTruthY = 0, eTruthZ = 0, eTruthR = 0;
    Float_t eLeadPzGeV = 0, eLeadQ = 0, eLeadTheta = 0, eLeadRVn = 0, eLeadRMax = 0, eLeadRIft = 0, eLeadYTrig = 0;
    Float_t eCaloEM = 0, ePS0Q = 0, ePS1Q = 0;
    Float_t eVnQRaw[2]{}, eVnQRed[2]{}, eVnWidth[2]{};
    Int_t eVnSt[2]{};
    Bool_t eVnValid[2]{};
    Float_t eVnDt[2]{}, eVnDtTg[2]{}, eVnDtTrim[2]{}, eVnPull[2]{}, eVnSigma[2]{}, eVnT0Mc[2]{};
    Float_t eT0Down = 0, eSigT0Down = 0, eChi2Down = 0;
    Float_t eT0DownTrigGeom = 0, eChi2DownTrigGeom = 0;
    Float_t eT0DownTrim = 0, eChi2DownTrim = 0;
    Float_t eDtComb = 0, eZComb = 0, eDt10 = 0, eDeltaChi2Back = 0, eBeta = 0;
    Float_t eDtCombTg = 0, eZCombTg = 0, eDeltaChi2BackTg = 0;
    Float_t eDtCombTrim = 0, eZCombTrim = 0, eDeltaChi2BackTrim = 0;
    Float_t eDtCombRaw40 = 0, eZCombRaw40 = 0, eDeltaChi2BackRaw40 = 0;
    // Per-downstream channel diagnostics (2..9: V10, V11, V20, V21, T01, T23, PS0, PS1)
    Int_t eDownSt[8]{};
    Float_t eDownTCal[8]{}, eDownTSig[8]{}, eDownTUnsmear[8]{}, eDownQRaw[8]{};
    // Geant4 HITS dissection per plate (0=VetoNu0, 1=VetoNu1)
    Int_t eG4NHits[2]{}, eG4DomCat[2]{}, eG4DomPdg[2]{}, eG4DomMom[2]{};
    Float_t eG4SumE[2]{}, eG4Dedx[2]{}, eG4TEw[2]{}, eG4TFirst[2]{}, eG4TSpread[2]{};
    Float_t eG4Ke[2]{}, eG4CosBack[2]{}, eG4ProdZ[2]{}, eG4FracP[2]{}, eG4FracPi[2]{}, eG4FracEl[2]{}, eG4FracRec[2]{};

    evTree->Branch("run", &eRun);
    evTree->Branch("eventID", &eEventID);
    evTree->Branch("hits_mc_evtnbr", &eHitMcEvtNbr);
    evTree->Branch("hits_vtx_match", &eHitsVtxMatch);
    evTree->Branch("truth_nu_pdg", &eNuPdg);
    evTree->Branch("truth_mu_pdg", &eMuPdg);
    evTree->Branch("truth_E_nu_GeV", &eEnuGeV);
    evTree->Branch("truth_pz_mu_GeV", &ePzMuGeV);
    evTree->Branch("truth_y_inel", &eYInel);
    evTree->Branch("truth_dec_x", &eTruthX);
    evTree->Branch("truth_dec_y", &eTruthY);
    evTree->Branch("truth_dec_z", &eTruthZ);
    evTree->Branch("truth_dec_r", &eTruthR);
    evTree->Branch("lead_pz0_GeV", &eLeadPzGeV);
    evTree->Branch("lead_q", &eLeadQ);
    evTree->Branch("lead_theta_mrad", &eLeadTheta);
    evTree->Branch("lead_r_vn", &eLeadRVn);
    evTree->Branch("lead_r_max", &eLeadRMax);
    evTree->Branch("lead_r_ift", &eLeadRIft);
    evTree->Branch("lead_y_trig", &eLeadYTrig);
    evTree->Branch("calo_total_E_EM", &eCaloEM);
    evTree->Branch("nClusters0", &eNClus0);
    evTree->Branch("preshower0_raw_charge", &ePS0Q);
    evTree->Branch("preshower1_raw_charge", &ePS1Q);
    evTree->Branch("vn_q_raw", eVnQRaw, "vn_q_raw[2]/F");
    evTree->Branch("vn_q_red", eVnQRed, "vn_q_red[2]/F");
    evTree->Branch("vn_width", eVnWidth, "vn_width[2]/F");
    evTree->Branch("vn_st", eVnSt, "vn_st[2]/I");
    evTree->Branch("vn_valid", eVnValid, "vn_valid[2]/O");
    evTree->Branch("vn_dt", eVnDt, "vn_dt[2]/F");
    evTree->Branch("vn_dt_tgeom", eVnDtTg, "vn_dt_tgeom[2]/F");
    evTree->Branch("vn_dt_trim", eVnDtTrim, "vn_dt_trim[2]/F");
    evTree->Branch("vn_pull", eVnPull, "vn_pull[2]/F");
    evTree->Branch("vn_sigma", eVnSigma, "vn_sigma[2]/F");
    evTree->Branch("vn_t0_mc", eVnT0Mc, "vn_t0_mc[2]/F");
    evTree->Branch("anchor_ch", &eAnchorCh);
    evTree->Branch("n_down_used", &eNDown);
    evTree->Branch("ndof_down", &eNdofDown);
    evTree->Branch("t0_down", &eT0Down);
    evTree->Branch("sigma_t0_down", &eSigT0Down);
    evTree->Branch("chi2_down", &eChi2Down);
    evTree->Branch("n_down_tgeom", &eNDownTrigGeom);
    evTree->Branch("ndof_down_tgeom", &eNdofDownTrigGeom);
    evTree->Branch("t0_down_tgeom", &eT0DownTrigGeom);
    evTree->Branch("chi2_down_tgeom", &eChi2DownTrigGeom);
    evTree->Branch("n_down_trim", &eNDownTrim);
    evTree->Branch("ndof_down_trim", &eNdofDownTrim);
    evTree->Branch("t0_down_trim", &eT0DownTrim);
    evTree->Branch("chi2_down_trim", &eChi2DownTrim);
    evTree->Branch("vn_dt_comb", &eDtComb);
    evTree->Branch("vn_z_comb", &eZComb);
    evTree->Branch("vn_dt10", &eDt10);
    evTree->Branch("delta_chi2_back", &eDeltaChi2Back);
    evTree->Branch("vn_dt_comb_tgeom", &eDtCombTg);
    evTree->Branch("vn_z_comb_tgeom", &eZCombTg);
    evTree->Branch("delta_chi2_back_tgeom", &eDeltaChi2BackTg);
    evTree->Branch("vn_dt_comb_trim", &eDtCombTrim);
    evTree->Branch("vn_z_comb_trim", &eZCombTrim);
    evTree->Branch("delta_chi2_back_trim", &eDeltaChi2BackTrim);
    evTree->Branch("vn_dt_comb_raw40", &eDtCombRaw40);
    evTree->Branch("vn_z_comb_raw40", &eZCombRaw40);
    evTree->Branch("delta_chi2_back_raw40", &eDeltaChi2BackRaw40);
    evTree->Branch("timing_beta", &eBeta);
    evTree->Branch("down_st", eDownSt, "down_st[8]/I");
    evTree->Branch("down_t_cal", eDownTCal, "down_t_cal[8]/F");
    evTree->Branch("down_t_sig", eDownTSig, "down_t_sig[8]/F");
    evTree->Branch("down_t_unsmear", eDownTUnsmear, "down_t_unsmear[8]/F");
    evTree->Branch("down_q_raw", eDownQRaw, "down_q_raw[8]/F");
    evTree->Branch("g4_nhits", eG4NHits, "g4_nhits[2]/I");
    evTree->Branch("g4_dom_cat", eG4DomCat, "g4_dom_cat[2]/I");
    evTree->Branch("g4_dom_pdg", eG4DomPdg, "g4_dom_pdg[2]/I");
    evTree->Branch("g4_dom_mom", eG4DomMom, "g4_dom_mom[2]/I");
    evTree->Branch("g4_sum_e_mev", eG4SumE, "g4_sum_e_mev[2]/F");
    evTree->Branch("g4_dedx", eG4Dedx, "g4_dedx[2]/F");
    evTree->Branch("g4_t_ew", eG4TEw, "g4_t_ew[2]/F");
    evTree->Branch("g4_t_first", eG4TFirst, "g4_t_first[2]/F");
    evTree->Branch("g4_t_spread", eG4TSpread, "g4_t_spread[2]/F");
    evTree->Branch("g4_dom_ke_mev", eG4Ke, "g4_dom_ke_mev[2]/F");
    evTree->Branch("g4_dom_cos_back", eG4CosBack, "g4_dom_cos_back[2]/F");
    evTree->Branch("g4_dom_prod_z", eG4ProdZ, "g4_dom_prod_z[2]/F");
    evTree->Branch("g4_frac_p", eG4FracP, "g4_frac_p[2]/F");
    evTree->Branch("g4_frac_pi", eG4FracPi, "g4_frac_pi[2]/F");
    evTree->Branch("g4_frac_el", eG4FracEl, "g4_frac_el[2]/F");
    evTree->Branch("g4_frac_rec", eG4FracRec, "g4_frac_rec[2]/F");

    std::map<int, std::array<uint64_t, 9>> runCounters;

    for (const auto& pf : physFiles) {
        std::string rstr, tag;
        int subStart = 0;
        const bool parsed = parsePhysSubrange(pf, rstr, tag, subStart);
        std::unordered_map<int, std::string>* hmapPtr = nullptr;
        if (parsed) {
            auto key = std::make_pair(rstr, tag);
            if (!hitsIndexCache.count(key)) hitsIndexCache[key] = indexHitsFilesForRun(rstr, tag);
            hmapPtr = &hitsIndexCache[key];
        }

        std::unique_ptr<TFile> fPhys(TFile::Open(pf.c_str(), "READ"));
        if (!fPhys || fPhys->IsZombie()) continue;
        TTree* nt = fPhys->Get<TTree>("nt");
        if (!nt) continue;
        PhysReader rd;
        rd.attach(nt);

        int curSub = -1;
        std::unique_ptr<TFile> fHit;
        TTree* colTree = nullptr;
        ScintHitCollection_p1a* vnHits = nullptr;
        McEventCollection_p6* mcEvt = nullptr;

        const Long64_t nEnt = nt->GetEntries();
        for (Long64_t i = 0; i < nEnt; ++i) {
            nt->GetEntry(i);
            auto& rc = runCounters[rd.run];
            ++rc[0]; // nGen

            const bool isCaloNuRun = (200137 <= rd.run && rd.run <= 200147) || (200172 <= rd.run && rd.run <= 200183);
            const size_t nTr = rd.truth_pdg ? rd.truth_pdg->size() : 0;
            const int nuPdg = (nTr > 0) ? (*rd.truth_pdg)[0] : 0;
            const float tx = (rd.truth_dec_x && !rd.truth_dec_x->empty()) ? (*rd.truth_dec_x)[0] : kNaN;
            const float ty = (rd.truth_dec_y && !rd.truth_dec_y->empty()) ? (*rd.truth_dec_y)[0] : kNaN;
            const float tz = (rd.truth_dec_z && !rd.truth_dec_z->empty()) ? (*rd.truth_dec_z)[0] : kNaN;
            const float tpz = (rd.truth_pz && !rd.truth_pz->empty()) ? ((*rd.truth_pz)[0] * 1e-3f) : 0.0f;
            const float tPnu = (rd.truth_P && !rd.truth_P->empty()) ? ((*rd.truth_P)[0] * 1e-3f) : 0.0f;
            const float tr = std::hypot(tx, ty);

            if (isCaloNuRun && isInCaloNuPmt(tz)) continue;
            ++rc[1]; // nNoCaloNu

            bool isCC = false;
            int muIdx = -1;
            int muPdg = 0;
            if (rd.truth_pdg) {
                for (size_t k = 0; k < rd.truth_pdg->size(); ++k) {
                    const int ap = std::abs((*rd.truth_pdg)[k]);
                    if (ap == 11 || ap == 13 || ap == 15) isCC = true;
                    if (ap == 13 && k > 0 && muIdx < 0) { muIdx = static_cast<int>(k); muPdg = (*rd.truth_pdg)[k]; }
                }
            }
            if (!isCC) continue;
            ++rc[2]; // nCc

            if (std::abs(nuPdg) != 14) continue;
            ++rc[3]; // nNuMuCc

            const bool inBox = isInFaserNuBox(tx, ty, tz);
            const bool inLead = isInLeadBlock(tx, ty, tz);
            if (!inBox && !inLead) continue;
            ++rc[4]; // nFidVol

            if (!(tr < 100.0f)) continue;
            ++rc[5]; // nFidR

            if (!(tpz > 100.0f)) continue;
            ++rc[6]; // nFidPz

            // Outgoing muon kinematics & fill 6D truth fiducial histograms
            float pzMuGeV = 0.0f, yInel = kNaN;
            if (muIdx >= 0 && rd.truth_pz && rd.truth_P && muIdx < static_cast<int>(rd.truth_P->size())) {
                pzMuGeV = (*rd.truth_pz)[muIdx] * 1e-3f;
                const double pMuMeV = (*rd.truth_P)[muIdx];
                const double eMuGeV = std::sqrt(pMuMeV * pMuMeV + kMuMassMeV * kMuMassMeV) * 1e-3;
                if (tPnu > 0.0f) yInel = static_cast<float>(1.0 - eMuGeV / tPnu);
            }
            const double qMuTruth = (muPdg == 13) ? -1.0 : ((muPdg == -13) ? 1.0 : 0.0);
            hFidEnu.Fill(tPnu);
            hFidPzMu.Fill(pzMuGeV);
            if (std::isfinite(yInel)) hFidY.Fill(yInel);
            hFidZvtx.Fill(tz);
            hFidRvtx.Fill(tr);
            hFidQmu.Fill(qMuTruth);

            // Downstream kinematic SR check
            if (rd.longTracks <= 0 || !rd.tk_pz0 || rd.tk_pz0->empty()) continue;
            const int leadIdx = static_cast<int>(vecMaxIdxPos(*rd.tk_pz0));
            const double leadPzGeV = (*rd.tk_pz0)[leadIdx] * 1e-3;
            const double leadPx = (*rd.tk_px0)[leadIdx];
            const double leadPy = (*rd.tk_py0)[leadIdx];
            const uint32_t leadNLay = (*rd.tk_nLayers)[leadIdx];
            const double leadNdof = (*rd.tk_nDoF)[leadIdx];
            const double leadChi2 = (*rd.tk_Chi2)[leadIdx];
            const double leadRMax = (*rd.tk_rMax)[leadIdx];
            const double leadQ = (*rd.tk_charge)[leadIdx];
            const double leadThetaMrad = std::atan(std::hypot(leadPx, leadPy) / (*rd.tk_pz0)[leadIdx]) * 1000.0;

            double leadYTrig = kNaN;
            const RawInputArray inputs = rd.buildInputs(leadIdx, leadYTrig);
            const double leadRVn = inputs[0].validPos ? std::hypot(inputs[0].xMm, inputs[0].yMm) : kNaN;
            const double leadRIft = inputs[4].validPos ? std::hypot(inputs[4].xMm, inputs[4].yMm) : kNaN;

            TimingBlinding::EventKinematicsAndVeto kinEv;
            kinEv.isMC = true;
            kinEv.distanceToCollidingBCID = 0;
            kinEv.longTracks = rd.longTracks;
            kinEv.veto20Charge = rd.Veto20_charge;
            kinEv.veto21Charge = rd.Veto21_charge;
            kinEv.timingChargeTop = rd.Timing2_charge + rd.Timing3_charge;
            kinEv.timingChargeBottom = rd.Timing0_charge + rd.Timing1_charge;
            kinEv.preshower0Charge = rd.Preshower0_charge;
            kinEv.preshower1Charge = rd.Preshower1_charge;
            kinEv.leadYatTrig = leadYTrig;
            kinEv.leadPz0GeV = leadPzGeV;
            kinEv.leadNLayers = leadNLay;
            kinEv.leadNDoF = leadNdof;
            kinEv.leadChi2NDF = (leadNdof > 0.0) ? (leadChi2 / leadNdof) : 999.0;
            kinEv.leadRMax = leadRMax;
            kinEv.leadRIFT = leadRIft;
            kinEv.leadRVetoNu = leadRVn;
            kinEv.leadThetaMrad = leadThetaMrad;

            if (!TimingBlinding::isKinematicSignalRegion(kinEv)) continue;
            ++rc[7]; // nKinSr

            // Calibrate timing with smeared MC TimingCalibrator
            const auto evt = calib->calibrateMCEvent(rd.run, static_cast<int64_t>(rd.eventID), inputs, true, true);
            const auto downAll = TimingCalibrator::fitDownstreamReferenceMode(evt, DownstreamMode::AllValid, leadYTrig, &inputs);
            const auto downTg = TimingCalibrator::fitDownstreamReferenceMode(evt, DownstreamMode::TimingGeom, leadYTrig, &inputs);
            const auto downTr = TimingCalibrator::fitDownstreamReferenceMode(evt, DownstreamMode::Trimmed3Sigma, leadYTrig, &inputs);
            const auto spd = TimingCalibrator::fitSpeedAndArrival(evt);

            const float qCheck0 = (rd.hasReduced && rd.VetoNu0_reduced_charge >= 0.0f) ? rd.VetoNu0_reduced_charge : rd.qRaw[0];
            const float qCheck1 = (rd.hasReduced && rd.VetoNu1_reduced_charge >= 0.0f) ? rd.VetoNu1_reduced_charge : rd.qRaw[1];
            const auto back = TimingCalibrator::evaluateBackwardHypothesis(evt, downAll, (qCheck0 >= 30.0f), (qCheck1 >= 30.0f));
            const auto backTg = TimingCalibrator::evaluateBackwardHypothesis(evt, downTg, (qCheck0 >= 30.0f), (qCheck1 >= 30.0f));
            const auto backTrim = TimingCalibrator::evaluateBackwardHypothesis(evt, downTr, (qCheck0 >= 30.0f), (qCheck1 >= 30.0f));
            const auto backRaw40 = TimingCalibrator::evaluateBackwardHypothesis(evt, downAll, (rd.qRaw[0] >= 40.0f), (rd.qRaw[1] >= 40.0f));

            // Lookup matched Geant4 HITS entry ONLY on kinematic-SR events!
            VetoNuTruthDissection dis;
            bool vtxMatched = false;
            if (hmapPtr) {
                const int sub = (rd.eventID >= 0) ? (rd.eventID / 1000) : (subStart + static_cast<int>(i / 1000LL));
                const Long64_t hEntry = (rd.eventID >= 0) ? (rd.eventID % 1000) : (i % 1000LL);
                auto itH = hmapPtr->find(sub);
                if (itH != hmapPtr->end()) {
                    if (sub != curSub) {
                        fHit.reset(TFile::Open(itH->second.c_str(), "READ"));
                        colTree = (fHit && !fHit->IsZombie()) ? fHit->Get<TTree>("CollectionTree") : nullptr;
                        if (colTree) {
                            colTree->SetBranchStatus("*", 0);
                            colTree->SetBranchStatus("*VetoNuHits*", 1);
                            colTree->SetBranchStatus("*TruthEvent*", 1);
                            colTree->SetBranchAddress("ScintHitCollection_p1a_VetoNuHits", &vnHits);
                            colTree->SetBranchAddress("McEventCollection_p6_TruthEvent", &mcEvt);
                        }
                        curSub = sub;
                    }
                    if (colTree && hEntry < colTree->GetEntries()) {
                        colTree->GetEntry(hEntry);
                        dis = dissectVetoNuTruth(vnHits, mcEvt);
                        if (dis.hasPrimVtx) {
                            const double dv = std::hypot(dis.primX - tx, std::hypot(dis.primY - ty, dis.primZ - tz));
                            vtxMatched = (dv < 0.5);
                        }
                    }
                }
            }
            if (vtxMatched) ++rc[8]; // nHitsMatched

            eRun = rd.run;
            eEventID = rd.eventID;
            eHitMcEvtNbr = dis.mcEventNbr;
            eHitsVtxMatch = vtxMatched;
            eNuPdg = nuPdg;
            eMuPdg = muPdg;
            eEnuGeV = tPnu;
            ePzMuGeV = pzMuGeV;
            eYInel = yInel;
            eTruthX = tx; eTruthY = ty; eTruthZ = tz; eTruthR = tr;
            eLeadPzGeV = static_cast<float>(leadPzGeV);
            eLeadQ = static_cast<float>(leadQ);
            eLeadTheta = static_cast<float>(leadThetaMrad);
            eLeadRVn = static_cast<float>(leadRVn);
            eLeadRMax = static_cast<float>(leadRMax);
            eLeadRIft = static_cast<float>(leadRIft);
            eLeadYTrig = static_cast<float>(leadYTrig);
            eCaloEM = rd.hasCalo ? rd.Calo_total_E_EM : -1.0f;
            eNClus0 = rd.nClusters0;
            ePS0Q = rd.Preshower0_charge;
            ePS1Q = rd.Preshower1_charge;

            for (int pl = 0; pl < 2; ++pl) {
                eVnQRaw[pl] = rd.qRaw[pl];
                eVnQRed[pl] = rd.hasReduced ? rd.VetoNu0_reduced_charge * (pl == 0) + rd.VetoNu1_reduced_charge * (pl == 1) : -1.0f;
                eVnWidth[pl] = rd.w[pl];
                eVnSt[pl] = rd.st[pl];
                eVnValid[pl] = evt.channels[pl].valid;
                eVnDt[pl] = (downAll.valid && evt.channels[pl].valid) ? static_cast<float>(evt.channels[pl].tCalNs - downAll.t0Ns) : static_cast<float>(kNaN);
                eVnDtTg[pl] = (downTg.valid && evt.channels[pl].valid) ? static_cast<float>(evt.channels[pl].tCalNs - downTg.t0Ns) : static_cast<float>(kNaN);
                eVnDtTrim[pl] = (downTr.valid && evt.channels[pl].valid) ? static_cast<float>(evt.channels[pl].tCalNs - downTr.t0Ns) : static_cast<float>(kNaN);
                eVnSigma[pl] = evt.channels[pl].valid ? static_cast<float>(evt.channels[pl].sigmaCalNs) : static_cast<float>(kNaN);
                const double combSig = (downAll.valid && evt.channels[pl].valid) ? std::hypot(evt.channels[pl].sigmaCalNs, downAll.sigmaT0Ns) : kNaN;
                eVnPull[pl] = (std::isfinite(eVnDt[pl]) && combSig > 0.0) ? static_cast<float>(eVnDt[pl] / combSig) : static_cast<float>(kNaN);
                eVnT0Mc[pl] = evt.channels[pl].valid ? static_cast<float>(evt.channels[pl].t2Ns) : static_cast<float>(kNaN);

                const auto& g4 = dis.plate[pl];
                eG4NHits[pl] = g4.nHits;
                eG4DomCat[pl] = g4.domSrcCat;
                eG4DomPdg[pl] = g4.domPdg;
                eG4DomMom[pl] = g4.domMotherPdg;
                eG4SumE[pl] = static_cast<float>(g4.sumEMeV);
                eG4Dedx[pl] = static_cast<float>(g4.dEdxMeVPerMm);
                eG4TEw[pl] = static_cast<float>(g4.tEwNs);
                eG4TFirst[pl] = static_cast<float>(g4.tFirstNs);
                eG4TSpread[pl] = static_cast<float>(g4.tSpreadNs);
                eG4Ke[pl] = static_cast<float>(g4.domKeMeV);
                eG4CosBack[pl] = static_cast<float>(g4.domCosBack);
                eG4ProdZ[pl] = static_cast<float>(g4.domProdZMm);
                eG4FracP[pl] = static_cast<float>(g4.fracProtonE);
                eG4FracPi[pl] = static_cast<float>(g4.fracPionE);
                eG4FracEl[pl] = static_cast<float>(g4.fracElecE);
                eG4FracRec[pl] = static_cast<float>(g4.fracRecoilUnmatchedE);
            }

            eAnchorCh = evt.anchorChannel;
            eNDown = downAll.nUsed;
            eNdofDown = downAll.ndof;
            eT0Down = downAll.valid ? static_cast<float>(downAll.t0Ns) : static_cast<float>(kNaN);
            eSigT0Down = downAll.valid ? static_cast<float>(downAll.sigmaT0Ns) : static_cast<float>(kNaN);
            eChi2Down = downAll.valid ? static_cast<float>(downAll.chi2) : static_cast<float>(kNaN);

            eNDownTrigGeom = downTg.nUsed;
            eNdofDownTrigGeom = downTg.ndof;
            eT0DownTrigGeom = downTg.valid ? static_cast<float>(downTg.t0Ns) : static_cast<float>(kNaN);
            eChi2DownTrigGeom = downTg.valid ? static_cast<float>(downTg.chi2) : static_cast<float>(kNaN);

            eNDownTrim = downTr.nUsed;
            eNdofDownTrim = downTr.ndof;
            eT0DownTrim = downTr.valid ? static_cast<float>(downTr.t0Ns) : static_cast<float>(kNaN);
            eChi2DownTrim = downTr.valid ? static_cast<float>(downTr.chi2) : static_cast<float>(kNaN);

            eDtComb = back.valid ? static_cast<float>(back.dtCombNs) : static_cast<float>(kNaN);
            eZComb = back.valid ? static_cast<float>(back.zComb) : static_cast<float>(kNaN);
            eDt10 = static_cast<float>(back.dt10Ns);
            eDeltaChi2Back = back.valid ? static_cast<float>(back.deltaChi2Back) : static_cast<float>(kNaN);

            eDtCombTg = backTg.valid ? static_cast<float>(backTg.dtCombNs) : static_cast<float>(kNaN);
            eZCombTg = backTg.valid ? static_cast<float>(backTg.zComb) : static_cast<float>(kNaN);
            eDeltaChi2BackTg = backTg.valid ? static_cast<float>(backTg.deltaChi2Back) : static_cast<float>(kNaN);

            eDtCombTrim = backTrim.valid ? static_cast<float>(backTrim.dtCombNs) : static_cast<float>(kNaN);
            eZCombTrim = backTrim.valid ? static_cast<float>(backTrim.zComb) : static_cast<float>(kNaN);
            eDeltaChi2BackTrim = backTrim.valid ? static_cast<float>(backTrim.deltaChi2Back) : static_cast<float>(kNaN);

            eDtCombRaw40 = backRaw40.valid ? static_cast<float>(backRaw40.dtCombNs) : static_cast<float>(kNaN);
            eZCombRaw40 = backRaw40.valid ? static_cast<float>(backRaw40.zComb) : static_cast<float>(kNaN);
            eDeltaChi2BackRaw40 = backRaw40.valid ? static_cast<float>(backRaw40.deltaChi2Back) : static_cast<float>(kNaN);

            eBeta = spd.valid ? static_cast<float>(spd.beta) : static_cast<float>(kNaN);

            for (int c = 2; c < 10; ++c) {
                const int dIdx = c - 2;
                int rawSt = -1;
                if (c < 6) rawSt = rd.st[c];
                else if (c == 6) rawSt = (rd.st[6] | rd.st[7]);
                else if (c == 7) rawSt = (rd.st[8] | rd.st[9]);
                else rawSt = rd.st[c + 2];
                eDownSt[dIdx] = rawSt;
                eDownQRaw[dIdx] = static_cast<float>(inputs[c].rawCharge);
                eDownTCal[dIdx] = evt.channels[c].valid ? static_cast<float>(evt.channels[c].tCalNs) : static_cast<float>(kNaN);
                eDownTSig[dIdx] = evt.channels[c].valid ? static_cast<float>(evt.channels[c].sigmaCalNs) : static_cast<float>(kNaN);
                eDownTUnsmear[dIdx] = evt.channels[c].valid ? static_cast<float>(evt.channels[c].t2Ns) : static_cast<float>(kNaN);
            }
            evTree->Fill();
        }
    }

    for (const auto& [r, rc] : runCounters) {
        sRun = r;
        nGen = rc[0]; nNoCaloNu = rc[1]; nCc = rc[2]; nNuMuCc = rc[3];
        nFidVol = rc[4]; nFidR = rc[5]; nFidPz = rc[6]; nKinSr = rc[7]; nHitsMatched = rc[8];
        sumTree->Fill();
    }

    const Long64_t nEventsSrOut = evTree->GetEntries();
    outFile->cd();
    sumTree->Write();
    evTree->Write();
    hFidEnu.Write();
    hFidPzMu.Write();
    hFidY.Write();
    hFidZvtx.Write();
    hFidRvtx.Write();
    hFidQmu.Write();
    outFile->Close();

    const double wallS = std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStart).count();
    std::cout << "[t3-extract] files=" << physFiles.size() << " events_sr=" << nEventsSrOut
              << " wall_s=" << wallS << " out=" << outputPath << "\n";
    return 0;
}
