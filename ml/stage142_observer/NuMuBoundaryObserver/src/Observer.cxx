// Read-only G4 ancestry and actual EmulsionStationA envelope crossing observer.
// It changes neither the random streams, track information, nor transport.
#include "G4AtlasTools/UserActionToolBase.h"
#include "G4UserTrackingAction.hh"
#include "G4UserSteppingAction.hh"
#include "G4UserEventAction.hh"
#include "G4Event.hh"
#include "G4PrimaryVertex.hh"
#include "G4Box.hh"
#include "G4TransportationManager.hh"
#include "G4Navigator.hh"
#include "G4TouchableHistory.hh"
#include <algorithm>
#include <tuple>
#include <vector>
#include "G4Step.hh"
#include "G4LogicalVolume.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VSensitiveDetector.hh"
#include "StoreGate/StoreGateSvc.h"
#include "FaserCaloSimEvent/CaloHitCollection.h"
#include "ScintSimEvent/ScintHitCollection.h"
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <string>
#include <unordered_map>

namespace NuMu142 {
struct Origin { int root=0; int pdg=0; bool escaped=false; bool startedInside=false; };
struct Deposit { std::array<double,3> all{}, prompt{}; std::array<unsigned long,3> steps{}; };

class Observer final : public G4UserTrackingAction, public G4UserSteppingAction,
                       public G4UserEventAction {
    std::unordered_map<const G4Track*,Origin> born;
    std::unordered_map<int,Origin> ancestry;
    std::map<std::string,Deposit> deposits;
    std::map<std::string,size_t> daqRead;
    std::map<std::string,std::vector<std::array<double,14>>> daqHits;
    std::set<std::string> envelopes;
    unsigned long tracks=0, unknown=0, steps=0, crossings=0, missingBirth=0;
    unsigned long primaryMu=0, outsidePrimary=0;
    std::array<double,4> flowKE{}, flowTotal{};
    struct SensorBox {
        G4ThreeVector center,half;
        G4RotationMatrix rotation;
        int kind;
    };
    struct Bin { unsigned long count=0; double ke=0,total=0,x=0,y=0,z=0,ux=0,uy=0,uz=0,time=0; };
    std::vector<SensorBox> sensors;
    std::map<std::tuple<int,int,int,int>,Bin> boundary;
    std::vector<std::array<double,13>> qa;
    double eventT0=0;
    unsigned long nonBoxEnvelope=0;
    std::string output;
    StoreGateSvc* store;
    const CaloHitCollection* calo=nullptr;
    size_t caloRead=0;
    double caloRaw=0;

    void scanGeometry(G4VPhysicalVolume* volume,const G4RotationMatrix& parentRotation,
                      const G4ThreeVector& parentPosition) {
        const auto rotation=parentRotation*volume->GetObjectRotationValue();
        const auto position=parentPosition+parentRotation*volume->GetObjectTranslation();
        auto* logical=volume->GetLogicalVolume();
        auto* sd=logical->GetSensitiveDetector();
        if (sd) {
            const std::string name=sd->GetName();
            const int kind=name.find("Ecal")!=std::string::npos ? 2 :
                (name.find("Veto")!=std::string::npos && name.find("VetoNu")==std::string::npos) ? 1 : 0;
            if (kind) {
                const auto* box=dynamic_cast<const G4Box*>(logical->GetSolid());
                if (!box) throw std::runtime_error("Expected actual downstream sensitive G4Box");
                sensors.push_back({position,{box->GetXHalfLength(),box->GetYHalfLength(),box->GetZHalfLength()},rotation,kind});
            }
        }
        for (int j=0;j<logical->GetNoDaughters();++j)
            scanGeometry(logical->GetDaughter(j),rotation,position);
    }
    int rayAcceptance(const G4ThreeVector& position,const G4ThreeVector& direction) const {
        int flags=0;
        for (const auto& sensor:sensors) {
            if (sensor.center.z()<=position.z() || direction.z()<=0) continue;
            const auto inverse=sensor.rotation.inverse();
            const auto point=inverse*(position-sensor.center),unit=inverse*direction;
            double lo=0,hi=1e30;
            for (int j=0;j<3;++j) {
                if (std::abs(unit[j])<1e-14) {
                    if (std::abs(point[j])>sensor.half[j]) hi=-1;
                } else {
                    double a=(-sensor.half[j]-point[j])/unit[j],b=(sensor.half[j]-point[j])/unit[j];
                    if (a>b) std::swap(a,b);
                    lo=std::max(lo,a);hi=std::min(hi,b);
                }
            }
            if (hi>=lo) flags |= sensor.kind;
        }
        return flags;
    }
    void recordExit(const G4Step* step) {
        const auto* pre=step->GetPreStepPoint();const auto* post=step->GetPostStepPoint();
        const auto& touch=pre->GetTouchableHandle();int level=-1;
        for (int j=0;j<=touch->GetHistoryDepth();++j) {
            const std::string name=touch->GetVolume(j)->GetLogicalVolume()->GetName();
            if (name=="EmulsionStationA" || name=="Emulsion::EmulsionStationA") {level=j;break;}
        }
        if (level<0) throw std::runtime_error("Missing exiting envelope");
        const auto* history=dynamic_cast<const G4TouchableHistory*>(pre->GetTouchable());
        const auto transform=history->GetHistory()->GetTransform(touch->GetHistoryDepth()-level);
        const auto* solid=dynamic_cast<const G4Box*>(touch->GetVolume(level)->GetLogicalVolume()->GetSolid());
        if (!solid) {++nonBoxEnvelope;throw std::runtime_error("Envelope is not frozen box geometry");}
        const auto local=transform.TransformPoint(post->GetPosition());
        const auto normal=transform.Inverse().TransformAxis(solid->SurfaceNormal(local));
        const int face=normal.z()>.5 ? 0 : normal.z()<-.5 ? 1 : 2;
        const auto* particle=step->GetTrack()->GetDefinition();
        const int pdg=std::abs(particle->GetPDGEncoding());
        const bool charged=particle->GetPDGCharge()!=0;
        const auto type=particle->GetParticleType();
        const bool hadron=type=="baryon" || type=="meson" || type=="nucleus";
        const int kind=pdg==11||pdg==22 ? 0 : hadron ? (charged ? 1 : 2) : charged ? 3 : 4;
        const auto position=post->GetPosition(),direction=post->GetMomentumDirection();
        const double time=post->GetGlobalTime()-eventT0;
        const int timebin=time<0 ? 0 : time<1 ? 1 : time<10 ? 2 : time<100 ? 3 : time<1000 ? 4 : 5;
        const int acceptance=rayAcceptance(position,direction);
        auto& bin=boundary[{face,kind,acceptance,timebin}];const double ke=post->GetKineticEnergy();
        ++bin.count;bin.ke+=ke;bin.total+=post->GetTotalEnergy();
        bin.x+=ke*position.x();bin.y+=ke*position.y();bin.z+=ke*position.z();
        bin.ux+=ke*direction.x();bin.uy+=ke*direction.y();bin.uz+=ke*direction.z();bin.time+=ke*time;
        if (qa.size()<64) qa.push_back({double(particle->GetPDGEncoding()),double(face),double(kind),double(acceptance),
            position.x(),position.y(),position.z(),direction.x(),direction.y(),direction.z(),time,ke,post->GetTotalEnergy()});
    }
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
    void BeginOfEventAction(const G4Event* event) override {
        if (sensors.empty()) scanGeometry(G4TransportationManager::GetTransportationManager()->GetNavigatorForTracking()->GetWorldVolume(),G4RotationMatrix(),G4ThreeVector());
        boundary.clear();qa.clear();nonBoxEnvelope=0;
        if (!event->GetPrimaryVertex()) throw std::runtime_error("Missing event t0");
        eventT0=event->GetPrimaryVertex()->GetT0();
        for (int j=1;j<event->GetNumberOfPrimaryVertex();++j) eventT0=std::min(eventT0,event->GetPrimaryVertex(j)->GetT0());
        born.clear(); ancestry.clear(); deposits.clear(); envelopes.clear();
        daqRead.clear();daqHits.clear();
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
            if (k==1) recordExit(step);
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
                // Sensitive ProcessHits already ran: label the ACTUAL new
                // hit, never infer ancestry from persisted barcode conventions.
                std::string collection;
                const std::string detector=sd->GetName();
                if(detector.find("VetoNu")!=std::string::npos)collection="VetoNuHits";
                else if(detector.find("Veto")!=std::string::npos)collection="VetoHits";
                else if(detector.find("Trigger")!=std::string::npos)collection="TriggerHits";
                else if(detector.find("Preshower")!=std::string::npos)collection="PreshowerHits";
                if(!collection.empty()) {
                    const ScintHitCollection* hits=nullptr;
                    if(store->retrieve(hits,collection).isFailure() || hits->size()!=daqRead[collection]+1)
                        throw std::runtime_error("Scint step/hit cardinality mismatch: "+collection);
                    const auto& h=(*hits)[daqRead[collection]++];
                    daqHits[collection].push_back({double(c),double(o.root),double(o.pdg),double(track->GetTrackID()),
                        double(h.identify()),h.energyLoss(),h.meanTime(),double(h.trackNumber()),
                        h.localStartPosition().x(),h.localStartPosition().y(),h.localStartPosition().z(),
                        h.localEndPosition().x(),h.localEndPosition().y(),h.localEndPosition().z()});
                } else if(detector.find("Ecal")!=std::string::npos) {
                    const auto& h=(*calo)[caloRead-1];
                    daqHits["EcalHits"].push_back({double(c),double(o.root),double(o.pdg),double(track->GetTrackID()),
                        double(h.identify()),h.energyLoss(),h.meanTime(),double(h.trackNumber()),
                        h.localStartPosition().x(),h.localStartPosition().y(),h.localStartPosition().z(),
                        h.localEndPosition().x(),h.localEndPosition().y(),h.localEndPosition().z()});
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
        f<<"},\"event_t0_ns\":"<<eventT0<<",\"geometry_sensor_boxes\":"<<sensors.size()
         <<",\"nonbox_envelope\":"<<nonBoxEnvelope<<",\"boundary_bins\":[";first=true;
        for (const auto& [key,bin]:boundary) {
            if (!first) f<<',';first=false;
            f<<'['<<std::get<0>(key)<<','<<std::get<1>(key)<<','<<std::get<2>(key)<<','<<std::get<3>(key)
             <<','<<bin.count<<','<<bin.ke<<','<<bin.total<<','<<bin.x<<','<<bin.y<<','<<bin.z
             <<','<<bin.ux<<','<<bin.uy<<','<<bin.uz<<','<<bin.time<<']';
        }
        f<<"],\"crossing_qa\":[";first=true;
        for (const auto& q:qa) {if (!first) f<<',';first=false;array(q);}
        f<<"],\"daq_hits\":{";first=true;
        for(const auto& [name,rows]:daqHits) {
            if(!first)f<<',';first=false;
            f<<'"'<<name<<"\":[";bool firstrow=true;
            for(const auto& row:rows){if(!firstrow)f<<',';firstrow=false;array(row);}
            f<<']';
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
DECLARE_COMPONENT(NuMu142::ObserverTool)
