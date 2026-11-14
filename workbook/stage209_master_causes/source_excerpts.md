# Production source excerpts at 7fd40df8

## Seed covariance and beam coordinates

`Tracking/Acts/FaserActsKalmanFilter/src/CircleFitTrackSeedTool.cxx`

```text
160:     // });
161:     allSeeds.remove_if([&](const Seed &p) {
162:       return (p.size < 10) || ((p.clusterSet & selected.clusterSet).count() > 6);
163:     });
164:   }
165: 
166:   Acts::BoundSquareMatrix cov = Acts::BoundSquareMatrix::Zero();
167:   cov(Acts::eBoundLoc0, Acts::eBoundLoc0) = m_covLoc0;
168:   cov(Acts::eBoundLoc1, Acts::eBoundLoc1) = m_covLoc1;
169:   cov(Acts::eBoundPhi, Acts::eBoundPhi) = m_covPhi;
170:   cov(Acts::eBoundTheta, Acts::eBoundTheta) = m_covTheta;
171:   cov(Acts::eBoundQOverP, Acts::eBoundQOverP) = m_covQOverP;
172:   cov(Acts::eBoundTime, Acts::eBoundTime) = m_covTime;
173: 
174:   m_cov = cov;
175: 
176:   double origin;
177:   if (!backward) {
178:     auto minSeed = std::min_element(
179:         selectedSeeds.begin(), selectedSeeds.end(), [](const Seed &lhs, const Seed &rhs) {
180:           return lhs.minZ < rhs.minZ;
181:         });
182:     origin = !selectedSeeds.empty() ? minSeed->minZ - 10 : 0;
183:   } else {
184:     origin = 2470;
185:   }
186:   m_targetZPosition = origin;
187:   std::vector<Acts::BoundTrackParameters> initParams {};
188:   ATH_MSG_DEBUG("Sorted seed properties:");
189:   for (const Seed &seed : selectedSeeds) {
190:     ATH_MSG_DEBUG("seed size: " << seed.size << ", chi2: " << seed.chi2);
```

## Circle seed and direct q/p

`Tracking/Acts/FaserActsKalmanFilter/src/CircleFitTrackSeedTool.cxx`

```text
338: void CircleFitTrackSeedTool::Seed::fakeFit(double B) {
339:   CircleFit::CircleData circleData(fakePositions);
340:   CircleFit::Circle circle = CircleFit::circleFit(circleData);
341:   cx = circle.cx;
342:   cy = circle.cy;
343:   r = circle.r;
344:   momentum = r * 0.3 * B * m_MeV2GeV;
345:   charge = circle.cy < 0 ? 1 : -1;
346: }
347: 
348: void CircleFitTrackSeedTool::Seed::linearFit(const std::vector<Acts::Vector2> &points) {
349:   auto [origin, dir] = LinearFit::linearFit(points);
350:   c1 = dir[1]/dir[0];
351:   c0 = origin[1] - origin[0] * c1;
352: }
353: 
354: 
355: double CircleFitTrackSeedTool::Seed::getY(double z) {
356:   double sqt = std::sqrt(-cx*cx + 2*cx*z + r*r - z*z);
357:   return abs(cy - sqt) < abs(cy + sqt) ? cy - sqt : cy + sqt;
358: }
359: 
```

## Seed parameters

`Tracking/Acts/FaserActsKalmanFilter/src/CircleFitTrackSeedTool.cxx`

```text
397:   rotation.col(0) = Acts::Vector3(0, 1, 0);
398:   rotation.col(1) = Acts::Vector3(0, 0, -1);
399:   rotation.col(2) = Acts::Vector3(-1, 0, 0);
400:   Acts::Translation3 trans(pos.z(), 0., 0.);
401:   Acts::Transform3 traf(trans*rotation);
402:   double theta = Acts::VectorHelpers::theta(trafo*direction);
403:   double phi = Acts::VectorHelpers::phi(trafo*direction);
404: 
405: //  Acts::Vector3 direct(-1,0,0);
406:   auto refPlane = Acts::Surface::makeShared<Acts::PlaneSurface>(traf);; 
407:   Acts::GeometryContext gctx;
408:   auto lpResult = refPlane->globalToLocal(gctx, trafo*pos);
409:   if (not lpResult.ok()) {
410:     throw std::runtime_error("globalToLocal transformation failed. This should not happen");
411:   }
412:   auto lPosition = lpResult.value();
413:   Acts::BoundVector params = Acts::BoundVector::Zero();
414:   params[Acts::eBoundLoc0] = lPosition.x();
415:   params[Acts::eBoundLoc1] = lPosition.y();
416:   params[Acts::eBoundTime] = 0;
417:   params[Acts::eBoundPhi] = phi;
418:   params[Acts::eBoundTheta] = theta;
419:   //params[Acts::eBoundQOverP] = particleHypothesis.qOverP(p, charge);
420: 
421:   params[Acts::eBoundQOverP] = charge/(momentum);
422: 
423:   
424:  //@todo make the particle hypothesis configurable
425:   return Acts::BoundTrackParameters(refPlane, params, cov, Acts::ParticleHypothesis::muon()); 
426: }
427: 
```

## Production covariance defaults

`Tracking/Acts/FaserActsKalmanFilter/python/CKF2Config.py`

```text
45:     track_seed_tool = CompFactory.CircleFitTrackSeedTool()
46:     sigma_loc0 = 1.9e-2
47:     sigma_loc1 = 9e-1
48:     sigma_phi = 3.3e-2
49:     sigma_theta = 2.9e-4
50:     #sigma_theta = 3e-2
51:     p = 1000
52:     sigma_p = 0.1 * p
53:     sigma_qop = sigma_p / (p * p)
54:     initial_variance_inflation = kwargs.pop(
55:         "initialVarianceInflation",
56:         [100, 100, 100, 10000, 100000]
57:     )
58:     # initial_variance_inflation = [1000, 1000, 100, 100, 10000]
59:     #initial_variance_inflation = [100, 100, 100, 100, 1000]
60:     #initial_variance_inflation = [100, 100, 10000, 100, 100000]
61:     #initial_variance_inflation = [100, 100, 100, 10000, 100000]
62:     track_seed_tool.covLoc0 = initial_variance_inflation[0] * sigma_loc1 * sigma_loc1
63:     track_seed_tool.covLoc1 = initial_variance_inflation[1] * sigma_loc0 * sigma_loc0
64:     track_seed_tool.covPhi = initial_variance_inflation[2] * sigma_phi * sigma_phi
65:     track_seed_tool.covTheta = initial_variance_inflation[3] * sigma_theta * sigma_theta
66:     track_seed_tool.covQOverP = initial_variance_inflation[4] * sigma_qop * sigma_qop
67:     track_seed_tool.std_cluster = 0.0231
```

## Candidate selection and smoothing

`Tracking/Acts/FaserActsKalmanFilter/src/CKF2.cxx`

```text
266: 
267:   while (not allTracks.empty()) {
268:     TrackInfo selected = allTracks.front();
269:     allTracks.erase(allTracks.begin());
270: 
271:     
272:     auto destProxy = selectedTracks.getTrack(selectedTracks.addTrack());
273:     destProxy.copyFrom(tracks.getTrack(selected.index), true);  // make sure we copy track states!
274:     // CKF branches share ancestor states. Their smoothed values may have been
275:     // overwritten by another branch before the finder returned. Deep-copying
276:     // alone preserves those values: recompute only after the states are private.
277:     if (m_isolateSmoothing) {
278:       const auto status = Acts::GainMatrixSmoother()(
279:           gctx, selectedTracks.trackStateContainer(), destProxy.tipIndex(), *m_logger);
280:       if (!status.ok()) {
281:         ATH_MSG_ERROR("Isolated candidate smoothing failed for candidate "
282:                       << selected.index << ": " << status.error());
283:         return StatusCode::FAILURE;
284:       }
285:     }
286:     
287:     if(not allTracks.empty()){ 
288:       allTracks.remove_if([&](const TrackInfo &p) {
289:         return ((p.nMeasurements <= 12) || ((p.clusterSet & selected.clusterSet).count() > 6));
290:       });
291:       //allTracks.remove_if([&](const TrackInfo &p) {
292:       //  	      ATH_MSG_DEBUG("selected"<<selected.index<<" | nMeas="<<selected.nMeasurements<<" chi2="<<selected.chi2);
293: 
294:       //  int shared = (p.clusterSet & selected.clusterSet).count();
295:       //  bool killByNMeas = (p.nMeasurements <= 3);
296:       //  bool killByShared = (shared > 6);
297:     
298:       //    ATH_MSG_DEBUG(
299:       //      "[CKF2-SELECTOR] "
300:       //      << "candidate=" << p.index
301:       //      << " vs selected=" << selected.index
302:       //      << " | nMeas=" << p.nMeasurements
```

## Refit acceptance

`Tracking/Acts/FaserActsKalmanFilter/src/CKF2.cxx`

```text
345:     }
346:   }
347: 
348:     //write out all acts found tracks for debugging 
349: //  // @todo run the performance writer
350: //  if  (m_performanceWriter && !m_noDiagnostics) {
351: //    ATH_CHECK(m_performanceWriterTool->write(gctx, tracks));
352: //  }
353: 
354:   //write selectedTracks after track finding
355:   if (m_statesWriter && !m_noDiagnostics) {
356:     ATH_CHECK(m_trajectoryStatesWriterTool->write(gctx, selectedTracks, m_isMC));
357:   }
358:   if (m_summaryWriter && !m_noDiagnostics) {
359:     ATH_CHECK(m_trajectorySummaryWriterTool->write(gctx, selectedTracks, *measurements, m_isMC));
360:   }
361:   if (m_alignmentWriter) {
362:     ATH_CHECK(m_alignmentDerivativesWriterTool->write(gctx, selectedTracks, refitStatus));
363:   }
364:   // ATH_CHECK(allTrackContainer.record(std::move(outputAllTracks)));
365:   ATH_CHECK(trackContainer.record(std::move(outputTracks)));
366: 
```

## Direct inverse and covariance copy

`Tracking/Acts/FaserActsKalmanFilter/src/CreateTrkTrackTool.cxx`

```text
103: 
104: std::unique_ptr<Trk::TrackParameters>
105: CreateTrkTrackTool::ConvertActsTrackParameterToATLAS(const Acts::BoundTrackParameters &actsParameter, const Acts::GeometryContext& gctx) const {
106:   using namespace Acts::UnitLiterals;
107:   std::optional<AmgSymMatrix(5)> cov = std::nullopt;
108:   if (actsParameter.covariance()){
109:     AmgSymMatrix(5) newcov(actsParameter.covariance()->topLeftCorner(5, 5));
110:     // Convert the covariance matrix to GeV
111:     for(int i=0; i < newcov.rows(); i++){
112:       newcov(i, 4) = newcov(i, 4)*1_MeV;
113:     }
114:     for(int i=0; i < newcov.cols(); i++){
115:       newcov(4, i) = newcov(4, i)*1_MeV;
116:     }
117:     cov =  std::optional<AmgSymMatrix(5)>(newcov);
118:   }
119:   const Amg::Vector3D& pos=actsParameter.position(gctx);
120:   double tphi=actsParameter.get<Acts::eBoundPhi>();
121:   double ttheta=actsParameter.get<Acts::eBoundTheta>();
122:   double tqOverP=actsParameter.get<Acts::eBoundQOverP>()*1_MeV;
123:   double p = std::abs(1. / tqOverP);
124:   Amg::Vector3D tmom(p * std::cos(tphi) * std::sin(ttheta), p * std::sin(tphi) * std::sin(ttheta), p * std::cos(ttheta));
125:   double charge = tqOverP > 0. ? 1. : -1.;
126:   //std::cout
127:   //  << "\n===== ACTS -> ATLAS conversion =====\n"
```

## Refit minimum measurements

`Tracking/Acts/FaserActsKalmanFilter/src/KalmanFitterTool.cxx`

```text
343: std::unique_ptr<Trk::Track>
344: KalmanFitterTool::fit(const EventContext &ctx, const Acts::GeometryContext &gctx,
345:                       Trk::Track* inputTrack, const Acts::BoundVector& inputVector,
346:                       bool isMC) const {
347:   std::unique_ptr<Trk::Track> newTrack = nullptr;
348: 
349:   if (!inputTrack->measurementsOnTrack() || inputTrack->measurementsOnTrack()->size() < m_minMeasurements) {
350:     ATH_MSG_WARNING("Input track has only " << inputTrack->measurementsOnTrack()->size() <<" measurements and cannot be fitted");
351:     return nullptr;
352:   }
353: 
354:   if (!inputTrack->trackParameters() || inputTrack->trackParameters()->empty()) {
```

## Refit covariance copy and inflation

`Tracking/Acts/FaserActsKalmanFilter/src/KalmanFitterTool.cxx`

```text
615:     //params(0) = center[Trk::locY];
616:     //params(1) = center[Trk::locX];
617:     params(0) = center.y();
618:     params(1) = -center.z();
619:     params(2) = atlasParam[Trk::phi0];
620:     params(3) = atlasParam[Trk::theta];
621:     params(4) = inputParameters->charge() / (inputParameters->momentum().norm() * 1_MeV);
622:     params(5) = 0.;
623:   } else {
624:     params = inputVector;
625:   }
626:   //std::cout<<"before params : "<<params(0)<<"    "<<params(1)<<"  "<<params(2)<<"   "<<params(3)<<"   "<<params(4)<<std::endl;
627:   Acts::BoundSquareMatrix cov = Acts::BoundSquareMatrix::Identity();
628:   cov.topLeftCorner(5, 5) = *inputParameters->covariance();
629: 
630:   for(int i=0; i < cov.rows(); i++){
631:     cov(i, 4) = cov(i, 4)/1_MeV;
632:   }
633:   for(int i=0; i < cov.cols(); i++){
634:     cov(4, i) = cov(4, i)/1_MeV;
635:   }
636:   for (int i = 0; i < 6; ++i) {
637:     cov(i,i) = m_seedCovarianceScale * cov(i,i);
638:   }
639: 
640:   return Acts::BoundTrackParameters(pSurface, params, cov, Acts::ParticleHypothesis::muon());
641: }
```

## Merge ranking

`Tracking/TrkAlgorithms/src/MergeTracksAlg.cxx`

```text
94:     //Now that all the tracks are in a common list we can sort them
95:     //first by greatest number of measurements 
96:     //Then by lowest chi squared for a tie breaker
97:     allTracks.sort([](const Trk::Track &left, const Trk::Track &right) {
98:         uint leftMeasurements = left.measurementsOnTrack()->size();
99:         uint rightMeasurements = right.measurementsOnTrack()->size();
100:         double leftChi2PerDof = left.fitQuality()->chiSquared() / left.fitQuality()->numberDoF();
101:         double rightChi2PerDof = right.fitQuality()->chiSquared() / right.fitQuality()->numberDoF();
102: 
103:         if (leftMeasurements > rightMeasurements) return true;
104:         if (leftMeasurements < rightMeasurements) return false;
105:         if (leftChi2PerDof < rightChi2PerDof) return true;
106:         else return false;
107:     });
108: 
```
