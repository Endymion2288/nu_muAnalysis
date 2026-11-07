// Read-only G4 ancestry and actual EmulsionStationA envelope crossing observer.
// It changes neither the random streams, track information, nor transport.
#include "G4AtlasTools/UserActionToolBase.h"
#include "G4UserTrackingAction.hh"
#include "G4UserSteppingAction.hh"
#include "G4UserEventAction.hh"
#include "G4Event.hh"
#include "G4Step.hh"
#include "G4LogicalVolume.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VSensitiveDetector.hh"
#include "StoreGate/StoreGateSvc.h"
#include "FaserCaloSimEvent/CaloHitCollection.h"
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <string>
#include <unordered_map>

namespace NuMu {
struct Origin { int root=0; int pdg=0; bool escaped=false; bool startedInside=false; };
struct Deposit { std::array<double,3> all{}, prompt{}; std::array<unsigned long,3> steps{}; };

class Observer final : public G4UserTrackingAction, public G4UserSteppingAction,
                       public G4UserEventAction {
    std::unordered_map<const G4Track*,Origin> born;
    std::unordered_map<int,Origin> ancestry;
    std::map<std::string,Deposit> deposits;
    std::set<std::string> envelopes;
    unsigned long tracks=0, unknown=0, steps=0, crossings=0, missingBirth=0;
    unsigned long primaryMu=0, outsidePrimary=0;
    std::array<double,4> flowKE{}, flowTotal{};
    std::string output;
    StoreGateSvc* store;
    const CaloHitCollection* calo=nullptr;
    size_t caloRead=0;
    double caloRaw=0;

    static bool inside(const G4StepPoint* point) {
        if (!point || !point->GetPhysicalVolume()) return false;
        const auto& touch=point->GetTouchableHandle();
        for (int i=0;i<=touch->GetHistoryDepth();++i) {
            const auto& n=touch->GetVolume(i)->GetLogicalVolume()->GetName();
            if (n=="EmulsionStationA" || n=="Emulsion::EmulsionStationA") return true;
        }
        return false;
    }
    static int category(const Origin& o) { return o.root==0 ? 2 : std::abs(o.pdg)==13 ? 0 : 1; }
public:
    Observer(std::string path,StoreGateSvc* sg):output(std::move(path)),store(sg) {}
    void BeginOfEventAction(const G4Event*) override {
        born.clear(); ancestry.clear(); deposits.clear(); envelopes.clear();
        tracks=unknown=steps=crossings=missingBirth=primaryMu=outsidePrimary=0;
        flowKE.fill(0);flowTotal.fill(0);
        calo=nullptr;caloRead=0;caloRaw=0;
    }
    void PreUserTrackingAction(const G4Track* track) override {
        ++tracks;
        Origin o;
        if (track->GetParentID()==0) {
            o.root=track->GetTrackID();o.pdg=track->GetDefinition()->GetPDGEncoding();
            if (std::abs(o.pdg)==13) ++primaryMu;
        } else {
            auto it=born.find(track);
            if (it!=born.end()) {o=it->second;born.erase(it);}
            else { ++missingBirth; }
        }
        if (o.root==0) ++unknown;
        ancestry[track->GetTrackID()]=o;
    }
    void UserSteppingAction(const G4Step* step) override {
        ++steps;
        const auto* track=step->GetTrack();auto& o=ancestry.at(track->GetTrackID());
        const auto* pre=step->GetPreStepPoint();const auto* post=step->GetPostStepPoint();
        const bool a=inside(pre),b=inside(post);
        if (track->GetCurrentStepNumber()==1 && track->GetParentID()==0) {
            o.startedInside=a;
            if (!a) {o.escaped=true;++outsidePrimary;}
        }
        if (pre->GetPhysicalVolume()) {
            const auto& touch=pre->GetTouchableHandle();
            for(int i=0;i<=touch->GetHistoryDepth();++i) {
                std::string n=touch->GetVolume(i)->GetLogicalVolume()->GetName();
                if (n.find("EmulsionStation")!=std::string::npos) envelopes.insert(n);
            }
        }
        const int c=category(o);
        if (a && !b && !o.escaped) {
            ++crossings;
            // Never count subsequent returns, nor daughters born after a counted exit.
            // Neutrinos have a separate invisible category; these are transport KE/total,
            // not transfer H, energy closure, or a truth-neutrino-energy feature.
            const int pdg=std::abs(track->GetDefinition()->GetPDGEncoding());
            const int k=c==2 ? 3 : (pdg==12||pdg==14||pdg==16) ? 2 : c==0 ? 0 : 1;
            flowKE[k]+=post->GetKineticEnergy();flowTotal[k]+=post->GetTotalEnergy();
            o.escaped=true;
        }
        const double e=step->GetTotalEnergyDeposit();
        if (e>0 && pre->GetPhysicalVolume()) {
            auto* sd=pre->GetPhysicalVolume()->GetLogicalVolume()->GetSensitiveDetector();
            if (sd) {
                double response=e;
                if (sd->GetName().find("Ecal")!=std::string::npos) {
                    // SD::ProcessHits already ran for this step. Read the actual
                    // official Birks/nonuniformity-corrected transient hit, rather
                    // than reproducing its physics correction in the observer.
                    if (!calo && store->retrieve(calo,"EcalHits").isFailure())
                        throw std::runtime_error("Missing live EcalHits");
                    if (calo->size()!=caloRead+1)
                        throw std::runtime_error("Ecal step/hit cardinality mismatch");
                    response=(*calo)[caloRead].energyLoss();++caloRead;caloRaw+=e;
                }
                auto& d=deposits[sd->GetName()];d.all[c]+=response;++d.steps[c];
                const double t=pre->GetGlobalTime();
                if (t>=0 && t<1000) d.prompt[c]+=response;
            }
        }
        // Capture ancestry at birth, before a parent might escape at a later step.
        // G4 secondaries do not yet have their final track IDs here.
        for (const auto* child:*step->GetSecondaryInCurrentStep()) born[child]=o;
    }
    void EndOfEventAction(const G4Event* event) override {
        std::ofstream f(output,std::ios::app);f<<std::setprecision(17);
        f<<"{\"event\":"<<event->GetEventID()<<",\"tracks\":"<<tracks
         <<",\"unknown_tracks\":"<<unknown<<",\"missing_birth\":"<<missingBirth
         <<",\"steps\":"<<steps<<",\"primary_muons\":"<<primaryMu
         <<",\"outside_primaries\":"<<outsidePrimary<<",\"crossings\":"<<crossings;
        f<<",\"calo_uncorrected_deposit_MeV\":"<<caloRaw<<",\"calo_live_hits\":"<<caloRead;
        auto array=[&](const auto& a){f<<'[';for(size_t i=0;i<a.size();++i){if(i)f<<',';f<<a[i];}f<<']';};
        f<<",\"flow_KE_MeV\":";array(flowKE);f<<",\"flow_total_MeV\":";array(flowTotal);
        f<<",\"envelopes\":[";bool first=true;
        for (const auto& n:envelopes) {if(!first)f<<',';first=false;f<<'"'<<n<<'"';}
        f<<"],\"deposits\":{";first=true;
        for (const auto& [name,d]:deposits) {
            if (!first)f<<',';
            first=false;
            f<<'"'<<name<<"\":{\"all_MeV\":";array(d.all);
            f<<",\"prompt_MeV\":";array(d.prompt);f<<",\"steps\":";array(d.steps);f<<'}';
        }
        f<<"}}\n";
    }
};
class ObserverTool final : public G4UA::UserActionToolBase<Observer> {
    Gaudi::Property<std::string> output{this,"Output","lineage.jsonl"};
public:
    ObserverTool(const std::string& t,const std::string& n,const IInterface* p)
        :UserActionToolBase<Observer>(t,n,p) {}
    StatusCode initialize() override { return evtStore().retrieve(); }
    std::unique_ptr<Observer> makeAndFillAction(G4UA::G4AtlasUserActions& lists) override {
        auto action=std::make_unique<Observer>(output.value(),evtStore().get());
        lists.trackingActions.push_back(action.get());lists.steppingActions.push_back(action.get());
        lists.eventActions.push_back(action.get());return action;
    }
};
}
DECLARE_COMPONENT(NuMu::ObserverTool)
