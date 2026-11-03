// Read the persisted collections using their production identifier/converter semantics.
#include "IdDictParser/IdDictParser.h"
#include "TrackerIdentifier/FaserSCT_ID.h"
#include "TrackerEventAthenaPool/FaserSCT_RawDataContainer_p4.h"
#include "TrackerEventTPCnv/TrackerPrepRawData/TrackerPRD_Collection_p2.h"
#include "TrkEventTopLevelCnv/TrackCollection_tlp6.h"
#include "TTree.h"
#include "TClass.h"
#include "TBranchElement.h"
#include "TVirtualCollectionProxy.h"
#include <array>
#include <set>
#include <unordered_map>

FaserSCT_ID* ReadoutID(const std::string& base) {
    IdDictParser parser;
    for (auto item : std::vector<std::pair<std::string,std::string>>{
        {"Tracker","TrackerIdDictFiles/IdDictInterface.xml"},
        {"Neutrino","NeutrinoIdDictFiles/IdDictNeutrino.xml"},
        {"Scintillator","ScintIdDictFiles/IdDictScintillator.xml"},
        {"Calorimeter","CaloIdDictFiles/IdDictCalorimeter.xml"},
        {"FASER","FaserGeoModel/IdDictFASER.xml"}})
        parser.register_external_entity(item.first,base+"/"+item.second);
    auto& dict=parser.parse(base+"/FaserGeoModel/FASER_IDS.xml");
    auto* id=new FaserSCT_ID;
    if (id->initialize_from_dictionary(dict)) throw std::runtime_error("ID initialization");
    return id;
}

// No ordinal or event-number/file-size interpolation: join the actual header IDs.
std::vector<long long> ReadoutFind(TTree* tree, const std::vector<unsigned long long>& events,
                                 unsigned int run) {
    auto* branch=tree->GetBranch("EventInfoAux.");
    auto* klass=TClass::GetClass(branch->GetClassName());
    void* info=nullptr; branch->SetAddress(&info);
    auto ro=klass->GetDataMember("runNumber")->GetOffset();
    auto eo=klass->GetDataMember("eventNumber")->GetOffset();
    std::unordered_map<unsigned long long,size_t> wanted;
    std::vector<long long> found(events.size(),-1);
    for(size_t i=0;i<events.size();++i) wanted.emplace(events[i],i);
    for(long long i=0;i<tree->GetEntries();++i) {
        if(branch->GetEntry(i)<=0 || !info) throw std::runtime_error("header read failed");
        if(*reinterpret_cast<unsigned int*>(static_cast<char*>(info)+ro)!=run)
            throw std::runtime_error("header run mismatch");
        auto event=*reinterpret_cast<unsigned long long*>(static_cast<char*>(info)+eo);
        auto it=wanted.find(event);
        if(it!=wanted.end()) {
            if(found[it->second]!=-1) throw std::runtime_error("duplicate identity");
            found[it->second]=i;
        }
    }
    branch->ResetAddress();
    return found;
}

// Per station: raw unique strips, off-corridor strips, isolated off strips,
// clusters, off-corridor clusters, singleton off clusters, nominal outside channels,
// measured wafers, raw groups, then 8 strip-weighted timebins, 5 cluster sizes,
// off-corridor clusters with no immediately adjacent raw strip outside cluster,
// and clusters / RDO-list entries with invalid decoded strip IDs.
std::vector<std::vector<int>> ReadoutSummary(
    const FaserSCT_RawDataContainer_p4& raw,
    const void* clusterObject,
    const Trk::TrackCollection_tlp6& tracks, const FaserSCT_ID* id) {
    std::array<std::set<int>,192> strips, corridor;
    std::vector<std::vector<int>> out(4,std::vector<int>(25));
    if (!tracks.m_trackerTrackExt) throw std::runtime_error("missing tracker track extension");
    for(const auto& cot:tracks.m_trackerTrackExt->m_sctClustersOT) {
        Identifier hit(cot.m_id);
        auto hash=id->wafer_hash(id->wafer_id(hit)).value();
        if(hash>=192) throw std::runtime_error("track hash");
        int center=id->strip(hit);
        // Fixed inclusive 64-strip neighbourhood around every saved backward-track COT.
        for(int s=std::max(0,center-64);s<=std::min(767,center+64);++s)
            corridor[hash].insert(s);
    }
    for(const auto& coll:raw.m_collections) {
        Identifier wafer(coll.m_id);
        auto hash=id->wafer_hash(wafer).value(); int st=id->station(wafer);
        if(hash!=coll.m_hashId || hash>=192) throw std::runtime_error("RDO wafer/hash");
        for(unsigned i=coll.m_begin;i<coll.m_end;++i) {
            const auto& r=raw.m_sct3data.at(i);
            int first=r.getStrip(),size=r.m_word&0x7ff,bin=(r.m_word>>11)&7;
            if(first<0 || size<1 || first+size>768) throw std::runtime_error("raw strip range");
            ++out[st][8]; out[st][9+bin]+=size;
            for(int s=first;s<first+size;++s) strips[hash].insert(s);
        }
    }
    for(unsigned h=0;h<192;++h) {
        int st=id->station(id->wafer_id(IdentifierHash(h)));
        out[st][0]+=strips[h].size(); out[st][6]+=768-corridor[h].size();
        out[st][7]+=!corridor[h].empty();
        for(int s:strips[h]) if(!corridor[h].count(s)) {
            ++out[st][1];
            out[st][2]+=!strips[h].count(s-1)&&!strips[h].count(s+1);
        }
    }
    unsigned hash=0,index=0;
    // The deployed dictionary uses the production float LocalPosition_p1 (8 B),
    // while Athena24 headers use doubles (16 B). Never stride with a recompiled
    // FaserSCT_Cluster_p3: use the deployed dictionary's own collection proxy.
    auto* cc=TClass::GetClass("Tracker::FaserSCT_ClusterContainer_p3");
    auto* element=TClass::GetClass("Tracker::FaserSCT_Cluster_p3");
    const char* clusters=static_cast<const char*>(clusterObject);
    auto& collections=*reinterpret_cast<const std::vector<Tracker::TrackerPRD_Collection_p2>*>(
        clusters+cc->GetDataMember("m_collections")->GetOffset());
    auto& deltas=*reinterpret_cast<const std::vector<Identifier::diff_type>*>(
        clusters+cc->GetDataMember("m_prdDeltaId")->GetOffset());
    auto* field=cc->GetDataMember("m_rawdata");
    auto* proxy=TClass::GetClass(field->GetTrueTypeName())->GetCollectionProxy();
    TVirtualCollectionProxy::TPushPop context(proxy,const_cast<char*>(clusters)+field->GetOffset());
    auto rdoOffset=element->GetDataMember("m_rdoList")->GetOffset();
    for(const auto& coll:collections) {
        hash+=coll.m_hashId;
        if(hash>=192) throw std::runtime_error("cluster collection hash");
        auto wafer=id->wafer_id(IdentifierHash(hash)); int st=id->station(wafer);
        for(unsigned j=0;j<coll.m_size;++j,++index) {
            auto& rdos=*reinterpret_cast<const std::vector<short>*>(static_cast<char*>(proxy->At(index))+rdoOffset);
            if(rdos.empty()) throw std::runtime_error("empty cluster RDO list");
            auto center=id->strip_id_offset(wafer,deltas.at(index));
            bool outside=true;
            bool valid=true;
            std::set<int> own;
            for(auto delta:rdos) {
                auto stripId=id->strip_id_offset(center,delta);
                int s=id->strip(stripId);
                if(s<0||s>767||id->wafer_id(stripId)!=wafer) {
                    valid=false; ++out[st][24];
                    std::cerr << "INVALID_CLUSTER_STRIP hash=" << hash << " cluster=" << index
                              << " center=" << id->strip(center) << " delta=" << delta
                              << " decoded=" << s << " size=" << rdos.size() << std::endl;
                    continue;
                }
                outside=outside&&!corridor[hash].count(s);
                own.insert(s);
            }
            bool isolated=true;
            for(int s:own) for(int neighbour:{s-1,s+1})
                if(strips[hash].count(neighbour)&&!own.count(neighbour)) isolated=false;
            ++out[st][3];
            ++out[st][17+std::min(size_t(4),rdos.size()-1)];
            if(valid&&outside) {++out[st][4];out[st][5]+=rdos.size()==1;}
            out[st][22]+=valid&&outside&&isolated;
            out[st][23]+=!valid;
        }
    }
    if(index!=proxy->Size()) throw std::runtime_error("cluster flat size");
    return out;
}

std::vector<unsigned long long> ReadoutHeader(TTree* tree) {
    auto* branch=dynamic_cast<TBranchElement*>(tree->GetBranch("EventInfoAux."));
    if(!branch) throw std::runtime_error("header branch type");
    auto* klass=TClass::GetClass(branch->GetClassName());
    if(!klass) throw std::runtime_error("header class");
    char* info=branch->GetObject();
    if(!info) throw std::runtime_error("missing header object");
    std::vector<unsigned long long> out;
    for(const auto& name:{"runNumber","timeStamp","bcid"}) {
        auto* member=klass->GetDataMember(name);
        if(!member) throw std::runtime_error(std::string("header member ")+name);
        out.push_back(*reinterpret_cast<unsigned int*>(info+member->GetOffset()));
    }
    out.push_back(*reinterpret_cast<unsigned long long*>(info+klass->GetDataMember("eventNumber")->GetOffset()));
    return out;
}

std::vector<std::vector<int>> ReadoutFromTree(TTree* tree, const FaserSCT_ID* id) {
    auto object=[&](const char* name) {
        return dynamic_cast<TBranchElement*>(tree->GetBranch(name))->GetObject();
    };
    return ReadoutSummary(*reinterpret_cast<FaserSCT_RawDataContainer_p4*>(object("SCT_RDOs")),
        object("SCT_ClusterContainer"),
        *reinterpret_cast<Trk::TrackCollection_tlp6*>(object("CKFTrackCollectionBackwardWithoutIFT")),id);
}
