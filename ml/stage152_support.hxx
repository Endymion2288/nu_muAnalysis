// Exact native histogram support, including the producer's excluded final bin.
std::vector<std::vector<double>> Stage152Support(
    const std::vector<std::vector<double>>& timing,
    const std::vector<unsigned int>& identifiers) {
    TH1D histogram("Stage152Support", "", 20*(600+10), -20., 1200.);
    std::vector<std::vector<double>> result;
    for(auto id:identifiers) {
        unsigned int count=0;
        double energy=0.;
        for(const auto& row:timing) {
            if(static_cast<unsigned int>(row[0])!=id) continue;
            const float time=row[3];
            const int bin=histogram.FindBin(time);
            if(bin<1 || bin>=histogram.GetNbinsX()) {++count; energy+=row[1];}
        }
        result.push_back({double(id),double(count),energy});
    }
    return result;
}
