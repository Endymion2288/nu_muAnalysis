// Instrument the pinned d32 algorithm BEFORE ADC rounding and clipping.
// Inputs are actual per-PMT timing contributions and measured channel conditions.
#include "TF1.h"
#include "TH1D.h"
#include "TRandom3.h"
#include <vector>
#include <cmath>

std::vector<std::vector<double>> Stage141Analog(
    const std::vector<double>& hits, const std::vector<double>& conditions,
    const std::vector<unsigned int>& identifiers, unsigned int seed,
    unsigned int samples) {
    TF1 kernel("Stage141PDF","[4]*ROOT::Math::crystalball_pdf(x,[0],[1],[2],[3])",0,1200);
    for(int j=0;j<5;++j)kernel.SetParameter(j,conditions[3+j]);
    TRandom3 random(seed);
    const unsigned int over=20,pre=10;
    const float period=2.f;
    std::vector<std::vector<double>> output;
    for(auto id:identifiers) {
        TH1D histogram("Stage141Evst","",over*(samples+pre),-period*pre,period*samples);
        bool present=false;
        for(size_t j=0;j<hits.size();j+=3) {
            if(static_cast<unsigned int>(hits[j])!=id)continue;
            float time=hits[j+1],energy=hits[j+2];
            histogram.Fill(time,energy);present=true;
        }
        std::vector<double> dwave(samples*over),signal(samples);
        if(present) {
            // Match original strict '< NbinsX' endpoint and float products.
            for(int ih=1;ih<histogram.GetNbinsX();++ih) {
                float value=histogram.GetBinContent(ih);
                if(value<=0)continue;
                int iw=ih-1-pre*over;
                for(unsigned int ik=0;ik<dwave.size();++ik) {
                    if(iw+int(ik)<0 || (iw+ik)>=dwave.size())continue;
                    float ktime=ik*period/over;
                    float kval=kernel.Eval(ktime)*value;
                    dwave[iw+ik]+=kval;
                }
            }
            for(unsigned int i=0;i<dwave.size();++i)signal[i/over]+=dwave[i]/over;
        }
        for(unsigned int i=0;i<samples;++i) {
            float amplitude=signal[i];
            float baseline=random.Gaus(conditions[0],conditions[1]);
            int adc=std::round(baseline-amplitude);
            output.push_back({double(id),double(i),signal[i],double(amplitude),
                              double(baseline),double(std::max(0,adc))});
        }
    }
    return output;
}
