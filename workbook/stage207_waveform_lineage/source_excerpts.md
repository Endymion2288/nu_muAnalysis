# 波形调用链与两版源码定位

## d32b0ff3 / Waveform/WaveRecTools/src/WaveformReconstructionTool.cxx

定位：`WaveformReconstructionTool::reconstructPrimary(`，原文件第52行。

```text
52: WaveformReconstructionTool::reconstructPrimary(
53: 	 const RawWaveform& wave,
54: 	 xAOD::WaveformHitContainer* hitContainer) const {
55: 
56:   ATH_MSG_DEBUG(" reconstructPrimary called");
57: 
58:   xAOD::WaveformHit* newhit = new xAOD::WaveformHit();
59:   hitContainer->push_back(newhit);
60: 
61:   // Set digitizer channel and identifier
62:   newhit->set_channel(wave.channel());
63:   newhit->set_identifier(wave.identify());
64: 
65:   // Make sure we have ADC counts
66:   if (wave.adc_counts().size() == 0) {
67:     ATH_MSG_WARNING( "Found waveform for channel " << wave.channel() 
68: 		     << " with size " << wave.adc_counts().size() << "!");
69: 	
70:     newhit->set_status_bit(xAOD::WaveformStatus::WAVEFORM_MISSING);
71:     return StatusCode::SUCCESS;
72:   } 
73: 
74:   if (wave.adc_counts().size() != wave.n_samples()) {
75:     ATH_MSG_WARNING( "Found waveform for channel " << wave.channel() 
76: 		     << " with size " << wave.adc_counts().size() 
77: 		     << " not equal to number of samples " << wave.n_samples());
78: 	
79:     newhit->set_status_bit(xAOD::WaveformStatus::WAVEFORM_INVALID);
80:     return StatusCode::SUCCESS;
81:   }
82: 
83:     // Find the baseline for this waveform
84:   findBaseline(wave, newhit);
85: 
86:   // Check for problems
87:   if (newhit->status_bit(xAOD::WaveformStatus::BASELINE_FAILED)) {
88:     return StatusCode::SUCCESS;
89:   }
90: 
91:   // Get the nominal trigger time (in ns) from config
92:   float trigger_time = m_timingTool->nominalTriggerTime();
93: 
94:   // Set range for windowed data in digitizer samples
95:   float trigger_offset = m_timingTool->triggerTimeOffset(wave.channel());
96: 
97:   
98:   int lo_edge = int((trigger_time+trigger_offset)/2.) + m_windowStart;
99:   int hi_edge = int((trigger_time+trigger_offset)/2.) + m_windowStart + m_windowWidth;
100: 
101:   if (hi_edge >= int(wave.size())) {
102:     // This likely means we have the wrong digitizer range
103:     ATH_MSG_WARNING("Found channel " << wave.channel() << " with low edge: " << lo_edge << " hi edge: " << hi_edge << " > wave.size() " << wave.size());
104:     ATH_MSG_WARNING("  trigger_time + trigger_offset: " << (trigger_time+trigger_offset) << " => " << int((trigger_time+trigger_offset)/2.));
105:     newhit->set_status_bit(xAOD::WaveformStatus::WAVEFORM_INVALID);
106:     return StatusCode::SUCCESS;
107:   }
108:   
109:   // Adjust window time if 2nd digitizer triggered late
110:   // Waveform will arrive early by 16ns
111:   if (wave.trigger_offset() >= 1) {
112:     lo_edge -= 8;
113:     hi_edge -= 8;
114:   }
115: 
116:   // Fill raw hit values
117:   fillRawHitValues(wave, lo_edge, hi_edge, newhit);
118: 
119:   // Check if this is over threshold
120:   if (newhit->peak() < newhit->baseline_rms() * m_primaryPeakThreshold) {
121:     ATH_MSG_DEBUG("Primary hit failed threshold");
122:     newhit->set_status_bit(xAOD::WaveformStatus::THRESHOLD_FAILED);
123:   } else {
124:     // Reconstruct hit in this range
125:     reconstructHit(newhit);
126:   }
```

定位：`WaveformReconstructionTool::fillRawHitValues(`，原文件第391行。

```text
391: WaveformReconstructionTool::fillRawHitValues(const RawWaveform& wave,
392: 					   int lo_edge, int hi_edge, 
393: 					   xAOD::WaveformHit* hit) const {
394:   
395:   // First, make sure we don't overflow the waveform range
396:   if (lo_edge < 0) lo_edge = 0;
397:   if (hi_edge >= int(wave.size())) hi_edge = wave.size() - 1;
398:   if (hi_edge <= lo_edge) {
399:     ATH_MSG_WARNING("Channel " << wave.channel() << " waveform with lo: " << lo_edge << " hi: " << hi_edge << "!");
400:     return;
401:   }
402:   
403:   ATH_MSG_DEBUG("Fill channel " << wave.channel() 
404: 		<< " waveform from sample " << lo_edge << " to " << hi_edge);
405: 
406:   // Fill hit window with data from wave
407:   std::vector<float> wtime(hi_edge-lo_edge+1);
408:   std::vector<float> wwave(hi_edge-lo_edge+1);
409: 
410:   // Also look for overflows here
411:   int iover_start = 9999;
412:   int iover_end = 0;
413:   
414:   for (int i=lo_edge; i<=hi_edge; i++) {
415:     unsigned int j = i-lo_edge;
416:     wtime[j] = 2.*i; // 2ns per sample at 500 MHz
417:     wwave[j] = hit->baseline_mean() - wave.mv_per_bit() * wave.adc_counts()[i];
418: 
419:     if (wave.adc_counts()[i] <= 0) {
420:       iover_start = std::min(iover_start, i);
421:       iover_end = std::max(iover_end, i);
422:     }
423:   }
424: 
425:   hit->set_time_vector(wtime);
426:   hit->set_wave_vector(wwave);
427: 
428:   float overtime = 0.;
429:   if (iover_end > iover_start) {
430:     overtime = 2.*(iover_end - iover_start); 
431:     hit->set_status_bit(xAOD::WaveformStatus::WAVE_OVERFLOW);
432:   }
433:   hit->set_over_time(overtime);
434:     
435:   // Set raw values
436:   WaveformFitResult raw = findRawHitValues(wtime, wwave);
437:   hit->set_peak(raw.peak);
438:   hit->set_mean(raw.mean);
439:   hit->set_width(raw.sigma);
440:   hit->set_integral(raw.integral);
441:   hit->set_localtime(raw.time);
442:   hit->set_raw_peak(raw.peak);
443:   hit->set_raw_integral(raw.integral);
444: 
445:   // Indicate digitizer timing shift
446:   if (wave.trigger_offset() >= 1) {
447:     hit->set_status_bit(xAOD::WaveformStatus::TIMING_SHIFTED);
448:   }
449: 
450: }
451: 
452: // Reconstruct a hit from the RawWaveform in the range specified
453: // Range is in units digitizer samples (not ns)
454: void
455: WaveformReconstructionTool::reconstructHit(xAOD::WaveformHit* hit) const {
456: 
457:   // Time and waveform vectors
458:   // Don't use reference as we may modify this below
459:   std::vector<float> wtime = hit->time_vector();
460:   std::vector<float> wwave = hit->wave_vector();
461: 
462:   ATH_MSG_DEBUG("Reconstruct channel " << hit->channel() 
463: 		<< " waveform from " << wtime.front() 
464: 		<< " to " << wtime.back());
465: 
```

定位：`WaveformReconstructionTool::reconstructHit(`，原文件第455行。

```text
455: WaveformReconstructionTool::reconstructHit(xAOD::WaveformHit* hit) const {
456: 
457:   // Time and waveform vectors
458:   // Don't use reference as we may modify this below
459:   std::vector<float> wtime = hit->time_vector();
460:   std::vector<float> wwave = hit->wave_vector();
461: 
462:   ATH_MSG_DEBUG("Reconstruct channel " << hit->channel() 
463: 		<< " waveform from " << wtime.front() 
464: 		<< " to " << wtime.back());
465: 
466:   // Fill values needed for fit (peak, mean, and sigma)
467:   // Save initial values (from parameter estimation)
468:   WaveformFitResult raw;
469:   raw.peak = hit->peak();
470:   raw.mean = hit->mean();
471:   raw.sigma = hit->width();
472:   raw.time = hit->localtime();
473:   raw.integral = hit->integral();
474:   
475:   //
476:   // Check for overflow (now done in fillRawHitValues
477:   // This will also remove overflow values based on m_removeOverflow or m_removeAllOverflow
478:   if (hit->overflow()) {
479:     if (!findOverflow(hit->baseline_mean(), wtime, wwave)) {
480:       ATH_MSG_INFO("finOverflow returned false even though overflow bit set!  tover = " << hit->over_time());
481:     } else {
482:       ATH_MSG_DEBUG("Found waveform overflow");
483:     }
484:   }
485:   
486:   //
487:   // Perform Gaussian fit to waveform
488:   WaveformFitResult previous_fit;
489:   WaveformFitResult gfit = fitGaussian(raw, wtime, wwave);
490:   if (! gfit.valid) {
491:     ATH_MSG_INFO( " Gaussian waveform fit failed for channel " << hit->channel() << "!  Status: " << gfit.fit_status);
492:     hit->set_status_bit(xAOD::WaveformStatus::GFIT_FAILED);
493:     previous_fit = raw;    
494:   } else {
495:     // Update if fit succeeded
496:     hit->set_peak(gfit.peak);
497:     hit->set_mean(gfit.mean);
498:     hit->set_width(gfit.sigma);
499:     hit->set_localtime(gfit.time);
500:     hit->set_integral(gfit.integral);
501:     previous_fit = gfit;
502:   }
503:   
504:   //
505:   // Perform CB fit
506:   WaveformFitResult cbfit;
507:   if (hit->status_bit(xAOD::WaveformStatus::WAVE_OVERFLOW)) {
508:     cbfit = fitCBallOverflow(previous_fit, wtime, wwave);
509:   } else {
510:     cbfit = fitCBall(previous_fit, wtime, wwave);
511:   }
512: 
513:   if (!cbfit.valid) {
514:     // CB fit failed, mark it here
515:     ATH_MSG_INFO("CrystalBall fit failed for channel " << hit->channel() << "!   Status: " << cbfit.fit_status);
516:     hit->set_status_bit(xAOD::WaveformStatus::CBFIT_FAILED);
517:     
518:     if (hit->status_bit(xAOD::WaveformStatus::WAVE_OVERFLOW)) {
519:       // For overflow, use raw values as likely better estimate than Gauss fit
520:       // Time comes from peak, which is first overflow
521:       hit->set_peak(raw.peak);
522:       hit->set_mean(raw.mean);
523:       hit->set_width(raw.sigma);
524:       hit->set_localtime(raw.time);  
525:       hit->set_integral(raw.integral);
526:     }
527:     
528:     // for(unsigned int i=0; i<wwave.size(); i++) {
529:     //   ATH_MSG_INFO(" Time: " << wtime[i] << " Value: " << wwave[i]);
530:     // }
531: 
532:   } else {
533:     // CB fit succeeded
534:     hit->set_peak(cbfit.peak);
535:     hit->set_mean(cbfit.mean);
536:     hit->set_width(cbfit.sigma);
537:     hit->set_alpha(cbfit.alpha);
538:     hit->set_nval(cbfit.nval);
539:     hit->set_localtime(cbfit.time);    
540:     hit->set_integral(cbfit.integral);
541:   }
542: 
543:   // Check time (to avoid NaN)
544:   // This shouldn't happen any more
545:   if (isnan(hit->localtime())) {
546:     ATH_MSG_WARNING("Found waveform time NaN for channel " << hit->channel() << "!  valid = " << cbfit.valid);
547:     hit->set_localtime(raw.time);
548:   }
549: 
550:   if (isnan(hit->integral())) {
551:     ATH_MSG_WARNING("Found waveform integral NaN for channel " << hit->channel() << "!  valid = " << cbfit.valid);
552:     hit->set_integral(raw.integral);
553:   }
554:   
555:   ATH_MSG_DEBUG("Done reconstructing channel " << hit->channel() 
556: 		<< " waveform from " << wtime.front() << " to " << wtime.back());
557: }
558: 
559: 
560: // Returns location of peak in array wave
561: // Return value is -1 if peak is below threshold
562: int
563: WaveformReconstructionTool::findPeak(WaveformBaselineData& baseline, 
564: 				     float threshold,
565: 				     std::vector<float>& wave) const 
566: {
567: 
568:   ATH_MSG_DEBUG("findPeak called");
569: 
570:   // Find max value location in array
571:   unsigned int imax = std::max_element(wave.begin(), wave.end()) - wave.begin();
572:   float maxval = wave[imax];
573:   ATH_MSG_DEBUG( "Found peak value " << maxval << " at position " << imax );
574: 
575:   // Check if this is over threshold (in sigma)
576:   if (maxval < threshold*baseline.rms) {
577:     ATH_MSG_DEBUG("Failed threshold");
578:     return -1;
579:   }
580: 
581:   return imax;
582: }
583: 
584: // Return overflow time (in ns)
```

定位：`WaveformReconstructionTool::findRawHitValues(`，原文件第797行。

```text
797: WaveformReconstructionTool::findRawHitValues(const std::vector<float> time, const std::vector<float> wave) const {
798: 
799:   ATH_MSG_DEBUG("findRawHitValues called");
800: 
801:   // This must be static so we can return a reference
802:   static WaveformFitResult rfit;
803:   rfit.clear();
804: 
805:   // Better to start with the peak and find mean and RMS from narrower window?
806: 
807:   // Pointer to peak
808:   auto peakloc = std::max_element(wave.begin(), wave.end());
809:   int ipeak = std::distance(wave.begin(), peakloc);
810:   int size = wave.size();
811:   
812:   // Define a truncated range around peak to calculate raw quantities
813:   unsigned int istart = std::max(ipeak-10, 0);
814:   unsigned int iend   = std::min(ipeak+10, size-1);
815: 
816:   // ATH_MSG_INFO("Calculating raw quantities from " << istart << " to " << iend);
817:   
818:   // First, estimate starting values from input waveform
819:   // Will use this to pre-set fit values, but also as a backup in case fit fails
820:   double tot = 0.;
821:   double sum = 0.;
822:   double sum2 = 0.;
823:   for (unsigned int i=istart; i<=iend; i++) {
824:     // ATH_MSG_INFO("findRawHitValues Time: " << time[i] << " Wave: " << wave[i]);
825:     if (wave[i] <= 0.) continue; // Don't sum negative values, causes problems
826:     tot += wave[i];
827:     sum += time[i] * wave[i];
828:     sum2 += time[i] * time[i] * wave[i];
829:   }
830: 
831:   // Initial parameters from waveform  
832:   rfit.mean = sum/tot;
833:   rfit.sigma = std::sqrt(sum2/tot - rfit.mean*rfit.mean);
834:   rfit.peak = *peakloc;
835:   // Time is set to peak location
836:   // This works well for overflows as it is the time of overflow
837:   rfit.time = time[ipeak];
838: 
839:   // For integral, use entire range
840:   // Factor of 2 because at 500 MHz, dt = 2 ns
841:   rfit.integral = 2*std::accumulate(wave.begin(), wave.end(), 0.);
842: 
843:   ATH_MSG_DEBUG( 
844: 		"findRawHitValues Initial Mean: " << rfit.mean 
845: 		<< " RMS: " << rfit.sigma 
846: 		<< " Peak: " << rfit.peak
847: 		<< " Time: " << rfit.time
848: 		<< " Integral: " << rfit.integral
849: 		 );  
850: 
851:   // Fix bad values
852:   if (isnan(rfit.sigma)) {
853:     ATH_MSG_WARNING("findRawHitValues Found sigma: " << rfit.sigma << " Replace with 2.");
854:     rfit.sigma = 2.;
855:   }
856: 
857:   if (rfit.mean < time.front() || rfit.mean > time.back()) {
858:     ATH_MSG_WARNING("findRawHitValues Found mean: " << rfit.mean << " out of range " << time.front() << "-" << time.back() << " Replace with peak time " << rfit.time);
859:     // Use peak time instead
860:     rfit.mean = rfit.time;
861:   }
862: 
863:   return rfit;
864: }
865: 
866: WaveformFitResult&
867: WaveformReconstructionTool::fitGaussian(const WaveformFitResult& raw, const std::vector<float> time, const std::vector<float> wave) const {
868: 
869:   ATH_MSG_DEBUG("fitGaussian called");
870: 
871:   // This must be static so we can return a reference
```

定位：`WaveformReconstructionTool::fitGaussian(`，原文件第867行。

```text
867: WaveformReconstructionTool::fitGaussian(const WaveformFitResult& raw, const std::vector<float> time, const std::vector<float> wave) const {
868: 
869:   ATH_MSG_DEBUG("fitGaussian called");
870: 
871:   // This must be static so we can return a reference
872:   static WaveformFitResult gfit;
873:   gfit.clear();
874: 
875:   // Start with raw values by default
876:   gfit = raw;
877: 
878:   // Start by creating a TGraph and fitting this with a Gaussian
879:   // Must pass arrays to TGraph, use pointer to first vector element
880:   TGraph tg(time.size(), &time[0], &wave[0]);
881: 
882:   // Define fit function and preset range
883:   TF1 gfunc("gfunc", "gaus");
884:   gfunc.SetParameters(raw.peak, raw.mean, raw.sigma);
885:   gfunc.SetParError(0, raw.peak/10.);
886:   gfunc.SetParError(1, raw.sigma);
887:   gfunc.SetParError(2, raw.sigma / 10.);
888:   gfunc.SetParLimits(0, 1, 5000);
889:   gfunc.SetParLimits(1, time.front(), time.back());
890:   gfunc.SetParLimits(2, 1, 50);  // Constrain width
891: 
892:   // First fix the width
893:   gfunc.FixParameter(2, raw.sigma);
894:   TFitResultPtr gfitptr = tg.Fit(&gfunc, "QNSB", "");
895: 
896:   gfit.fit_status = gfitptr;
897:   gfit.valid = (gfit.fit_status%10 == 0);
898: 
899:   if (!gfit.valid) {
900:     ATH_MSG_DEBUG( " First Gaussian waveform fit failed!");
901:     ATH_MSG_DEBUG( " Raw    Mean: " << raw.mean << " RMS: " << raw.sigma << " Peak:" << raw.peak);
902:     ATH_MSG_DEBUG( " G Fit  Mean: " << gfitptr->Parameter(1) << " RMS: " << gfitptr->Parameter(2) << " Peak:" << gfitptr->Parameter(0));
903:   }
904: 
905:   // Now release width and fit again
906:   gfunc.ReleaseParameter(2);
907:   gfunc.SetParameter(2, raw.sigma);
908:   gfunc.SetParError(2, raw.sigma / 10.);
909:   gfunc.SetParLimits(2, 1, 50); // Constrain width
910: 
911:   gfitptr = tg.Fit(&gfunc, "QNSB", "");  
912: 
913:   gfit.fit_status = gfitptr;
914:   gfit.valid = (gfit.fit_status%10 == 0);
915: 
916:   // Only consider fit failed if minimization fails (Migrad)
917:   // Failure in errors (Minos or Hesse) are not critical
918:   //if (!gfitptr->IsValid()) {
919:   if (!gfit.valid) {
920:     ATH_MSG_DEBUG( " Second Gaussian waveform fit failed!");
921:     ATH_MSG_DEBUG( " Raw    Mean: " << raw.mean << " RMS: " << raw.sigma << " Peak:" << raw.peak);
922:     ATH_MSG_DEBUG( " G Fit  Mean: " << gfitptr->Parameter(1) << " RMS: " << gfitptr->Parameter(2) << " Peak:" << gfitptr->Parameter(0));
923: 
924:   } else {
925:     // Improve estimation with fit results
926:     gfit.peak = gfitptr->Parameter(0);
927:     gfit.mean = gfitptr->Parameter(1);
928:     gfit.sigma = gfitptr->Parameter(2);
929:     gfit.integral = gfunc.Integral(time.front(), time.back());
930: 
931:     // Find time here
932:     //gfit.time = gfunc.GetX( gfit.peak * m_timingPeakFraction, time.front(), gfit.mean );
933:     // Start checking function from t=0 in case Gaussian width pushes time
934:     // before start of window
935:     gfit.time = gfunc.GetX( gfit.peak * m_timingPeakFraction, 0., gfit.mean );
936: 
937:     if (isnan(gfit.time)) {
938:       ATH_MSG_DEBUG(" Gaussian fit returned time as NaN, assume fit failed");
939:       ATH_MSG_DEBUG( " Raw    Mean: " << raw.mean << " RMS: " << raw.sigma << " Peak:" << raw.peak);
940:       ATH_MSG_DEBUG( " G Fit  Mean: " << gfitptr->Parameter(1) << " RMS: " << gfitptr->Parameter(2) << " Peak:" << gfitptr->Parameter(0));
941: 
942:       gfit = raw;
943:       gfit.fit_status = 4;
944:       gfit.valid = false;
945:     }
946: 
947:     ATH_MSG_DEBUG("G Fit   Mean: " << gfit.mean << " RMS: " << gfit.sigma 
948: 		  << " Peak: " << gfit.peak << " Int: " << gfit.integral << " Time: " << gfit.time);
949:   }
950: 
951:   // If we have a valid fit, return it
952:   if (gfit.valid) return gfit;
953: 
954:   // Try last chance
955:   ATH_MSG_DEBUG("Attempting emergency Gaussian fit!");
956: 
957:   // Fit to restricted range around peak (+/- 10ns)
958:   TF1 gfunc2("gfunc2", "gaus", raw.time-10, raw.time+10);
959:   gfunc2.SetParameters(raw.peak, raw.mean, raw.sigma);
960:   gfunc2.SetParError(0, raw.peak/10.);
961:   gfunc2.SetParLimits(0, 0, 5000);
962:   gfunc2.FixParameter(1, raw.mean);
963:   gfunc2.SetParError(2, raw.sigma/10.);
964:   gfunc2.SetParLimits(2, 0.5, 10);
965: 
966:   gfitptr = tg.Fit(&gfunc2, "QNSB", "");
967: 
968:   // Now release mean and fix width
969:   //gfunc2.ReleaseParameter(1);
970:   //gfunc2.SetParameter(1, gfitptr->Parameter(1));
971:   //gfunc2.SetParError(1, gfitptr->Parameter(2)/10.);
972:   //gfunc2.FixParameter(2, gfitptr->Parameter(2));
973: 
974:   //gfitptr = tg.Fit(&gfunc2, "QNS", "");
975:     
976:   gfit.fit_status = gfitptr;
977:   gfit.valid = (gfit.fit_status%10 == 0);
978: 
979:   if (!gfit.valid) {
980:     ATH_MSG_DEBUG( " Emergency Gaussian waveform fit failed!");
981:     ATH_MSG_DEBUG( " Raw    Mean: " << raw.mean << " RMS: " << raw.sigma << " Peak:" << raw.peak);
982:     ATH_MSG_DEBUG( " G Fit  Mean: " << gfitptr->Parameter(1) << " RMS: " << gfitptr->Parameter(2) << " Peak:" << gfitptr->Parameter(0));
983:   
984:     //for(unsigned int i=0; i<wave.size(); i++) {
985:     //  ATH_MSG_DEBUG(" Time: " << time[i] << " Value: " << wave[i]);
986:     //}
987:   } else {
988:     gfit.peak = gfitptr->Parameter(0);
989:     gfit.mean = gfitptr->Parameter(1);
990:     gfit.sigma = gfitptr->Parameter(2);
991:     gfit.integral = gfunc2.Integral(time.front(), time.back());
992: 
993:     gfit.time = gfunc2.GetX( gfit.peak * m_timingPeakFraction, 0., gfit.mean );
994: 
995:     if (isnan(gfit.time)) {
996:       ATH_MSG_DEBUG(" Emergency Gaussian fit returned time as NaN, assume fit failed");
```

定位：`WaveformReconstructionTool::fitCBall(`，原文件第1011行。

```text
1011: WaveformReconstructionTool::fitCBall(const WaveformFitResult& gfit, 
1012:      const std::vector<float> time, const std::vector<float> wave) const {
1013: 
1014:   ATH_MSG_DEBUG("fitCBall called");
1015: 
1016:   // This must be static so we can return a reference
1017:   static WaveformFitResult cbfit;
1018:   cbfit.clear();
1019: 
1020:   // Must pass arrays to TGraph, use pointer to first vector element
1021:   TGraph tg(time.size(), &time[0], &wave[0]);
1022: 
1023:   // Values to preset CB fit
1024:   cbfit.peak = abs(gfit.peak);
1025:   cbfit.mean = gfit.mean;
1026:   cbfit.sigma = std::min(abs(gfit.sigma), 10.);
1027:   //if (cbfit.sigma > 20.) cbfit.sigma = 2.;
1028:   cbfit.alpha = -0.5;  // Negative to get tail on high side
1029:   cbfit.nval = 2.;
1030: 
1031:   // Define fit function and preset values
1032:   TF1 cbfunc("cbfunc", "crystalball");
1033:   cbfunc.SetParameter(0, cbfit.peak); // Peak height
1034:   cbfunc.SetParError(0,  cbfit.peak/10.);
1035:   cbfunc.SetParameter(1, cbfit.mean); // Mean
1036:   cbfunc.SetParError(1, cbfit.sigma);
1037:   cbfunc.SetParLimits(1, time.front(), time.back());
1038:   cbfunc.SetParameter(2, cbfit.sigma);  // Width
1039:   cbfunc.SetParError(2, cbfit.sigma/5.);
1040:   cbfunc.SetParLimits(2, 0.5, 20.);
1041:   cbfunc.SetParameter(3, cbfit.alpha); // Tail parameter (negative for high-side tail)
1042:   cbfunc.SetParError(3, -cbfit.alpha/5.);
1043:   cbfunc.SetParLimits(3, -10., 0.);
1044:   // Try fixing the tail first
1045:   cbfunc.FixParameter(3, cbfit.alpha);
1046:   cbfunc.FixParameter(4, cbfit.nval);
1047: 
1048:   TFitResultPtr cbfitptr = tg.Fit(&cbfunc, "QNSB", "");
1049: 
1050:   if (cbfitptr%10) {
1051:     ATH_MSG_DEBUG( " First Crystal Ball waveform fit failed! ");
1052:     ATH_MSG_DEBUG( " Gauss Mean: " << gfit.mean << " RMS: " << gfit.sigma << " Peak:" << gfit.peak);
1053:     ATH_MSG_DEBUG( " CB    Mean: " << cbfitptr->Parameter(1) << " RMS: " << cbfitptr->Parameter(2) << " Peak:" << cbfitptr->Parameter(0) << " Alpha: " << cbfitptr->Parameter(3));
1054:   }
1055: 
1056:   // Now try releasing the tail parameter
1057:   cbfunc.ReleaseParameter(3);
1058:   cbfunc.SetParameter(3, cbfit.alpha); // Tail parameter (negative for high-side tail)
1059:   cbfunc.SetParError(3, -cbfit.alpha/5.);
1060:   cbfunc.SetParLimits(3, -10., 0.);
1061:   
1062:   cbfunc.ReleaseParameter(4);
1063:   cbfunc.SetParameter(4, cbfit.nval);  // Tail power
1064:   cbfunc.SetParError(4, cbfit.nval/5.);
1065:   cbfunc.SetParLimits(4, 0., 1.E3);
1066: 
1067:   cbfitptr = tg.Fit(&cbfunc, "QNSB", "");
1068: 
1069:   cbfit.fit_status = cbfitptr;
1070:   cbfit.valid = (cbfit.fit_status%10 == 0);
1071: 
1072:   if (! cbfit.valid) {
1073:     ATH_MSG_DEBUG( " Full Crystal Ball waveform fit failed! ");
1074:     ATH_MSG_DEBUG( " Gauss Mean: " << gfit.mean << " RMS: " << gfit.sigma << " Peak:" << gfit.peak);
1075:     ATH_MSG_DEBUG( " CB    Mean: " << cbfitptr->Parameter(1) << " RMS: " << cbfitptr->Parameter(2) << " Peak:" << cbfitptr->Parameter(0) << " Alpha: " << cbfitptr->Parameter(3));
1076:   } else {
1077:     // Improve estimation with fit results
1078:     cbfit.peak = cbfitptr->Parameter(0);
1079:     cbfit.mean = cbfitptr->Parameter(1);
1080:     cbfit.sigma = cbfitptr->Parameter(2);
1081:     cbfit.alpha = cbfitptr->Parameter(3);
1082:     cbfit.nval = cbfitptr->Parameter(4);
1083: 
1084:     double chi2 = cbfitptr->Chi2();
1085:     unsigned int ndf = cbfitptr->Ndf();
1086:     if (ndf == 0) ndf = 1;
1087:     cbfit.chi2ndf = chi2/ndf;
1088: 
1089:     // cbfit.integral = cbfunc.Integral(time.front(), time.back());
1090: 
1091:     // Try specific integral function to avoid FPE from symbolic integrator failing?
1092:     // Start with default precision values, yes this works!
1093:     double error;
1094:     cbfit.integral = cbfunc.IntegralOneDim(time.front(), time.back(), -1, -1, error);
1095: 
1096:     // Find time here (start from t=0 to avoid NaN)
1097:     cbfit.time = cbfunc.GetX( cbfit.peak * m_timingPeakFraction, 0., cbfit.mean );
1098: 
1099:     if (isnan(cbfit.time)) {
1100:       ATH_MSG_WARNING(" Crystal Ball fit returned time as NaN, assume fit failes");
1101:       cbfit = gfit;
1102:       //cbfit.time = gfit.time;
1103:       cbfit.fit_status = 4;
1104:       cbfit.valid = false;
1105:     }
1106: 
1107:     ATH_MSG_DEBUG("CB Fit  Mean: " << cbfit.mean << " RMS: " << cbfit.sigma 
1108: 		  << " Peak: " << cbfit.peak << " Int: " << cbfit.integral
1109: 		  << " Time: " << cbfit.time 
1110: 		  << " N: " << cbfit.nval << " Alpha: " << cbfit.alpha 
1111: 		  << " Chi2/Ndf: " << cbfit.chi2ndf );
1112: 
1113:   }
1114: 
1115:   return cbfit;
1116: }
1117: 
1118: WaveformFitResult&
1119: WaveformReconstructionTool::fitCBallOverflow(const WaveformFitResult& gfit, 
1120: 					     const std::vector<float> time,
1121: 					     const std::vector<float> wave) const {
1122: 
1123:   ATH_MSG_DEBUG("fitCBallOverflow called");
1124: 
1125:   // This must be static so we can return a reference
1126:   static WaveformFitResult cbfit;
1127:   cbfit.clear();
1128: 
1129:   // Must pass arrays to TGraph, use pointer to first vector element
1130:   TGraph tg(time.size(), &time[0], &wave[0]);
1131: 
1132:   // Find overflow times
1133:   // Must look for removed elements
1134:   float tover_start = time.front();
1135:   float tover_end = time.back();
1136: 
1137:   for (unsigned int i=1; i<wave.size(); i++) {
1138:     if (time[i]-time[i-1] <= 2.1) continue; // 2ns is normal spacing
1139:     tover_start = time[i-1];
1140:     tover_end = time[i];
```

## d32b0ff3 / Waveform/WaveRecTools/src/WaveformReconstructionTool.h

定位：`BooleanProperty m_removeOverflow`，原文件第106行。

```text
106:   BooleanProperty m_removeOverflow{this, "RemoveOverflow", false};
107: 
108:   //
109:   // Remove from first to last overflow
110:   BooleanProperty m_removeAllOverflow{this, "RemoveAllOverflow", true};
111: 
112:   // Maximum range to fit overflows (to avoid overshoot at end) in ns!
113:   IntegerProperty m_overflowFitRange{this, "OverflowFitRange", 170};
114:   
115:   //
116:   // Fraction of peak to set local hit time
117:   FloatProperty m_timingPeakFraction{this, "TimingPeakFraction", 0.4};
118: 
119:   //
120:   // When looking for secondary hits with a primary found above threshold
121:   // should we look before or after the primary hit?
122:   BooleanProperty m_findSecondaryBefore{this, "FindSecondaryBefore", true};
123:   BooleanProperty m_findSecondaryAfter{this, "FindSecondaryAfter", false};
124: 
125:   // Reco algorithms
126:   // Fill hit with raw data from waveform
127:   void fillRawHitValues(const RawWaveform& wave,
128: 			int lo_edge, int hi_edge,
129: 			xAOD::WaveformHit* hit) const;
130: 
131:   // Perform fits to WaveformHit data
132:   void reconstructHit(xAOD::WaveformHit* hit) const;
133: 
134:   // Baseline algorithms
135:   WaveformBaselineData& findSimpleBaseline(const RawWaveform& wave) const;
136:   WaveformBaselineData& findAdvancedBaseline(const RawWaveform& wave) const;
137:   WaveformBaselineData& findBaseline(const RawWaveform& wave, 
138: 				     xAOD::WaveformHit* hit) const;
139: 
140: 
141:   // Find peak in wave, return index to peak position, or -1 if 
142:   // peak isn't greater than threshold
143:   int findPeak(WaveformBaselineData& baseline, float threshold, 
144: 		std::vector<float>& wave) const;
145: 
146:   // Get estimate from waveform data itself
147:   WaveformFitResult& findRawHitValues(const std::vector<float> time, 
148: 				      const std::vector<float> wave) const;
149: 
150:   // Fit windowed data to Gaussian (to get initial estimate of parameters
151:   WaveformFitResult& fitGaussian(const WaveformFitResult& raw,
152: 				 const std::vector<float> time, 
153: 				 const std::vector<float> wave) const;
154: 
155:   // Find overflows and remove points from arrays
156:   bool findOverflow(float baseline, 
157: 		    std::vector<float>& time, std::vector<float>& wave) const;
158: 
159:   // Fit windowed data to CrystalBall function
160:   WaveformFitResult& fitCBall(const WaveformFitResult& gfit, 
161: 			      const std::vector<float> time, 
162: 			      const std::vector<float> wave) const;
163: 
164:   WaveformFitResult& fitCBallOverflow(const WaveformFitResult& gfit, 
165: 				      const std::vector<float> time, 
166: 				      const std::vector<float> wave) const;
167: 
168: };
169: 
170: #endif // WAVERECTOOLS_WAVEFORMRECONSTRUCTIONTOOL_H
```

## d32b0ff3 / Waveform/WaveRecAlgs/python/WaveRecAlgsConfig.py

定位：`"PreshowerWaveformRecAlg"`，原文件第31行。

```text
31:         acc.merge(WaveformHitRecCfg(flags, "PreshowerWaveformRecAlg", "Preshower", FitWindowWidth=100, **kwargs ))
32: 
33:     else:
34:         acc.merge(WaveformHitRecCfg(flags, "CaloWaveformRecAlg", "Calo", **kwargs))
35:         if flags.Input.isMC:
36:             print("Calo2WaveformRecAlg diabled for MC in WaveformReconstructionCfg!")
37:         else:
38:             # 2024/25 detectors (not in MC yet)
39:             acc.merge(WaveformHitRecCfg(flags, "Calo2WaveformRecAlg", "Calo2", **kwargs))
40:             acc.merge(WaveformHitRecCfg(flags, "CaloNuWaveformRecAlg", "CaloNu", BaselineSampleHi=50, **kwargs))
41:             acc.merge(WaveformHitRecCfg(flags, "VetoGmWaveformRecAlg", "VetoGm", FitWindowWidth=100, BaselineSampleHi=60, **kwargs))
42:             acc.merge(WaveformHitRecCfg(flags, "MuonWaveformRecAlg", "Muon", FitWindowWidth=100, BaselineSampleHi=60, **kwargs))
43: 
44:         # Make preshower window 200 ns wide (value in digitizer clock ticks)
45:         # Limit range to determine baseline for early channels
46:         acc.merge(WaveformHitRecCfg(flags, "VetoWaveformRecAlg", "Veto", FitWindowWidth=100, **kwargs))
47:         acc.merge(WaveformHitRecCfg(flags, "PreshowerWaveformRecAlg", "Preshower", FitWindowWidth=100, BaselineSampleHi=60, **kwargs ))
48:         acc.merge(WaveformHitRecCfg(flags, "TriggerWaveformRecAlg", "Trigger", FitWindowWidth=100, **kwargs))
49:         acc.merge(WaveformHitRecCfg(flags, "VetoNuWaveformRecAlg", "VetoNu", FitWindowWidth=100, BaselineSampleHi=60, KeepAll=True))
50: 
51:     acc.merge(WaveformTimingCfg(flags))
52: 
53:     return acc
54: 
55: # Return configured WaveformClock reconstruction algorithm
56: def WaveformClockRecCfg(flags, name="ClockRecAlg", **kwargs):
57: 
58:     acc = ComponentAccumulator()
59: 
60:     tool = ClockReconstructionTool(name="ClockReconstructionTool")
61:     # tool.CheckResult = True
62:     kwargs.setdefault("ClockReconstructionTool", tool)
63: 
64:     recoAlg = CompFactory.WaveClockRecAlg(name, **kwargs)
65:     recoAlg.ClockReconstructionTool = tool
66:     acc.addEventAlgo(recoAlg)
67: 
68:     return acc
69: 
70: # Return configured WaveformHit reconstruction algorithm
71: # Specify data source (Veto, VetoNu, Trigger, Preshower, Calo, Test)
72: def WaveformHitRecCfg(flags, name="WaveformRecAlg", source="", **kwargs):
73: 
74:     acc = ComponentAccumulator()
75: 
76:     #if flags.Input.isMC:
77:     #    kwargs.setdefault("PeakThreshold", 5)
78: 
79:     toolargs = {}
80:     # Remove arguments intended for WaveRecTool
81:     for key in ["PeakThreshold", "FitWindowWidth", "BaselineSampleHi"]:
82:         if key in kwargs: toolargs[key] = kwargs.pop(key)   
83:     tool  = WaveformReconstructionTool(name=source+"WaveformRecTool", **toolargs)
84: 
85:     toolargs = {}
86:     for key in ["KeepAll", "Prescale", "KeepOverflow"]:
87:         if key in kwargs: toolargs[key] = kwargs.pop(key)        
88:     tool2 = WaveformCleanupTool(name=source+"WaveformCleanupTool", **toolargs)
89:     
90:     kwargs.setdefault("WaveformContainerKey", source+"Waveforms")
91:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
92:     kwargs.setdefault("WaveformReconstructionTool", tool)
93:     kwargs.setdefault("WaveformCleanupTool", tool2)
94:               
95:     recoAlg = CompFactory.RawWaveformRecAlg(name, **kwargs)
96:     recoAlg.WaveformReconstructionTool = tool
97:     recoAlg.WaveformCleanupTool = tool2
98:     acc.addEventAlgo(recoAlg)
99: 
100:     return acc
101: 
102: def WaveformReconstructionOutputCfg(flags, **kwargs):
103:     """ Return ComponentAccumulator with output for Waveform Reco"""
104:     acc = ComponentAccumulator()
105:     ItemList = [
```

定位：`"PreshowerWaveformRecAlg"`，原文件第47行。

```text
47:         acc.merge(WaveformHitRecCfg(flags, "PreshowerWaveformRecAlg", "Preshower", FitWindowWidth=100, BaselineSampleHi=60, **kwargs ))
48:         acc.merge(WaveformHitRecCfg(flags, "TriggerWaveformRecAlg", "Trigger", FitWindowWidth=100, **kwargs))
49:         acc.merge(WaveformHitRecCfg(flags, "VetoNuWaveformRecAlg", "VetoNu", FitWindowWidth=100, BaselineSampleHi=60, KeepAll=True))
50: 
51:     acc.merge(WaveformTimingCfg(flags))
52: 
53:     return acc
54: 
55: # Return configured WaveformClock reconstruction algorithm
56: def WaveformClockRecCfg(flags, name="ClockRecAlg", **kwargs):
57: 
58:     acc = ComponentAccumulator()
59: 
60:     tool = ClockReconstructionTool(name="ClockReconstructionTool")
61:     # tool.CheckResult = True
62:     kwargs.setdefault("ClockReconstructionTool", tool)
63: 
64:     recoAlg = CompFactory.WaveClockRecAlg(name, **kwargs)
65:     recoAlg.ClockReconstructionTool = tool
66:     acc.addEventAlgo(recoAlg)
67: 
68:     return acc
69: 
70: # Return configured WaveformHit reconstruction algorithm
71: # Specify data source (Veto, VetoNu, Trigger, Preshower, Calo, Test)
72: def WaveformHitRecCfg(flags, name="WaveformRecAlg", source="", **kwargs):
73: 
74:     acc = ComponentAccumulator()
75: 
76:     #if flags.Input.isMC:
77:     #    kwargs.setdefault("PeakThreshold", 5)
78: 
79:     toolargs = {}
80:     # Remove arguments intended for WaveRecTool
81:     for key in ["PeakThreshold", "FitWindowWidth", "BaselineSampleHi"]:
82:         if key in kwargs: toolargs[key] = kwargs.pop(key)   
83:     tool  = WaveformReconstructionTool(name=source+"WaveformRecTool", **toolargs)
84: 
85:     toolargs = {}
86:     for key in ["KeepAll", "Prescale", "KeepOverflow"]:
87:         if key in kwargs: toolargs[key] = kwargs.pop(key)        
88:     tool2 = WaveformCleanupTool(name=source+"WaveformCleanupTool", **toolargs)
89:     
90:     kwargs.setdefault("WaveformContainerKey", source+"Waveforms")
91:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
92:     kwargs.setdefault("WaveformReconstructionTool", tool)
93:     kwargs.setdefault("WaveformCleanupTool", tool2)
94:               
95:     recoAlg = CompFactory.RawWaveformRecAlg(name, **kwargs)
96:     recoAlg.WaveformReconstructionTool = tool
97:     recoAlg.WaveformCleanupTool = tool2
98:     acc.addEventAlgo(recoAlg)
99: 
100:     return acc
101: 
102: def WaveformReconstructionOutputCfg(flags, **kwargs):
103:     """ Return ComponentAccumulator with output for Waveform Reco"""
104:     acc = ComponentAccumulator()
105:     ItemList = [
106:         "xAOD::WaveformHitContainer#*"
107:         , "xAOD::WaveformHitAuxContainer#*"
108:         , "xAOD::WaveformClock#*"
109:         , "xAOD::WaveformClockAuxInfo#*"
110:     ]
111:     print(flags)
112:     acc.merge(OutputStreamCfg(flags, "xAOD", ItemList, disableEventTag=True))
113:     # ostream = acc.getEventAlgo("OutputStreamRDO")
114:     # ostream.TakeItemsFromInput = True # Don't know what this does
115:     return acc
116: 
117: # Return configured "reconstruction" algorithm from scint SIM hits
118: # Specify data source (Veto, Trigger, Preshower)
119: def PseudoScintHitToWaveformRecCfg(flags, name="PseudoScintHitToWaveformRecAlg", source="", **kwargs):
120: 
121:     acc = ComponentAccumulator()
```

定位：`for key in ["PeakThreshold"`，原文件第81行。

```text
81:     for key in ["PeakThreshold", "FitWindowWidth", "BaselineSampleHi"]:
82:         if key in kwargs: toolargs[key] = kwargs.pop(key)   
83:     tool  = WaveformReconstructionTool(name=source+"WaveformRecTool", **toolargs)
84: 
85:     toolargs = {}
86:     for key in ["KeepAll", "Prescale", "KeepOverflow"]:
87:         if key in kwargs: toolargs[key] = kwargs.pop(key)        
88:     tool2 = WaveformCleanupTool(name=source+"WaveformCleanupTool", **toolargs)
89:     
90:     kwargs.setdefault("WaveformContainerKey", source+"Waveforms")
91:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
92:     kwargs.setdefault("WaveformReconstructionTool", tool)
93:     kwargs.setdefault("WaveformCleanupTool", tool2)
94:               
95:     recoAlg = CompFactory.RawWaveformRecAlg(name, **kwargs)
96:     recoAlg.WaveformReconstructionTool = tool
97:     recoAlg.WaveformCleanupTool = tool2
98:     acc.addEventAlgo(recoAlg)
99: 
100:     return acc
101: 
102: def WaveformReconstructionOutputCfg(flags, **kwargs):
103:     """ Return ComponentAccumulator with output for Waveform Reco"""
104:     acc = ComponentAccumulator()
105:     ItemList = [
106:         "xAOD::WaveformHitContainer#*"
107:         , "xAOD::WaveformHitAuxContainer#*"
108:         , "xAOD::WaveformClock#*"
109:         , "xAOD::WaveformClockAuxInfo#*"
110:     ]
111:     print(flags)
112:     acc.merge(OutputStreamCfg(flags, "xAOD", ItemList, disableEventTag=True))
113:     # ostream = acc.getEventAlgo("OutputStreamRDO")
114:     # ostream.TakeItemsFromInput = True # Don't know what this does
115:     return acc
116: 
117: # Return configured "reconstruction" algorithm from scint SIM hits
118: # Specify data source (Veto, Trigger, Preshower)
119: def PseudoScintHitToWaveformRecCfg(flags, name="PseudoScintHitToWaveformRecAlg", source="", **kwargs):
120: 
121:     acc = ComponentAccumulator()
122: 
123:     tool = CompFactory.PseudoSimToWaveformRecTool(name=source+"PseudoSimToWaveformRecTool", **kwargs)
124:     
125:     kwargs.setdefault("ScintHitContainerKey", source+"Hits")
126:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
127:     kwargs.setdefault("PseudoSimToWaveformRecTool", tool)
128: 
129:     
130:     recoAlg = CompFactory.PseudoScintHitToWaveformRecAlg(name, **kwargs)
131:     recoAlg.PseudoSimToWaveformRecTool = tool
132: 
133:     acc.addEventAlgo(recoAlg)
134: 
135:     return acc
136: 
137: # Return configured "reconstruction" algorithm from calo SIM hits
138: def PseudoCaloHitToWaveformRecCfg(flags, name="PseudoCaloHitToWaveformRecAlg", **kwargs):
139: 
140:     acc = ComponentAccumulator()
141: 
142:     tool = CompFactory.PseudoSimToWaveformRecTool(name="CaloPseudoSimToWaveformRecTool", **kwargs)
143:     
144:     kwargs.setdefault("CaloHitContainerKey", "EcalHits")
145:     kwargs.setdefault("WaveformHitContainerKey", "CaloWaveformHits")
146:     kwargs.setdefault("PseudoSimToWaveformRecTool", tool)
147:     
148:     recoAlg = CompFactory.PseudoCaloHitToWaveformRecAlg(name, **kwargs)
149:     recoAlg.PseudoSimToWaveformRecTool = tool
150: 
151:     acc.addEventAlgo(recoAlg)
152: 
153:     return acc
```

定位：`for key in ["KeepAll"`，原文件第86行。

```text
86:     for key in ["KeepAll", "Prescale", "KeepOverflow"]:
87:         if key in kwargs: toolargs[key] = kwargs.pop(key)        
88:     tool2 = WaveformCleanupTool(name=source+"WaveformCleanupTool", **toolargs)
89:     
90:     kwargs.setdefault("WaveformContainerKey", source+"Waveforms")
91:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
92:     kwargs.setdefault("WaveformReconstructionTool", tool)
93:     kwargs.setdefault("WaveformCleanupTool", tool2)
94:               
95:     recoAlg = CompFactory.RawWaveformRecAlg(name, **kwargs)
96:     recoAlg.WaveformReconstructionTool = tool
97:     recoAlg.WaveformCleanupTool = tool2
98:     acc.addEventAlgo(recoAlg)
99: 
100:     return acc
101: 
102: def WaveformReconstructionOutputCfg(flags, **kwargs):
103:     """ Return ComponentAccumulator with output for Waveform Reco"""
104:     acc = ComponentAccumulator()
105:     ItemList = [
106:         "xAOD::WaveformHitContainer#*"
107:         , "xAOD::WaveformHitAuxContainer#*"
108:         , "xAOD::WaveformClock#*"
109:         , "xAOD::WaveformClockAuxInfo#*"
110:     ]
111:     print(flags)
112:     acc.merge(OutputStreamCfg(flags, "xAOD", ItemList, disableEventTag=True))
113:     # ostream = acc.getEventAlgo("OutputStreamRDO")
114:     # ostream.TakeItemsFromInput = True # Don't know what this does
115:     return acc
116: 
117: # Return configured "reconstruction" algorithm from scint SIM hits
118: # Specify data source (Veto, Trigger, Preshower)
119: def PseudoScintHitToWaveformRecCfg(flags, name="PseudoScintHitToWaveformRecAlg", source="", **kwargs):
120: 
121:     acc = ComponentAccumulator()
122: 
123:     tool = CompFactory.PseudoSimToWaveformRecTool(name=source+"PseudoSimToWaveformRecTool", **kwargs)
124:     
125:     kwargs.setdefault("ScintHitContainerKey", source+"Hits")
126:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
127:     kwargs.setdefault("PseudoSimToWaveformRecTool", tool)
128: 
129:     
130:     recoAlg = CompFactory.PseudoScintHitToWaveformRecAlg(name, **kwargs)
131:     recoAlg.PseudoSimToWaveformRecTool = tool
132: 
133:     acc.addEventAlgo(recoAlg)
134: 
135:     return acc
136: 
137: # Return configured "reconstruction" algorithm from calo SIM hits
138: def PseudoCaloHitToWaveformRecCfg(flags, name="PseudoCaloHitToWaveformRecAlg", **kwargs):
139: 
140:     acc = ComponentAccumulator()
141: 
142:     tool = CompFactory.PseudoSimToWaveformRecTool(name="CaloPseudoSimToWaveformRecTool", **kwargs)
143:     
144:     kwargs.setdefault("CaloHitContainerKey", "EcalHits")
145:     kwargs.setdefault("WaveformHitContainerKey", "CaloWaveformHits")
146:     kwargs.setdefault("PseudoSimToWaveformRecTool", tool)
147:     
148:     recoAlg = CompFactory.PseudoCaloHitToWaveformRecAlg(name, **kwargs)
149:     recoAlg.PseudoSimToWaveformRecTool = tool
150: 
151:     acc.addEventAlgo(recoAlg)
152: 
153:     return acc
```

## d32b0ff3 / Waveform/WaveRecAlgs/src/RawWaveformRecAlg.cxx

定位：`RawWaveformRecAlg::execute(`，原文件第45行。

```text
45: RawWaveformRecAlg::execute(const EventContext& ctx) const {
46:   ATH_MSG_DEBUG("Executing");
47: 
48:   // Keep track of some statistics
49:   m_numberOfEvents++;
50: 
51:   ATH_MSG_DEBUG("Run: " << ctx.eventID().run_number() 
52: 		<< " Event: " << ctx.eventID().event_number());
53: 
54:   // Find the input waveform container
55:   SG::ReadHandle<RawWaveformContainer> waveformHandle(m_waveformContainerKey, ctx);
56: 
57:   ATH_CHECK( waveformHandle.isValid() );
58:   ATH_MSG_DEBUG("Found ReadHandle for RawWaveformContainer " << m_waveformContainerKey);
59: 
60:   // Find the output waveform container
61:   SG::WriteHandle<xAOD::WaveformHitContainer> hitContainerHandle(m_waveformHitContainerKey, ctx);
62:   ATH_CHECK( hitContainerHandle.record( std::make_unique<xAOD::WaveformHitContainer>(),
63: 					std::make_unique<xAOD::WaveformHitAuxContainer>() ) );
64: 
65:   ATH_MSG_DEBUG("WaveformsHitContainer '" << hitContainerHandle.name() << "' initialized");
66: 
67:   if (waveformHandle->size() == 0) {
68:     ATH_MSG_DEBUG("Waveform container found with zero length!");
69:     return StatusCode::SUCCESS;
70:   }
71: 
72:   // Save to local storage first
73:   xAOD::WaveformHitContainer* hit_cont_ptr = hitContainerHandle.ptr();
74: 
75:   // First reconstruct the primary hit (based on trigger time)
76:   for( const auto& wave : *waveformHandle) {
77:     ATH_MSG_DEBUG("Reconstruct primary waveform for channel " << wave->channel());
78:     CHECK( m_recoTool->reconstructPrimary(*wave, hit_cont_ptr) );
79:   }
80: 
81:   // Second, reconstruct any additional out of time hits
82:   if (m_findMultipleHits) {
83:     for( const auto& wave : *waveformHandle) {
84:       ATH_MSG_DEBUG("Reconstruct secondary waveform for channel " << wave->channel());
85:       CHECK( m_recoTool->reconstructSecondary(*wave, hit_cont_ptr) );
86:     }
87:   }
88: 
89:   // Also find the clock information
90:   SG::ReadHandle<xAOD::WaveformClock> clockHandle(m_clockKey, ctx);
91:   const xAOD::WaveformClock* clockptr = NULL;
92: 
93:   // Fix timing for all hits
94:   // Can survive without this, but make a note
95:   if ( clockHandle.isValid() ) {
96:     ATH_MSG_DEBUG("Found ReadHandle for WaveformClock");
97:     clockptr = clockHandle.ptr();
98:     CHECK( m_recoTool->setLocalTime(clockptr, hit_cont_ptr) );
99:   } else {
100:     ATH_MSG_WARNING("Didn't find ReadHandle for WaveformClock!");
101:   }
102: 
103:   ATH_MSG_DEBUG("WaveformsHitContainer '" << hitContainerHandle.name() << "' filled with "<< hitContainerHandle->size() <<" items");
104: 
105:   // Clean up waveforms
106:   CHECK( m_cleanupTool->cleanupWaveforms(hit_cont_ptr, ctx.eventID().event_number()) );
107:   
108:   // Keep track of some statistics on the SG container
109:   for (const auto& hit : *(hitContainerHandle.ptr())) {
110:     m_numberOfWaveforms++;
111:     if (hit->status_bit(xAOD::WaveformStatus::WAVE_OVERFLOW)) m_numberOfOverflows++;
112:     if (hit->status_bit(xAOD::WaveformStatus::SECONDARY)) m_numberOfSecondaries++;
113:     
114:     if (hit->status_bit(xAOD::WaveformStatus::GFIT_FAILED)) {
115:       m_numberOfFitErrors++;
116:     } else if (hit->status_bit(xAOD::WaveformStatus::CBFIT_FAILED)) {
117:       m_numberOfFitErrors++;
118:     }
119: 
```

## d32b0ff3 / Waveform/WaveRecAlgs/src/RawWaveformRecAlg.h

定位：`SG::ReadHandleKey`，原文件第72行。

```text
72:    * @name Input raw waveform data using SG::ReadHandleKey
73:    */
74:   //@{
75:   SG::ReadHandleKey<RawWaveformContainer> m_waveformContainerKey
76:     {this, "WaveformContainerKey", ""};
77:   //@}
78: 
79:   /**
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

定位：`SG::ReadHandleKey`，原文件第75行。

```text
75:   SG::ReadHandleKey<RawWaveformContainer> m_waveformContainerKey
76:     {this, "WaveformContainerKey", ""};
77:   //@}
78: 
79:   /**
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

定位：`SG::ReadHandleKey`，原文件第80行。

```text
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

定位：`SG::ReadHandleKey`，原文件第83行。

```text
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

定位：`ToolHandle`，原文件第27行。

```text
27: #include "GaudiKernel/ToolHandle.h"
28: 
29: // STL
30: #include <string>
31: 
32: class RawWaveformRecAlg : public AthReentrantAlgorithm {
33: 
34:  public:
35:   // Constructor
36:   RawWaveformRecAlg(const std::string& name, ISvcLocator* pSvcLocator);
37:   virtual ~RawWaveformRecAlg() = default;
38: 
39:   /** @name Usual algorithm methods */
40:   //@{
41:   virtual StatusCode initialize() override;
42:   virtual StatusCode execute(const EventContext& ctx) const override;
43:   virtual StatusCode finalize() override;
44:   //@}
45: 
46:   //
47:   // Look for more than one hit in each channel
48:   BooleanProperty m_findMultipleHits{this, "FindMultipleHits", true};
49: 
50:  private:
51: 
52:   /** @name Disallow default instantiation, copy, assignment */
53:   //@{
54:   RawWaveformRecAlg() = delete;
55:   RawWaveformRecAlg(const RawWaveformRecAlg&) = delete;
56:   RawWaveformRecAlg &operator=(const RawWaveformRecAlg&) = delete;
57:   //@}
58: 
59:   /**
60:    * @name Reconstruction tool
61:    */
62:   ToolHandle<IWaveformReconstructionTool> m_recoTool
63:     {this, "WaveformReconstructionTool", "WaveformReconstructionTool"};
64: 
65:   /**
66:    * @name Cleanup tool
67:    */
68:   ToolHandle<IWaveformCleanupTool> m_cleanupTool
69:     {this, "WaveformCleanupTool", "WaveformCleanupTool"};
70:   
71:   /**
72:    * @name Input raw waveform data using SG::ReadHandleKey
73:    */
74:   //@{
75:   SG::ReadHandleKey<RawWaveformContainer> m_waveformContainerKey
76:     {this, "WaveformContainerKey", ""};
77:   //@}
78: 
79:   /**
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
```

定位：`ToolHandle`，原文件第62行。

```text
62:   ToolHandle<IWaveformReconstructionTool> m_recoTool
63:     {this, "WaveformReconstructionTool", "WaveformReconstructionTool"};
64: 
65:   /**
66:    * @name Cleanup tool
67:    */
68:   ToolHandle<IWaveformCleanupTool> m_cleanupTool
69:     {this, "WaveformCleanupTool", "WaveformCleanupTool"};
70:   
71:   /**
72:    * @name Input raw waveform data using SG::ReadHandleKey
73:    */
74:   //@{
75:   SG::ReadHandleKey<RawWaveformContainer> m_waveformContainerKey
76:     {this, "WaveformContainerKey", ""};
77:   //@}
78: 
79:   /**
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

定位：`ToolHandle`，原文件第68行。

```text
68:   ToolHandle<IWaveformCleanupTool> m_cleanupTool
69:     {this, "WaveformCleanupTool", "WaveformCleanupTool"};
70:   
71:   /**
72:    * @name Input raw waveform data using SG::ReadHandleKey
73:    */
74:   //@{
75:   SG::ReadHandleKey<RawWaveformContainer> m_waveformContainerKey
76:     {this, "WaveformContainerKey", ""};
77:   //@}
78: 
79:   /**
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

## d32b0ff3 / PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx

定位：`void NtupleDumperAlg::FillWaveBranches(`，原文件第246行。

```text
246: void NtupleDumperAlg::FillWaveBranches(const xAOD::WaveformHitContainer &wave, bool isMC) const {
247:   // ATH_MSG_DEBUG("FillWaveBranches called");
248:   for (auto hit : wave) {
249:     if (!hit->secondary()) { // dont store secoondary hits as they can overwrite the primary hit
250:       int ch=hit->channel();
251: 
252:       m_wave_localtime[ch]=hit->localtime();
253:       m_wave_bcidtime[ch] = hit->bcid_time(); // Now corrected for offsets
254:       // Not sure why this doesn't exist in MC...
255:       if (!isMC)
256: 	m_wave_triggertime[ch] = hit->trigger_time(); // + m_clock_phase;
257:       m_wave_peak[ch]=hit->peak();
258:       m_wave_width[ch]=hit->width();
259:       m_wave_charge[ch]=hit->integral()/50;  // In pC
260: 
261:       m_wave_raw_peak[ch]=hit->raw_peak();
262:       m_wave_raw_charge[ch]=hit->raw_integral()/50;  // In pC
263:       m_wave_baseline_mean[ch]=hit->baseline_mean();
264:       m_wave_baseline_rms[ch]=hit->baseline_rms();
265:       m_wave_status[ch]=hit->hit_status();
266: 
267:       // Check for overflows
268:       if (hit->overflow()) {  // Overflow
269: 
270: 	// For v3 Waveforms, we store overflow time directly
271: 	if (hit->over_time() > 0) {
272: 	  m_wave_overflow[ch] = hit->over_time();
273: 	}
274: 	
275: 	// Need raw waveform, if it doesn't exist, set time as -1 (unknown)
276: 	else if (hit->wave_vector().size() == 0) {
277: 	  m_wave_overflow[ch] = -1;
278: 	  ATH_MSG_DEBUG("Found overflow hit but no wave_vector for channel " << ch << "!");
279: 	}
280: 
281: 	// Reconstruct from raw waveform
282: 	else {
283: 	  
284: 	  // Find first instance of max
285: 	  // I get crashes with std:: algorithms, so do this brute force
286: 	  float max_val=0.;
287: 	  unsigned int ifirst = 0;
288: 	  unsigned int ilast = 0;
289: 	  for (unsigned int i=0; i < hit->wave_vector().size(); i++) {
290: 	    if (hit->wave_vector()[i] > max_val) {  // New max
291: 	      max_val = hit->wave_vector()[i];
292: 	      ifirst = i;
293: 	      ilast = i;
294: 	    } else if (hit->wave_vector()[i] == max_val) { // Equal to max
295: 	      ilast = i;
296: 	    } 
297: 	  }
298: 	    	  
299: 	  m_wave_overflow[ch] = hit->time_vector()[ilast] - hit->time_vector()[ifirst];
300: 
301: 	  ATH_MSG_DEBUG("Found overflow from " << ifirst << " to " << ilast << " for tover = " << m_wave_overflow[ch]);
302: 	  
303: 	}
304:       } else {
305: 	m_wave_overflow[ch] = 0;
306:       }
307:     }
308:   }
309:   //ATH_MSG_DEBUG("FillWaveBranches done");
310: }
311: 
312: void NtupleDumperAlg::addCalibratedBranches(const std::string &name,
313: 					    std::list<int> channel_list) const {
314: 
315:   ATH_MSG_DEBUG("Adding calibrated " << name << " with channels " << channel_list);
316: 
317:   int nchannels = channel_list.size();
318:   for(int i=0;i<nchannels;i++) {
319:     int ch = channel_list.front();
320:     channel_list.pop_front();
```

## 88c457c1 / Waveform/WaveRecTools/src/WaveformReconstructionTool.cxx

定位：`WaveformReconstructionTool::reconstructPrimary(`，原文件第52行。

```text
52: WaveformReconstructionTool::reconstructPrimary(
53: 	 const RawWaveform& wave,
54: 	 xAOD::WaveformHitContainer* hitContainer) const {
55: 
56:   ATH_MSG_DEBUG(" reconstructPrimary called");
57: 
58:   xAOD::WaveformHit* newhit = new xAOD::WaveformHit();
59:   hitContainer->push_back(newhit);
60: 
61:   // Set digitizer channel and identifier
62:   newhit->set_channel(wave.channel());
63:   newhit->set_identifier(wave.identify());
64: 
65:   // Make sure we have ADC counts
66:   if (wave.adc_counts().size() == 0) {
67:     ATH_MSG_WARNING( "Found waveform for channel " << wave.channel() 
68: 		     << " with size " << wave.adc_counts().size() << "!");
69: 	
70:     newhit->set_status_bit(xAOD::WaveformStatus::WAVEFORM_MISSING);
71:     return StatusCode::SUCCESS;
72:   } 
73: 
74:   if (wave.adc_counts().size() != wave.n_samples()) {
75:     ATH_MSG_WARNING( "Found waveform for channel " << wave.channel() 
76: 		     << " with size " << wave.adc_counts().size() 
77: 		     << " not equal to number of samples " << wave.n_samples());
78: 	
79:     newhit->set_status_bit(xAOD::WaveformStatus::WAVEFORM_INVALID);
80:     return StatusCode::SUCCESS;
81:   }
82: 
83:   // Find the baseline for this waveform
84:   findBaseline(wave, newhit);
85: 
86:   // Check for problems
87:   if (newhit->status_bit(xAOD::WaveformStatus::BASELINE_FAILED)) {
88:     return StatusCode::SUCCESS;
89:   }
90:   
91:   // Get the nominal trigger time (in ns) from config
92:   float trigger_time = m_timingTool->nominalTriggerTime();
93: 
94:   // Set range for windowed data in digitizer samples
95:   float trigger_offset = m_timingTool->triggerTimeOffset(wave.channel());
96: 
97:   
98:   int lo_edge = int((trigger_time+trigger_offset)/2.) + m_windowStart;
99:   int hi_edge = int((trigger_time+trigger_offset)/2.) + m_windowStart + m_windowWidth;
100: 
101:   if (hi_edge >= int(wave.size())) {
102:     // This likely means we have the wrong digitizer range
103:     ATH_MSG_WARNING("Found channel " << wave.channel() << " with low edge: " << lo_edge << " hi edge: " << hi_edge << " > wave.size() " << wave.size());
104:     ATH_MSG_WARNING("  trigger_time + trigger_offset: " << (trigger_time+trigger_offset) << " => " << int((trigger_time+trigger_offset)/2.));
105:     newhit->set_status_bit(xAOD::WaveformStatus::WAVEFORM_INVALID);
106:     return StatusCode::SUCCESS;
107:   }
108:   
109:   // Adjust window time if 2nd digitizer triggered late
110:   // Waveform will arrive early by 16ns
111:   if (wave.trigger_offset() >= 1) {
112:     lo_edge -= 8;
113:     hi_edge -= 8;
114:   }
115: 
116:   // Fill raw hit values
117:   fillRawHitValues(wave, lo_edge, hi_edge, newhit);
118: 
119:   // Check if this is over threshold
120:   if (newhit->peak() < newhit->baseline_rms() * m_primaryPeakThreshold) {
121:     ATH_MSG_DEBUG("Primary hit failed threshold");
122:     newhit->set_status_bit(xAOD::WaveformStatus::THRESHOLD_FAILED);
123:   } else {
124:     // Reconstruct hit in this range
125:     reconstructHit(newhit);
126:   }
```

定位：`WaveformReconstructionTool::fillRawHitValues(`，原文件第391行。

```text
391: WaveformReconstructionTool::fillRawHitValues(const RawWaveform& wave,
392: 					   int lo_edge, int hi_edge, 
393: 					   xAOD::WaveformHit* hit) const {
394:   
395:   // First, make sure we don't overflow the waveform range
396:   if (lo_edge < 0) lo_edge = 0;
397:   if (hi_edge >= int(wave.size())) hi_edge = wave.size() - 1;
398:   if (hi_edge <= lo_edge) {
399:     ATH_MSG_WARNING("Channel " << wave.channel() << " waveform with lo: " << lo_edge << " hi: " << hi_edge << "!");
400:     return;
401:   }
402:   
403:   ATH_MSG_DEBUG("Fill channel " << wave.channel() 
404: 		<< " waveform from sample " << lo_edge << " to " << hi_edge);
405: 
406:   // Fill hit window with data from wave
407:   std::vector<float> wtime(hi_edge-lo_edge+1);
408:   std::vector<float> wwave(hi_edge-lo_edge+1);
409: 
410:   for (int i=lo_edge; i<=hi_edge; i++) {
411:     unsigned int j = i-lo_edge;
412:     wtime[j] = 2.*i; // 2ns per sample at 500 MHz
413:     wwave[j] = hit->baseline_mean() - wave.mv_per_bit() * wave.adc_counts()[i];
414:   }
415: 
416:   hit->set_time_vector(wtime);
417:   hit->set_wave_vector(wwave);
418: 
419:   // Set raw values
420:   WaveformFitResult raw = findRawHitValues(wtime, wwave);
421:   hit->set_peak(raw.peak);
422:   hit->set_mean(raw.mean);
423:   hit->set_width(raw.sigma);
424:   hit->set_integral(raw.integral);
425:   hit->set_localtime(raw.mean);
426:   hit->set_raw_peak(raw.peak);
427:   hit->set_raw_integral(raw.integral);
428: 
429:   // Indicate digitizer timing shift
430:   if (wave.trigger_offset() >= 1) {
431:     hit->set_status_bit(xAOD::WaveformStatus::TIMING_SHIFTED);
432:   }
433:       
434: 
435: }
436: 
437: // Reconstruct a hit from the RawWaveform in the range specified
438: // Range is in units digitizer samples (not ns)
439: void
440: WaveformReconstructionTool::reconstructHit(xAOD::WaveformHit* hit) const {
441: 
442:   // Time and waveform vectors
443:   // Don't use reference as we may modify this below
444:   std::vector<float> wtime = hit->time_vector();
445:   std::vector<float> wwave = hit->wave_vector();
446: 
447:   ATH_MSG_DEBUG("Reconstruct channel " << hit->channel() 
448: 		<< " waveform from " << wtime.front() 
449: 		<< " to " << wtime.back());
450: 
451:   // Fill values needed for fit (peak, mean, and sigma)
452:   WaveformFitResult raw;
453:   raw.peak = hit->peak();
454:   raw.mean = hit->mean();
455:   raw.sigma = hit->width();
456: 
457:   //
458:   // Perform Gaussian fit to waveform
459:   WaveformFitResult gfit = fitGaussian(raw, wtime, wwave);
460:   if (! gfit.valid) {
461:     // Lets try again with a more restricted width
462:     ATH_MSG_WARNING( " Gaussian waveform fit failed with width " << raw.sigma << " try reducing width to 1 " );
463:     raw.sigma = 1.;
464:     gfit = fitGaussian(raw, wtime, wwave);
465:     if (!gfit.valid) {
```

定位：`WaveformReconstructionTool::reconstructHit(`，原文件第440行。

```text
440: WaveformReconstructionTool::reconstructHit(xAOD::WaveformHit* hit) const {
441: 
442:   // Time and waveform vectors
443:   // Don't use reference as we may modify this below
444:   std::vector<float> wtime = hit->time_vector();
445:   std::vector<float> wwave = hit->wave_vector();
446: 
447:   ATH_MSG_DEBUG("Reconstruct channel " << hit->channel() 
448: 		<< " waveform from " << wtime.front() 
449: 		<< " to " << wtime.back());
450: 
451:   // Fill values needed for fit (peak, mean, and sigma)
452:   WaveformFitResult raw;
453:   raw.peak = hit->peak();
454:   raw.mean = hit->mean();
455:   raw.sigma = hit->width();
456: 
457:   //
458:   // Perform Gaussian fit to waveform
459:   WaveformFitResult gfit = fitGaussian(raw, wtime, wwave);
460:   if (! gfit.valid) {
461:     // Lets try again with a more restricted width
462:     ATH_MSG_WARNING( " Gaussian waveform fit failed with width " << raw.sigma << " try reducing width to 1 " );
463:     raw.sigma = 1.;
464:     gfit = fitGaussian(raw, wtime, wwave);
465:     if (!gfit.valid) {
466:       hit->set_status_bit(xAOD::WaveformStatus::GFIT_FAILED);
467:     }
468:   } 
469: 
470:   // Fit results (or raw if it failed)
471:   hit->set_peak(gfit.peak);
472:   hit->set_mean(gfit.mean);
473:   hit->set_width(gfit.sigma);
474:   hit->set_integral(gfit.integral);
475:   hit->set_localtime(gfit.time);
476:   
477:   //
478:   // Check for overflow
479:   if (m_removeOverflow && findOverflow(hit->baseline_mean(), wtime, wwave)) {
480:     ATH_MSG_INFO("Found waveform overflow");
481:     hit->set_status_bit(xAOD::WaveformStatus::WAVE_OVERFLOW);
482:   }
483:   
484:   //
485:   // Perform CB fit
486:   WaveformFitResult cbfit = fitCBall(gfit, wtime, wwave);
487:   if (! cbfit.valid) {
488:     ATH_MSG_WARNING("CrystalBall fit failed for channel " << hit->channel() << "!");
489:     // Still have gaussian parameters as an estimate
490:     hit->set_status_bit(xAOD::WaveformStatus::CBFIT_FAILED);
491:   } else {
492:     hit->set_peak(cbfit.peak);
493:     hit->set_mean(cbfit.mean);
494:     hit->set_width(cbfit.sigma);
495:     hit->set_integral(cbfit.integral);
496:     hit->set_localtime(cbfit.time);
497:     
498:     hit->set_alpha(cbfit.alpha);
499:     hit->set_nval(cbfit.nval);
500:   }
501: 
502:   ATH_MSG_DEBUG("Done reconstructing channel " << hit->channel() 
503: 		<< " waveform from " << wtime.front() << " to " << wtime.back());
504: 
505: }
506: 
507: // Returns location of peak in array wave
508: // Return value is -1 if peak is below threshold
509: int
510: WaveformReconstructionTool::findPeak(WaveformBaselineData& baseline, 
511: 				     float threshold,
512: 				     std::vector<float>& wave) const 
513: {
514: 
515:   ATH_MSG_DEBUG("findPeak called");
516: 
517:   // Find max value location in array
518:   unsigned int imax = std::max_element(wave.begin(), wave.end()) - wave.begin();
519:   float maxval = wave[imax];
520:   ATH_MSG_DEBUG( "Found peak value " << maxval << " at position " << imax );
521: 
522:   // Check if this is over threshold (in sigma)
523:   if (maxval < threshold*baseline.rms) {
524:     ATH_MSG_DEBUG("Failed threshold");
525:     return -1;
526:   }
527: 
528:   return imax;
529: }
530: 
531: bool
532: WaveformReconstructionTool::findOverflow(float baseline,
533: 	      std::vector<float>& time, std::vector<float>& wave) const {
534: 
535:   auto peakloc = std::max_element(wave.begin(), wave.end());
536: 
537:   // If peak value is less than baseline, we have no overflow
538:   if (*peakloc < baseline) return false;
539: 
540:   ATH_MSG_DEBUG("Removing overflows from waveform with length " << wave.size());
541: 
542:   // We have an overflow, remove all elements that are overflowing
543:   unsigned int i = peakloc - wave.begin();
544:   for (; i<wave.size(); i++) {
545:     if (wave[i] < baseline) continue;
546: 
547:     ATH_MSG_DEBUG("Removing position "<< i<< " with value " << wave[i] << " > " << baseline);
548:     // This is an overflow, remove elements
549:     time.erase(time.begin() + i);
550:     wave.erase(wave.begin() + i);
551:     i--;  // Decrement so that loop itertaion points to next element
552:   }
553: 
554:   ATH_MSG_DEBUG("Removed overflows, length now " << wave.size());
555:   return true;
556: }
557: 
558: WaveformBaselineData&
559: WaveformReconstructionTool::findSimpleBaseline(const RawWaveform& raw_wave) const {
560: 
561:   ATH_MSG_DEBUG( "findSimpleBaseline called" );
562:   //ATH_MSG_DEBUG( raw_wave );
563: 
564:   // This must be static so we can return a reference
565:   static WaveformBaselineData baseline;  
566:   baseline.clear();
567: 
568:   // Calling algorithm checks for proper data
569:   // Here we just check algorithm-specific issues
```

定位：`WaveformReconstructionTool::findRawHitValues(`，原文件第707行。

```text
707: WaveformReconstructionTool::findRawHitValues(const std::vector<float> time, const std::vector<float> wave) const {
708: 
709:   ATH_MSG_DEBUG("findRawHitValues called");
710: 
711:   // This must be static so we can return a reference
712:   static WaveformFitResult rfit;
713:   rfit.clear();
714: 
715:   // First, estimate starting values from input waveform
716:   // Will use this to pre-set fit values, but also as a backup in case fit fails
717:   double tot = 0.;
718:   double sum = 0.;
719:   double sum2 = 0.;
720:   for (unsigned int i=0; i<time.size(); i++) {
721:     //ATH_MSG_DEBUG("findRawHitValues Time: " << time[i] << " Wave: " << wave[i]);
722:     if (wave[i] <= 0.) continue; // Don't sum negative values, causes problems with RMS
723:     tot += wave[i];
724:     sum += time[i] * wave[i];
725:     sum2 += time[i] * time[i] * wave[i];
726:   }
727: 
728:   // Pointer to peak
729:   auto peakloc = std::max_element(wave.begin(), wave.end());
730: 
731:   // Initial parameters from waveform
732:   rfit.mean = sum/tot;
733:   rfit.sigma = std::sqrt(sum2/tot - rfit.mean*rfit.mean);
734:   rfit.peak = *peakloc;
735:   rfit.integral = 2*tot; // Factor of 2 because at 500 MHz, dt = 2 ns
736:   rfit.time = rfit.mean;
737: 
738:   ATH_MSG_DEBUG( 
739: 		"Initial Mean: " << rfit.mean 
740: 		<< " RMS: " << rfit.sigma 
741: 		<< " Peak: " << rfit.peak 
742: 		<< " Integral: " << rfit.integral
743: 		 );  
744: 
745:   // Fix bad values
746:   if (isnan(rfit.sigma)) {
747:     ATH_MSG_DEBUG("Found sigma: " << rfit.sigma << " Replace with 2.");
748:     rfit.sigma = 2.;
749:   }
750: 
751:   if (rfit.mean < time.front() || rfit.mean > time.back()) {
752:     rfit.mean = (3*time.front() + time.back())/4.; // Set time to 1/4 of way through window
753:     ATH_MSG_DEBUG("Found mean: " << rfit.time << " out of range " << time.front() << "-" << time.back() << " Replace with " << rfit.mean);
754:     rfit.time = rfit.mean;
755:   }
756: 
757:   return rfit;
758: }
759: 
760: WaveformFitResult&
761: WaveformReconstructionTool::fitGaussian(const WaveformFitResult& raw, const std::vector<float> time, const std::vector<float> wave) const {
762: 
763:   ATH_MSG_DEBUG("fitGaussian called");
764: 
765:   // This must be static so we can return a reference
766:   static WaveformFitResult gfit;
767:   gfit.clear();
768: 
769:   // Start with raw values by default
770:   gfit = raw;
771: 
772:   // Start by creating a TGraph and fitting this with a Gaussian
773:   // Must pass arrays to TGraph, use pointer to first vector element
774:   TGraph tg(time.size(), &time[0], &wave[0]);
775: 
776:   // Define fit function and preset range
777:   TF1 gfunc("gfunc", "gaus");
778:   gfunc.SetParameters(raw.peak, raw.mean, raw.sigma);
779:   gfunc.SetParError(0, raw.peak/10.);
780:   gfunc.SetParError(1, raw.sigma);
781:   gfunc.SetParError(2, raw.sigma / 5.);
```

定位：`WaveformReconstructionTool::fitGaussian(`，原文件第761行。

```text
761: WaveformReconstructionTool::fitGaussian(const WaveformFitResult& raw, const std::vector<float> time, const std::vector<float> wave) const {
762: 
763:   ATH_MSG_DEBUG("fitGaussian called");
764: 
765:   // This must be static so we can return a reference
766:   static WaveformFitResult gfit;
767:   gfit.clear();
768: 
769:   // Start with raw values by default
770:   gfit = raw;
771: 
772:   // Start by creating a TGraph and fitting this with a Gaussian
773:   // Must pass arrays to TGraph, use pointer to first vector element
774:   TGraph tg(time.size(), &time[0], &wave[0]);
775: 
776:   // Define fit function and preset range
777:   TF1 gfunc("gfunc", "gaus");
778:   gfunc.SetParameters(raw.peak, raw.mean, raw.sigma);
779:   gfunc.SetParError(0, raw.peak/10.);
780:   gfunc.SetParError(1, raw.sigma);
781:   gfunc.SetParError(2, raw.sigma / 5.);
782:   gfunc.SetParLimits(2, 0., 20.);  // Constrain width
783: 
784:   TFitResultPtr gfitptr = tg.Fit(&gfunc, "QNS", "");
785: 
786:   gfit.fit_status = gfitptr;
787:   gfit.valid = (gfit.fit_status == 0);
788: 
789:   if (!gfitptr->IsValid()) {
790:     ATH_MSG_WARNING( " Gaussian waveform fit failed! ");
791:   } else {
792:     // Improve estimation with fit results
793:     gfit.peak = gfitptr->Parameter(0);
794:     gfit.mean = gfitptr->Parameter(1);
795:     gfit.sigma = gfitptr->Parameter(2);
796:     gfit.integral = gfunc.Integral(time.front(), time.back());
797: 
798:     // Find time here
799:     gfit.time = gfunc.GetX( gfit.peak * m_timingPeakFraction, time.front(), gfit.mean );
800: 
801:     if (isnan(gfit.time)) {
802:       ATH_MSG_WARNING(" Gaussian fit returned time as NaN, assume fit failed");
803:       gfit = raw;
804:       gfit.fit_status = false;
805:     }
806: 
807:     ATH_MSG_DEBUG("G Fit   Mean: " << gfit.mean << " RMS: " << gfit.sigma 
808: 		  << " Peak: " << gfit.peak << " Int: " << gfit.integral << " Time: " << gfit.time);
809:   }
810: 
811:   return gfit;
812: }
813: 
814: WaveformFitResult&
815: WaveformReconstructionTool::fitCBall(const WaveformFitResult& gfit, 
816:      const std::vector<float> time, const std::vector<float> wave) const {
817: 
818:   ATH_MSG_DEBUG("fitCBall called");
819: 
820:   // This must be static so we can return a reference
821:   static WaveformFitResult cbfit;
822:   cbfit.clear();
823: 
824:   // Must pass arrays to TGraph, use pointer to first vector element
825:   TGraph tg(time.size(), &time[0], &wave[0]);
826: 
827:   // Values to preset CB fit
828:   cbfit.peak = abs(gfit.peak);
829:   cbfit.mean = gfit.mean;
830:   cbfit.sigma = abs(gfit.sigma);
831:   if (cbfit.sigma > 20.) cbfit.sigma = 2.;
832:   cbfit.alpha = -0.5;  // Negative to get tail on high side
833:   cbfit.nval = 2.;
834: 
835:   // Define fit function and preset values
836:   TF1 cbfunc("cbfunc", "crystalball");
837:   cbfunc.SetParameter(0, cbfit.peak); // Peak height
838:   cbfunc.SetParError(0,  cbfit.peak/10.);
839:   cbfunc.SetParameter(1, cbfit.mean); // Mean
840:   cbfunc.SetParError(1, cbfit.sigma);
841:   cbfunc.SetParameter(2, cbfit.sigma);  // Width
842:   cbfunc.SetParError(2, cbfit.sigma/5.);
843:   cbfunc.SetParLimits(2, 0., 20.);
844:   cbfunc.SetParameter(3, cbfit.alpha); // Tail parameter (negative for high-side tail)
845:   cbfunc.SetParError(3, -cbfit.alpha/5.);
846:   cbfunc.SetParLimits(3, -10., 0.);
847:   // Try fixing the tail first
848:   cbfunc.FixParameter(4, cbfit.nval);
849: 
850:   TFitResultPtr cbfitptr = tg.Fit(&cbfunc, "QNS", "");
851: 
852:   if (!cbfitptr->IsValid()) {
853:     ATH_MSG_DEBUG( " First Crystal Ball waveform fit failed! ");
854:   }
855: 
856:   // Now try releasing the tail parameter
857:   cbfunc.ReleaseParameter(4);
858:   cbfunc.SetParameter(4, cbfit.nval);  // Tail power
859:   cbfunc.SetParError(4, cbfit.nval/5.);
860:   cbfunc.SetParLimits(4, 0., 1.E3);
861: 
862:   cbfitptr = tg.Fit(&cbfunc, "QNS", "");
863: 
864:   cbfit.fit_status = cbfitptr;
865:   cbfit.valid = (cbfit.fit_status == 0);
866: 
867:   if (!cbfitptr->IsValid()) {
868:     ATH_MSG_DEBUG( " Full Crystal Ball waveform fit failed! ");
869:   } else {
870:     // Improve estimation with fit results
871:     cbfit.peak = cbfitptr->Parameter(0);
872:     cbfit.mean = cbfitptr->Parameter(1);
873:     cbfit.sigma = cbfitptr->Parameter(2);
874:     cbfit.alpha = cbfitptr->Parameter(3);
875:     cbfit.nval = cbfitptr->Parameter(4);
876: 
877:     double chi2 = cbfitptr->Chi2();
878:     unsigned int ndf = cbfitptr->Ndf();
879:     if (ndf == 0) ndf = 1;
880:     cbfit.chi2ndf = chi2/ndf;
881: 
882:     cbfit.integral = cbfunc.Integral(time.front(), time.back());
883: 
884:     // Find time here
885:     cbfit.time = cbfunc.GetX( cbfit.peak * m_timingPeakFraction, time.front(), cbfit.mean );
886: 
887:     if (isnan(cbfit.time)) {
888:       ATH_MSG_WARNING(" Crystal Ball fit returned time as NaN, assume fit failes");
889:       cbfit.time = gfit.time;
890:       cbfit.fit_status = false;
```

定位：`WaveformReconstructionTool::fitCBall(`，原文件第815行。

```text
815: WaveformReconstructionTool::fitCBall(const WaveformFitResult& gfit, 
816:      const std::vector<float> time, const std::vector<float> wave) const {
817: 
818:   ATH_MSG_DEBUG("fitCBall called");
819: 
820:   // This must be static so we can return a reference
821:   static WaveformFitResult cbfit;
822:   cbfit.clear();
823: 
824:   // Must pass arrays to TGraph, use pointer to first vector element
825:   TGraph tg(time.size(), &time[0], &wave[0]);
826: 
827:   // Values to preset CB fit
828:   cbfit.peak = abs(gfit.peak);
829:   cbfit.mean = gfit.mean;
830:   cbfit.sigma = abs(gfit.sigma);
831:   if (cbfit.sigma > 20.) cbfit.sigma = 2.;
832:   cbfit.alpha = -0.5;  // Negative to get tail on high side
833:   cbfit.nval = 2.;
834: 
835:   // Define fit function and preset values
836:   TF1 cbfunc("cbfunc", "crystalball");
837:   cbfunc.SetParameter(0, cbfit.peak); // Peak height
838:   cbfunc.SetParError(0,  cbfit.peak/10.);
839:   cbfunc.SetParameter(1, cbfit.mean); // Mean
840:   cbfunc.SetParError(1, cbfit.sigma);
841:   cbfunc.SetParameter(2, cbfit.sigma);  // Width
842:   cbfunc.SetParError(2, cbfit.sigma/5.);
843:   cbfunc.SetParLimits(2, 0., 20.);
844:   cbfunc.SetParameter(3, cbfit.alpha); // Tail parameter (negative for high-side tail)
845:   cbfunc.SetParError(3, -cbfit.alpha/5.);
846:   cbfunc.SetParLimits(3, -10., 0.);
847:   // Try fixing the tail first
848:   cbfunc.FixParameter(4, cbfit.nval);
849: 
850:   TFitResultPtr cbfitptr = tg.Fit(&cbfunc, "QNS", "");
851: 
852:   if (!cbfitptr->IsValid()) {
853:     ATH_MSG_DEBUG( " First Crystal Ball waveform fit failed! ");
854:   }
855: 
856:   // Now try releasing the tail parameter
857:   cbfunc.ReleaseParameter(4);
858:   cbfunc.SetParameter(4, cbfit.nval);  // Tail power
859:   cbfunc.SetParError(4, cbfit.nval/5.);
860:   cbfunc.SetParLimits(4, 0., 1.E3);
861: 
862:   cbfitptr = tg.Fit(&cbfunc, "QNS", "");
863: 
864:   cbfit.fit_status = cbfitptr;
865:   cbfit.valid = (cbfit.fit_status == 0);
866: 
867:   if (!cbfitptr->IsValid()) {
868:     ATH_MSG_DEBUG( " Full Crystal Ball waveform fit failed! ");
869:   } else {
870:     // Improve estimation with fit results
871:     cbfit.peak = cbfitptr->Parameter(0);
872:     cbfit.mean = cbfitptr->Parameter(1);
873:     cbfit.sigma = cbfitptr->Parameter(2);
874:     cbfit.alpha = cbfitptr->Parameter(3);
875:     cbfit.nval = cbfitptr->Parameter(4);
876: 
877:     double chi2 = cbfitptr->Chi2();
878:     unsigned int ndf = cbfitptr->Ndf();
879:     if (ndf == 0) ndf = 1;
880:     cbfit.chi2ndf = chi2/ndf;
881: 
882:     cbfit.integral = cbfunc.Integral(time.front(), time.back());
883: 
884:     // Find time here
885:     cbfit.time = cbfunc.GetX( cbfit.peak * m_timingPeakFraction, time.front(), cbfit.mean );
886: 
887:     if (isnan(cbfit.time)) {
888:       ATH_MSG_WARNING(" Crystal Ball fit returned time as NaN, assume fit failes");
889:       cbfit.time = gfit.time;
890:       cbfit.fit_status = false;
891:     }
892: 
893:     ATH_MSG_DEBUG("CB Fit  Mean: " << cbfit.mean << " RMS: " << cbfit.sigma 
894: 		  << " Peak: " << cbfit.peak << " Int: " << cbfit.integral
895: 		  << " Time: " << cbfit.time 
896: 		  << " N: " << cbfit.nval << " Alpha: " << cbfit.alpha 
897: 		  << " Chi2/Ndf: " << cbfit.chi2ndf );
898: 
899:   }
900: 
901:   return cbfit;
902: }
```

## 88c457c1 / Waveform/WaveRecTools/src/WaveformReconstructionTool.h

定位：`BooleanProperty m_removeOverflow`，原文件第106行。

```text
106:   BooleanProperty m_removeOverflow{this, "RemoveOverflow", true};
107: 
108:   //
109:   // Fraction of peak to set local hit time
110:   FloatProperty m_timingPeakFraction{this, "TimingPeakFraction", 0.4};
111: 
112:   //
113:   // When looking for secondary hits with a primary found above threshold
114:   // should we look before or after the primary hit?
115:   BooleanProperty m_findSecondaryBefore{this, "FindSecondaryBefore", true};
116:   BooleanProperty m_findSecondaryAfter{this, "FindSecondaryAfter", false};
117: 
118:   // Reco algorithms
119:   // Fill hit with raw data from waveform
120:   void fillRawHitValues(const RawWaveform& wave,
121: 			int lo_edge, int hi_edge,
122: 			xAOD::WaveformHit* hit) const;
123: 
124:   // Perform fits to WaveformHit data
125:   void reconstructHit(xAOD::WaveformHit* hit) const;
126: 
127:   // Baseline algorithms
128:   WaveformBaselineData& findSimpleBaseline(const RawWaveform& wave) const;
129:   WaveformBaselineData& findAdvancedBaseline(const RawWaveform& wave) const;
130:   WaveformBaselineData& findBaseline(const RawWaveform& wave, 
131: 				     xAOD::WaveformHit* hit) const;
132: 
133: 
134:   // Find peak in wave, return index to peak position, or -1 if 
135:   // peak isn't greater than threshold
136:   int findPeak(WaveformBaselineData& baseline, float threshold, 
137: 		std::vector<float>& wave) const;
138: 
139:   // Get estimate from waveform data itself
140:   WaveformFitResult& findRawHitValues(const std::vector<float> time, 
141: 				      const std::vector<float> wave) const;
142: 
143:   // Fit windowed data to Gaussian (to get initial estimate of parameters
144:   WaveformFitResult& fitGaussian(const WaveformFitResult& raw,
145: 				 const std::vector<float> time, 
146: 				 const std::vector<float> wave) const;
147: 
148:   // Find overflows and remove points from arrays
149:   bool findOverflow(float baseline, 
150: 		    std::vector<float>& time, std::vector<float>& wave) const;
151: 
152:   // Fit windowed data to CrystalBall function
153:   WaveformFitResult& fitCBall(const WaveformFitResult& gfit, 
154: 			      const std::vector<float> time, 
155: 			      const std::vector<float> wave) const;
156: 
157: };
158: 
159: #endif // WAVERECTOOLS_WAVEFORMRECONSTRUCTIONTOOL_H
```

## 88c457c1 / Waveform/WaveRecAlgs/python/WaveRecAlgsConfig.py

定位：`"PreshowerWaveformRecAlg"`，原文件第31行。

```text
31:         acc.merge(WaveformHitRecCfg(flags, "PreshowerWaveformRecAlg", "Preshower", FitWindowWidth=100, **kwargs ))
32: 
33:     else:
34:         acc.merge(WaveformHitRecCfg(flags, "CaloWaveformRecAlg", "Calo", **kwargs))
35:         if flags.Input.isMC:
36:             print("Calo2WaveformRecAlg diabled for MC in WaveformReconstructionCfg!")
37:         else:
38:             # 2024/25 detectors (not in MC yet)
39:             acc.merge(WaveformHitRecCfg(flags, "Calo2WaveformRecAlg", "Calo2", **kwargs))
40:             acc.merge(WaveformHitRecCfg(flags, "CaloNuWaveformRecAlg", "CaloNu", BaselineSampleHi=50, **kwargs))
41:             acc.merge(WaveformHitRecCfg(flags, "VetoGmWaveformRecAlg", "VetoGm", FitWindowWidth=100, BaselineSampleHi=60, **kwargs))
42:             acc.merge(WaveformHitRecCfg(flags, "MuonWaveformRecAlg", "Muon", FitWindowWidth=100, BaselineSampleHi=60, **kwargs))
43: 
44:         # Make preshower window 200 ns wide (value in digitizer clock ticks)
45:         # Limit range to determine baseline for early channels
46:         acc.merge(WaveformHitRecCfg(flags, "VetoWaveformRecAlg", "Veto", FitWindowWidth=100, **kwargs))
47:         acc.merge(WaveformHitRecCfg(flags, "PreshowerWaveformRecAlg", "Preshower", FitWindowWidth=100, BaselineSampleHi=60, **kwargs ))
48:         acc.merge(WaveformHitRecCfg(flags, "TriggerWaveformRecAlg", "Trigger", FitWindowWidth=100, **kwargs))
49:         acc.merge(WaveformHitRecCfg(flags, "VetoNuWaveformRecAlg", "VetoNu", FitWindowWidth=100, BaselineSampleHi=60, KeepAll=True))
50: 
51:     acc.merge(WaveformTimingCfg(flags))
52: 
53:     return acc
54: 
55: # Return configured WaveformClock reconstruction algorithm
56: def WaveformClockRecCfg(flags, name="ClockRecAlg", **kwargs):
57: 
58:     acc = ComponentAccumulator()
59: 
60:     tool = ClockReconstructionTool(name="ClockReconstructionTool")
61:     # tool.CheckResult = True
62:     kwargs.setdefault("ClockReconstructionTool", tool)
63: 
64:     recoAlg = CompFactory.WaveClockRecAlg(name, **kwargs)
65:     recoAlg.ClockReconstructionTool = tool
66:     acc.addEventAlgo(recoAlg)
67: 
68:     return acc
69: 
70: # Return configured WaveformHit reconstruction algorithm
71: # Specify data source (Veto, VetoNu, Trigger, Preshower, Calo, Test)
72: def WaveformHitRecCfg(flags, name="WaveformRecAlg", source="", **kwargs):
73: 
74:     acc = ComponentAccumulator()
75: 
76:     #if flags.Input.isMC:
77:     #    kwargs.setdefault("PeakThreshold", 5)
78: 
79:     toolargs = {}
80:     # Remove arguments intended for WaveRecTool
81:     for key in ["PeakThreshold", "FitWindowWidth", "BaselineSampleHi"]:
82:         if key in kwargs: toolargs[key] = kwargs.pop(key)   
83:     tool  = WaveformReconstructionTool(name=source+"WaveformRecTool", **toolargs)
84: 
85:     toolargs = {}
86:     for key in ["KeepAll", "Prescale"]:
87:         if key in kwargs: toolargs[key] = kwargs.pop(key)        
88:     tool2 = WaveformCleanupTool(name=source+"WaveformCleanupTool", **toolargs)
89:     
90:     kwargs.setdefault("WaveformContainerKey", source+"Waveforms")
91:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
92:     kwargs.setdefault("WaveformReconstructionTool", tool)
93:     kwargs.setdefault("WaveformCleanupTool", tool2)
94:               
95:     recoAlg = CompFactory.RawWaveformRecAlg(name, **kwargs)
96:     recoAlg.WaveformReconstructionTool = tool
97:     recoAlg.WaveformCleanupTool = tool2
98:     acc.addEventAlgo(recoAlg)
99: 
100:     return acc
101: 
102: def WaveformReconstructionOutputCfg(flags, **kwargs):
103:     """ Return ComponentAccumulator with output for Waveform Reco"""
104:     acc = ComponentAccumulator()
105:     ItemList = [
```

定位：`"PreshowerWaveformRecAlg"`，原文件第47行。

```text
47:         acc.merge(WaveformHitRecCfg(flags, "PreshowerWaveformRecAlg", "Preshower", FitWindowWidth=100, BaselineSampleHi=60, **kwargs ))
48:         acc.merge(WaveformHitRecCfg(flags, "TriggerWaveformRecAlg", "Trigger", FitWindowWidth=100, **kwargs))
49:         acc.merge(WaveformHitRecCfg(flags, "VetoNuWaveformRecAlg", "VetoNu", FitWindowWidth=100, BaselineSampleHi=60, KeepAll=True))
50: 
51:     acc.merge(WaveformTimingCfg(flags))
52: 
53:     return acc
54: 
55: # Return configured WaveformClock reconstruction algorithm
56: def WaveformClockRecCfg(flags, name="ClockRecAlg", **kwargs):
57: 
58:     acc = ComponentAccumulator()
59: 
60:     tool = ClockReconstructionTool(name="ClockReconstructionTool")
61:     # tool.CheckResult = True
62:     kwargs.setdefault("ClockReconstructionTool", tool)
63: 
64:     recoAlg = CompFactory.WaveClockRecAlg(name, **kwargs)
65:     recoAlg.ClockReconstructionTool = tool
66:     acc.addEventAlgo(recoAlg)
67: 
68:     return acc
69: 
70: # Return configured WaveformHit reconstruction algorithm
71: # Specify data source (Veto, VetoNu, Trigger, Preshower, Calo, Test)
72: def WaveformHitRecCfg(flags, name="WaveformRecAlg", source="", **kwargs):
73: 
74:     acc = ComponentAccumulator()
75: 
76:     #if flags.Input.isMC:
77:     #    kwargs.setdefault("PeakThreshold", 5)
78: 
79:     toolargs = {}
80:     # Remove arguments intended for WaveRecTool
81:     for key in ["PeakThreshold", "FitWindowWidth", "BaselineSampleHi"]:
82:         if key in kwargs: toolargs[key] = kwargs.pop(key)   
83:     tool  = WaveformReconstructionTool(name=source+"WaveformRecTool", **toolargs)
84: 
85:     toolargs = {}
86:     for key in ["KeepAll", "Prescale"]:
87:         if key in kwargs: toolargs[key] = kwargs.pop(key)        
88:     tool2 = WaveformCleanupTool(name=source+"WaveformCleanupTool", **toolargs)
89:     
90:     kwargs.setdefault("WaveformContainerKey", source+"Waveforms")
91:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
92:     kwargs.setdefault("WaveformReconstructionTool", tool)
93:     kwargs.setdefault("WaveformCleanupTool", tool2)
94:               
95:     recoAlg = CompFactory.RawWaveformRecAlg(name, **kwargs)
96:     recoAlg.WaveformReconstructionTool = tool
97:     recoAlg.WaveformCleanupTool = tool2
98:     acc.addEventAlgo(recoAlg)
99: 
100:     return acc
101: 
102: def WaveformReconstructionOutputCfg(flags, **kwargs):
103:     """ Return ComponentAccumulator with output for Waveform Reco"""
104:     acc = ComponentAccumulator()
105:     ItemList = [
106:         "xAOD::WaveformHitContainer#*"
107:         , "xAOD::WaveformHitAuxContainer#*"
108:         , "xAOD::WaveformClock#*"
109:         , "xAOD::WaveformClockAuxInfo#*"
110:     ]
111:     print(flags)
112:     acc.merge(OutputStreamCfg(flags, "xAOD", ItemList, disableEventTag=True))
113:     # ostream = acc.getEventAlgo("OutputStreamRDO")
114:     # ostream.TakeItemsFromInput = True # Don't know what this does
115:     return acc
116: 
117: # Return configured "reconstruction" algorithm from scint SIM hits
118: # Specify data source (Veto, Trigger, Preshower)
119: def PseudoScintHitToWaveformRecCfg(flags, name="PseudoScintHitToWaveformRecAlg", source="", **kwargs):
120: 
121:     acc = ComponentAccumulator()
```

定位：`for key in ["PeakThreshold"`，原文件第81行。

```text
81:     for key in ["PeakThreshold", "FitWindowWidth", "BaselineSampleHi"]:
82:         if key in kwargs: toolargs[key] = kwargs.pop(key)   
83:     tool  = WaveformReconstructionTool(name=source+"WaveformRecTool", **toolargs)
84: 
85:     toolargs = {}
86:     for key in ["KeepAll", "Prescale"]:
87:         if key in kwargs: toolargs[key] = kwargs.pop(key)        
88:     tool2 = WaveformCleanupTool(name=source+"WaveformCleanupTool", **toolargs)
89:     
90:     kwargs.setdefault("WaveformContainerKey", source+"Waveforms")
91:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
92:     kwargs.setdefault("WaveformReconstructionTool", tool)
93:     kwargs.setdefault("WaveformCleanupTool", tool2)
94:               
95:     recoAlg = CompFactory.RawWaveformRecAlg(name, **kwargs)
96:     recoAlg.WaveformReconstructionTool = tool
97:     recoAlg.WaveformCleanupTool = tool2
98:     acc.addEventAlgo(recoAlg)
99: 
100:     return acc
101: 
102: def WaveformReconstructionOutputCfg(flags, **kwargs):
103:     """ Return ComponentAccumulator with output for Waveform Reco"""
104:     acc = ComponentAccumulator()
105:     ItemList = [
106:         "xAOD::WaveformHitContainer#*"
107:         , "xAOD::WaveformHitAuxContainer#*"
108:         , "xAOD::WaveformClock#*"
109:         , "xAOD::WaveformClockAuxInfo#*"
110:     ]
111:     print(flags)
112:     acc.merge(OutputStreamCfg(flags, "xAOD", ItemList, disableEventTag=True))
113:     # ostream = acc.getEventAlgo("OutputStreamRDO")
114:     # ostream.TakeItemsFromInput = True # Don't know what this does
115:     return acc
116: 
117: # Return configured "reconstruction" algorithm from scint SIM hits
118: # Specify data source (Veto, Trigger, Preshower)
119: def PseudoScintHitToWaveformRecCfg(flags, name="PseudoScintHitToWaveformRecAlg", source="", **kwargs):
120: 
121:     acc = ComponentAccumulator()
122: 
123:     tool = CompFactory.PseudoSimToWaveformRecTool(name=source+"PseudoSimToWaveformRecTool", **kwargs)
124:     
125:     kwargs.setdefault("ScintHitContainerKey", source+"Hits")
126:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
127:     kwargs.setdefault("PseudoSimToWaveformRecTool", tool)
128: 
129:     
130:     recoAlg = CompFactory.PseudoScintHitToWaveformRecAlg(name, **kwargs)
131:     recoAlg.PseudoSimToWaveformRecTool = tool
132: 
133:     acc.addEventAlgo(recoAlg)
134: 
135:     return acc
136: 
137: # Return configured "reconstruction" algorithm from calo SIM hits
138: def PseudoCaloHitToWaveformRecCfg(flags, name="PseudoCaloHitToWaveformRecAlg", **kwargs):
139: 
140:     acc = ComponentAccumulator()
141: 
142:     tool = CompFactory.PseudoSimToWaveformRecTool(name="CaloPseudoSimToWaveformRecTool", **kwargs)
143:     
144:     kwargs.setdefault("CaloHitContainerKey", "EcalHits")
145:     kwargs.setdefault("WaveformHitContainerKey", "CaloWaveformHits")
146:     kwargs.setdefault("PseudoSimToWaveformRecTool", tool)
147:     
148:     recoAlg = CompFactory.PseudoCaloHitToWaveformRecAlg(name, **kwargs)
149:     recoAlg.PseudoSimToWaveformRecTool = tool
150: 
151:     acc.addEventAlgo(recoAlg)
152: 
153:     return acc
```

定位：`for key in ["KeepAll"`，原文件第86行。

```text
86:     for key in ["KeepAll", "Prescale"]:
87:         if key in kwargs: toolargs[key] = kwargs.pop(key)        
88:     tool2 = WaveformCleanupTool(name=source+"WaveformCleanupTool", **toolargs)
89:     
90:     kwargs.setdefault("WaveformContainerKey", source+"Waveforms")
91:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
92:     kwargs.setdefault("WaveformReconstructionTool", tool)
93:     kwargs.setdefault("WaveformCleanupTool", tool2)
94:               
95:     recoAlg = CompFactory.RawWaveformRecAlg(name, **kwargs)
96:     recoAlg.WaveformReconstructionTool = tool
97:     recoAlg.WaveformCleanupTool = tool2
98:     acc.addEventAlgo(recoAlg)
99: 
100:     return acc
101: 
102: def WaveformReconstructionOutputCfg(flags, **kwargs):
103:     """ Return ComponentAccumulator with output for Waveform Reco"""
104:     acc = ComponentAccumulator()
105:     ItemList = [
106:         "xAOD::WaveformHitContainer#*"
107:         , "xAOD::WaveformHitAuxContainer#*"
108:         , "xAOD::WaveformClock#*"
109:         , "xAOD::WaveformClockAuxInfo#*"
110:     ]
111:     print(flags)
112:     acc.merge(OutputStreamCfg(flags, "xAOD", ItemList, disableEventTag=True))
113:     # ostream = acc.getEventAlgo("OutputStreamRDO")
114:     # ostream.TakeItemsFromInput = True # Don't know what this does
115:     return acc
116: 
117: # Return configured "reconstruction" algorithm from scint SIM hits
118: # Specify data source (Veto, Trigger, Preshower)
119: def PseudoScintHitToWaveformRecCfg(flags, name="PseudoScintHitToWaveformRecAlg", source="", **kwargs):
120: 
121:     acc = ComponentAccumulator()
122: 
123:     tool = CompFactory.PseudoSimToWaveformRecTool(name=source+"PseudoSimToWaveformRecTool", **kwargs)
124:     
125:     kwargs.setdefault("ScintHitContainerKey", source+"Hits")
126:     kwargs.setdefault("WaveformHitContainerKey", source+"WaveformHits")
127:     kwargs.setdefault("PseudoSimToWaveformRecTool", tool)
128: 
129:     
130:     recoAlg = CompFactory.PseudoScintHitToWaveformRecAlg(name, **kwargs)
131:     recoAlg.PseudoSimToWaveformRecTool = tool
132: 
133:     acc.addEventAlgo(recoAlg)
134: 
135:     return acc
136: 
137: # Return configured "reconstruction" algorithm from calo SIM hits
138: def PseudoCaloHitToWaveformRecCfg(flags, name="PseudoCaloHitToWaveformRecAlg", **kwargs):
139: 
140:     acc = ComponentAccumulator()
141: 
142:     tool = CompFactory.PseudoSimToWaveformRecTool(name="CaloPseudoSimToWaveformRecTool", **kwargs)
143:     
144:     kwargs.setdefault("CaloHitContainerKey", "EcalHits")
145:     kwargs.setdefault("WaveformHitContainerKey", "CaloWaveformHits")
146:     kwargs.setdefault("PseudoSimToWaveformRecTool", tool)
147:     
148:     recoAlg = CompFactory.PseudoCaloHitToWaveformRecAlg(name, **kwargs)
149:     recoAlg.PseudoSimToWaveformRecTool = tool
150: 
151:     acc.addEventAlgo(recoAlg)
152: 
153:     return acc
```

## 88c457c1 / Waveform/WaveRecAlgs/src/RawWaveformRecAlg.cxx

定位：`RawWaveformRecAlg::execute(`，原文件第45行。

```text
45: RawWaveformRecAlg::execute(const EventContext& ctx) const {
46:   ATH_MSG_DEBUG("Executing");
47: 
48:   // Keep track of some statistics
49:   m_numberOfEvents++;
50: 
51:   ATH_MSG_DEBUG("Run: " << ctx.eventID().run_number() 
52: 		<< " Event: " << ctx.eventID().event_number());
53: 
54:   // Find the input waveform container
55:   SG::ReadHandle<RawWaveformContainer> waveformHandle(m_waveformContainerKey, ctx);
56: 
57:   ATH_CHECK( waveformHandle.isValid() );
58:   ATH_MSG_DEBUG("Found ReadHandle for RawWaveformContainer " << m_waveformContainerKey);
59: 
60:   // Find the output waveform container
61:   SG::WriteHandle<xAOD::WaveformHitContainer> hitContainerHandle(m_waveformHitContainerKey, ctx);
62:   ATH_CHECK( hitContainerHandle.record( std::make_unique<xAOD::WaveformHitContainer>(),
63: 					std::make_unique<xAOD::WaveformHitAuxContainer>() ) );
64: 
65:   ATH_MSG_DEBUG("WaveformsHitContainer '" << hitContainerHandle.name() << "' initialized");
66: 
67:   if (waveformHandle->size() == 0) {
68:     ATH_MSG_DEBUG("Waveform container found with zero length!");
69:     return StatusCode::SUCCESS;
70:   }
71: 
72:   // Save to local storage first
73:   xAOD::WaveformHitContainer* hit_cont_ptr = hitContainerHandle.ptr();
74: 
75:   // First reconstruct the primary hit (based on trigger time)
76:   for( const auto& wave : *waveformHandle) {
77:     ATH_MSG_DEBUG("Reconstruct primary waveform for channel " << wave->channel());
78:     CHECK( m_recoTool->reconstructPrimary(*wave, hit_cont_ptr) );
79:   }
80: 
81:   // Second, reconstruct any additional out of time hits
82:   if (m_findMultipleHits) {
83:     for( const auto& wave : *waveformHandle) {
84:       ATH_MSG_DEBUG("Reconstruct secondary waveform for channel " << wave->channel());
85:       CHECK( m_recoTool->reconstructSecondary(*wave, hit_cont_ptr) );
86:     }
87:   }
88: 
89:   // Also find the clock information
90:   SG::ReadHandle<xAOD::WaveformClock> clockHandle(m_clockKey, ctx);
91:   const xAOD::WaveformClock* clockptr = NULL;
92: 
93:   // Fix timing for all hits
94:   // Can survive without this, but make a note
95:   if ( clockHandle.isValid() ) {
96:     ATH_MSG_DEBUG("Found ReadHandle for WaveformClock");
97:     clockptr = clockHandle.ptr();
98:     CHECK( m_recoTool->setLocalTime(clockptr, hit_cont_ptr) );
99:   } else {
100:     ATH_MSG_WARNING("Didn't find ReadHandle for WaveformClock!");
101:   }
102: 
103:   ATH_MSG_DEBUG("WaveformsHitContainer '" << hitContainerHandle.name() << "' filled with "<< hitContainerHandle->size() <<" items");
104: 
105:   // Clean up waveforms
106:   CHECK( m_cleanupTool->cleanupWaveforms(hit_cont_ptr, ctx.eventID().event_number()) );
107:   
108:   // Keep track of some statistics on the SG container
109:   for (const auto& hit : *(hitContainerHandle.ptr())) {
110:     m_numberOfWaveforms++;
111:     if (hit->status_bit(xAOD::WaveformStatus::WAVE_OVERFLOW)) m_numberOfOverflows++;
112:     if (hit->status_bit(xAOD::WaveformStatus::SECONDARY)) m_numberOfSecondaries++;
113:     
114:     if (hit->status_bit(xAOD::WaveformStatus::GFIT_FAILED)) {
115:       m_numberOfFitErrors++;
116:     } else if (hit->status_bit(xAOD::WaveformStatus::CBFIT_FAILED)) {
117:       m_numberOfFitErrors++;
118:     }
119: 
```

## 88c457c1 / Waveform/WaveRecAlgs/src/RawWaveformRecAlg.h

定位：`SG::ReadHandleKey`，原文件第72行。

```text
72:    * @name Input raw waveform data using SG::ReadHandleKey
73:    */
74:   //@{
75:   SG::ReadHandleKey<RawWaveformContainer> m_waveformContainerKey
76:     {this, "WaveformContainerKey", ""};
77:   //@}
78: 
79:   /**
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

定位：`SG::ReadHandleKey`，原文件第75行。

```text
75:   SG::ReadHandleKey<RawWaveformContainer> m_waveformContainerKey
76:     {this, "WaveformContainerKey", ""};
77:   //@}
78: 
79:   /**
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

定位：`SG::ReadHandleKey`，原文件第80行。

```text
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

定位：`SG::ReadHandleKey`，原文件第83行。

```text
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

定位：`ToolHandle`，原文件第27行。

```text
27: #include "GaudiKernel/ToolHandle.h"
28: 
29: // STL
30: #include <string>
31: 
32: class RawWaveformRecAlg : public AthReentrantAlgorithm {
33: 
34:  public:
35:   // Constructor
36:   RawWaveformRecAlg(const std::string& name, ISvcLocator* pSvcLocator);
37:   virtual ~RawWaveformRecAlg() = default;
38: 
39:   /** @name Usual algorithm methods */
40:   //@{
41:   virtual StatusCode initialize() override;
42:   virtual StatusCode execute(const EventContext& ctx) const override;
43:   virtual StatusCode finalize() override;
44:   //@}
45: 
46:   //
47:   // Look for more than one hit in each channel
48:   BooleanProperty m_findMultipleHits{this, "FindMultipleHits", true};
49: 
50:  private:
51: 
52:   /** @name Disallow default instantiation, copy, assignment */
53:   //@{
54:   RawWaveformRecAlg() = delete;
55:   RawWaveformRecAlg(const RawWaveformRecAlg&) = delete;
56:   RawWaveformRecAlg &operator=(const RawWaveformRecAlg&) = delete;
57:   //@}
58: 
59:   /**
60:    * @name Reconstruction tool
61:    */
62:   ToolHandle<IWaveformReconstructionTool> m_recoTool
63:     {this, "WaveformReconstructionTool", "WaveformReconstructionTool"};
64: 
65:   /**
66:    * @name Cleanup tool
67:    */
68:   ToolHandle<IWaveformCleanupTool> m_cleanupTool
69:     {this, "WaveformCleanupTool", "WaveformCleanupTool"};
70:   
71:   /**
72:    * @name Input raw waveform data using SG::ReadHandleKey
73:    */
74:   //@{
75:   SG::ReadHandleKey<RawWaveformContainer> m_waveformContainerKey
76:     {this, "WaveformContainerKey", ""};
77:   //@}
78: 
79:   /**
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
```

定位：`ToolHandle`，原文件第62行。

```text
62:   ToolHandle<IWaveformReconstructionTool> m_recoTool
63:     {this, "WaveformReconstructionTool", "WaveformReconstructionTool"};
64: 
65:   /**
66:    * @name Cleanup tool
67:    */
68:   ToolHandle<IWaveformCleanupTool> m_cleanupTool
69:     {this, "WaveformCleanupTool", "WaveformCleanupTool"};
70:   
71:   /**
72:    * @name Input raw waveform data using SG::ReadHandleKey
73:    */
74:   //@{
75:   SG::ReadHandleKey<RawWaveformContainer> m_waveformContainerKey
76:     {this, "WaveformContainerKey", ""};
77:   //@}
78: 
79:   /**
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

定位：`ToolHandle`，原文件第68行。

```text
68:   ToolHandle<IWaveformCleanupTool> m_cleanupTool
69:     {this, "WaveformCleanupTool", "WaveformCleanupTool"};
70:   
71:   /**
72:    * @name Input raw waveform data using SG::ReadHandleKey
73:    */
74:   //@{
75:   SG::ReadHandleKey<RawWaveformContainer> m_waveformContainerKey
76:     {this, "WaveformContainerKey", ""};
77:   //@}
78: 
79:   /**
80:    * @name Input WaveformClock data using SG::ReadHandleKey
81:    */
82:   //@{
83:   SG::ReadHandleKey<xAOD::WaveformClock> m_clockKey
84:     {this, "WaveformClockKey", "WaveformClock"};
85:   //@}
86: 
87:   /**
88:    * @name Output data using SG::WriteHandleKey
89:    */
90:   //@{
91:   SG::WriteHandleKey<xAOD::WaveformHitContainer> m_waveformHitContainerKey
92:     {this, "WaveformHitContainerKey", ""};
93:   //@}
94:   
95:   /**
96:    * @name Counters
97:    * Use mutable to be updated in const methods.
98:    * AthReentrantAlgorithm is const during event processing.
99:    * Use std::atomic to be multi-thread safe.
100:    */
101:   //@{
102:   mutable std::atomic<int> m_numberOfEvents{0};
103:   mutable std::atomic<int> m_numberOfWaveforms{0};
104:   mutable std::atomic<int> m_numberOfSecondaries{0};
105:   mutable std::atomic<int> m_numberOfOverflows{0};
106:   mutable std::atomic<int> m_numberOfFitErrors{0};
107:   //@}
108: 
109: };
110: 
111: #endif // WAVERECALGS_RAWWAVEFORMRECALG_H
```

## 88c457c1 / PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx

定位：`void NtupleDumperAlg::FillWaveBranches(`，原文件第246行。

```text
246: void NtupleDumperAlg::FillWaveBranches(const xAOD::WaveformHitContainer &wave, bool isMC) const {
247:   ATH_MSG_DEBUG("FillWaveBranches called");
248:   for (auto hit : wave) {
249:     if ((hit->hit_status()&2)==0) { // dont store secoondary hits as they can overwrite the primary hit
250:       int ch=hit->channel();
251:       ATH_MSG_DEBUG("FillWaveBranches filling channel " << ch);
252: 
253:       m_wave_localtime[ch]=hit->localtime();
254:       m_wave_bcidtime[ch] = hit->bcid_time(); // Now corrected for offsets
255:       // Not sure why this doesn't exist in MC...
256:       if (!isMC)
257: 	m_wave_triggertime[ch] = hit->trigger_time(); // + m_clock_phase;
258:       m_wave_peak[ch]=hit->peak();
259:       m_wave_width[ch]=hit->width();
260:       m_wave_charge[ch]=hit->integral()/50;  // In pC
261: 
262:       m_wave_raw_peak[ch]=hit->raw_peak();
263:       m_wave_raw_charge[ch]=hit->raw_integral()/50;  // In pC
264:       m_wave_baseline_mean[ch]=hit->baseline_mean();
265:       m_wave_baseline_rms[ch]=hit->baseline_rms();
266:       m_wave_status[ch]=hit->hit_status();  
267:     }
268:   }
269:   ATH_MSG_DEBUG("FillWaveBranches done");
270: }
271: 
272: void NtupleDumperAlg::addCalibratedBranches(const std::string &name,
273: 					    std::list<int> channel_list) const {
274: 
275:   ATH_MSG_DEBUG("Adding calibrated " << name << " with channels " << channel_list);
276: 
277:   int nchannels = channel_list.size();
278:   for(int i=0;i<nchannels;i++) {
279:     int ch = channel_list.front();
280:     channel_list.pop_front();
281:     
282:     std::string base=name+std::to_string(i);
283:     addBranch(base+"_nMIP", &m_calibrated_nMIP[ch]);
284:     addBranch(base+"_E_dep",&m_calibrated_E_dep[ch]);
285:     addBranch(base+"_E_EM", &m_calibrated_E_EM[ch]);    
286:     ATH_MSG_DEBUG("Added "  << base << " ch " << ch);
287: 
288:   }
289: }
290: 
291: 
292: StatusCode NtupleDumperAlg::initialize() 
293: {
294: 
295:   m_first = true;
296:   
297:   ATH_CHECK(m_truthEventContainer.initialize());
298:   ATH_CHECK(m_mcEventContainer.initialize());
299:   ATH_CHECK(m_truthParticleContainer.initialize());
300:   ATH_CHECK(m_lhcData.initialize());
301:   ATH_CHECK(m_trackCollection.initialize());
302:   ATH_CHECK(m_trackCollectionWithoutIFT.initialize());
303:   ATH_CHECK(m_trackSegmentCollection.initialize());
304:   ATH_CHECK(m_ghostbustedtrackSegmentCollection.initialize());
305: 
306:   ATH_CHECK(m_vetoContainer.initialize());
307:   ATH_CHECK(m_vetoNuContainer.initialize());
308:   ATH_CHECK(m_vetoGmContainer.initialize());
309:   ATH_CHECK(m_triggerContainer.initialize());
310:   ATH_CHECK(m_preshowerContainer.initialize());
311:   ATH_CHECK(m_muonContainer.initialize());
312: 
313:   ATH_CHECK(m_ecalContainer.initialize());
314:   ATH_CHECK(m_ecal2Container.initialize());
315:   ATH_CHECK(m_caloNuContainer.initialize());
316:   ATH_CHECK(m_clusterContainer.initialize());
317:   ATH_CHECK(m_simDataCollection.initialize());
318:   ATH_CHECK(m_FaserTriggerData.initialize());
319:   ATH_CHECK(m_ClockWaveformContainer.initialize());
320:   ATH_CHECK(m_siHitCollectionKey.initialize());
```
