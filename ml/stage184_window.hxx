// Fixed-window ideal response of the pinned Stage141 convolution.
// Only float-product rounding is omitted; the window, TH1D binning, float
// hit/value/time casts and the producer's strict last-bin omission are kept.
#include "TF1.h"
#include "TH1D.h"
#include <vector>
#include <map>
#include <cmath>
#include <stdexcept>

class Stage184Window {
    std::vector<double> weights;
    unsigned firstSample, lastSample;
public:
    Stage184Window(const std::vector<double>& conditions, unsigned first, unsigned last)
        : weights(12201,0.), firstSample(first), lastSample(last) {
        if(first>last || last>=600) throw std::runtime_error("Invalid fixed window");
        TF1 kernel("Stage184PDF","[4]*ROOT::Math::crystalball_pdf(x,[0],[1],[2],[3])",0,1200);
        for(int j=0;j<5;++j)kernel.SetParameter(j,conditions[3+j]);
        std::vector<double> prefix(12001,0.);
        for(unsigned k=0;k<12000;++k) {
            float time=k*2.f/20;
            const double value=kernel.Eval(time);
            if(!std::isfinite(value) || value<0) throw std::runtime_error("Nonpositive kernel unsupported");
            prefix[k+1]=prefix[k]+value;
        }
        for(int ih=1;ih<12200;++ih) {
            const int shift=ih-1-200;
            int lo=std::max(0,int(20*first)-shift);
            int hi=std::min(12000,int(20*(last+1))-shift);
            if(lo<hi) weights[ih]=(prefix[hi]-prefix[lo])/20.;
        }
    }
    std::vector<std::vector<double>> integrate(const std::vector<double>& hits,
                                               const std::vector<unsigned int>& ids) const {
        if(hits.size()%3) throw std::runtime_error("Hit layout");
        std::map<unsigned int,std::vector<double>> byId;
        for(size_t j=0;j<hits.size();j+=3) {
            auto& values=byId[static_cast<unsigned int>(hits[j])];
            values.push_back(hits[j+1]);values.push_back(hits[j+2]);
        }
        std::vector<std::vector<double>> output;
        TH1D histogram("Stage184Evst","",12200,-20.,1200.);
        histogram.SetDirectory(nullptr);
        for(auto id:ids) {
            histogram.Reset();
            const auto found=byId.find(id);
            if(found!=byId.end()) {
                const auto& values=found->second;
                for(size_t j=0;j<values.size();j+=2) {
                    const float time=values[j], energy=values[j+1];
                    histogram.Fill(time,energy);
                }
            }
            double integral=0.;
            unsigned nonempty=0;
            for(int ih=1;ih<12200;++ih) {
                const float value=histogram.GetBinContent(ih);
                if(value<=0)continue;
                integral+=weights[ih]*value; ++nonempty;
            }
            // ADC code -> mV, 2 ns per sample, 50 Ohm -> pC.
            output.push_back({double(id),integral*(2.*2000./16384./50.),double(nonempty)});
        }
        return output;
    }
};
