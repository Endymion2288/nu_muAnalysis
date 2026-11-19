#include "NtupleDumperAlg.h"
#include "TrkTrack/Track.h"
#include "TrackerRIO_OnTrack/FaserSCT_ClusterOnTrack.h"
#include "TrackerIdentifier/FaserSCT_ID.h"
#include "ScintIdentifier/VetoNuID.h"
#include "ScintIdentifier/VetoGmID.h"
#include "ScintIdentifier/VetoID.h"
#include "ScintIdentifier/TriggerID.h"
#include "ScintIdentifier/PreshowerID.h"
#include "FaserCaloIdentifier/EcalID.h"
#include "TrackerPrepRawData/FaserSCT_Cluster.h"
#include "TrackerSpacePoint/FaserSCT_SpacePoint.h"
#include "Identifier/Identifier.h"
#include "TrackerReadoutGeometry/SCT_DetectorManager.h"
#include "TrackerReadoutGeometry/SiDetectorElement.h"
#include "TrackerPrepRawData/FaserSCT_Cluster.h"
#include "xAODTruth/TruthParticle.h"
#include "AtlasHepMC/GenEvent.h"

#include "Acts/Definitions/TrackParametrization.hpp"
#include "Acts/EventData/Measurement.hpp"
#include "Acts/Geometry/GeometryContext.hpp"
#include "Acts/Geometry/GeometryIdentifier.hpp"
#include "Acts/Geometry/TrackingGeometry.hpp"
#include "Acts/Surfaces/Surface.hpp"

#include <cmath>
#include <TH1F.h>
#include <numeric>
#include <limits>

constexpr double NaN = std::numeric_limits<double>::quiet_NaN();
using namespace Acts::UnitLiterals;

NtupleDumperAlg::NtupleDumperAlg(const std::string &name, 
                                    ISvcLocator *pSvcLocator)
    : AthReentrantAlgorithm(name, pSvcLocator), 
      AthHistogramming(name),
      m_histSvc("THistSvc/THistSvc", name) {}


void NtupleDumperAlg::addBranch(const std::string &name,
				float* var) const {
  m_tree->Branch(name.c_str(),var,(name+"/F").c_str());
}
void NtupleDumperAlg::addBranch(const std::string &name,
				unsigned int* var) const {
  m_tree->Branch(name.c_str(),var,(name+"/I").c_str());
}

// Initialize channel map from mappingTool
void NtupleDumperAlg::initializeChannelMap() const {
  // Only populate if empty (first call)
  if (m_wave_map.empty()) {
    ATH_MSG_DEBUG("initializeChannelMap");
    // Use waveform map to find all defined waveform channels
    auto mapping = m_mappingTool->getCableMapping();
    ATH_MSG_DEBUG("Cable mapping contains " << mapping.size() << " entries");
    std::string detector;
    for (const auto& [key, value] : mapping) {
      // Special handling for Veto to differentiate veto1 from veto2
      detector = value.first;
      if (value.first == std::string("veto")) {
        // Append station to key string
        detector += std::to_string(m_vetoID->station(value.second)+1);
      }
      m_wave_map[detector].push_back(key);
      ATH_MSG_DEBUG("Found mapping " << detector << " chan " << key);
    }
  }
}

// Have to declare this const to call during execute
void NtupleDumperAlg::defineWaveBranches() const {

  ATH_MSG_DEBUG("defineWaveBranches called");

  // Now go through found types and define ntuple entries
  // Keys are defined in cable map and used by RawWaveformDecoder
  for (const auto& [key, value] : m_wave_map) {

    if (key == std::string("calo")) {
      m_calolo_channels = value;
      // Figure out ntuple below
    }
    else if (key == std::string("calo2")) {
      m_calohi_channels = value;
      // Figure out ntuple below
    }
    else if (key == std::string("calonu")) {
      m_calonu_channels = value;
      addWaveBranches("CaloNu", value);
      addCalibratedBranches("CaloNu", value);
      addCaloSumBranches("CaloNu");
    }
    // Old way (depends on cable map order)
    else if (key == std::string("veto")) {
      addWaveBranches("Veto", value);
    }
    // New way (better, differentiates veto1 and veto2
    else if (key == std::string("veto1")) {
      addWaveBranches("Veto1", value);
    }
    else if (key == std::string("veto2")) {
      addWaveBranches("Veto2", value);
    }    
    else if (key == std::string("vetonu")) {
      addWaveBranches("VetoNu", value);
    }
    else if (key == std::string("vetogm")) {
      addWaveBranches("VetoGm", value);
    }
    else if (key == std::string("trigger")) {
      addWaveBranches("Timing", value);
    }
    else if (key == std::string("preshower")) {
      addWaveBranches("Preshower", value);
      addCalibratedBranches("Preshower", value);
      addBranch("Preshower_total_nMIP", &m_preshower_total_nMIP);
      addBranch("Preshower_total_E_dep", &m_preshower_total_E_dep);      
    }
    else if (key == std::string("muon")) {
      addWaveBranches("Muon", value);
    }
    else if (key == std::string("clock")) {
      // ignore this
    }
    else if (key == std::string("none")) {
      // ignore this
    }
    else {
      ATH_MSG_WARNING("Found unknown mapping type " << key);
    }
  } // End of loop over wave_map entries

  // Figure out calorimeter
  if (m_calolo_channels.size() && !m_calohi_channels.size()) {
    // Only "calo" type found, 2022/23 configuration
    ATH_MSG_INFO("defineWaveBranches found " << m_calolo_channels.size() << " calo channels => 2022/23 configuration");
    m_dual_gain = false;
    m_calo_channels = m_calolo_channels;
    m_calolo_channels.clear();
    addWaveBranches("Calo", m_calo_channels);
    addCalibratedBranches("Calo", m_calo_channels);
    addCaloSumBranches("Calo");
  }
  else if (m_calolo_channels.size() && m_calohi_channels.size()) {
    // Both found, 2024/25 configuration (both defined)
    ATH_MSG_INFO("defineWaveBranches found " << m_calolo_channels.size() << " calo and " << m_calohi_channels.size() << " calo2 channels => 2024/25 configuration");
    m_dual_gain = true;
    addWaveBranches("CaloLo", m_calolo_channels);
    addWaveBranches("CaloHi", m_calohi_channels);
    addCalibratedBranches("CaloLo", m_calolo_channels);    
    addCalibratedBranches("CaloHi", m_calohi_channels);
    addCaloSumBranches("CaloLo");
    addCaloSumBranches("CaloHi");
  }
  else {
    // Unknown configuration
    ATH_MSG_WARNING("defineWaveBranches found " << m_calolo_channels.size() << " calo channels and " << m_calohi_channels.size() << " calo2 channels!");
    m_dual_gain = false;
    return;
  }
  
  ATH_MSG_DEBUG("defineWaveBranches done");
}

void
NtupleDumperAlg::addCaloSumBranches(const std::string &name) const {

  ATH_MSG_DEBUG("addCaloSumBranches " << name << " called");
  
  // Utility to define the calorimeter sum branches
  if (name == std::string("Calo")) {
    addBranch("Calo_total_nMIP", &m_calo_total_nMIP);
    addBranch("Calo_total_E_dep", &m_calo_total_E_dep);
    addBranch("Calo_total_fit_E_EM", &m_calo_total_fit_E_EM);
    addBranch("Calo_total_raw_E_EM", &m_calo_total_raw_E_EM);
    addBranch("Calo_total_E_EM", &m_calo_total_E_EM);

    addBranch("Calo_total_fit_E_EM_fudged", &m_calo_total_fit_E_EM_fudged);
    addBranch("Calo_total_raw_E_EM_fudged", &m_calo_total_raw_E_EM_fudged);
    addBranch("Calo_total_E_EM_fudged", &m_calo_total_E_EM_fudged);
  }
  else if (name == std::string("CaloLo")) {
    addBranch("CaloLo_total_nMIP", &m_calolo_total_nMIP);
    addBranch("CaloLo_total_E_dep", &m_calolo_total_E_dep);
    addBranch("CaloLo_total_fit_E_EM", &m_calolo_total_fit_E_EM);
    addBranch("CaloLo_total_raw_E_EM", &m_calolo_total_raw_E_EM);
    addBranch("CaloLo_total_E_EM", &m_calolo_total_E_EM);
  }
  else if (name == std::string("CaloHi")) {
    addBranch("CaloHi_total_nMIP", &m_calohi_total_nMIP);
    addBranch("CaloHi_total_E_dep", &m_calohi_total_E_dep);
    addBranch("CaloHi_total_fit_E_EM", &m_calohi_total_fit_E_EM);
    addBranch("CaloHi_total_raw_E_EM", &m_calohi_total_raw_E_EM);
    addBranch("CaloHi_total_E_EM", &m_calohi_total_E_EM);
  }
  else if (name == std::string("CaloNu")) {
    addBranch("CaloNu_total_nMIP", &m_calonu_total_nMIP);
    addBranch("CaloNu_total_E_dep", &m_calonu_total_E_dep);
    addBranch("CaloNu_total_fit_E_EM", &m_calonu_total_fit_E_EM);
    addBranch("CaloNu_total_raw_E_EM", &m_calonu_total_raw_E_EM);
    addBranch("CaloNu_total_E_EM", &m_calonu_total_E_EM);
  }
  else {
    ATH_MSG_WARNING("addCaloSumBranches - Unknown type " << name << "!");
  }    
}

// Use channel list to add branches
void NtupleDumperAlg::addWaveBranches(const std::string &name,
				      std::list<int> channel_list) const {

  ATH_MSG_DEBUG("Adding waveforms " << name << " with channels " << channel_list);

  int nchannels = channel_list.size();
  for(int i=0;i<nchannels;i++) {
    int ch = channel_list.front();
    channel_list.pop_front();
    
    std::string base=name+std::to_string(i);
    addBranch(base+"_triggertime",&m_wave_triggertime[ch]);
    addBranch(base+"_localtime",&m_wave_localtime[ch]);
    addBranch(base+"_bcidtime",&m_wave_bcidtime[ch]);
    addBranch(base+"_peak",&m_wave_peak[ch]);
    addBranch(base+"_width",&m_wave_width[ch]);
    addBranch(base+"_charge",&m_wave_charge[ch]);
    addBranch(base+"_tover",&m_wave_overflow[ch]);
    addBranch(base+"_raw_peak",&m_wave_raw_peak[ch]);
    addBranch(base+"_raw_charge",&m_wave_raw_charge[ch]);
    addBranch(base+"_baseline",&m_wave_baseline_mean[ch]);
    addBranch(base+"_baseline_rms",&m_wave_baseline_rms[ch]);
    addBranch(base+"_status",&m_wave_status[ch]);
    ATH_MSG_DEBUG("Added "  << base << " ch " << ch);
    
    // Also add the random histogram
    std::string hname = "hRandomCharge"+std::to_string(ch);
    base = name + std::to_string(i) + " Ch" + std::to_string(ch);
    std::string title = base+" Charge from RandomEvents;charge (pC);Events/bin";
    m_HistRandomCharge[ch] = new TH1F(hname.c_str(), title.c_str(), 100, -1.0, 1.0);
    StatusCode sc = histSvc()->regHist("/HIST2/RandomCharge"+std::to_string(ch), m_HistRandomCharge[ch]);
  }
}

void NtupleDumperAlg::FillWaveBranches(const xAOD::WaveformHitContainer &wave, bool isMC) const {
  // ATH_MSG_DEBUG("FillWaveBranches called");
  for (auto hit : wave) {
    if (!hit->secondary()) { // dont store secoondary hits as they can overwrite the primary hit
      int ch=hit->channel();

      m_wave_localtime[ch]=hit->localtime();
      m_wave_bcidtime[ch] = hit->bcid_time(); // Now corrected for offsets
      // Not sure why this doesn't exist in MC...
      if (!isMC)
	m_wave_triggertime[ch] = hit->trigger_time(); // + m_clock_phase;
      m_wave_peak[ch]=hit->peak();
      m_wave_width[ch]=hit->width();
      m_wave_charge[ch]=hit->integral()/50;  // In pC

      m_wave_raw_peak[ch]=hit->raw_peak();
      m_wave_raw_charge[ch]=hit->raw_integral()/50;  // In pC
      m_wave_baseline_mean[ch]=hit->baseline_mean();
      m_wave_baseline_rms[ch]=hit->baseline_rms();
      m_wave_status[ch]=hit->hit_status();

      // Check for overflows
      if (hit->overflow()) {  // Overflow

	// For v3 Waveforms, we store overflow time directly
	if (hit->over_time() > 0) {
	  m_wave_overflow[ch] = hit->over_time();
	}
	
	// Need raw waveform, if it doesn't exist, set time as -1 (unknown)
	else if (hit->wave_vector().size() == 0) {
	  m_wave_overflow[ch] = -1;
	  ATH_MSG_DEBUG("Found overflow hit but no wave_vector for channel " << ch << "!");
	}

	// Reconstruct from raw waveform
	else {
	  
	  // Find first instance of max
	  // I get crashes with std:: algorithms, so do this brute force
	  float max_val=0.;
	  unsigned int ifirst = 0;
	  unsigned int ilast = 0;
	  for (unsigned int i=0; i < hit->wave_vector().size(); i++) {
	    if (hit->wave_vector()[i] > max_val) {  // New max
	      max_val = hit->wave_vector()[i];
	      ifirst = i;
	      ilast = i;
	    } else if (hit->wave_vector()[i] == max_val) { // Equal to max
	      ilast = i;
	    } 
	  }
	    	  
	  m_wave_overflow[ch] = hit->time_vector()[ilast] - hit->time_vector()[ifirst];

	  ATH_MSG_DEBUG("Found overflow from " << ifirst << " to " << ilast << " for tover = " << m_wave_overflow[ch]);
	  
	}
      } else {
	m_wave_overflow[ch] = 0;
      }
    }
  }
  //ATH_MSG_DEBUG("FillWaveBranches done");
}

void NtupleDumperAlg::addCalibratedBranches(const std::string &name,
					    std::list<int> channel_list) const {

  ATH_MSG_DEBUG("Adding calibrated " << name << " with channels " << channel_list);

  int nchannels = channel_list.size();
  for(int i=0;i<nchannels;i++) {
    int ch = channel_list.front();
    channel_list.pop_front();
    
    std::string base=name+std::to_string(i);
    addBranch(base+"_nMIP", &m_calibrated_nMIP[ch]);
    addBranch(base+"_E_dep",&m_calibrated_E_dep[ch]);
    addBranch(base+"_E_EM", &m_calibrated_E_EM[ch]);    
    ATH_MSG_DEBUG("Added "  << base << " ch " << ch);

  }
}


StatusCode NtupleDumperAlg::initialize() 
{

  m_first = true;
  
  ATH_CHECK(m_truthEventContainer.initialize());
  ATH_CHECK(m_mcEventContainer.initialize());
  ATH_CHECK(m_truthParticleContainer.initialize());
  ATH_CHECK(m_lhcData.initialize());
  ATH_CHECK(m_trackCollection.initialize());
  ATH_CHECK(m_trackCollectionWithoutIFT.initialize());
  ATH_CHECK(m_trackSegmentCollection.initialize());
  ATH_CHECK(m_ghostbustedtrackSegmentCollection.initialize());

  ATH_CHECK(m_vetoContainer.initialize());
  ATH_CHECK(m_vetoNuContainer.initialize());
  ATH_CHECK(m_vetoGmContainer.initialize());
  ATH_CHECK(m_triggerContainer.initialize());
  ATH_CHECK(m_preshowerContainer.initialize());
  ATH_CHECK(m_muonContainer.initialize());

  ATH_CHECK(m_ecalContainer.initialize());
  ATH_CHECK(m_ecal2Container.initialize());
  ATH_CHECK(m_caloNuContainer.initialize());
  ATH_CHECK(m_clusterContainer.initialize());
  ATH_CHECK(m_simDataCollection.initialize());
  ATH_CHECK(m_FaserTriggerData.initialize());
  ATH_CHECK(m_ClockWaveformContainer.initialize());
  ATH_CHECK(m_siHitCollectionKey.initialize());

  ATH_CHECK(m_preshowerCalibratedContainer.initialize());
  ATH_CHECK(m_ecalCalibratedContainer.initialize());
  ATH_CHECK(m_ecal2CalibratedContainer.initialize());
  ATH_CHECK(m_calonuCalibratedContainer.initialize());
  ATH_CHECK(m_eventInfoKey.initialize());
  ATH_CHECK(m_faserEventInfoKey.initialize());

  ATH_CHECK(detStore()->retrieve(m_sctHelper,       "FaserSCT_ID"));
  
  ATH_CHECK(detStore()->retrieve(m_detMgr, "SCT"));

  ATH_CHECK(detStore()->retrieve(m_vetoID, "VetoID"));
    
  ATH_CHECK(m_extrapolationTool.retrieve());
  ATH_CHECK(m_trackingGeometryTool.retrieve());
  ATH_CHECK(m_trackTruthMatchingTool.retrieve());
  ATH_CHECK(m_fiducialParticleTool.retrieve());
  ATH_CHECK(m_vertexingTool.retrieve());
  ATH_CHECK(m_mappingTool.retrieve());
  
  ATH_CHECK(m_spacePointContainerKey.initialize());

  // Read GRL if requested
  if (!m_goodRunsList.value().empty()) {
    ATH_MSG_INFO("Opening GRL file " << m_goodRunsList);
    ATH_MSG_INFO(m_applyGoodRunsList);
    std::ifstream f(m_goodRunsList);
    m_grl = nlohmann::json::parse(f);
    f.close();
    ATH_MSG_INFO("Read GRL with " << m_grl.size() << " records");
  } else {
    // Make sure this is empty
    m_grl.clear();
  }

  if (m_useFlukaWeights)
  {
    m_baseEventCrossSection = (m_flukaCrossSection * kfemtoBarnsPerMilliBarn)/m_flukaCollisions;
  }
  else if (m_useGenieWeights)
  {
    m_baseEventCrossSection = 1.0/m_genieLuminosity;
  }
  else
  {
    m_baseEventCrossSection = 1.0;
  }

  m_tree = new TTree("nt", "NtupleDumper tree");

  //META INFORMATION
  m_tree->Branch("run", &m_run_number, "run/I");
  m_tree->Branch("eventID", &m_event_number, "eventID/I");
  m_tree->Branch("eventTime", &m_event_time, "eventTime/I");
  m_tree->Branch("eventTimeNSOffset", &m_event_timeNSOffset, "eventTimeNSOffset/I");
  m_tree->Branch("BCID", &m_bcid, "BCID/I");
  m_tree->Branch("inGRL", &m_in_grl, "inGRL/I");
  m_tree->Branch("clockPhase", &m_clock_phase, "clockPhase");
  
  m_tree->Branch("fillNumber", &m_fillNumber, "fillNumber/I");
  m_tree->Branch("betaStar", &m_betaStar, "betaStar/F");
  m_tree->Branch("crossingAngle", &m_crossingAngle, "crossingAngle/F");
  m_tree->Branch("isVerticalCrossingAngle", &m_isVerticalCrossingAngle, "isVerticalCrossingAngle/O");
  m_tree->Branch("distanceToCollidingBCID", &m_distanceToCollidingBCID, "distanceToCollidingBCID/I");
  m_tree->Branch("distanceToUnpairedB1", &m_distanceToUnpairedB1, "distanceToUnpairedB1/I");
  m_tree->Branch("distanceToUnpairedB2", &m_distanceToUnpairedB2, "distanceToUnpairedB2/I");
  m_tree->Branch("distanceToInboundB1", &m_distanceToInboundB1, "distanceToInboundB1/I");
  m_tree->Branch("distanceToTrainStart", &m_distanceToTrainStart, "distanceToTrainStart/I");
  m_tree->Branch("distanceToPreviousColliding", &m_distanceToPreviousColliding, "distanceToPreviousColliding/I");

  m_tree->Branch("TBP", &m_tbp, "TBP/I");
  m_tree->Branch("TAP", &m_tap, "TAP/I");
  m_tree->Branch("inputBits", &m_inputBits, "inputBits/I");
  m_tree->Branch("inputBitsNext", &m_inputBitsNext, "inputBitsNext/I");

  // WAVEFORMS
  // Now defined on first event so we can use cable mapping tool
  m_tree->Branch("VetoNu0_reduced_charge", &m_vetonu_reduced_charge[0]);
  m_tree->Branch("VetoNu1_reduced_charge", &m_vetonu_reduced_charge[1]);
  m_tree->Branch("ScintHit", &m_scintHit);


  //TRACKER
  addBranch("nClusters0",&m_station0Clusters);
  addBranch("nClusters1",&m_station1Clusters);
  addBranch("nClusters2",&m_station2Clusters);
  addBranch("nClusters3",&m_station3Clusters);

  addBranch("SpacePoints",&m_nspacepoints);
  m_tree->Branch("SpacePoint_x", &m_spacepointX);
  m_tree->Branch("SpacePoint_y", &m_spacepointY);
  m_tree->Branch("SpacePoint_z", &m_spacepointZ);

  addBranch("TrackSegments",&m_ntracksegs);
  m_tree->Branch("TrackSegment_Chi2", &m_trackseg_Chi2);
  m_tree->Branch("TrackSegment_nDoF", &m_trackseg_DoF);
  m_tree->Branch("TrackSegment_x", &m_trackseg_x);
  m_tree->Branch("TrackSegment_y", &m_trackseg_y);
  m_tree->Branch("TrackSegment_z", &m_trackseg_z);
  m_tree->Branch("TrackSegment_px", &m_trackseg_px);
  m_tree->Branch("TrackSegment_py", &m_trackseg_py);
  m_tree->Branch("TrackSegment_pz", &m_trackseg_pz);

  addBranch("GhostBustedTrackSegments",&m_nghostbustedtracksegs);
  m_tree->Branch("GhostBustedTrackSegment_Chi2", &m_ghostbustedtrackseg_Chi2);
  m_tree->Branch("GhostBustedTrackSegment_nDoF", &m_ghostbustedtrackseg_DoF);
  m_tree->Branch("GhostBustedTrackSegment_x", &m_ghostbustedtrackseg_x);
  m_tree->Branch("GhostBustedTrackSegment_y", &m_ghostbustedtrackseg_y);
  m_tree->Branch("GhostBustedTrackSegment_z", &m_ghostbustedtrackseg_z);
  m_tree->Branch("GhostBustedTrackSegment_px", &m_ghostbustedtrackseg_px);
  m_tree->Branch("GhostBustedTrackSegment_py", &m_ghostbustedtrackseg_py);
  m_tree->Branch("GhostBustedTrackSegment_pz", &m_ghostbustedtrackseg_pz);

  //TrackCollection
  m_tree->Branch("Track_PropagationError", &m_propagationError, "Track_PropagationError/I");
  m_tree->Branch("longTracks", &m_longTracks, "longTracks/I");
  m_tree->Branch("Track_Chi2", &m_Chi2);
  m_tree->Branch("Track_nDoF", &m_DoF);
  m_tree->Branch("Track_module_eta0", &m_module_eta0);
  m_tree->Branch("Track_module_phi0", &m_module_phi0);
  m_tree->Branch("Track_hitSet", &m_hitSet);
  m_tree->Branch("Track_nMeasurements", &m_nMeasurements);
  m_tree->Branch("Track_x0", &m_xup);
  m_tree->Branch("Track_y0", &m_yup);
  m_tree->Branch("Track_z0", &m_zup);
  m_tree->Branch("Track_px0", &m_pxup);
  m_tree->Branch("Track_py0", &m_pyup);
  m_tree->Branch("Track_pz0", &m_pzup);
  m_tree->Branch("Track_p0", &m_pup);
  m_tree->Branch("Track_x1", &m_xdown);
  m_tree->Branch("Track_y1", &m_ydown);
  m_tree->Branch("Track_z1", &m_zdown);
  m_tree->Branch("Track_px1", &m_pxdown);
  m_tree->Branch("Track_py1", &m_pydown);
  m_tree->Branch("Track_pz1", &m_pzdown);
  m_tree->Branch("Track_p1", &m_pdown);
  m_tree->Branch("Track_charge", &m_charge);
  m_tree->Branch("Track_nLayers", &m_nLayers);
  m_tree->Branch("Track_isForward", &m_isForward);

  //Which Stations were hit?
  m_tree->Branch("Track_InStation0",&m_nHit0);
  m_tree->Branch("Track_InStation1",&m_nHit1);
  m_tree->Branch("Track_InStation2",&m_nHit2);
  m_tree->Branch("Track_InStation3",&m_nHit3);

  //Extrapolated Track Info
  m_tree->Branch("Track_X_atVetoNu", &m_xVetoNu);
  m_tree->Branch("Track_Y_atVetoNu", &m_yVetoNu);
  m_tree->Branch("Track_ThetaX_atVetoNu", &m_thetaxVetoNu);
  m_tree->Branch("Track_ThetaY_atVetoNu", &m_thetayVetoNu);

  m_tree->Branch("Track_X_atVetoStation1", &m_xVetoStation1);
  m_tree->Branch("Track_Y_atVetoStation1", &m_yVetoStation1);
  m_tree->Branch("Track_ThetaX_atVetoStation1", &m_thetaxVetoStation1);
  m_tree->Branch("Track_ThetaY_atVetoStation1", &m_thetayVetoStation1);

  m_tree->Branch("Track_X_atVetoStation2", &m_xVetoStation2);
  m_tree->Branch("Track_Y_atVetoStation2", &m_yVetoStation2);
  m_tree->Branch("Track_ThetaX_atVetoStation2", &m_thetaxVetoStation2);
  m_tree->Branch("Track_ThetaY_atVetoStation2", &m_thetayVetoStation2);

  m_tree->Branch("Track_X_atTrig", &m_xTrig);
  m_tree->Branch("Track_Y_atTrig", &m_yTrig);
  m_tree->Branch("Track_ThetaX_atTrig", &m_thetaxTrig);
  m_tree->Branch("Track_ThetaY_atTrig", &m_thetayTrig);

  m_tree->Branch("Track_X_atPreshower1", &m_xPreshower1);
  m_tree->Branch("Track_Y_atPreshower1", &m_yPreshower1);
  m_tree->Branch("Track_ThetaX_atPreshower1", &m_thetaxPreshower1);
  m_tree->Branch("Track_ThetaY_atPreshower1", &m_thetayPreshower1);

  m_tree->Branch("Track_X_atPreshower2", &m_xPreshower2);
  m_tree->Branch("Track_Y_atPreshower2", &m_yPreshower2);
  m_tree->Branch("Track_ThetaX_atPreshower2", &m_thetaxPreshower2);
  m_tree->Branch("Track_ThetaY_atPreshower2", &m_thetayPreshower2);

  m_tree->Branch("Track_X_atCalo", &m_xCalo);
  m_tree->Branch("Track_Y_atCalo", &m_yCalo);
  m_tree->Branch("Track_ThetaX_atCalo", &m_thetaxCalo);
  m_tree->Branch("Track_ThetaY_atCalo", &m_thetayCalo);

  m_tree->Branch("Track_x_atMaxRadius", &m_x_atMaxRadius);
  m_tree->Branch("Track_y_atMaxRadius", &m_y_atMaxRadius);
  m_tree->Branch("Track_z_atMaxRadius", &m_z_atMaxRadius);
  m_tree->Branch("Track_r_atMaxRadius", &m_r_atMaxRadius);

  //TRUTH

  m_tree->Branch("t_pdg", &m_t_pdg);
  m_tree->Branch("t_barcode", &m_t_barcode);
  m_tree->Branch("t_pdg_parent", &m_t_pdg_parent);
  m_tree->Branch("t_barcode_parent", &m_t_barcode_parent);
  m_tree->Branch("t_truthHitRatio", &m_t_truthHitRatio);

  m_tree->Branch("t_prodVtx_x", &m_t_prodVtx_x);
  m_tree->Branch("t_prodVtx_y", &m_t_prodVtx_y);
  m_tree->Branch("t_prodVtx_z", &m_t_prodVtx_z);

  m_tree->Branch("t_decayVtx_x", &m_t_decayVtx_x);
  m_tree->Branch("t_decayVtx_y", &m_t_decayVtx_y);
  m_tree->Branch("t_decayVtx_z", &m_t_decayVtx_z);

  //Truth track info
  m_tree->Branch("t_px", &m_t_px);
  m_tree->Branch("t_py", &m_t_py);
  m_tree->Branch("t_pz", &m_t_pz);
  m_tree->Branch("t_theta", &m_t_theta);
  m_tree->Branch("t_phi", &m_t_phi);
  m_tree->Branch("t_p", &m_t_p);
  m_tree->Branch("t_pT", &m_t_pT);
  m_tree->Branch("t_eta", &m_t_eta);
  m_tree->Branch("t_st0_x", &m_t_st_x[0]);
  m_tree->Branch("t_st0_y", &m_t_st_y[0]);
  m_tree->Branch("t_st0_z", &m_t_st_z[0]);
  m_tree->Branch("t_st1_x", &m_t_st_x[1]);
  m_tree->Branch("t_st1_y", &m_t_st_y[1]);
  m_tree->Branch("t_st1_z", &m_t_st_z[1]);
  m_tree->Branch("t_st2_x", &m_t_st_x[2]);
  m_tree->Branch("t_st2_y", &m_t_st_y[2]);
  m_tree->Branch("t_st2_z", &m_t_st_z[2]);
  m_tree->Branch("t_st3_x", &m_t_st_x[3]);
  m_tree->Branch("t_st3_y", &m_t_st_y[3]);
  m_tree->Branch("t_st3_z", &m_t_st_z[3]);
  m_tree->Branch("t_st0_px", &m_t_st_px[0]);
  m_tree->Branch("t_st0_py", &m_t_st_py[0]);
  m_tree->Branch("t_st0_pz", &m_t_st_pz[0]);
  m_tree->Branch("t_st1_px", &m_t_st_px[1]);
  m_tree->Branch("t_st1_py", &m_t_st_py[1]);
  m_tree->Branch("t_st1_pz", &m_t_st_pz[1]);
  m_tree->Branch("t_st2_px", &m_t_st_px[2]);
  m_tree->Branch("t_st2_py", &m_t_st_py[2]);
  m_tree->Branch("t_st2_pz", &m_t_st_pz[2]);
  m_tree->Branch("t_st3_px", &m_t_st_px[3]);
  m_tree->Branch("t_st3_py", &m_t_st_py[3]);
  m_tree->Branch("t_st3_pz", &m_t_st_pz[3]);
  m_tree->Branch("isFiducial", &m_isFiducial);

  m_tree->Branch("truthParticleBarcode", &m_truthParticleBarcode);
  m_tree->Branch("truthParticleMatchedTracks", &m_truthParticleMatchedTracks);
  m_tree->Branch("truthParticleIsFiducial", &m_truthParticleIsFiducial);

  m_tree->Branch("pTruthLepton", &m_truthLeptonMomentum, "pTruthLepton/D");
  m_tree->Branch("truthBarcode", &m_truthBarcode, "truthBarcode/I");
  m_tree->Branch("truthPdg", &m_truthPdg, "truthPdg/I");
  m_tree->Branch("CrossSection", &m_crossSection, "crossSection/D");
  m_tree->Branch("GenWeights", &m_genWeights);


  //truth information
  m_tree->Branch("truth_barcode", &m_truth_barcode);
  m_tree->Branch("truth_pdg", &m_truth_pdg);
  m_tree->Branch("truth_nHits", &m_truth_nHits);
  m_tree->Branch("truth_P", &m_truth_P);
  m_tree->Branch("truth_px", &m_truth_px);
  m_tree->Branch("truth_py", &m_truth_py);
  m_tree->Branch("truth_pz", &m_truth_pz);
  m_tree->Branch("truth_m", &m_truth_m);
  m_tree->Branch("truth_pT", &m_truth_pT);
  m_tree->Branch("truth_theta", &m_truth_theta);
  m_tree->Branch("truth_phi", &m_truth_phi);
  m_tree->Branch("truth_eta", &m_truth_eta);
  m_tree->Branch("truth_isFiducial", &m_truth_isFiducial);
  m_tree->Branch("truth_prod_x", &m_truth_prod_x);
  m_tree->Branch("truth_prod_y", &m_truth_prod_y);
  m_tree->Branch("truth_prod_z", &m_truth_prod_z);
  m_tree->Branch("truth_dec_x", &m_truth_dec_x);
  m_tree->Branch("truth_dec_y", &m_truth_dec_y);
  m_tree->Branch("truth_dec_z", &m_truth_dec_z);
  
  m_tree->Branch("truth_nHits_st0_l0", &m_st0[0]);
  m_tree->Branch("truth_nHits_st0_l1", &m_st0[1]);
  m_tree->Branch("truth_nHits_st0_l2", &m_st0[2]);
  m_tree->Branch("truth_nHits_st1_l0", &m_st1[0]);
  m_tree->Branch("truth_nHits_st1_l1", &m_st1[1]);
  m_tree->Branch("truth_nHits_st1_l2", &m_st1[2]);
  m_tree->Branch("truth_nHits_st2_l0", &m_st2[0]);
  m_tree->Branch("truth_nHits_st2_l1", &m_st2[1]);
  m_tree->Branch("truth_nHits_st2_l2", &m_st2[2]);
  m_tree->Branch("truth_nHits_st3_l0", &m_st3[0]);
  m_tree->Branch("truth_nHits_st3_l1", &m_st3[1]);
  m_tree->Branch("truth_nHits_st3_l2", &m_st3[2]);

  m_tree->Branch("truth_st0_x", &m_truth_st_x[0]);
  m_tree->Branch("truth_st0_y", &m_truth_st_y[0]);
  m_tree->Branch("truth_st0_z", &m_truth_st_z[0]);
  m_tree->Branch("truth_st1_x", &m_truth_st_x[1]);
  m_tree->Branch("truth_st1_y", &m_truth_st_y[1]);
  m_tree->Branch("truth_st1_z", &m_truth_st_z[1]);
  m_tree->Branch("truth_st2_x", &m_truth_st_x[2]);
  m_tree->Branch("truth_st2_y", &m_truth_st_y[2]);
  m_tree->Branch("truth_st2_z", &m_truth_st_z[2]);
  m_tree->Branch("truth_st3_x", &m_truth_st_x[3]);
  m_tree->Branch("truth_st3_y", &m_truth_st_y[3]);
  m_tree->Branch("truth_st3_z", &m_truth_st_z[3]);
  m_tree->Branch("truth_st0_px", &m_truth_st_px[0]);
  m_tree->Branch("truth_st0_py", &m_truth_st_py[0]);
  m_tree->Branch("truth_st0_pz", &m_truth_st_pz[0]);
  m_tree->Branch("truth_st1_px", &m_truth_st_px[1]);
  m_tree->Branch("truth_st1_py", &m_truth_st_py[1]);
  m_tree->Branch("truth_st1_pz", &m_truth_st_pz[1]);
  m_tree->Branch("truth_st2_px", &m_truth_st_px[2]);
  m_tree->Branch("truth_st2_py", &m_truth_st_py[2]);
  m_tree->Branch("truth_st2_pz", &m_truth_st_pz[2]);
  m_tree->Branch("truth_st3_px", &m_truth_st_px[3]);
  m_tree->Branch("truth_st3_py", &m_truth_st_py[3]);
  m_tree->Branch("truth_st3_pz", &m_truth_st_pz[3]);

  // for mother + daughter particle truth infomation 

  m_tree->Branch("truthM_P", &m_truthM_P);
  m_tree->Branch("truthM_px", &m_truthM_px);
  m_tree->Branch("truthM_py", &m_truthM_py);
  m_tree->Branch("truthM_pz", &m_truthM_pz);
  m_tree->Branch("truthM_x", &m_truthM_x);
  m_tree->Branch("truthM_y", &m_truthM_y);
  m_tree->Branch("truthM_z", &m_truthM_z);
  m_tree->Branch("truthM_isFiducial", &m_truthM_isFiducial);

  m_tree->Branch("truthd0_P", &m_truthd0_P);
  m_tree->Branch("truthd0_px", &m_truthd0_px);
  m_tree->Branch("truthd0_py", &m_truthd0_py);
  m_tree->Branch("truthd0_pz", &m_truthd0_pz);
  m_tree->Branch("truthd0_x", &m_truthd0_x);
  m_tree->Branch("truthd0_y", &m_truthd0_y);
  m_tree->Branch("truthd0_z", &m_truthd0_z);
  m_tree->Branch("truthd0_isFiducial", &m_truthd0_isFiducial);

  m_tree->Branch("truthd1_P", &m_truthd1_P);
  m_tree->Branch("truthd1_px", &m_truthd1_px);
  m_tree->Branch("truthd1_py", &m_truthd1_py);
  m_tree->Branch("truthd1_pz", &m_truthd1_pz);
  m_tree->Branch("truthd1_x", &m_truthd1_x);
  m_tree->Branch("truthd1_y", &m_truthd1_y);
  m_tree->Branch("truthd1_z", &m_truthd1_z);
  m_tree->Branch("truthd1_isFiducial", &m_truthd1_isFiducial);

  m_tree->Branch("vertex_x", &m_vertex_x, "vertex_x/D");
  m_tree->Branch("vertex_y", &m_vertex_y, "vertex_y/D");
  m_tree->Branch("vertex_z", &m_vertex_z, "vertex_z/D");
  m_tree->Branch("vertex_chi2", &m_vertex_chi2, "vertex_chi2/D");
  m_tree->Branch("vertex_px0", &m_vertex_px0, "vertex_px0/D");
  m_tree->Branch("vertex_py0", &m_vertex_py0, "vertex_py0/D");
  m_tree->Branch("vertex_pz0", &m_vertex_pz0, "vertex_pz0/D");
  m_tree->Branch("vertex_p0", &m_vertex_p0, "vertex_p0/D");
  m_tree->Branch("vertex_px1", &m_vertex_px1, "vertex_px1/D");
  m_tree->Branch("vertex_py1", &m_vertex_py1, "vertex_py1/D");
  m_tree->Branch("vertex_pz1", &m_vertex_pz1, "vertex_pz1/D");
  m_tree->Branch("vertex_p1", &m_vertex_p1, "vertex_p1/D");

  ATH_CHECK(histSvc()->regTree("/HIST2/tree", m_tree));

  // Register histograms
  // Also done on first event

  if (m_onlyBlinded){
    ATH_MSG_INFO("Only events that would be blinded are saved in ntuple");
    m_doBlinding = false;
  } else if (m_doBlinding) {
    ATH_MSG_INFO("Blinding will be enforced for real data.");
  } else {
    ATH_MSG_INFO("Blinding will NOT be enforced for real data.");
  }

  // Make sure charge histogram pointers are empty
  for (unsigned int chan = 0; chan<max_chan; chan++)
    m_HistRandomCharge[chan] = NULL;
  
  return StatusCode::SUCCESS;
}

StatusCode NtupleDumperAlg::execute(const EventContext &ctx) const
{
  clearTree();

  // Define waveform channels on first event
  if (m_first) {
    initializeChannelMap();
    defineWaveBranches();
    m_first = false;
  }
  
  // check if real data or simulation data
  bool isMC = false;
  SG::ReadHandle<xAOD::TruthEventContainer> truthEventContainer { m_truthEventContainer, ctx };
  if (truthEventContainer.isValid() && truthEventContainer->size() > 0)
  {
    isMC = true;
    ATH_MSG_INFO("Configuring for MC events");
  }
  else {
    ATH_MSG_INFO("Configuring for real data events");    
  }
  
  SG::ReadHandle<McEventCollection> mcEventContainer {m_mcEventContainer, ctx};
  if (isMC && (!mcEventContainer.isValid() || mcEventContainer->size() == 0)) {
    ATH_MSG_WARNING("Could not retrieve MCEventCollection " << m_mcEventContainer);
    return StatusCode::SUCCESS;
  }


  // EventInfo data
  m_run_number = ctx.eventID().run_number();
  m_event_number = ctx.eventID().event_number();
  m_event_time = ctx.eventID().time_stamp();
  m_event_timeNSOffset = ctx.eventID().time_stamp_ns_offset();
  m_bcid = ctx.eventID().bunch_crossing_id();

  // For real data, find if data is in GoodRunsList
  if (!isMC && !m_grl.empty()) {
    ATH_MSG_DEBUG("Checking GRL for run " << m_run_number << " event " << m_event_number);

    // JSON keys are always strings
    std::string run_string = std::to_string(m_run_number);
    std::string reason("unknown");

    if (m_grl.contains(run_string)) {
      // m_in_grl set to 0 by clearTree
      auto jrun = m_grl[run_string];

      // Make sure this is in the stable beams range
      if (jrun.contains("stable_list")) {
	for ( auto& slist : jrun["stable_list"]) {
	  // Check if event falls in this range
	  if (slist["start_utime"] > m_event_time) continue;
	  if (slist["stop_utime"] <= m_event_time) continue;
	  m_in_grl = 1;
	  break;
	}

	// Check exclude list (not all runs will have this)
	if (jrun.contains("excluded_list")) {
	  ATH_MSG_DEBUG("Checking excluded list");
	  for ( auto& blist : jrun["excluded_list"]) {
	    ATH_MSG_DEBUG("Checking excluded list start " << blist["start_utime"] << " stop " << blist["stop_utime"] << " event " << m_event_time);

	    // Check if event falls in this range
	    if (blist["start_utime"] > m_event_time) continue;
	    if (blist["stop_utime"] <= m_event_time) continue;
	    if (blist.contains("reason")) {
	      reason = blist["reason"];
	    } 
	    m_in_grl = 0;
	    break;
	  }
	}

	if (m_in_grl == 0) {
	  ATH_MSG_DEBUG("Run " << run_string << " event " << m_event_number << " time " << m_event_time << " excluded for " << reason);
	}

      } else {
	ATH_MSG_WARNING("Run " << run_string << " has no stable_list!");
      }
    } else {
      ATH_MSG_WARNING("Run " << run_string << " not found in GRL!");
    }
  }

  // Skip this event?
  if (m_applyGoodRunsList && (m_in_grl == 0)) {
    ATH_MSG_DEBUG("Skipping run " << m_run_number 
		  << " event " << m_event_number << " - outside GRL" );
    m_eventsFailedGRL += 1;
    return StatusCode::SUCCESS;
  }

  // if real data, correct for diigitzer timing jitter with clock phase
  if (!isMC) {
    // correct waveform time with clock phase
    // needs to be done before processing waveform values
    SG::ReadHandle<xAOD::WaveformClock> clockHandle(m_ClockWaveformContainer, ctx);
    ATH_CHECK(clockHandle.isValid());

    if (clockHandle->phase() < -2.0) { // wrap around clock pahse so -pi goes to pi
      m_clock_phase = ((clockHandle->phase() + 2*3.14159) / 3.14159) * 12.5;
    } else {
      m_clock_phase = (clockHandle->phase() / 3.14159) * 12.5;
    }
  }
  
  // process all waveform data for all scintillator and calorimeter channels
  // Not all are guaranteed to exist, so fill the ones that are valid
  SG::ReadHandle<xAOD::WaveformHitContainer> vetoNuContainer { m_vetoNuContainer, ctx };
  if (vetoNuContainer.isValid()) {
    FillWaveBranches(*vetoNuContainer, isMC);
  }

  SG::ReadHandle<xAOD::WaveformHitContainer> vetoGmContainer { m_vetoGmContainer, ctx };
  if (vetoGmContainer.isValid()) {
    FillWaveBranches(*vetoGmContainer, isMC);
  }

  SG::ReadHandle<xAOD::WaveformHitContainer> vetoContainer { m_vetoContainer, ctx };
  if (vetoContainer.isValid()) {
    FillWaveBranches(*vetoContainer, isMC);
  }

  SG::ReadHandle<xAOD::WaveformHitContainer> triggerContainer { m_triggerContainer, ctx };
  if (triggerContainer.isValid()) {
    FillWaveBranches(*triggerContainer, isMC);
  }

  SG::ReadHandle<xAOD::WaveformHitContainer> preshowerContainer { m_preshowerContainer, ctx };
  if (preshowerContainer.isValid()) {
    FillWaveBranches(*preshowerContainer, isMC);
  }

  SG::ReadHandle<xAOD::WaveformHitContainer> muonContainer { m_muonContainer, ctx };
  if (muonContainer.isValid()) {
    FillWaveBranches(*muonContainer, isMC);
  }
  
  SG::ReadHandle<xAOD::WaveformHitContainer> ecalContainer { m_ecalContainer, ctx };
  if (ecalContainer.isValid()) {
    FillWaveBranches(*ecalContainer, isMC);
  }

  SG::ReadHandle<xAOD::WaveformHitContainer> ecal2Container { m_ecal2Container, ctx };
  if (ecal2Container.isValid()) {
    FillWaveBranches(*ecal2Container, isMC);
  }

  SG::ReadHandle<xAOD::WaveformHitContainer> caloNuContainer { m_caloNuContainer, ctx };
  if (caloNuContainer.isValid()) {
    FillWaveBranches(*caloNuContainer, isMC);
  }

  // Some things for real data
  if (!isMC) {
    // if real data, store charge in histograms from random events
    SG::ReadHandle<xAOD::FaserTriggerData> triggerData(m_FaserTriggerData, ctx);
    m_tap=triggerData->tap();

    // for random (only) triggers, store charge of scintillators in histograms
    if (m_tap == 16) {
      ATH_MSG_DEBUG("Filling random charge histogram");
      // Fill histograms
      for (unsigned int chan = 0; chan<max_chan; chan++) {
	// Only fill histograms that have been defined
	if (m_HistRandomCharge[chan]) {
	  ATH_MSG_DEBUG("Filling random charge histogram chan= " << chan);
	  m_HistRandomCharge[chan]->Fill(m_wave_raw_charge[chan]);
	}
      }
    }

    // Apply ntuple selection for real data
    if (m_doTrigFilter) {

      unsigned int tap=0;

      if (m_useLateTriggers) {
	// Must form tap from 8 input bits
	unsigned int curr_bits = triggerData->inputBits();
	unsigned int next_bits = triggerData->inputBitsNextClk();
	unsigned int inp_bits = curr_bits | next_bits;

	// Brute force this, want to combine bits 1|0 => 0, 3|2 => 1
	tap |= (0x01 & inp_bits);
	tap |= (0x01 & (inp_bits >> 1));
	tap |= (0x02 & (inp_bits >> 1));
	tap |= (0x02 & (inp_bits >> 2));
	tap |= (0x04 & (inp_bits >> 2));
	tap |= (0x04 & (inp_bits >> 3));
	tap |= (0x08 & (inp_bits >> 3));
	tap |= (0x08 & (inp_bits >> 4));
	  
      } else {
	// Classic use
	tap = triggerData->tap();
      }
      
      bool trig_coincidence_preshower_and_vetoes = ( tap&8 );
      bool trig_coincidence_timing_and_vetoesORpreshower = ( tap&4 && tap&2 );
      bool trig_calo = (tap & 1);

      if ( !(trig_coincidence_preshower_and_vetoes || trig_coincidence_timing_and_vetoesORpreshower || trig_calo) ) { 
        // don't process events that fail to activate coincidence triggers
        ATH_MSG_DEBUG("event did not pass trigger filter");
        return StatusCode::SUCCESS;
      }
    }
    
    if (m_doRandomFilter) {
      bool trig_random = m_tap & 16;
      if ( !(trig_random)) { 
        // don't process events that fail to activate random trigger
        ATH_MSG_DEBUG("event did not pass random trigger filter");
        return StatusCode::SUCCESS;
      }
    }

    if (m_doRandomOnlyFilter) {
      bool trig_random = m_tap == 16;
      if ( !(trig_random)) { 
        // don't process events that fail to activate random only trigger
        ATH_MSG_DEBUG("event did not pass random trigger filter");
        return StatusCode::SUCCESS;
      } 
    }

    if (m_doScintFilter) {
      // filter events, but use waveform peak cuts instead of triggers, as triggers could miss signals slightly out of time
      // digitizer channels described here: https://twiki.cern.ch/twiki/bin/viewauth/FASER/CaloScintillator
      // Make calorimeter trigger, use CaloHi if it exists
      bool calo_trig = false;
      if (m_wave_map.contains(std::string("calo2"))) {
	  for (auto chan : m_wave_map[std::string("calo2")]) {
	    calo_trig |= m_wave_raw_peak[chan] > 3.0;
	  }
      }
      else if (m_wave_map.contains(std::string("calo"))) {
	  for (auto chan : m_wave_map[std::string("calo")]) {
	    calo_trig |= m_wave_raw_peak[chan] > 3.0;
	  }
      }

      // VetoNu trigger
      bool vetoNu_trig = true;
      if (m_wave_map.contains(std::string("vetonu"))) {
	  for (auto chan : m_wave_map[std::string("vetonu")]) {
	    vetoNu_trig &= m_wave_raw_peak[chan] > 25.0;
	  }
      } else {
	vetoNu_trig = false;
      }

      // Veto Station 2
      bool vetoSt1_trig = true;
      bool vetoSt2_trig = true;
      if (m_wave_map.contains(std::string("veto"))) {
	int ncount = 0; 
	for (auto chan : m_wave_map[std::string("veto")]) {
	  if (++ncount < 3) {
	    vetoSt2_trig &= m_wave_raw_peak[chan] > 25.0;
	  } else {
	    vetoSt1_trig &= m_wave_raw_peak[chan] > 25.0;
	  }
	}
      } else if (m_wave_map.contains(std::string("veto1"))) {
	for (auto chan : m_wave_map[std::string("veto1")]) {
	  vetoSt1_trig &= m_wave_raw_peak[chan] > 25.0;
	}
	for (auto chan : m_wave_map[std::string("veto2")]) {
	  vetoSt2_trig &= m_wave_raw_peak[chan] > 25.0;
	}
      } else {
	vetoSt1_trig = false;
	vetoSt2_trig = false;
      }
      bool veto_OR_trig = vetoNu_trig || vetoSt1_trig || vetoSt2_trig;
      
      // Timing layer (either top or bottom)      
      bool timingScint_trig  = true;
      bool timingScint_trig1 = true;
      bool timingScint_trig2 = true;
      if (m_wave_map.contains(std::string("trigger"))) {
	int ncount = 0;
	for (auto chan : m_wave_map[std::string("trigger")]) {
	  if (++ncount < 3) {
	    timingScint_trig1 &= m_wave_raw_peak[chan] > 25.0;
	  } else {
	    timingScint_trig2 &= m_wave_raw_peak[chan] > 25.0;
	  }
	}
	timingScint_trig = timingScint_trig1 || timingScint_trig2;
      } else {
	timingScint_trig = false;
      }
      
      bool preshower_trig = true;
      if (m_wave_map.contains(std::string("preshower"))) {
	for (auto chan : m_wave_map[std::string("preshower")]) {
	  preshower_trig &= m_wave_raw_peak[chan] > 3.0;
	}
      } else {
	preshower_trig = false;
      }
      
      bool passes_ScintFilter = false;
      if (calo_trig) {
        passes_ScintFilter = true;
      } else if (veto_OR_trig && timingScint_trig) {
        passes_ScintFilter = true;
      } else if (veto_OR_trig && preshower_trig) {
        passes_ScintFilter = true;
      } else if (timingScint_trig && preshower_trig) {
        passes_ScintFilter = true;
      } 

      if (!passes_ScintFilter) {
        ATH_MSG_DEBUG("event did not pass scint filter");
        return StatusCode::SUCCESS; // only store events that pass filter
      }
    }

    if (m_doOverflowFilter) {
      bool overflow = false;

      // Go through every status word and look for an overflow
      // Any overflow will do...
      for (unsigned int i=0; i<max_chan; i++) {
	if (m_wave_status[i] & 4) { // Overflows
	  overflow = true;
	  break; // Seen enough
	}
      }
      
      if (!overflow) {
	ATH_MSG_DEBUG("event did not pass overflow filter");
	return StatusCode::SUCCESS; // only store events that pass filter
      }
    }

    // store trigger data in ntuple variables
    m_tbp=triggerData->tbp();
    m_tap=triggerData->tap();
    m_inputBits=triggerData->inputBits();
    m_inputBitsNext=triggerData->inputBitsNextClk();

    // load in LHC data
    SG::ReadHandle<xAOD::FaserLHCData> lhcData { m_lhcData, ctx };
    ATH_CHECK(lhcData.isValid());

    // don't process events that were not taken during "Stable Beams"
    if (!(lhcData->stableBeams()) && m_stableOnly) return StatusCode::SUCCESS;

    //If we are only looking for cosmic events then we only care about events
    //during beam modes "NO BEAM", "SETUP", "CYCLING", and "RAMP DOWN"
    if (m_cosmicsOnly)
    {
      if ((lhcData->beamMode() != "NO BEAM") && (lhcData->beamMode() != "SETUP") &&
          (lhcData->beamMode() != "CYCLING") && (lhcData->beamMode() != "RAMP DOWN"))
	{
	  ATH_MSG_DEBUG("fail cosmics check on beam mode " << lhcData->beamMode());
	  return StatusCode::SUCCESS;
	}
      ATH_MSG_DEBUG("pass the cosmics check on beam mode " << lhcData->beamMode());
    }

    // store interesting data in ntuple variables
    m_fillNumber = lhcData->fillNumber();
    m_betaStar = lhcData->betaStar();
    m_crossingAngle = lhcData->crossingAngle();
    m_distanceToCollidingBCID = lhcData->distanceToCollidingBCID();
    m_distanceToUnpairedB1 = lhcData->distanceToUnpairedB1();
    m_distanceToUnpairedB2 = lhcData->distanceToUnpairedB2();
    m_distanceToInboundB1 = lhcData->distanceToInboundB1();
    m_distanceToTrainStart = lhcData->distanceToTrainStart();
    m_distanceToPreviousColliding = lhcData->distanceToPreviousColliding();
    // debug print out all LHC data info available
    ATH_MSG_DEBUG("LHC data fillNumber = " << lhcData->fillNumber() );    
    ATH_MSG_DEBUG("LHC data machineMode = " << lhcData->machineMode() );
    ATH_MSG_DEBUG("LHC data beamMode = " << lhcData->beamMode() );
    ATH_MSG_DEBUG("LHC data beamType1 = " << lhcData->beamType1() );
    ATH_MSG_DEBUG("LHC data beamType2 = " << lhcData->beamType2() );
    ATH_MSG_DEBUG("LHC data betaStar = " << lhcData->betaStar() );
    ATH_MSG_DEBUG("LHC data crossingAngle = " << lhcData->crossingAngle() );
    ATH_MSG_DEBUG("LHC data stableBeams = " << lhcData->stableBeams() );
    ATH_MSG_DEBUG("LHC data injectionScheme = " << lhcData->injectionScheme() );
    ATH_MSG_DEBUG("LHC data numBunchBeam1 = " << lhcData->numBunchBeam1() );
    ATH_MSG_DEBUG("LHC data numBunchBeam2 = " << lhcData->numBunchBeam2() );
    ATH_MSG_DEBUG("LHC data numBunchColliding = " << lhcData->numBunchColliding() );
    ATH_MSG_DEBUG("LHC data distanceToCollidingBCID = " << lhcData->distanceToCollidingBCID() );
    ATH_MSG_DEBUG("LHC data distanceToUnpairedB1 = " << lhcData->distanceToUnpairedB1() );
    ATH_MSG_DEBUG("LHC data distanceToUnpairedB1 = " << lhcData->distanceToUnpairedB2() );
    ATH_MSG_DEBUG("LHC data distanceToInboundB1 = " << lhcData->distanceToInboundB1() );
    ATH_MSG_DEBUG("LHC data distanceToTrainStart = " << lhcData->distanceToTrainStart() );
    ATH_MSG_DEBUG("LHC data distanceToPreviousColliding = " << lhcData->distanceToPreviousColliding() );

  } // done with processing only on real data

  // fill scintHit word with bits that reflect if a scintillator was hit (1 = vetoNu0, 2 = vetoNu1, 4 = vetoSt1_1, 8 vetoSt2_0, 16 = vetoSt2_1, 32 = Timing scint, 64 = preshower0, 128 = preshower1)

  // This either needs to be updated to use cable map, or skipped
  // Skip for now
  // if (m_wave_raw_charge[4] > 40.0) {
  //   m_scintHit = m_scintHit | 1;
  // }
  // if (m_wave_raw_charge[5] > 40.0) {
  //   m_scintHit = m_scintHit | 2;
  // }
  // if (m_wave_raw_charge[14] > 40.0) {
  //   m_scintHit = m_scintHit | 4;
  // }
  // if (m_wave_raw_charge[6] > 40.0) {
  //   m_scintHit = m_scintHit | 8;
  // }
  // if (m_wave_raw_charge[7] > 40.0) {
  //   m_scintHit = m_scintHit | 16;
  // }
  // if (m_wave_raw_charge[8]+m_wave_raw_charge[9]+m_wave_raw_charge[10]+m_wave_raw_charge[11] > 25.0) {
  //   m_scintHit = m_scintHit | 32;
  // }
  // if (m_wave_raw_charge[12] > 2.5) {
  //   m_scintHit = m_scintHit | 64;
  // }
  // if (m_wave_raw_charge[13] > 2.5) {
  //   m_scintHit = m_scintHit | 128;
  // }

  if (isMC) { // if simulation find MC cross section and primary lepton
    // Work out effective cross section for MC
    SG::ReadHandle<xAOD::FaserEventInfo> faserEventInfo (m_faserEventInfoKey, ctx);
    if (faserEventInfo.isValid()) {
      m_crossingAngle = faserEventInfo->crossingAngle();
      m_isVerticalCrossingAngle = faserEventInfo->isVerticalCrossingAngle();
    }

    if (m_useFlukaWeights) {
      double flukaWeight = truthEventContainer->at(0)->weights()[0];
      ATH_MSG_ALWAYS("Found fluka weight = " << flukaWeight);
      m_crossSection = m_baseEventCrossSection * flukaWeight;
    } else if (m_useGenieWeights) {
      m_crossSection = m_baseEventCrossSection;
    } else {
      //ATH_MSG_WARNING("Monte carlo event with no weighting scheme specified.  Setting crossSection (weight) to " << m_baseEventCrossSection << " fb.");
      m_crossSection = m_baseEventCrossSection;
    }

    // Store event weights if exist
    const HepMC::GenEvent* genEvent = mcEventContainer->at(0);
    for (auto wt : genEvent->weights()) {
      m_genWeights.push_back(wt);
    }


    // Find truth particle information 
    SG::ReadHandle<xAOD::TruthParticleContainer> truthParticleContainer { m_truthParticleContainer, ctx };
    // std::cout << std::endl;
    // if (!truthParticleContainer.isValid())
    // {
    //   std::cout << "truthParticleContainer is not valid" << std::endl; 
    // }
    // else
    // {
    //   std::cout << "truthParticleContainer is valid with a size of " << truthParticleContainer->size() << std::endl;
    // }
    // std::cout << "barcodes of truths particles" << std::endl;
    // for (auto particle : *truthParticleContainer)
    // {
    //   std::cout << particle->barcode() << std::endl;
    // }
    // std::cout << truthParticleContainer->front()->barcode();
    // std::cout << std::endl;
    if (truthParticleContainer.isValid() && truthParticleContainer->size() > 0) {

      std::map<int,std::vector<FaserSiHit>> hitCountMap;
    
      //get simulated hits
      SG::ReadHandle<FaserSiHitCollection> siHitCollection(m_siHitCollectionKey, ctx);
      if (!siHitCollection.isValid()) {
        ATH_MSG_WARNING("FaserSiHitCollection not valid.");
      }
      
      // create map
      for(const FaserSiHit &hit : *siHitCollection){
        hitCountMap[hit.trackNumber()].push_back(hit);
      }
      
      //To do: identify whether the sample is A'
      int ipart(0);
      for (auto particle : *truthParticleContainer) { 	// loop over first 10 truth particles (for non A' samples)
        if (ipart++ > 9) break;
	
	int barcode = particle->barcode();
	
	//store hits of per truthParticle
        int truth_nHits = 0;
        int st0[3] = {0};
        int st1[3] = {0};
        int st2[3] = {0};
        int st3[3] = {0};

        if(hitCountMap.find(barcode) != hitCountMap.end()){
          truth_nHits = hitCountMap[barcode].size();
          for(auto hit : hitCountMap[barcode]){
            auto position = m_fiducialParticleTool->getGlobalPosition(hit);
            int stationID = hit.getStation();
            int layerID = hit.getPlane();
            if (layerID < 0 || layerID >= 3) {
	      ATH_MSG_INFO("Invalid layerID: " << layerID);
              continue;
            }
            switch (stationID) {

              case 0:
                st0[layerID]++;
                break;
              case 1:
                st1[layerID]++;
                break;
              case 2:
                st2[layerID]++;
                break;
              case 3:
                st3[layerID]++;
                break;
              default:
		ATH_MSG_INFO("Unexpected stationID: " << stationID);
                break;
            }
          }
        }
	  
	// get the particle hits on different station/layer. The vector size is the number of  particles
        for (int i = 0; i < 3; ++i) {
          m_st0[i].push_back(st0[i]);
          m_st1[i].push_back(st1[i]);
          m_st2[i].push_back(st2[i]);
          m_st3[i].push_back(st3[i]);
        }

	m_truth_barcode.push_back(barcode);
        m_truth_pdg.push_back(particle->pdgId());
	m_truth_nHits.push_back(truth_nHits);

        m_truth_P.push_back(particle->p4().P());
        m_truth_px.push_back(particle->px());
        m_truth_py.push_back(particle->py());
        m_truth_pz.push_back(particle->pz());
        m_truth_pT.push_back(particle->p4().Pt());
	m_truth_m.push_back(particle->m());
        m_truth_theta.push_back(particle->p4().Theta());
        m_truth_phi.push_back(particle->p4().Phi());
        m_truth_eta.push_back(particle->p4().Eta());
	m_truth_isFiducial.push_back(m_fiducialParticleTool->isFiducial(particle->barcode()));
	
	auto positions = m_fiducialParticleTool->getTruthPositions(particle->barcode()); // Add truth position information at each station
        for (int station = 0; station < 4; ++station) {
          m_truth_st_x[station].push_back(positions[station].x());
          m_truth_st_y[station].push_back(positions[station].y());
          m_truth_st_z[station].push_back(positions[station].z());
        }

        auto momenta = m_fiducialParticleTool->getTruthMomenta(particle->barcode()); //  Add truth momentum information at each station
        for (int station = 0; station < 4; ++station) {
          m_truth_st_px[station].push_back(momenta[station].x());
          m_truth_st_py[station].push_back(momenta[station].y());
          m_truth_st_pz[station].push_back(momenta[station].z());
        }
        
	if ( particle->hasProdVtx()) {
          m_truth_prod_x.push_back(particle->prodVtx()->x());
          m_truth_prod_y.push_back(particle->prodVtx()->y());
          m_truth_prod_z.push_back(particle->prodVtx()->z());
        } else {
          m_truth_prod_x.push_back(999999);
          m_truth_prod_y.push_back(999999);
          m_truth_prod_z.push_back(999999);
        }

        if ( particle->hasDecayVtx()) {
          m_truth_dec_x.push_back(particle->decayVtx()->x());
          m_truth_dec_y.push_back(particle->decayVtx()->y());
          m_truth_dec_z.push_back(particle->decayVtx()->z());
        } else {
          m_truth_dec_x.push_back(999999);
          m_truth_dec_y.push_back(999999);
          m_truth_dec_z.push_back(999999);
        }


        // Find the M d0 and d1 truth information for dark photon
        if ( particle->barcode() == 1 || particle->barcode() == 2 || particle->barcode() == 3 ) {
          auto positions = m_fiducialParticleTool->getTruthPositions(particle->barcode());
	  if ( particle->pdgId() == 32) { // mother particle (A')
            m_truthM_P.push_back(particle->p4().P());
            m_truthM_px.push_back(particle->p4().X());
            m_truthM_py.push_back(particle->p4().Y());
            m_truthM_pz.push_back(particle->p4().Z());
            m_truthM_isFiducial.push_back(m_fiducialParticleTool->isFiducial(particle->barcode()));

	    if ( particle->hasDecayVtx()) { // decay vertex for A' particle
              m_truthM_x.push_back(particle->decayVtx()->x());
              m_truthM_y.push_back(particle->decayVtx()->y());
              m_truthM_z.push_back(particle->decayVtx()->z());
            } else {
              m_truthM_x.push_back(999999);
              m_truthM_y.push_back(999999);
              m_truthM_z.push_back(999999);
            }
          }

          if ( (particle->pdgId() == 11) || (particle->pdgId() == 13) || (particle->pdgId() == 211) ) { // daughter particles (electron/muon/pion) 
            m_truthd0_P.push_back(particle->p4().P());
            m_truthd0_px.push_back(particle->p4().X());
            m_truthd0_py.push_back(particle->p4().Y());
            m_truthd0_pz.push_back(particle->p4().Z());
	    m_truthd0_isFiducial.push_back(m_fiducialParticleTool->isFiducial(particle->barcode()));
	    
	    if ( particle->hasProdVtx()) {
              m_truthd0_x.push_back(particle->prodVtx()->x());
              m_truthd0_y.push_back(particle->prodVtx()->y());
              m_truthd0_z.push_back(particle->prodVtx()->z());
            } else {
              m_truthd0_x.push_back(999999);
              m_truthd0_y.push_back(999999);
              m_truthd0_z.push_back(999999);
            }
	    for (int station = 1; station < 4; ++station) {
              m_truthd0_x.push_back(positions[station].x());
              m_truthd0_y.push_back(positions[station].y());
              m_truthd0_z.push_back(positions[station].z());
            }
          }
          if ( (particle->pdgId() == -11) || (particle->pdgId() == -13) || (particle->pdgId() == -211) ) { // daughter particles (positron/mu+/pi-)
          
            m_truthd1_P.push_back(particle->p4().P());
            m_truthd1_px.push_back(particle->p4().X());
            m_truthd1_py.push_back(particle->p4().Y());
            m_truthd1_pz.push_back(particle->p4().Z());
	    m_truthd1_isFiducial.push_back(m_fiducialParticleTool->isFiducial(particle->barcode()));

            if ( particle->hasProdVtx()) {
              m_truthd1_x.push_back(particle->prodVtx()->x());
              m_truthd1_y.push_back(particle->prodVtx()->y());
              m_truthd1_z.push_back(particle->prodVtx()->z());
            } else {
              m_truthd1_x.push_back(999999);
              m_truthd1_y.push_back(999999);
              m_truthd1_z.push_back(999999);
            }
            for (int station = 1; station < 4; ++station) {
              m_truthd1_x.push_back(positions[station].x());
              m_truthd1_y.push_back(positions[station].y());
              m_truthd1_z.push_back(positions[station].z());
            }
          }
        }
      }//end of all particle
    }//end of isValid
  }//end of isMC



  // load in calibrated calo container
  SG::ReadHandle<xAOD::CalorimeterHitContainer> ecalCalibratedContainer { m_ecalCalibratedContainer, ctx };
  if (ecalCalibratedContainer.isValid()) {
    for (auto hit : *ecalCalibratedContainer) {
      int ch=hit->channel();
      m_calibrated_nMIP[ch] = hit->Nmip();
      m_calibrated_E_dep[ch] = hit->E_dep(); 
      m_calibrated_E_EM[ch] = hit->E_EM();

      ATH_MSG_DEBUG("Calibrated calo: ch is " << ch
		  << ", edep is " << hit->E_dep()
		  << ", E_EM is " << hit->E_EM()
		  << ", Nmip is " << hit->Nmip()
		  << ", fit_to_raw_ratio is " << hit->fit_to_raw_ratio());
    
      if (m_dual_gain) {
	m_calolo_total_nMIP += hit->Nmip();
	m_calolo_total_E_dep += hit->E_dep();
	m_calolo_total_fit_E_EM += hit->E_EM();
	m_calolo_total_raw_E_EM += (hit->E_EM()*hit->fit_to_raw_ratio());
	
	if (m_wave_status[ch]&4) { // Overflows
	  m_calolo_total_E_EM += hit->E_EM();
	} else {
	  m_calolo_total_E_EM += (hit->E_EM()*hit->fit_to_raw_ratio());
	}
      } else {
	m_calo_total_nMIP += hit->Nmip();
	m_calo_total_E_dep += hit->E_dep();
	m_calo_total_fit_E_EM += hit->E_EM();
	m_calo_total_raw_E_EM += (hit->E_EM()*hit->fit_to_raw_ratio());
	
	if (m_wave_status[ch]&4) { // Overflows
	  m_calo_total_E_EM += hit->E_EM();
	} else {
	  m_calo_total_E_EM += (hit->E_EM()*hit->fit_to_raw_ratio());
	}

	// add a fudged energy variable that corrects the MC to agree with the testbeam results
	if (isMC) {
	  // Add fudge factor for MC
	  m_calo_total_fit_E_EM_fudged = m_calo_total_fit_E_EM * m_caloMC_FudgeFactor;
	  m_calo_total_raw_E_EM_fudged = m_calo_total_raw_E_EM * m_caloMC_FudgeFactor;
	  m_calo_total_E_EM_fudged = m_calo_total_E_EM * m_caloMC_FudgeFactor;
	} else {
	  // Unchanged in data
	  m_calo_total_fit_E_EM_fudged = m_calo_total_fit_E_EM;
	  m_calo_total_raw_E_EM_fudged = m_calo_total_raw_E_EM;
	  m_calo_total_E_EM_fudged = m_calo_total_E_EM;
	}
      }
    }

    //// the following is an example of how to access the linked waveform data from the calibrated data
    //auto measurements = &(hit->WaveformLinks())[0];
    //auto link_collections = measurements->getDataPtr();
    //auto link_collection = link_collections[0];
    //auto link_index = measurements->index();
    //auto link = link_collection[link_index];
    //if (link_collection != nullptr) {
    //  ATH_MSG_INFO("DEION TEST: wavelink status is " << link->hit_status() );
    //  ATH_MSG_INFO("DEION TEST: wavelink integral is " << link->integral() );
    //}
  }

  // load in calibrated calo2 container
  SG::ReadHandle<xAOD::CalorimeterHitContainer> ecal2CalibratedContainer { m_ecal2CalibratedContainer, ctx };
  if (ecal2CalibratedContainer.isValid()) {
    for (auto hit : *ecal2CalibratedContainer) {
      int ch=hit->channel();
      m_calibrated_nMIP[ch] = hit->Nmip();
      m_calibrated_E_dep[ch] = hit->E_dep(); 
      m_calibrated_E_EM[ch] = hit->E_EM();
      
      ATH_MSG_DEBUG("Calibrated calo: ch is " << ch
		    << ", edep is " << hit->E_dep()
		    << ", E_EM is " << hit->E_EM()
		    << ", Nmip is " << hit->Nmip()
		    << ", fit_to_raw_ratio is " << hit->fit_to_raw_ratio());
      
      m_calohi_total_nMIP += hit->Nmip();
      m_calohi_total_E_dep += hit->E_dep();
      m_calohi_total_fit_E_EM += hit->E_EM();
      m_calohi_total_raw_E_EM += (hit->E_EM()*hit->fit_to_raw_ratio());
      
      if (m_wave_status[ch]&4) { // Overflows
	m_calohi_total_E_EM += hit->E_EM();
      } else {
	m_calohi_total_E_EM += (hit->E_EM()*hit->fit_to_raw_ratio());
      }     
    }
  }
  
  // load in calibrated calo2 container
  SG::ReadHandle<xAOD::CalorimeterHitContainer> calonuCalibratedContainer { m_calonuCalibratedContainer, ctx };
  if (calonuCalibratedContainer.isValid()) {
    for (auto hit : *calonuCalibratedContainer) {
      int ch=hit->channel();
      m_calibrated_nMIP[ch] = hit->Nmip();
      m_calibrated_E_dep[ch] = hit->E_dep(); 
      m_calibrated_E_EM[ch] = hit->E_EM();
      
      ATH_MSG_DEBUG("Calibrated calo: ch is " << ch
		    << ", edep is " << hit->E_dep()
		    << ", E_EM is " << hit->E_EM()
		    << ", Nmip is " << hit->Nmip()
		    << ", fit_to_raw_ratio is " << hit->fit_to_raw_ratio());
      
      m_calonu_total_nMIP += hit->Nmip();
      m_calonu_total_E_dep += hit->E_dep();
      m_calonu_total_fit_E_EM += hit->E_EM();
      m_calonu_total_raw_E_EM += (hit->E_EM()*hit->fit_to_raw_ratio());
      
      if (m_wave_status[ch]&4) { // Overflows
	m_calonu_total_E_EM += hit->E_EM();
      } else {
	m_calonu_total_E_EM += (hit->E_EM()*hit->fit_to_raw_ratio());
      }     
    }
  }
  
  // load in calibrated preshower container
  SG::ReadHandle<xAOD::CalorimeterHitContainer> preshowerCalibratedContainer { m_preshowerCalibratedContainer, ctx };
  if (preshowerCalibratedContainer.isValid()) {
    for (auto hit : *preshowerCalibratedContainer) {
      int ch=hit->channel();
      m_calibrated_nMIP[ch] = hit->Nmip() * hit->fit_to_raw_ratio();
      m_calibrated_E_dep[ch] = hit->E_dep() * hit->fit_to_raw_ratio();
      
      m_preshower_total_nMIP += hit->Nmip() * hit->fit_to_raw_ratio();
      m_preshower_total_E_dep += hit->E_dep() * hit->fit_to_raw_ratio();
      
      ATH_MSG_DEBUG("Calibrated preshower: ch is " << ch << ", edep is " << hit->E_dep() << ", E_EM is " << hit->E_EM() << ", Nmip is " << hit->Nmip() << ", fit_to_raw_ratio is " << hit->fit_to_raw_ratio());
    }
  }
  
  // enforce blinding such that events that miss the veto layers and have a large calo signal are skipped and not in the output root file
  // Also blind events with two tracks that don't leave signal in the veto signals.
  // Only blind colliding BCIDs (+/- 1)

  // This needs to be fixed!!!
  bool blinded_event = false;
  if ((!isMC) && abs(m_distanceToCollidingBCID) <= 1) {
    if (m_wave_raw_charge[4] < 40.0 and m_wave_raw_charge[5] < 40.0 and m_wave_raw_charge[6] < 40.0 and m_wave_raw_charge[7] < 40.0 and m_wave_raw_charge[14] < 40.0) {  // channels 4 and 5 are vetoNu, channels 6,7, and 14 are veto 
      if ((m_calo_total_E_EM > m_blindingCaloThreshold ) || (m_longTracks == 2)) {  // energy is in MeV
        blinded_event = true;
      }
    }
  }

  if (blinded_event && m_doBlinding) {
    return StatusCode::SUCCESS;
  } else if (!blinded_event && m_onlyBlinded) {
    return StatusCode::SUCCESS;
  }

  SG::ReadHandle<xAOD::EventInfo> eventInfo (m_eventInfoKey, ctx);  
  if (eventInfo->errorState(xAOD::EventInfo_v1::SCT) == xAOD::EventInfo::Error) {
    m_propagationError = 1;
    ATH_MSG_DEBUG("NtupleDumper: xAOD::EventInfo::SCT::Error");
  } else {
    m_propagationError = 0;
  }

  // get geometry context
  FaserActsGeometryContext faserGeometryContext = m_trackingGeometryTool->getNominalGeometryContext();
  auto gctx = faserGeometryContext.context();

  // Write out all truth particle barcodes that have a momentum larger than MinMomentum (default is 50 GeV)
  std::map<int, size_t> truthParticleCount {};
  if (isMC) {
    SG::ReadHandle<xAOD::TruthParticleContainer> truthParticleContainer { m_truthParticleContainer, ctx };
    ATH_CHECK(truthParticleContainer.isValid() && truthParticleContainer->size() > 0);
    for (const xAOD::TruthParticle *tp : *truthParticleContainer) {
      if (tp->p4().P() > m_minMomentum)
        truthParticleCount[tp->barcode()] = 0;
    }
  }

  // Calculation of the reduced VetoNu charge
  // Expand Veto2 channels across single/dual digitizer layouts (6, 7 -> 22, 23 during 2024 CaloNu)
  std::list<int> vetoChannels = {6, 7, 22, 23};
  if (m_wave_map.contains(std::string("veto2"))) {
    for (int ch : m_wave_map[std::string("veto2")]) {
      if (std::find(vetoChannels.begin(), vetoChannels.end(), ch) == vetoChannels.end()) {
        vetoChannels.push_back(ch);
      }
    }
  }
  float vetoLocalTime = NaN;
  if (vetoContainer.isValid()) {
    vetoLocalTime = get_mean_scintillator_time(vetoChannels, *vetoContainer);
  }

  // Primary Preshower top PMTs {12, 13} only (exclude 2025+ low-gain bottom PMTs {24, 25})
  const std::list<int> preshowerChannels = {12, 13};
  float preshowerLocalTime = NaN;
  if (!m_disablePreshowerFallback && preshowerContainer.isValid()) {
    preshowerLocalTime = get_mean_scintillator_time(preshowerChannels, *preshowerContainer);
  }

  // Trigger/Timing station {8, 9, 10, 11} secondary fallback if both Veto2 and Preshower fail
  std::list<int> triggerChannels = {8, 9, 10, 11};
  if (m_wave_map.contains(std::string("trigger"))) {
    triggerChannels = m_wave_map[std::string("trigger")];
  }
  float triggerLocalTime = NaN;
  if (triggerContainer.isValid()) {
    triggerLocalTime = get_mean_scintillator_time(triggerChannels, *triggerContainer);
  }

  // Resolve period-aware station localtime offsets unless overridden by Gaudi properties
  double vvDiff = m_veto_vetoNu_timeDiff;
  double vtDiff = m_trigger_vetoNu_timeDiff;
  double vpDiff = m_preshower_vetoNu_timeDiff;
  if (isMC) {
    if (vvDiff < 0.0) vvDiff = 27.21;
    if (vtDiff < 0.0) vtDiff = 32.43;
    if (vpDiff < 0.0) vpDiff = 51.41;
  } else if (m_run_number >= 15821 && m_run_number <= 16924) {
    if (vvDiff < 0.0) vvDiff = 35.783;
    if (vtDiff < 0.0) vtDiff = 34.872;
    if (vpDiff < 0.0) vpDiff = 53.512;
  } else if (m_run_number >= 18500) {
    if (vvDiff < 0.0) vvDiff = 33.166;
    if (vtDiff < 0.0) vtDiff = 34.930;
    if (vpDiff < 0.0) vpDiff = 13.330;
  } else {
    if (vvDiff < 0.0) vvDiff = 33.165;
    if (vtDiff < 0.0) vtDiff = 34.725;
    if (vpDiff < 0.0) vpDiff = 53.625;
  }

  float expVetoNuLocalTime = NaN;
  if (!std::isnan(vetoLocalTime)) {
    expVetoNuLocalTime = vetoLocalTime - static_cast<float>(vvDiff);
  } else if (!std::isnan(preshowerLocalTime)) {
    expVetoNuLocalTime = preshowerLocalTime - static_cast<float>(vpDiff);
  } else if (!std::isnan(triggerLocalTime)) {
    expVetoNuLocalTime = triggerLocalTime - static_cast<float>(vtDiff);
  }

  m_vetonu_reduced_charge[0] = -1.0f;
  m_vetonu_reduced_charge[1] = -1.0f;
  if (!std::isnan(expVetoNuLocalTime) && vetoNuContainer.isValid()) {
    std::list<int> vetoNuChannels = {4, 5};
    if (m_wave_map.contains(std::string("vetonu")) && m_wave_map[std::string("vetonu")].size() == 2) {
      vetoNuChannels = m_wave_map[std::string("vetonu")];
    }
    const int ch0 = vetoNuChannels.front();
    const int ch1 = vetoNuChannels.back();
    bool good_vetoNu_hit[2]{false, false};
    for (const xAOD::WaveformHit *hit : *vetoNuContainer) {
      const int ch = hit->channel();
      if (ch != ch0 && ch != ch1) continue;
      const size_t idx = (ch == ch0) ? 0 : 1;
      if (((hit->hit_status() & 2) == 0) || !good_vetoNu_hit[idx]) {
        good_vetoNu_hit[idx] = true;
        const std::vector<float>& vetoNuTimeVector = hit->time_vector();
        const std::vector<float>& vetoNuWaveVector = hit->wave_vector();
        if (vetoNuTimeVector.size() != vetoNuWaveVector.size()) {
          ATH_MSG_ERROR("Time and Wave vector have to have same size.");
          return StatusCode::FAILURE;
        }
        // Sum up the waveform values up to the expected local time plus a time window
        // which covers the tail of the Crystal Ball function
        float q = 0.0f;
        for (size_t i = 0; i < vetoNuTimeVector.size(); i++) {
          if (vetoNuTimeVector[i] < expVetoNuLocalTime + m_reducedChargeIntegrationTime) {
            q += vetoNuWaveVector[i];
          } else {
            break;
          }
        }
        q *= m_int_to_charge;
        // Guard rare truncated waveforms returning 0 pC despite large raw charge
        if (!isMC && m_run_number >= 12000 && q == 0.0f && m_wave_raw_charge[ch] > 30.0f) {
          m_vetonu_reduced_charge[idx] = -1.0f;
        } else {
          m_vetonu_reduced_charge[idx] = q;
        }
      }
    }
  }

  // loop over all reconstructed tracks and use only the tracks that have hits in all three tracking stations (excludes IFT)
  // store track parameters at most upstream measurement and at most downstream measurement
  // extrapolate track to all scintillator positions and store extrapolated position and angle
  SG::ReadHandle<TrackCollection> trackCollection;
  if (m_useIFT) {
    SG::ReadHandle<TrackCollection> tc {m_trackCollection, ctx}; // use track collection that includes IFT
    trackCollection = tc;
  } else {
    SG::ReadHandle<TrackCollection> tc {m_trackCollectionWithoutIFT, ctx}; // use track collection that excludes IFT
    trackCollection = tc;
  }
  ATH_CHECK(trackCollection.isValid());

  // create list of good tracks in fiducial region (r < 95mm) and chi2/nDoF < 25, #Layers >= 7, #Hits >= 12
  std::vector<const Trk::Track*> goodTracks {};
  for (const Trk::Track* track : *trackCollection)
  {
    if (track == nullptr) continue;

    std::set<std::pair<int, int>> layerMap;
    std::set<int> stationMap;
    // Check for hit in the three downstream stations
    HitSet hitSet {24};
    for (auto measurement : *(track->measurementsOnTrack())) {
        const Tracker::FaserSCT_ClusterOnTrack* cluster = dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(measurement);
        if (cluster != nullptr) {
            Identifier id = cluster->identify();
            int station = m_sctHelper->station(id);
            int layer = m_sctHelper->layer(id);
            int side = m_sctHelper->side(id);
            stationMap.emplace(station);
            layerMap.emplace(station, layer);
            hitSet.set(23 - (station * 6 + layer * 2 + side));
        }
    }

    m_hitSet.push_back(hitSet.to_ulong());
    m_nMeasurements.push_back((track->measurementsOnTrack())->size());

    if (stationMap.count(1) == 0 || stationMap.count(2) == 0 || stationMap.count(3) == 0) continue;
    
    const Trk::TrackParameters* upstreamParameters = track->trackParameters()->front();
    const Trk::TrackParameters* downstreamParameters = track->trackParameters()->back();

    if ((upstreamParameters == nullptr) || (downstreamParameters == nullptr)) continue;

	  m_nLayers.push_back(layerMap.size());

    m_Chi2.push_back(track->fitQuality()->chiSquared());
    m_DoF.push_back(track->fitQuality()->numberDoF());
    const Trk::MeasurementBase *measurement = track->measurementsOnTrack()->front();
    const Tracker::FaserSCT_ClusterOnTrack* cluster =
      dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(measurement);
    Identifier id = cluster->identify();
    m_module_eta0.push_back(m_sctHelper->eta_module(id));
    m_module_phi0.push_back(m_sctHelper->phi_module(id));

    m_nHit0.push_back(stationMap.count(0));
    m_nHit1.push_back(stationMap.count(1));
    m_nHit2.push_back(stationMap.count(2));
    m_nHit3.push_back(stationMap.count(3));

    m_charge.push_back( (int) upstreamParameters->charge() );

    m_xup.push_back(upstreamParameters->position().x());
    m_yup.push_back(upstreamParameters->position().y());
    m_zup.push_back(upstreamParameters->position().z());
    m_pxup.push_back(upstreamParameters->momentum().x());
    m_pyup.push_back(upstreamParameters->momentum().y());
    m_pzup.push_back(upstreamParameters->momentum().z());
    m_pup.push_back(sqrt( pow(upstreamParameters->momentum().x(),2) + pow(upstreamParameters->momentum().y(),2) + pow(upstreamParameters->momentum().z(),2) ));

    m_xdown.push_back(downstreamParameters->position().x());
    m_ydown.push_back(downstreamParameters->position().y());
    m_zdown.push_back(downstreamParameters->position().z());
    m_pxdown.push_back(downstreamParameters->momentum().x());
    m_pydown.push_back(downstreamParameters->momentum().y());
    m_pzdown.push_back(downstreamParameters->momentum().z());
    m_pdown.push_back(sqrt( pow(downstreamParameters->momentum().x(),2) + pow(downstreamParameters->momentum().y(),2) + pow(downstreamParameters->momentum().z(),2) ));

    // find and store the position of the measurement on track with the largest radius
    double maxRadius = 0;
    Amg::Vector3D positionAtMaxRadius {};
    for (const Trk::TrackParameters* trackParameters : *track->trackParameters()) {
      if (radius(trackParameters->position()) > maxRadius) {
        maxRadius = radius(trackParameters->position());
        positionAtMaxRadius = trackParameters->position();
      }
    }
    m_r_atMaxRadius.push_back(maxRadius);
    m_x_atMaxRadius.push_back(positionAtMaxRadius.x());
    m_y_atMaxRadius.push_back(positionAtMaxRadius.y());
    m_z_atMaxRadius.push_back(positionAtMaxRadius.z());

    if ((m_Chi2.back() / m_DoF.back() < m_maxChi2NDOF) &&
        (m_nLayers.back() >= m_minLayers) &&
        (m_DoF.back() + 5 >= m_minHits) &&
        (m_r_atMaxRadius.back() < 95)) {
      goodTracks.push_back(track);
    }

    //Labled whether the track was made with forward or backward tracking
    if (m_trackType == "forward")
    {
      //All tracks in a forward track collection are forward tracking
      m_isForward.push_back(true);
    }
    else if (m_trackType == "backward")
    {
      //All tracks in a backward track collection are backward tracking
      m_isForward.push_back(false);
    }
    else if (m_trackType == "merge")
    {
      //In the case of merge tracking we need to check the track info
      //if track fitter is KalmanFitter then it is forward
      //if track fitter is Unknown then it is backward
      //everything else is an error case
      if (track->info().trackFitter() == Trk::TrackInfo::TrackFitter::KalmanFitter)
      {
        m_isForward.push_back(true);
      }
      else if (track->info().trackFitter() == Trk::TrackInfo::TrackFitter::Unknown)
      {
        m_isForward.push_back(false);
      }
      else
      {
        ATH_MSG_INFO("NtupleDumper: track marked with neither forward or backward tracking");
      }
    }
    else
    {
      ATH_MSG_INFO("NtupleDumper: Invalid track type given");
    }
    
    if (isMC) { // if simulation, store track truth info as well

      auto [truthParticle, hitCount] = m_trackTruthMatchingTool->getTruthParticle(track);
      if (truthParticle != nullptr) {
        if (truthParticleCount.count(truthParticle->barcode()) > 0)
          truthParticleCount[truthParticle->barcode()] += 1;
        m_t_pdg.push_back(truthParticle->pdgId());
        m_t_barcode.push_back(truthParticle->barcode());
        if (truthParticle->nParents() > 0){
          m_t_pdg_parent.push_back(truthParticle->parent(0)->pdgId());
          m_t_barcode_parent.push_back(truthParticle->parent(0)->barcode());
        } else {
          m_t_pdg_parent.push_back(0);
          m_t_barcode_parent.push_back(-1);
        }
        // the track fit eats up 5 degrees of freedom, thus the number of hits on track is m_DoF + 5
        m_t_truthHitRatio.push_back(hitCount / (m_DoF.back() + 5));
        m_isFiducial.push_back(m_fiducialParticleTool->isFiducial(truthParticle->barcode()));
        auto positions = m_fiducialParticleTool->getTruthPositions(truthParticle->barcode());
        for (int station = 0; station < 4; ++station) {
          m_t_st_x[station].push_back(positions[station].x());
          m_t_st_y[station].push_back(positions[station].y());
          m_t_st_z[station].push_back(positions[station].z());
        }
        
        auto momenta = m_fiducialParticleTool->getTruthMomenta(truthParticle->barcode());
        for (int station = 0; station < 4; ++station) {
          m_t_st_px[station].push_back(momenta[station].x());
          m_t_st_py[station].push_back(momenta[station].y());
          m_t_st_pz[station].push_back(momenta[station].z());
        }

        if (truthParticle->hasProdVtx()) {
          m_t_prodVtx_x.push_back(truthParticle->prodVtx()->x());
          m_t_prodVtx_y.push_back(truthParticle->prodVtx()->y());
          m_t_prodVtx_z.push_back(truthParticle->prodVtx()->z());
        } else {
          m_t_prodVtx_x.push_back(999999);
          m_t_prodVtx_y.push_back(999999);
          m_t_prodVtx_z.push_back(999999);
        }
        if (truthParticle->hasDecayVtx()) {
          m_t_decayVtx_x.push_back(truthParticle->decayVtx()->x());
          m_t_decayVtx_y.push_back(truthParticle->decayVtx()->y());
          m_t_decayVtx_z.push_back(truthParticle->decayVtx()->z());
        } else {
          m_t_decayVtx_x.push_back(999999);
          m_t_decayVtx_y.push_back(999999);
          m_t_decayVtx_z.push_back(999999);
        }
        m_t_px.push_back(truthParticle->px());
        m_t_py.push_back(truthParticle->py());
        m_t_pz.push_back(truthParticle->pz());
        m_t_theta.push_back(truthParticle->p4().Theta());
        m_t_phi.push_back(truthParticle->p4().Phi());
        // std::cout << "Filling t_P with " << truthParticle->p4().P() << std::endl;
        m_t_p.push_back(truthParticle->p4().P());
        m_t_pT.push_back(truthParticle->p4().Pt());
        m_t_eta.push_back(truthParticle->p4().Eta());
      } else {
        ATH_MSG_WARNING("Can not find truthParticle.");
        // std::cout << "Not finding truth partices" << std::endl;
        clearTrackTruth();
      }
    } else {
      // std::cout << "isMC is false" << std::endl;
      clearTrackTruth();
    }

    // fill extrapolation vectors with dummy values, will get set to real number if the track extrapolation succeeds
    m_xVetoNu.push_back(999999);
    m_yVetoNu.push_back(999999);
    m_thetaxVetoNu.push_back(999999);
    m_thetayVetoNu.push_back(999999);
    m_xVetoStation1.push_back(999999);
    m_yVetoStation1.push_back(999999);
    m_thetaxVetoStation1.push_back(999999);
    m_thetayVetoStation1.push_back(999999);
    m_xVetoStation2.push_back(999999);
    m_yVetoStation2.push_back(999999);
    m_thetaxVetoStation2.push_back(999999);
    m_thetayVetoStation2.push_back(999999);
    m_xTrig.push_back(999999);
    m_yTrig.push_back(999999);
    m_thetaxTrig.push_back(999999);
    m_thetayTrig.push_back(999999);
    m_xPreshower1.push_back(999999);
    m_yPreshower1.push_back(999999);
    m_thetaxPreshower1.push_back(999999);
    m_thetayPreshower1.push_back(999999);
    m_xPreshower2.push_back(999999);
    m_yPreshower2.push_back(999999);
    m_thetaxPreshower2.push_back(999999);
    m_thetayPreshower2.push_back(999999);
    m_xCalo.push_back(999999);
    m_yCalo.push_back(999999);
    m_thetaxCalo.push_back(999999);
    m_thetayCalo.push_back(999999);

    // Define paramters for track extrapolation from most upstream measurement
    Amg::Vector3D position_up = upstreamParameters->position();
    Amg::Vector3D momentum_up = upstreamParameters->momentum();
    Acts::BoundVector params_up = Acts::BoundVector::Zero();
    params_up[Acts::eBoundLoc0] = -position_up.y();
    params_up[Acts::eBoundLoc1] = position_up.x();
    params_up[Acts::eBoundPhi] = momentum_up.phi();
    params_up[Acts::eBoundTheta] = momentum_up.theta();
    params_up[Acts::eBoundQOverP] = upstreamParameters->charge() / (momentum_up.mag() * 1_MeV);
    params_up[Acts::eBoundTime] = 0;

    Acts::BoundSquareMatrix cov = Acts::BoundSquareMatrix::Zero();
    cov(Acts::eBoundLoc0, Acts::eBoundLoc0) = 1;
    cov(Acts::eBoundLoc1, Acts::eBoundLoc1) = 1;
    cov(Acts::eBoundPhi, Acts::eBoundPhi) = 1;
    cov(Acts::eBoundTheta, Acts::eBoundTheta) = 1;
    cov(Acts::eBoundQOverP, Acts::eBoundQOverP) = 1;
    cov(Acts::eBoundTime, Acts::eBoundTime) = 1;


    auto startSurface_up = Acts::Surface::makeShared<Acts::PlaneSurface>(Acts::Vector3(0, 0, position_up.z()), Acts::Vector3(0, 0, 1));
    Acts::BoundTrackParameters startParameters_up(std::move(startSurface_up), params_up, cov, Acts::ParticleHypothesis::muon());

    // Define paramters for track extrapolation from most downstream measurement
    Amg::Vector3D position_down = downstreamParameters->position();
    Amg::Vector3D momentum_down = downstreamParameters->momentum();
    Acts::BoundVector params_down = Acts::BoundVector::Zero();
    params_down[Acts::eBoundLoc0] = -position_down.y();
    params_down[Acts::eBoundLoc1] = position_down.x();
    params_down[Acts::eBoundPhi] = momentum_down.phi();
    params_down[Acts::eBoundTheta] = momentum_down.theta();
    params_down[Acts::eBoundQOverP] = downstreamParameters->charge() / (momentum_down.mag() * 1_MeV);
    params_down[Acts::eBoundTime] = 0;
    auto startSurface_down = Acts::Surface::makeShared<Acts::PlaneSurface>(Acts::Vector3(0, 0, position_down.z()), Acts::Vector3(0, 0, 1));
    Acts::BoundTrackParameters startParameters_down(std::move(startSurface_down), params_down, cov, Acts::ParticleHypothesis::muon());

    // Extrapolate track to scintillators
    auto targetSurface_VetoNu = Acts::Surface::makeShared<Acts::PlaneSurface>(Acts::Vector3(0, 0, -3112.0), Acts::Vector3(0, 0, 1)); // -3112 mm is z position of VetoNu planes touching
    std::optional<const Acts::BoundTrackParameters> targetParameters_VetoNu =m_extrapolationTool->propagate(ctx, startParameters_up, *targetSurface_VetoNu, Acts::Direction::Backward);

    if (targetParameters_VetoNu) {
      auto targetPosition_VetoNu = targetParameters_VetoNu->position(gctx);
      auto targetMomentum_VetoNu = targetParameters_VetoNu->momentum();
      m_xVetoNu[m_longTracks] = targetPosition_VetoNu.x();
      m_yVetoNu[m_longTracks] = targetPosition_VetoNu.y();
      m_thetaxVetoNu[m_longTracks] = atan(targetMomentum_VetoNu[0]/targetMomentum_VetoNu[2]);
      m_thetayVetoNu[m_longTracks] = atan(targetMomentum_VetoNu[1]/targetMomentum_VetoNu[2]);
    } else {
      ATH_MSG_INFO("vetoNu null targetParameters");
    }

    auto targetSurface_Veto1 = Acts::Surface::makeShared<Acts::PlaneSurface>(Acts::Vector3(0, 0, -1769.65), Acts::Vector3(0, 0, 1)); // -1769.65 mm is z position of center of operational layer in Veto station 1
    std::optional<const Acts::BoundTrackParameters> targetParameters_Veto1 =m_extrapolationTool->propagate(ctx, startParameters_up, *targetSurface_Veto1, Acts::Direction::Backward);
    
    if (targetParameters_Veto1) {
      auto targetPosition_Veto1 = targetParameters_Veto1->position(gctx);
      auto targetMomentum_Veto1 = targetParameters_Veto1->momentum();
      m_xVetoStation1[m_longTracks] = targetPosition_Veto1.x();
      m_yVetoStation1[m_longTracks] = targetPosition_Veto1.y();
      m_thetaxVetoStation1[m_longTracks] = atan(targetMomentum_Veto1[0]/targetMomentum_Veto1[2]);
      m_thetayVetoStation1[m_longTracks] = atan(targetMomentum_Veto1[1]/targetMomentum_Veto1[2]);
    } else {
      ATH_MSG_INFO("veto1 null targetParameters");
    }

    auto targetSurface_Veto2 = Acts::Surface::makeShared<Acts::PlaneSurface>(Acts::Vector3(0, 0, -1609.65), Acts::Vector3(0, 0, 1)); // -1609.65 mm is z position of where planes touch in Veto station 2
    std::optional<const Acts::BoundTrackParameters> targetParameters_Veto2 =m_extrapolationTool->propagate(ctx, startParameters_up, *targetSurface_Veto2, Acts::Direction::Backward);
    
    if (targetParameters_Veto2) {
      auto targetPosition_Veto2 = targetParameters_Veto2->position(gctx);
      auto targetMomentum_Veto2 = targetParameters_Veto2->momentum();
      m_xVetoStation2[m_longTracks] = targetPosition_Veto2.x();
      m_yVetoStation2[m_longTracks] = targetPosition_Veto2.y();
      m_thetaxVetoStation2[m_longTracks] = atan(targetMomentum_Veto2[0]/targetMomentum_Veto2[2]);
      m_thetayVetoStation2[m_longTracks] = atan(targetMomentum_Veto2[1]/targetMomentum_Veto2[2]);
    } else {
      ATH_MSG_INFO("veto2 null targetParameters");
    }

    auto targetSurface_Trig = Acts::Surface::makeShared<Acts::PlaneSurface>(Acts::Vector3(0, 0, 0.0), Acts::Vector3(0, 0, 1)); // 0 mm is z position of Trig planes overlapping
    std::optional<const Acts::BoundTrackParameters> targetParameters_Trig =m_extrapolationTool->propagate(ctx, startParameters_up, *targetSurface_Trig, Acts::Direction::Backward); // must extrapolate backsards to trig plane if track starts in station 1
    
    if (targetParameters_Trig) {
      auto targetPosition_Trig = targetParameters_Trig->position(gctx);
      auto targetMomentum_Trig = targetParameters_Trig->momentum();
      m_xTrig[m_longTracks] = targetPosition_Trig.x();
      m_yTrig[m_longTracks] = targetPosition_Trig.y();
      m_thetaxTrig[m_longTracks] = atan(targetMomentum_Trig[0]/targetMomentum_Trig[2]);
      m_thetayTrig[m_longTracks] = atan(targetMomentum_Trig[1]/targetMomentum_Trig[2]);
    } else {
      ATH_MSG_INFO("Trig null targetParameters");
    }

    auto targetSurface_Preshower1 = Acts::Surface::makeShared<Acts::PlaneSurface>(Acts::Vector3(0, 0, 2582.68), Acts::Vector3(0, 0, 1)); // 2582.68  mm is z position of center of upstream preshower layer
    std::optional<const Acts::BoundTrackParameters> targetParameters_Preshower1 =m_extrapolationTool->propagate(ctx, startParameters_down, *targetSurface_Preshower1, Acts::Direction::Forward);
    
    if (targetParameters_Preshower1) {
      auto targetPosition_Preshower1 = targetParameters_Preshower1->position(gctx);
      auto targetMomentum_Preshower1 = targetParameters_Preshower1->momentum();
      m_xPreshower1[m_longTracks] = targetPosition_Preshower1.x();
      m_yPreshower1[m_longTracks] = targetPosition_Preshower1.y();
      m_thetaxPreshower1[m_longTracks] = atan(targetMomentum_Preshower1[0]/targetMomentum_Preshower1[2]);
      m_thetayPreshower1[m_longTracks] = atan(targetMomentum_Preshower1[1]/targetMomentum_Preshower1[2]);
    } else {
      ATH_MSG_INFO("Preshower1 null targetParameters");
    }

    auto targetSurface_Preshower2 = Acts::Surface::makeShared<Acts::PlaneSurface>(Acts::Vector3(0, 0, 2657.68), Acts::Vector3(0, 0, 1)); // 2657.68  mm is z position of center of downstream preshower layer
    std::optional<const Acts::BoundTrackParameters> targetParameters_Preshower2 =m_extrapolationTool->propagate(ctx, startParameters_down, *targetSurface_Preshower2, Acts::Direction::Forward);
    
    if (targetParameters_Preshower2) {
      auto targetPosition_Preshower2 = targetParameters_Preshower2->position(gctx);
      auto targetMomentum_Preshower2 = targetParameters_Preshower2->momentum();
      m_xPreshower2[m_longTracks] = targetPosition_Preshower2.x();
      m_yPreshower2[m_longTracks] = targetPosition_Preshower2.y();
      m_thetaxPreshower2[m_longTracks] = atan(targetMomentum_Preshower2[0]/targetMomentum_Preshower2[2]);
      m_thetayPreshower2[m_longTracks] =  atan(targetMomentum_Preshower2[1]/targetMomentum_Preshower2[2]);
    } else {
      ATH_MSG_INFO("Preshower2 null targetParameters");
    }

    auto targetSurface_Calo = Acts::Surface::makeShared<Acts::PlaneSurface>(Acts::Vector3(0, 0, 2760.0), Acts::Vector3(0, 0, 1)); // 2760  mm is estimated z position of calorimeter face
    std::optional<const Acts::BoundTrackParameters> targetParameters_Calo =m_extrapolationTool->propagate(ctx, startParameters_down, *targetSurface_Calo, Acts::Direction::Forward);
    
    if (targetParameters_Calo) {
      auto targetPosition_Calo = targetParameters_Calo->position(gctx);
      auto targetMomentum_Calo = targetParameters_Calo->momentum();
      m_xCalo[m_longTracks] = targetPosition_Calo.x();
      m_yCalo[m_longTracks] = targetPosition_Calo.y();
      m_thetaxCalo[m_longTracks] = atan(targetMomentum_Calo[0]/targetMomentum_Calo[2]) ;
      m_thetayCalo[m_longTracks] = atan(targetMomentum_Calo[1]/targetMomentum_Calo[2]) ;
    } else {
      ATH_MSG_INFO("Calo null targetParameters");
    }
    
    m_longTracks++;
  } //end loop over tracks
  // std::cout << "number of reco tracks: " << m_longTracks << std::endl; 

  // Clear old vertex values
  m_vertex_x = 0.;
  m_vertex_y = 0.;
  m_vertex_z = 0.;
  m_vertex_chi2 = -1.;
  m_vertex_px0 = 0.;
  m_vertex_py0 = 0.;
  m_vertex_pz0 = 0.;
  m_vertex_p0 = 0.;
  m_vertex_px1 = 0.;
  m_vertex_py1 = 0.;
  m_vertex_pz1 = 0.;
  m_vertex_p1 = 0.;

  if (m_runVertexing && goodTracks.size() >= 2) {
    m_two_tracks ++;
    
    // sort tracks by momentum and reconstruct vertex
    std::sort(goodTracks.begin(), goodTracks.end(), [](const Trk::Track *lhs, const Trk::Track *rhs){
      return lhs->trackParameters()->front()->momentum().z() < rhs->trackParameters()->front()->momentum().z();
    });
    std::vector<const Trk::Track*> lowMomentumTracks {goodTracks[0], goodTracks[1]};

    std::optional<FaserTracking::POCA> vertex = m_vertexingTool->getVertex(lowMomentumTracks);
    if (vertex) {
      Eigen::Vector3d position = vertex->position;
      m_vertex_x = position.x();
      m_vertex_y = position.y();
      m_vertex_z = position.z();
      m_vertex_chi2 = vertex->chi2;
      m_verticies++;
      
      // get track parameters of two tracks with lowest momentum at vertex
      auto vertexTrackParameters0 = m_vertexingTool->extrapolateTrack(goodTracks[0], m_vertex_z);
      if (vertexTrackParameters0) {
	// convert momentum from GeV to MeV
	m_vertex_px0 = vertexTrackParameters0->momentum().x() * 1e3;
	m_vertex_py0 = vertexTrackParameters0->momentum().y() * 1e3;
	m_vertex_pz0 = vertexTrackParameters0->momentum().z() * 1e3;
	m_vertex_p0 = std::sqrt(m_vertex_px0*m_vertex_px0 + m_vertex_py0*m_vertex_py0 + m_vertex_pz0*m_vertex_pz0);
      }
      auto vertexTrackParameters1 = m_vertexingTool->extrapolateTrack(goodTracks[1], m_vertex_z);
      if (vertexTrackParameters1) {
	// convert momentum from GeV to MeV
	m_vertex_px1 = vertexTrackParameters1->momentum().x() * 1e3;
	m_vertex_py1 = vertexTrackParameters1->momentum().y() * 1e3;
	m_vertex_pz1 = vertexTrackParameters1->momentum().z() * 1e3;
	m_vertex_p1 = std::sqrt(m_vertex_px1*m_vertex_px1 + m_vertex_py1*m_vertex_py1 + m_vertex_pz1*m_vertex_pz1);
      }
    }
  }

  if (!isMC) {
    if (m_doTrackFilter) { // filter events: colliding bunches have at least one long track, non-colliding bunches have at least one long track or one calo module with raw_peak > 3 mV
      if (m_longTracks == 0 && abs(m_distanceToCollidingBCID) <= 1) {
        return StatusCode::SUCCESS;
      } else if (abs(m_distanceToCollidingBCID) > 1) {
        if (!(m_longTracks > 0 || m_wave_raw_peak[0] > 3.0 || m_wave_raw_peak[1] > 3.0 || m_wave_raw_peak[2] > 3.0 || m_wave_raw_peak[3] > 3.0 )) {
          return StatusCode::SUCCESS;
        }
      }
    }
  }

  if (isMC) {
    for (auto &tp : truthParticleCount) {
      m_truthParticleBarcode.push_back(tp.first);
      m_truthParticleMatchedTracks.push_back(tp.second);
      m_truthParticleIsFiducial.push_back(m_fiducialParticleTool->isFiducial(tp.first));
    }
  }

  // loop over clusters and store how many clusters are in each tracking station
  SG::ReadHandle<Tracker::FaserSCT_ClusterContainer> clusterContainer { m_clusterContainer, ctx };
  ATH_CHECK(clusterContainer.isValid());

  for (auto collection : *clusterContainer)
  { 
    Identifier id = collection->identify();
    int station = m_sctHelper->station(id);
    int clusters = (int) collection->size();
    switch (station)
    { 
      case 0:
        m_station0Clusters += clusters;
        // following lines commented out depict how to access cluster position
        //for (auto cluster : *collection) {
        //  if (cluster == nullptr) continue;
        //  auto pos = cluster->globalPosition();
        //  m_station0ClusterX.push_back(pos.x());
        //}
        break;
      case 1:
        m_station1Clusters += clusters;
        break;
      case 2:
        m_station2Clusters += clusters;
        break;
      case 3:
        m_station3Clusters += clusters;
        break;
      default:
        ATH_MSG_FATAL("Unknown tracker station number " << station);
        break;
    }
  }

  // loop over spacepoints and store each space point position
  SG::ReadHandle<FaserSCT_SpacePointContainer> spacePointContainer {m_spacePointContainerKey, ctx};
  ATH_CHECK(spacePointContainer.isValid());
  for (const FaserSCT_SpacePointCollection* spacePointCollection : *spacePointContainer) {
    m_nspacepoints += spacePointCollection->size();
    for (const Tracker::FaserSCT_SpacePoint *spacePoint: *spacePointCollection) {
      auto pos = spacePoint->globalPosition();
      m_spacepointX.push_back(pos.x());
      m_spacepointY.push_back(pos.y());
      m_spacepointZ.push_back(pos.z());
    }
  }

  // loop over track segments and store position, momentum, chi2, and nDOF for each segment
  SG::ReadHandle<TrackCollection> trackSegmentCollection {m_trackSegmentCollection, ctx};
  ATH_CHECK(trackSegmentCollection.isValid());
  for (const Trk::Track* trackSeg : *trackSegmentCollection) {
    if (trackSeg == nullptr) continue;
    m_ntracksegs += 1;
    m_trackseg_Chi2.push_back(trackSeg->fitQuality()->chiSquared());
    m_trackseg_DoF.push_back(trackSeg->fitQuality()->numberDoF());
    auto SegParameters = trackSeg->trackParameters()->front();
    const Amg::Vector3D SegPosition = SegParameters->position();
    const Amg::Vector3D SegMomentum = SegParameters->momentum();
    m_trackseg_x.push_back(SegPosition.x());
    m_trackseg_y.push_back(SegPosition.y());
    m_trackseg_z.push_back(SegPosition.z());
    m_trackseg_px.push_back(SegMomentum.x());
    m_trackseg_py.push_back(SegMomentum.y());
    m_trackseg_pz.push_back(SegMomentum.z());
  }

  SG::ReadHandle<TrackCollection> ghostbustedTrackSegmentCollection {m_ghostbustedtrackSegmentCollection, ctx};
  ATH_CHECK(ghostbustedTrackSegmentCollection.isValid());
  for (const Trk::Track* trackSeg : *ghostbustedTrackSegmentCollection) {
    if (trackSeg == nullptr) continue;
    m_nghostbustedtracksegs += 1;
    m_ghostbustedtrackseg_Chi2.push_back(trackSeg->fitQuality()->chiSquared());
    m_ghostbustedtrackseg_DoF.push_back(trackSeg->fitQuality()->numberDoF());
    auto SegParameters = trackSeg->trackParameters()->front();
    const Amg::Vector3D SegPosition = SegParameters->position();
    const Amg::Vector3D SegMomentum = SegParameters->momentum();
    m_ghostbustedtrackseg_x.push_back(SegPosition.x());
    m_ghostbustedtrackseg_y.push_back(SegPosition.y());
    m_ghostbustedtrackseg_z.push_back(SegPosition.z());
    m_ghostbustedtrackseg_px.push_back(SegMomentum.x());
    m_ghostbustedtrackseg_py.push_back(SegMomentum.y());
    m_ghostbustedtrackseg_pz.push_back(SegMomentum.z());
  }



  // finished processing event, now fill ntuple tree
  m_tree->Fill();
  m_eventsPassed += 1;
  return StatusCode::SUCCESS;
}

StatusCode NtupleDumperAlg::finalize()
{
  ATH_MSG_INFO("Number of events passed Ntuple selection = " << m_eventsPassed);
  ATH_MSG_INFO("Number of events failing GRL selection   = " << m_eventsFailedGRL);
  ATH_MSG_INFO("Number of 2-track events = " << m_two_tracks);
  ATH_MSG_INFO("Number of verticies =      " << m_verticies);
  return StatusCode::SUCCESS;
}

void
NtupleDumperAlg::clearTree() const
{
  // don't use NaN, they are annoying when doing cuts
  m_run_number = 0; 
  m_event_number = 0;
  m_event_time = 0;
  m_event_timeNSOffset = 0;
  m_bcid = 0;
  m_in_grl = 0;
  m_clock_phase = 0;
  
  m_fillNumber = 0;
  m_betaStar = 0;
  m_crossingAngle = 0;
  m_isVerticalCrossingAngle = false;
  m_distanceToCollidingBCID = 999999;
  m_distanceToUnpairedB1 = 999999;
  m_distanceToUnpairedB2 = 999999;
  m_distanceToInboundB1 = 999999;
  m_distanceToTrainStart = 999999;
  m_distanceToPreviousColliding = 999999;

  m_tbp=0;
  m_tap=0;
  m_inputBits=0;
  m_inputBitsNext=0;

  for(unsigned int ii=0;ii<max_chan;ii++) {
      m_wave_localtime[ii]=0;
      m_wave_triggertime[ii]=0;
      m_wave_bcidtime[ii]=0;
      m_wave_peak[ii]=0;
      m_wave_width[ii]=0;
      m_wave_charge[ii]=0;
      m_wave_overflow[ii]=0;
      
      m_wave_raw_peak[ii]=0;
      m_wave_raw_charge[ii]=0;
      m_wave_baseline_mean[ii]=0;
      m_wave_baseline_rms[ii]=0;
      m_wave_status[ii]=1; // default = 1 means below threshold

      m_calibrated_nMIP[ii]=0;
      m_calibrated_E_dep[ii]=0;
      m_calibrated_E_EM[ii]=0;
  }
  for (unsigned int ii=0; ii<2; ii++) {
    m_vetonu_reduced_charge[ii] = -1.0f;
  }

  m_scintHit = 0;

  m_calo_total_nMIP=0;
  m_calo_total_E_dep=0;
  m_calo_total_fit_E_EM=0;
  m_calo_total_raw_E_EM=0;
  m_calo_total_E_EM=0;
  m_calo_total_fit_E_EM_fudged=0;
  m_calo_total_raw_E_EM_fudged=0;
  m_calo_total_E_EM_fudged=0;

  m_calolo_total_nMIP=0;
  m_calolo_total_E_dep=0;
  m_calolo_total_fit_E_EM=0;
  m_calolo_total_raw_E_EM=0;
  m_calolo_total_E_EM=0;

  m_calohi_total_nMIP=0;
  m_calohi_total_E_dep=0;
  m_calohi_total_fit_E_EM=0;
  m_calohi_total_raw_E_EM=0;
  m_calohi_total_E_EM=0;

  m_calonu_total_nMIP=0;
  m_calonu_total_E_dep=0;
  m_calonu_total_fit_E_EM=0;
  m_calonu_total_raw_E_EM=0;
  m_calonu_total_E_EM=0;

  m_preshower_total_nMIP=0;
  m_preshower_total_E_dep=0;

  m_clock_phase=0;

  m_station0Clusters = 0;
  m_station1Clusters = 0;
  m_station2Clusters = 0;
  m_station3Clusters = 0;
  m_crossSection = 0;
  m_genWeights.clear();

  m_nspacepoints = 0;
  m_spacepointX.clear();
  m_spacepointY.clear();
  m_spacepointZ.clear();

  m_ntracksegs = 0;
  m_trackseg_Chi2.clear();
  m_trackseg_DoF.clear();
  m_trackseg_x.clear();
  m_trackseg_y.clear();
  m_trackseg_z.clear();
  m_trackseg_px.clear();
  m_trackseg_py.clear();
  m_trackseg_pz.clear();

  m_nghostbustedtracksegs = 0;
  m_ghostbustedtrackseg_Chi2.clear();
  m_ghostbustedtrackseg_DoF.clear();
  m_ghostbustedtrackseg_x.clear();
  m_ghostbustedtrackseg_y.clear();
  m_ghostbustedtrackseg_z.clear();
  m_ghostbustedtrackseg_px.clear();
  m_ghostbustedtrackseg_py.clear();
  m_ghostbustedtrackseg_pz.clear();

  m_xup.clear();
  m_yup.clear();
  m_zup.clear();
  m_pxup.clear();
  m_pyup.clear();
  m_pzup.clear();
  m_pup.clear();

  m_xdown.clear();
  m_ydown.clear();
  m_zdown.clear();
  m_pxdown.clear();
  m_pydown.clear();
  m_pzdown.clear();
  m_pdown.clear();

  m_Chi2.clear();
  m_DoF.clear();
  m_module_eta0.clear();
  m_module_phi0.clear();
  m_hitSet.clear();
  m_nMeasurements.clear();
  m_charge.clear();
  m_nLayers.clear();
  m_longTracks = 0;
  m_isForward.clear();

  m_nHit0.clear();
  m_nHit1.clear();
  m_nHit2.clear();
  m_nHit3.clear();

  m_xVetoNu.clear();
  m_yVetoNu.clear();
  m_thetaxVetoNu.clear();
  m_thetayVetoNu.clear();

  m_xVetoStation1.clear();
  m_yVetoStation1.clear();
  m_thetaxVetoStation1.clear();
  m_thetayVetoStation1.clear();

  m_xVetoStation2.clear();
  m_yVetoStation2.clear();
  m_thetaxVetoStation2.clear();
  m_thetayVetoStation2.clear();

  m_xTrig.clear();
  m_yTrig.clear();
  m_thetaxTrig.clear();
  m_thetayTrig.clear();

  m_xPreshower1.clear();
  m_yPreshower1.clear();
  m_thetaxPreshower1.clear();
  m_thetayPreshower1.clear();

  m_xPreshower2.clear();
  m_yPreshower2.clear();
  m_thetaxPreshower2.clear();
  m_thetayPreshower2.clear();

  m_xCalo.clear();
  m_yCalo.clear();
  m_thetaxCalo.clear();
  m_thetayCalo.clear();

  m_x_atMaxRadius.clear();
  m_y_atMaxRadius.clear();
  m_z_atMaxRadius.clear();
  m_r_atMaxRadius.clear();

  m_t_pdg.clear();
  m_t_barcode.clear();
  m_t_pdg_parent.clear();
  m_t_barcode_parent.clear();
  m_t_truthHitRatio.clear();
  m_t_prodVtx_x.clear();
  m_t_prodVtx_y.clear();
  m_t_prodVtx_z.clear();
  m_t_decayVtx_x.clear();
  m_t_decayVtx_y.clear();
  m_t_decayVtx_z.clear();
  m_t_px.clear();
  m_t_py.clear();
  m_t_pz.clear();
  m_t_theta.clear();
  m_t_phi.clear();
  m_t_p.clear();
  m_t_pT.clear();
  m_t_eta.clear();
  m_isFiducial.clear();
  for (int station = 0; station < 4; ++station) {
    m_t_st_x[station].clear();
    m_t_st_y[station].clear();
    m_t_st_z[station].clear();
  }
  for (int station = 0; station < 4; ++station) {
    m_t_st_px[station].clear();
    m_t_st_py[station].clear();
    m_t_st_pz[station].clear();
  }
  m_truthParticleBarcode.clear();
  m_truthParticleMatchedTracks.clear();
  m_truthParticleIsFiducial.clear();

  m_truthLeptonMomentum = 0;
  m_truthBarcode = -1;
  m_truthPdg = 0;

  m_truth_pdg.clear();
  m_truth_barcode.clear();
  m_truth_nHits.clear();
  for(int layer = 0; layer < 3; layer++){
    m_st0[layer].clear();
    m_st1[layer].clear();
    m_st2[layer].clear();
    m_st3[layer].clear();
  }
  m_truth_P.clear();
  m_truth_px.clear();
  m_truth_py.clear();
  m_truth_pz.clear();
  m_truth_m.clear();
  m_truth_pT.clear();
  m_truth_theta.clear();
  m_truth_phi.clear();
  m_truth_eta.clear();
  m_truth_isFiducial.clear();

  m_truth_prod_x.clear();
  m_truth_prod_y.clear();
  m_truth_prod_z.clear();
  m_truth_dec_x.clear();
  m_truth_dec_y.clear();
  m_truth_dec_z.clear();

  for (int station = 0; station < 4; ++station) {
    m_truth_st_x[station].clear();
    m_truth_st_y[station].clear();
    m_truth_st_z[station].clear();
  }
  for (int station = 0; station < 4; ++station) {
    m_truth_st_px[station].clear();
    m_truth_st_py[station].clear();
    m_truth_st_pz[station].clear();
  }

  m_truthM_P.clear();
  m_truthM_px.clear();
  m_truthM_py.clear();
  m_truthM_pz.clear();
  m_truthM_isFiducial.clear();
  m_truthM_x.clear();
  m_truthM_y.clear();
  m_truthM_z.clear();

  m_truthd0_P.clear();
  m_truthd0_px.clear();
  m_truthd0_py.clear();
  m_truthd0_pz.clear();
  m_truthd0_x.clear();
  m_truthd0_y.clear();
  m_truthd0_z.clear();
  m_truthd0_isFiducial.clear();

  m_truthd1_P.clear();
  m_truthd1_px.clear();
  m_truthd1_py.clear();
  m_truthd1_pz.clear();
  m_truthd1_x.clear();
  m_truthd1_y.clear();
  m_truthd1_z.clear();
  m_truthd1_isFiducial.clear();

  m_vertex_x = NaN;
  m_vertex_y = NaN;
  m_vertex_z = NaN;
  m_vertex_chi2 = NaN;
  m_vertex_px0 = NaN;
  m_vertex_py0 = NaN;
  m_vertex_pz0 = NaN;
  m_vertex_p0 = NaN;
  m_vertex_px1 = NaN;
  m_vertex_py1 = NaN;
  m_vertex_pz1 = NaN;
  m_vertex_p1 = NaN;
}

void NtupleDumperAlg::clearTrackTruth() const {
  m_t_pdg.push_back(0);
  m_t_barcode.push_back(-1);
  m_t_pdg_parent.push_back(0);
  m_t_barcode_parent.push_back(-1);
  m_t_truthHitRatio.push_back(0);
  m_t_prodVtx_x.push_back(999999);
  m_t_prodVtx_y.push_back(999999);
  m_t_prodVtx_z.push_back(999999);
  m_t_decayVtx_x.push_back(999999);
  m_t_decayVtx_y.push_back(999999);
  m_t_decayVtx_z.push_back(999999);
  m_t_px.push_back(0);
  m_t_py.push_back(0);
  m_t_pz.push_back(0);
  m_t_theta.push_back(999999);
  m_t_phi.push_back(999999);
  m_t_p.push_back(0);
  m_t_pT.push_back(0);
  m_t_eta.push_back(999999);
  for (int station = 0; station < 4; ++station) {
    m_t_st_x[station].push_back(999999);
    m_t_st_y[station].push_back(999999);
    m_t_st_z[station].push_back(999999);
  }
  for (int station = 0; station < 4; ++station) {
    m_t_st_px[station].push_back(999999);
    m_t_st_py[station].push_back(999999);
    m_t_st_pz[station].push_back(999999);
  }
  m_isFiducial.push_back(false);
}

double NtupleDumperAlg::radius(const Acts::Vector3 &position) const {
  return std::sqrt(position.x() * position.x() + position.y() * position.y());
}

// Calculate the mean time of all scintillators/channels in a station
float NtupleDumperAlg::get_mean_scintillator_time(
    const std::list<int> &channels,
    const xAOD::WaveformHitContainer &waveformContainer) const {
  size_t num_good_hits = 0;
  double localTime = 0.0;
  for (const xAOD::WaveformHit *hit : waveformContainer) {
    if (std::find(channels.begin(), channels.end(), hit->channel()) == channels.end()) {
      continue;
    }
    const int status = hit->hit_status();
    // Hits on the second digitizer have status bit 512 set; mask it when selecting good hits.
    if ((status & ~512) != 0) {
      continue;
    }
    double t = hit->localtime();
    if (status & 512) {
      t += 16.0;  // required offset correction for second digitizer (CaloNu period)
    }
    localTime += t;
    num_good_hits++;
  }
  if (num_good_hits > 0) {
    return static_cast<float>(localTime / num_good_hits);
  } else {
    return NaN;
  }
}
